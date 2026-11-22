"""Close surroundings from audio, matched against the real places around.

What one phone microphone can really measure about the next ~25 m, and how each
measurement is compared with every spot of the map (IGN building footprints and
OSM roads, data/twin). Nothing here is a guess drawn for show: every number is a
measurement on the clip, and every "expected" number is computed from real geometry.

MEASURED (on the clip)
  echoes    the phone's chirp, deconvolved (spatial.py): the distance of every
            reflecting wall, d = 343 x delay / 2. One mic = distance only, no direction.
  ambient   the background noise level in dB(A), with the operator's OWN VOICE as the
            loudness reference: a voice into a phone held ~15 cm away is ~76 dB(A),
            so "noise floor 14 dB below the voice" means ~62 dB(A) around. No calibration
            needed. Listen clips (no voice) reuse the offset found on the last voice clip.
  space     indoor / street / open ground, from reverberation (spatial.py)
  sounds    classifier scores (acoustic.py), now also UNDER speech (weak evidence)

EXPECTED (per spot, computed once, cached in data/twin/surround_cache.npz)
  echoes    from each spot (9 per 25 m cell), 36 rays over a 1 m building raster.
            A flat wall sends the chirp straight back from the foot of the
            perpendicular, which is where the distance-to-wall along the rays has a local
            minimum: those minima are the echo distances the phone should hear there.
            Two walls on opposite sides (a street) also give a wall-to-wall echo at
            a + b = the street width.
  ambient   a road-noise model: every OSM road / rail point is a source, louder for
            bigger roads, falling with distance (line source), -15 dB when a building
            stands in between (checked on the raster). Indoors: -25 dB through the facade.

MATCH  each measurement gives a likelihood per spot; per cell = mean over its spots.
They are multiplied in localise.py like any other clue. cue_bits() says how much each
one narrowed the map (bits of entropy removed, from a flat prior).

All constants are physics-based starting points, to calibrate on real recordings.
"""
import json
import math
import time

import numpy as np
from scipy import signal
from scipy.spatial import cKDTree

from . import config

RES = 1.0                 # metres per pixel of the building raster
DIRS = 36                 # rays per spot (every 10 degrees)
MAX_R = 25.0              # echo range of the chirp (spatial.analyse_ir looks up to 25 m)
STEP = 0.5                # ray step (m)
OFFS = (-25 / 3, 0.0, 25 / 3)   # 3 x 3 spots per 25 m cell
FLOOR_BAND = (0.8, 1.8)   # ground / ceiling, not a wall (as spatial.py)
VERSION = 4               # bump to rebuild the cache (4: trees soak up road noise)

# Echo matching
ECHO_FA = 0.25            # chance a measured echo comes from something not on the map (car, tree, person)
ECHO_SECOND = 0.6         # weight of the wall-to-wall (street width) echo
ECHO_TEMPER = 0.8
ECHO_INDOOR = 0.08        # likelihood of clean echoes for a spot inside a building
ECHO_FOREST = 0.45        # in woods trunks echo at any distance: an echo no wall explains is
                          # expected there (better than street clutter 0.25, worse than a matched wall)

# Ambient noise model, dB(A). Level at 10 m from the road, daytime (Paris-like).
L10 = {"road1": 78.0, "road2": 72.0, "road3": 69.0, "road4": 65.0, "railway": 67.0,
       "tram": 61.0, "industrial": 60.0}
SPACING = 25.0            # sources are points every 25 m along the line
L_RESIDUAL = 47.0         # small streets, city hum: never quieter than this outdoors
L_INDOOR_FLOOR = 36.0     # fridge, ventilation, people
FACADE_DB = 25.0          # facade insulation, windows closed
SCREEN_DB = 15.0          # a building between the source and the phone
NOISE_RADIUS = 500.0
VOICE_REF_DBA = 76.0      # operator's voice at the phone mic (normal voice, phone ~15 cm)
VOICE_SIGMA = 7.0         # how far a real voice strays from that (soft / loud talkers)
UNCAL_OFFSET = 125.0      # dBFS -> dB SPL for a typical phone mic with no calibration
L90_TO_LEQ = 4.0          # the measured floor is a background level (L90); the model is Leq


# =========================================================================== geometry
class Places:
    def __init__(self, eng):
        self.eng = eng
        self.ok = False
        db = eng.db
        s, w, _, _ = config.BBOX
        self.x0, self.y0 = db.to_xy(s, w)
        self.W, self.H = int(eng.nx * config.CELL_M / RES), int(eng.ny * config.CELL_M / RES)
        path = config.TWIN_DIR / "buildings.geojson"
        if not path.exists():
            path = config.TWIN_DIR / "buildings_osm.geojson"
        if not path.exists():
            print("surround disabled: no building footprints in data/twin")
            return
        t0 = time.time()
        self._load_buildings(path)
        self._spots()
        key = np.array([VERSION, len(self.polys), eng.nx, eng.ny], np.int64)
        cache = config.TWIN_DIR / "surround_cache.npz"
        z = None
        if cache.exists():
            z = np.load(cache)
            if not np.array_equal(z["key"], key):
                z = None
        if z is None:
            print("surround: building echo + noise maps (once, ~30 s)...")
            r = self.raycast(self.spot_xy)
            self.e_dist, self.e_width, self.e_dir = minima(r)
            self.l_out = self._noise_map()
            np.savez_compressed(cache, key=key, e_dist=self.e_dist, e_width=self.e_width,
                                e_dir=self.e_dir, l_out=self.l_out)
        else:
            self.e_dist, self.e_width, self.e_dir, self.l_out = z["e_dist"], z["e_width"], z["e_dir"], z["l_out"]
        self.l_in = _db_sum(self.l_out - FACADE_DB, L_INDOOR_FLOOR)
        self.ok = True
        print(f"surround ready in {time.time() - t0:.1f} s ({len(self.polys)} buildings)")

    # ------------------------------------------------------------- buildings
    def _load_buildings(self, path):
        from PIL import Image, ImageDraw
        db = self.eng.db
        img = Image.new("1", (self.W, self.H), 0)
        dr = ImageDraw.Draw(img)
        self.polys, self.heights, cents = [], [], []
        for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
            ring = np.array(f["geometry"]["coordinates"][0])
            if len(ring) < 3:
                continue
            x, y = db.to_xy(ring[:, 1], ring[:, 0])
            px, py = (x - self.x0) / RES, (y - self.y0) / RES
            dr.polygon(list(zip(px, py)), fill=1)
            self.polys.append(np.c_[x - self.x0, y - self.y0].astype(np.float32))
            self.heights.append(float((f.get("properties") or {}).get("h") or 9.0))
            cents.append(self.polys[-1].mean(axis=0))
        self.inside = np.array(img, bool)          # [row = y, col = x], row 0 = south
        self.bld_tree = cKDTree(np.array(cents))

    def _spots(self):
        """9 spots per cell, in raster metres; spot index = cell * 9 + k."""
        eng = self.eng
        cx, cy = eng.X - self.x0, eng.Y - self.y0
        ox, oy = np.meshgrid(OFFS, OFFS)
        self.spot_xy = np.c_[(cx[:, None] + ox.ravel()).ravel(), (cy[:, None] + oy.ravel()).ravel()].astype(np.float32)
        self.spot_in = self.is_inside(self.spot_xy)

    def is_inside(self, P):
        ix = np.clip((P[:, 0] / RES).astype(int), 0, self.W - 1)
        iy = np.clip((P[:, 1] / RES).astype(int), 0, self.H - 1)
        return self.inside[iy, ix]

    def raycast(self, P, chunk=3000):
        """(M, 2) points -> (M, DIRS) distance to the first building along each ray
        (inf if none within MAX_R). Ray k points to bearing k * 10 deg (0 = north)."""
        ang = np.radians(np.arange(DIRS) * 360.0 / DIRS)
        sa, ca = np.sin(ang).astype(np.float32), np.cos(ang).astype(np.float32)
        steps = (np.arange(1, int(MAX_R / STEP) + 1) * STEP).astype(np.float32)
        out = np.full((len(P), DIRS), np.inf, np.float32)
        for a in range(0, len(P), chunk):
            p = P[a:a + chunk]
            x = p[:, 0, None, None] + steps[None, None, :] * sa[None, :, None]
            y = p[:, 1, None, None] + steps[None, None, :] * ca[None, :, None]
            ix, iy = (x / RES).astype(np.int32), (y / RES).astype(np.int32)
            ok = (ix >= 0) & (ix < self.W) & (iy >= 0) & (iy < self.H)
            hit = np.zeros(ix.shape, bool)
            hit[ok] = self.inside[iy[ok], ix[ok]]
            first = hit.argmax(axis=2)
            out[a:a + chunk] = np.where(hit.any(axis=2), steps[first], np.inf)
        return out

    def near_buildings(self, x, y, r=45.0):
        """Footprints (raster metres) of the buildings within r of (x, y)."""
        idx = self.bld_tree.query_ball_point([x, y], r + 60)
        out = []
        for i in idx:
            p = self.polys[i]
            if np.min(np.hypot(p[:, 0] - x, p[:, 1] - y)) < r + 15:
                out.append({"pts": np.round(p - [x, y], 1).tolist(), "h": round(self.heights[i], 1)})
        return out

    # ------------------------------------------------------------- noise map
    def _noise_map(self):
        """Predicted outdoor Leq dB(A) per cell (from its most open spot)."""
        eng, db = self.eng, self.eng.db
        feats = json.loads((config.TWIN_DIR / "sources.geojson").read_text(encoding="utf-8"))["features"]
        sx, sy, sl = [], [], []
        for f in feats:
            p = f["properties"]
            key = f"road{p['cls']}" if p["kind"] == "road" else p["kind"]
            if key not in L10:
                continue
            lon, lat = f["geometry"]["coordinates"]
            x, y = db.to_xy(lat, lon)
            sx.append(x - self.x0); sy.append(y - self.y0)
            # Line of points every 25 m: sum of 1/d^2 ~ pi / (25 d), so the point level that
            # gives L10 at 10 m from the line is L10 - 10 log10(pi / 250) = L10 + 19.
            sl.append(L10[key] - 10 * math.log10(math.pi / (SPACING * 10)))
        S = np.c_[sx, sy]
        sl = np.array(sl)
        # Receiver per cell: the outdoor spot nearest the centre (else the centre).
        k = self.spot_in.reshape(-1, 9)
        order = [4, 1, 3, 5, 7, 0, 2, 6, 8]
        pick = np.full(eng.N, 4)
        for j in order[::-1]:
            pick = np.where(~k[:, j], j, pick)
        R = self.spot_xy.reshape(-1, 9, 2)[np.arange(eng.N), pick]
        M = cKDTree(R).sparse_distance_matrix(cKDTree(S), NOISE_RADIUS, output_type="coo_matrix")
        ri, si, d = M.row, M.col, np.maximum(M.data, 3.0)
        L = sl[si] - 20 * np.log10(d) - 0.004 * d
        # Screening: is there a building between them? Check the closer pairs on the raster.
        near = d <= 250
        blocked = np.zeros(d.size, bool)
        idx = np.where(near)[0]
        for a in range(0, idx.size, 200000):
            j = idx[a:a + 200000]
            p0, p1 = R[ri[j]], S[si[j]]
            n = 40
            t = np.linspace(0.08, 0.92, n)[None, :]
            x = p0[:, 0, None] + (p1[:, 0, None] - p0[:, 0, None]) * t
            y = p0[:, 1, None] + (p1[:, 1, None] - p0[:, 1, None]) * t
            ix = np.clip((x / RES).astype(np.int32), 0, self.W - 1)
            iy = np.clip((y / RES).astype(np.int32), 0, self.H - 1)
            blocked[j] = self.inside[iy, ix].any(axis=1)
        wood_db = self._forest_db(R[ri], S[si], d)
        # Near: buildings in the way (checked) plus trees. Far: buildings usually screen,
        # or trees do in the woods, whichever is more.
        L = L - np.where(near, blocked * SCREEN_DB + wood_db, np.maximum(SCREEN_DB * 0.7, wood_db))
        E = np.zeros(eng.N)
        np.add.at(E, ri, 10 ** (L / 10))
        return _db_sum(10 * np.log10(E + 1e-12), L_RESIDUAL).astype(np.float32)

    def _forest_db(self, P0, P1, d):
        """Extra road-noise attenuation through woodland on each receiver-source line:
        nothing for the first FOREST_NOISE_FREE_M of trees, then a constant dB per metre."""
        from .forest import RES as FRES, get_forest
        fo = get_forest(self.eng)
        out = np.zeros(d.size, np.float32)
        if not fo.ok:
            return out
        wood = fo.px_wood
        n = 24
        t = np.linspace(0.02, 0.98, n)[None, :]
        for a in range(0, d.size, 300000):
            p0, p1 = P0[a:a + 300000], P1[a:a + 300000]
            # surround raster metres -> forest raster pixels (same origin, 5 m pixels)
            x = (p0[:, 0, None] + (p1[:, 0, None] - p0[:, 0, None]) * t) / FRES
            y = (p0[:, 1, None] + (p1[:, 1, None] - p0[:, 1, None]) * t) / FRES
            ix = np.clip(x.astype(np.int32), 0, wood.shape[1] - 1)
            iy = np.clip(y.astype(np.int32), 0, wood.shape[0] - 1)
            share = wood[iy, ix].mean(axis=1)
            metres = share * d[a:a + 300000]
            out[a:a + 300000] = np.clip((metres - config.FOREST_NOISE_FREE_M) * config.FOREST_NOISE_DB_PER_M,
                                        0, config.FOREST_NOISE_CAP_DB)
        return out

    # ------------------------------------------------------------- likelihoods
    def likelihood(self, c, per_spot=False):
        if not self.ok:
            return None
        if c["kind"] == "echoes":
            L = self.echo_like(c)
        elif c["kind"] == "ambient":
            L = self.ambient_like(c)
        else:
            return None
        if per_spot:
            return L
        return L.reshape(-1, 9).mean(axis=1) if L.size == self.eng.N * 9 else L

    def echo_like(self, c):
        """Per spot: how well the measured echo distances fit the walls around it."""
        m = np.array([e["m"] for e in c["refl"]], np.float32)
        E1, Wd, Dr = self.e_dist, self.e_width, self.e_dir
        L = np.ones(len(E1), np.float32)
        v1 = np.isfinite(E1)
        E2, v2 = second_order(E1, Dr)
        if m.size:
            sig = 0.5 + 0.05 * m
            g1 = np.where(v1[:, :, None], np.exp(-0.5 * ((m[None, None, :] - E1[:, :, None]) / sig) ** 2), 0).max(axis=1)
            g2 = np.where(v2[:, :, None], np.exp(-0.5 * ((m[None, None, :] - E2[:, :, None]) / sig) ** 2), 0).max(axis=1)
            g = np.maximum(g1, ECHO_SECOND * g2)
            fa = ECHO_FA + (ECHO_FOREST - ECHO_FA) * self._wood_spots()
            L *= np.prod(fa[:, None] + (1 - fa[:, None]) * g, axis=1)
        # A big close wall that sends nothing back is unlikely (the two nearest measurable
        # ones: closer than ~1.8 m it hides in the ground echo).
        meas = v1 & (E1 > FLOOR_BAND[1])
        rank = np.cumsum(meas, axis=1)
        for j in range(E1.shape[1]):
            e = E1[:, j]
            strong = meas[:, j] & (rank[:, j] <= 2) & (e <= 15) & (Wd[:, j] >= 3)
            if m.size:
                found = (np.abs(m[None, :] - e[:, None]) < 2 * (0.5 + 0.05 * e[:, None])).any(axis=1)
            else:
                found = np.zeros(len(e), bool)
            L *= np.where(strong & ~found, np.where(e <= 8, 0.3, 0.5), 1.0)
        # Clean separate echoes (dry, DRR > 0) are rare indoors (rooms ring), so spots inside
        # buildings get a low flat value: room walls are not on the map anyway.
        L = np.where(self.spot_in, ECHO_INDOOR, L)
        return L ** ECHO_TEMPER

    def _wood_spots(self):
        """Share of trees in each spot's cell (0 without forest data)."""
        if getattr(self, "_wood", None) is None:
            from .forest import get_forest
            fo = get_forest(self.eng)
            self._wood = np.repeat(fo.wood, 9).astype(np.float32) if fo.ok else np.zeros(len(self.spot_xy), np.float32)
        return self._wood

    def ambient_like(self, c):
        """Per cell: measured background level vs the noise model, indoors or out."""
        from .soundscape import get_soundscape
        sc = get_soundscape(self.eng)
        p_in = sc.P_setting[:, :2].sum(axis=1) if sc.ok else self.spot_in.reshape(-1, 9).mean(axis=1)
        s = c.get("sigma", VOICE_SIGMA)
        a = c["dba"]
        return p_in * np.exp(-0.5 * ((a - self.l_in) / s) ** 2) + (1 - p_in) * np.exp(-0.5 * ((a - self.l_out) / s) ** 2)

    # ------------------------------------------------------------- one point
    def at_point(self, x, y):
        """Expected echoes and noise at a raster point (for plans and rehearsal)."""
        r = self.raycast(np.array([[x, y]], np.float32))
        d, w, k = minima(r)
        E2, v2 = second_order(d, k)
        cell = int(np.argmin((self.eng.X - self.x0 - x) ** 2 + (self.eng.Y - self.y0 - y) ** 2))
        inside = bool(self.is_inside(np.array([[x, y]], np.float32))[0])
        first = [{"m": round(float(d[0, j]), 1), "bearing": int(k[0, j]) * 10, "width": int(w[0, j]), "order": 1}
                 for j in range(d.shape[1]) if np.isfinite(d[0, j])]
        second = [{"m": round(float(E2[0, j]), 1), "order": 2} for j in range(E2.shape[1]) if v2[0, j]]
        return {"echoes": first, "echoes2": second, "inside": inside, "cell": cell,
                "l_out": round(float(self.l_out[cell]), 1), "l_in": round(float(self.l_in[cell]), 1),
                "rays": [None if not np.isfinite(v) else round(float(v), 1) for v in r[0]]}


def minima(r, keep=5):
    """Rays (M, DIRS) -> up to `keep` echo walls per point, nearest first:
    distance (inf = none), width (rays within 12 % of it: a long wall is wide), ray index."""
    M = r.shape[0]
    prev, nxt = np.roll(r, 1, axis=1), np.roll(r, -1, axis=1)
    is_min = (r < MAX_R) & (r <= prev) & (r <= nxt) & (r != prev)
    width = np.ones(r.shape, np.int16)
    for side in (1, -1):
        run = np.ones(r.shape, bool)
        for o in range(1, 7):
            run &= np.roll(r, -side * o, axis=1) <= 1.12 * r
            width += run
    is_min &= width >= 2
    d = np.where(is_min, r, np.inf)
    order = np.argsort(d, axis=1)[:, :keep]
    rows = np.arange(M)[:, None]
    return d[rows, order].astype(np.float32), np.where(np.isfinite(d[rows, order]), width[rows, order], 0).astype(np.uint8), order.astype(np.uint8)


def second_order(E1, Dr):
    """Wall-to-wall echoes: two walls on roughly opposite sides (150-210 deg apart)
    give an echo at a + b (the street width)."""
    pairs = [(i, j) for i in range(E1.shape[1]) for j in range(i + 1, E1.shape[1])]
    a = np.stack([E1[:, i] for i, _ in pairs], 1)
    b = np.stack([E1[:, j] for _, j in pairs], 1)
    da = np.stack([Dr[:, i].astype(int) for i, _ in pairs], 1)
    dbb = np.stack([Dr[:, j].astype(int) for _, j in pairs], 1)
    diff = np.abs(((da - dbb) * 10 + 180) % 360 - 180)
    E2 = a + b
    return E2, np.isfinite(E2) & (diff >= 150) & (E2 <= MAX_R)


def _db_sum(a, b):
    return 10 * np.log10(10 ** (np.asarray(a) / 10) + 10 ** (np.asarray(b) / 10))


_places = None


def get_places(eng=None):
    global _places
    if _places is None:
        from .localise import get_engine
        _places = Places(eng or get_engine())
    return _places


# =========================================================================== measuring
def a_weighting(sr):
    """Digital A-weighting filter (IEC 61672), as second-order sections."""
    f = [20.598997, 107.65265, 737.86223, 12194.217]
    z = [0, 0, 0, 0]
    p = [-2 * math.pi * f[0]] * 2 + [-2 * math.pi * f[1], -2 * math.pi * f[2]] + [-2 * math.pi * f[3]] * 2
    k = (2 * math.pi * f[3]) ** 2 * 10 ** (1.9997 / 20)
    zd, pd, kd = signal.bilinear_zpk(z, p, k, sr)
    return signal.zpk2sos(zd, pd, kd)


def frame_levels(wave, sr, frame_s=0.064):
    """A-weighted level per frame, in dBFS (a full-scale sine = 0 dBFS)."""
    y = signal.sosfilt(a_weighting(sr), wave)
    n = int(frame_s * sr)
    k = y.size // n
    if k < 4:
        return np.array([])
    p = (y[:k * n].reshape(k, n) ** 2).mean(axis=1)
    return 10 * np.log10(2 * p + 1e-15)


def measure_ambient(wave, sr, has_voice):
    """Background noise level. With the operator's voice in the clip, the voice is the
    loudness reference (no calibration). Returns a dict, or None if the clip is too short."""
    lv = frame_levels(wave, sr)
    if lv.size < 8:
        return None
    floor = float(np.percentile(lv, 10))
    out = {"floor_dbfs": round(floor, 1)}
    active = lv > floor + 10
    if has_voice and active.mean() >= 0.12:
        voice = float(np.percentile(lv[active], 70))
        out.update(voice_dbfs=round(voice, 1), snr_db=round(voice - floor, 1))
        out["offset"] = VOICE_REF_DBA - voice                 # dBFS -> dB(A) for this phone
        out["dba"] = round(floor + out["offset"] + L90_TO_LEQ, 1)
        out["sigma"] = VOICE_SIGMA
        out["ref"] = "own voice"
        if out["snr_db"] > 45:
            out["note"] = "very quiet around (or mic noise floor): level is an upper bound"
    else:
        out["dba"] = round(floor + UNCAL_OFFSET + L90_TO_LEQ, 1)
        out["sigma"] = 10.0
        out["ref"] = "uncalibrated phone"
    return out


def calibrate(an, rep):
    """Voice clip: remember this phone's dBFS -> dB(A) offset. Listen clip: use it."""
    amb = an.get("ambient")
    if not amb:
        return
    if amb.get("ref") == "own voice":
        rep["mic_cal"] = {"offset": amb["offset"], "ms": int(time.time() * 1000)}
    elif rep.get("mic_cal") and "floor_dbfs" in amb:     # (a radio packet carries dB(A) already)
        amb["dba"] = round(amb["floor_dbfs"] + rep["mic_cal"]["offset"] + L90_TO_LEQ, 1)
        amb["sigma"] = 6.0
        amb["ref"] = "this phone, calibrated on the last voice report"


def describe_level(dba):
    if dba is None:
        return ""
    for lim, txt in ((45, "very quiet (park, courtyard, indoors)"), (52, "quiet (side street, park)"),
                     (60, "moderate (residential street)"), (67, "busy street nearby"),
                     (74, "next to a main road"), (999, "next to a very loud road or rail")):
        if dba < lim:
            return txt


# =========================================================================== report view
def cue_bits(L):
    """Bits of uncertainty removed by one per-cell likelihood, from a flat prior."""
    L = np.asarray(L, float)
    if L.size == 0 or not np.isfinite(L).all() or L.max() <= 0:
        return 0.0
    p = L / L.sum()
    H = -(p[p > 0] * np.log2(p[p > 0])).sum()
    return round(float(math.log2(L.size) - H), 2)


def build(rep, eng):
    """Everything the Sound / Location panels show for a report."""
    from .soundscape import get_soundscape
    pl, sc = get_places(eng), get_soundscape(eng)
    an = next((a for a in reversed(rep.get("acoustic") or []) if a.get("space") or a.get("ambient")), None)
    cons = [c for c in rep["constraints"] if c["kind"] in ("echoes", "ambient", "setting", "hear")]
    out = {"report_id": rep["id"], "ok": pl.ok, "measured": measured_view(rep, an), "cues": [],
           "candidates": [], "audio_only": None}
    if not pl.ok:
        return out
    # Each acoustic cue alone: how much did it narrow the map?
    Ls = []
    for c in cons:
        L = pl.likelihood(c) if c["kind"] in ("echoes", "ambient") else sc.likelihood(c)
        if L is None:
            continue
        Ls.append((c, L))
        out["cues"].append({"kind": c["kind"], "label": cue_label(c), "bits": cue_bits(L),
                            "source": c.get("source", "audio")})
    # Audio alone over the whole map.
    if Ls:
        ll = sum(np.log(0.01 + 0.99 * L) for _, L in Ls)
        post = np.exp(ll - ll.max())
        post /= post.sum()
        order = np.sort(post)[::-1]
        n90 = int(np.searchsorted(np.cumsum(order), 0.9) + 1)
        out["audio_only"] = {"cells_90": n90, "cells": int(eng.N), "share": round(n90 / eng.N, 4),
                             "bits": cue_bits(post), "km2_90": round(n90 * config.CELL_M ** 2 / 1e6, 2),
                             "heat": eng.heat(post.reshape(eng.ny, eng.nx))}
        audio_post = post
    else:
        audio_post = None
    out["candidates"] = candidates(rep, eng, pl, sc, cons, audio_post)
    return out


def cue_label(c):
    k = c["kind"]
    if k == "echoes":
        return ("echoes at " + ", ".join(f"{e['m']:.1f} m" for e in c["refl"])) if c["refl"] else "no echo within 25 m"
    if k == "ambient":
        return f"background ≈ {c['dba']:.0f} dB(A) ±{c['sigma']:.0f}"
    if k == "setting":
        best = max(c["p"], key=c["p"].get)
        return f"space: {best.replace('_', ' ')} {c['p'][best]:.0%}" + (" (said)" if c.get("source") == "voice" else "")
    if k == "hear":
        verb = "heard" if c.get("q", 1) > 0 else "not heard"
        return f"{c['cls']} {verb}" + (" (said)" if c.get("source") == "voice" else
                                      f" ({c.get('score', 0):.2f}{', under speech' if c.get('under_speech') else ''})")
    return k


def measured_view(rep, an):
    """The latest clip's measurements, in plain numbers."""
    if not an:
        return None
    sp = an.get("space") or {}
    pr = sp.get("probe") or {}
    refl = [r for r in (pr.get("reflections") or []) if not FLOOR_BAND[0] <= r["m"] <= FLOOR_BAND[1]]
    if not pr:
        echo_status = "no chirp in this clip"
    elif not pr.get("ok"):
        echo_status = pr.get("why") or "chirp not heard"
    elif not refl and (pr.get("drr_db") or 0) > 0:
        echo_status = "no echo within 25 m: open around"
    elif refl and not pr.get("wall_reliable"):
        echo_status = "reverberant: echoes not reliable (indoors?)"
    else:
        echo_status = f"{len(refl)} echo{'es' if len(refl) != 1 else ''}"
    amb = an.get("ambient") or {}
    return {
        "kind": an.get("kind"), "simulated": an.get("source") == "simulated", "ms": an.get("ms"),
        "echoes": refl[:6], "echo_status": echo_status, "probe_ok": bool(pr.get("ok")),
        "rt60_s": pr.get("rt60_s") or sp.get("rt60_passive_s"), "drr_db": pr.get("drr_db"),
        "space": {"p": sp.get("p"), "label": sp.get("label"), "p_best": sp.get("p_best")} if sp.get("p") else None,
        "ambient": {**{k: amb.get(k) for k in ("dba", "sigma", "ref", "snr_db", "note")},
                    "label": describe_level(amb.get("dba"))} if amb.get("dba") is not None else None,
        "sounds": [{"cls": e["class"], "score": e["score"], "under_speech": e.get("under_speech", False)}
                   for e in an.get("events", [])][:5],
    }


def candidates(rep, eng, pl, sc, cons, audio_post, n=3):
    """Likely places (blobs of the full position, else of the audio alone), each with
    the real buildings around its best-fitting spot and a measured-vs-expected table."""
    p = rep.get("position")
    blobs = (p or {}).get("hyps") or (p or {}).get("blobs") or []    # up to 3 distinct likely spots
    src = "all clues"
    if not blobs and audio_post is not None:
        blobs = eng.find_blobs(audio_post.reshape(eng.ny, eng.nx))
        src = "audio only"
    if not blobs:
        return []
    echo_c = next((c for c in cons if c["kind"] == "echoes"), None)
    amb_c = next((c for c in cons if c["kind"] == "ambient"), None)
    spotL = np.ones(eng.N * 9)
    if echo_c:
        spotL *= pl.echo_like(echo_c)
    cellL = np.ones(eng.N)
    if amb_c:
        cellL *= pl.ambient_like(amb_c)
    for c in cons:
        if c["kind"] in ("setting", "hear"):
            L = sc.likelihood(c)
            if L is not None:
                cellL *= 0.01 + 0.99 * L
    out = []
    labels = "ABC"
    for i, b in enumerate(blobs[:n]):
        bx, by = eng.db.to_xy(b["lat"], b["lon"])
        near = np.where(np.hypot(eng.X - bx, eng.Y - by) <= max(60.0, 0.7 * (b.get("radius_m") or 60)))[0]
        if near.size == 0:
            near = np.array([int(np.argmin(np.hypot(eng.X - bx, eng.Y - by)))])
        sl = spotL.reshape(-1, 9)[near] * cellL[near, None]
        j = int(np.argmax(sl))
        cell, k = int(near[j // 9]), j % 9
        sx, sy = pl.spot_xy[cell * 9 + k]
        here = pl.at_point(float(sx), float(sy))
        lat, lon = eng.db.to_latlon(sx + pl.x0, sy + pl.y0)
        checks, scores = check_list(here, cons, sc, cell)
        out.append({
            "label": labels[i], "mass": round(float(b["mass"]), 3), "source": src,
            "lat": round(float(b["lat"]), 6), "lon": round(float(b["lon"]), 6), "radius_m": round(b.get("r80") or 60),
            "spot": {"lat": round(float(lat), 6), "lon": round(float(lon), 6)},     # best-fitting 8 m spot
            "plan": {"r": 40, "buildings": pl.near_buildings(float(sx), float(sy), 40)},
            "expected": here["echoes"], "expected2": here["echoes2"], "rays": here["rays"],
            "inside": here["inside"], "l_out": here["l_out"], "l_in": here["l_in"],
            "setting_here": dict(zip(config.SETTINGS, sc.P_setting[cell].round(2).tolist())) if sc.ok else None,
            "checks": checks, "fit": round(float(np.mean(scores)), 2) if scores else None,
        })
    return out


def check_list(here, cons, sc, cell):
    """Measured vs expected at one spot: [{label, text, score}], scores."""
    checks, scores = [], []
    for c in cons:
        k = c["kind"]
        if k == "echoes":
            exp = [e["m"] for e in here["echoes"] if e["m"] <= MAX_R]
            exp2 = [e["m"] for e in here["echoes2"]]
            if here["inside"]:
                checks.append({"label": "echoes", "text": "inside a building here: walls not on the map", "score": 0.5})
                scores.append(0.5)
                continue
            parts, sc_ = [], []
            for e in c["refl"]:
                best = min(exp + exp2, key=lambda x: abs(x - e["m"]), default=None)
                ok = best is not None and abs(best - e["m"]) < 2 * (0.5 + 0.05 * e["m"])
                parts.append(f"{e['m']:.1f} m → {'wall at ' + format(best, '.1f') + ' m' + (' (street width)' if best in exp2 and best not in exp else '') if ok else 'nothing on the map'}")
                sc_.append(1.0 if ok else 0.3)
            measurable = [e for e in exp if e > FLOOR_BAND[1]][:2]
            missed = [e for e in measurable if e <= 15 and not any(abs(e - r["m"]) < 2 * (0.5 + 0.05 * e) for r in c["refl"])]
            for e in missed:
                parts.append(f"wall at {e:.1f} m not heard")
                sc_.append(0.3)
            if not c["refl"] and not exp:
                parts.append("no echo, no wall within 25 m here")
                sc_.append(1.0)
            s = float(np.mean(sc_)) if sc_ else 0.5
            checks.append({"label": "echoes", "text": "; ".join(parts) or "–", "score": round(s, 2)})
            scores.append(s)
        elif k == "ambient":
            pred = here["l_in"] if here["inside"] else here["l_out"]
            diff = c["dba"] - pred
            s = float(math.exp(-0.5 * (diff / c["sigma"]) ** 2))
            checks.append({"label": "background noise",
                           "text": f"measured {c['dba']:.0f} dB(A), expected here {pred:.0f} ({'indoors' if here['inside'] else 'outdoors'}, road-noise model)",
                           "score": round(s, 2)})
            scores.append(s)
        elif k == "setting" and sc.ok:
            p_here = dict(zip(config.SETTINGS, sc.P_setting[cell]))
            best = max(c["p"], key=c["p"].get)
            s = float(sum(c["p"][x] * p_here[x] for x in config.SETTINGS) / max(max(p_here.values()), 1e-6))
            top_here = max(p_here, key=p_here.get)
            checks.append({"label": "kind of space", "text": f"heard {best.replace('_', ' ')}, here mostly {top_here.replace('_', ' ')}",
                           "score": round(min(s, 1.0), 2)})
            scores.append(min(s, 1.0))
        elif k == "hear" and sc.ok:
            P = float(sc.p_heard(c["cls"], "voice" if c.get("source") == "voice" else "audio")[cell])
            q = c.get("q", 1.0)
            s = q * P + (1 - q) * (1 - P)
            checks.append({"label": c["cls"], "text": f"{'heard' if q > 0 else 'not heard'}, chance here {P:.0%}",
                           "score": round(s, 2)})
            scores.append(s)
    return checks, scores
