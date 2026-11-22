"""Geography of sound: for every grid cell, what would a phone there hear, and
what kind of space would it be in?

Built once from data/twin (IGN building footprints + OSM noise sources):

  setting layer   P(indoor_small / indoor_large / outdoor_enclosed / outdoor_open | cell)
                  from a 5 m raster of the footprints: inside a building (large or not),
                  outdoors near a facade (< 15 m: street, courtyard) or far from one (> 40 m)
  facade distance distance from every outdoor 5 m pixel to the nearest building,
                  matched against the echo distance measured by the chirp
  hear layers     exposure 0..1 to each sound source group (railway, roads by class,
                  churches for bells, industrial areas, green space for birds)

Each evidence kind returns a likelihood per cell; localise.py multiplies it in
like any other constraint. Missing data files -> everything returns None and the
voice-only engine carries on unchanged.
"""
import json
import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import config
from .localise import soft_inside

FINE = 5   # metres per raster pixel


class Soundscape:
    def __init__(self, eng):
        self.eng = eng
        self.ok = False
        self.layers = {}
        try:
            self._build_buildings()
            self._load_sources()
            self.ok = True
        except FileNotFoundError as e:
            print("soundscape disabled (run scripts/fetch_twin.py + fetch_ign.py):", e)

    # ------------------------------------------------------------- buildings
    def _build_buildings(self):
        from PIL import Image, ImageDraw
        eng, db = self.eng, self.eng.db
        s, w, _, _ = config.BBOX
        self.x0, self.y0 = db.to_xy(s, w)
        k = config.CELL_M // FINE
        H, W = eng.ny * k, eng.nx * k
        inside = Image.new("1", (W, H), 0)
        large = Image.new("1", (W, H), 0)
        di, dl = ImageDraw.Draw(inside), ImageDraw.Draw(large)
        path = config.TWIN_DIR / "buildings.geojson"            # IGN heights (fetch_ign.py)
        if not path.exists():
            path = config.TWIN_DIR / "buildings_osm.geojson"    # OSM fallback (fetch_twin.py)
        feats = json.loads(path.read_text(encoding="utf-8"))["features"]
        self.n_buildings = len(feats)
        for f in feats:
            ring = np.array(f["geometry"]["coordinates"][0])
            x, y = db.to_xy(ring[:, 1], ring[:, 0])
            area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
            pts = list(zip((x - self.x0) / FINE, (y - self.y0) / FINE))   # row 0 = south
            if len(pts) < 3:
                continue
            di.polygon(pts, fill=1)
            p = f["properties"]
            if area >= config.LARGE_BUILDING_M2 or (p.get("use") == "Religieux" and area >= 250):
                dl.polygon(pts, fill=1)
        ins = np.array(inside, bool)
        lar = np.array(large, bool) & ins
        dist = ndimage.distance_transform_edt(~ins) * FINE    # metres to nearest building
        self.fine_dist = dist
        self.fine_inside = ins

        def per_cell(a):     # (H, W) -> (ny*nx,) mean over the k x k pixels of each cell
            return a.reshape(eng.ny, k, eng.nx, k).mean(axis=(1, 3)).ravel()

        out = ~ins
        f_in, f_large = per_cell(ins), per_cell(lar)
        f_enc = per_cell(out & (dist < config.ENCLOSED_FACADE_M))
        f_open = per_cell(out & (dist > config.OPEN_FACADE_M))
        f_mid = 1 - f_in - f_enc - f_open
        small_bldg = f_in - f_large
        P = np.vstack([
            small_bldg * 0.97 + f_large * 0.6,        # people in big buildings are often in small rooms
            small_bldg * 0.03 + f_large * 0.4,
            f_enc + 0.5 * f_mid,
            f_open + 0.5 * f_mid,
        ]).T
        self.P_setting = P / P.sum(axis=1, keepdims=True)
        self.built_cover = per_cell(ins)
        self.k = k

    # ------------------------------------------------------------- sources
    def _load_sources(self):
        eng, db = self.eng, self.eng.db
        feats = json.loads((config.TWIN_DIR / "sources.geojson").read_text(encoding="utf-8"))["features"]
        groups = {}
        for f in feats:
            p = f["properties"]
            key = "road%d" % p["cls"] if p["kind"] == "road" else p["kind"]
            groups.setdefault(key, []).append(f["geometry"]["coordinates"])
        self.src_counts = {k: len(v) for k, v in groups.items()}
        R = config.HEAR_RADIUS

        def exposure(key, radius):
            if key not in groups:
                return np.zeros(eng.N)
            c = np.array(groups[key])
            x, y = db.to_xy(c[:, 1], c[:, 0])
            d, _ = cKDTree(np.c_[x, y]).query(np.c_[eng.X, eng.Y])
            return soft_inside(d, radius)

        rail = np.maximum(exposure("railway", R["rail"]), exposure("tram", R["tram"]))
        road = np.max([exposure(f"road{i}", R[f"road{i}"]) for i in (1, 2, 3, 4)], axis=0)
        d_church, _ = eng._nearest("church")
        bells = soft_inside(d_church, R["bells"]) if d_church is not None else np.zeros(eng.N)
        machinery = exposure("industrial", R["machinery"])
        # Birds: strongest where there are few buildings around (parks, the Bois).
        around = ndimage.uniform_filter(self.built_cover.reshape(eng.ny, eng.nx), size=5).ravel()
        nature = np.clip(1 - around / 0.25, 0, 1)
        self.exposure = {"rail": rail, "traffic": road, "bells": bells, "machinery": machinery,
                         "nature": nature}

    # ------------------------------------------------------------- likelihoods
    def p_heard(self, cls, source="audio"):
        near, far = config.HEAR_MODEL[cls][source]
        return far + (near - far) * self.exposure[cls]

    def likelihood(self, c):
        """Per-cell likelihood (N,) of one acoustic constraint, or None."""
        if not self.ok:
            return None
        kind = c["kind"]
        if kind == "hear":
            P = self.p_heard(c["cls"], "voice" if c.get("source") == "voice" else "audio")
            q = c.get("q", 1.0)
            return q * P + (1 - q) * (1 - P)            # soft evidence (Jeffrey's rule)
        if kind == "setting":
            p = np.array([c["p"].get(s, 0.0) for s in config.SETTINGS])
            # The classifier output is a posterior under a flat prior, so it can be
            # mixed directly with P(setting | cell).
            if c.get("source") != "voice":
                return self._audio_setting() @ p
            return self.P_setting @ p
        if kind == "reflector":   # outdoor echo at d metres -> a facade at about d metres
            return self.facade_likelihood(c["distance_m"])
        return None

    # What the audio classifier says among trees: forest reverberation (1.3-1.7 s at 1 kHz,
    # dense even tail; Shelley et al. 2013) looks like a hall to a street/room-tuned model.
    # Placeholder until chirps recorded in the Bois calibrate it.
    FOREST_AUDIO = {"indoor_small": 0.10, "indoor_large": 0.35, "outdoor_enclosed": 0.30, "outdoor_open": 0.25}

    def _audio_setting(self):
        if getattr(self, "_P_audio", None) is None:
            from .forest import get_forest
            fo = get_forest(self.eng)
            P = self.P_setting
            if fo.ok:
                f = np.array([self.FOREST_AUDIO[s] for s in config.SETTINGS])
                w = np.clip(fo.wood * 1.15, 0, 1)[:, None]
                P = (1 - w) * P + w * f[None, :]
            self._P_audio = P
        return self._P_audio

    def facade_likelihood(self, d, sigma=0.35):
        """Per cell: chance that the nearest facade is ~d m away from a random outdoor
        point in the cell. Inside a building any wall distance is plausible (0.3)."""
        dist = np.maximum(self.fine_dist, 1.5)
        L = np.exp(-0.5 * (np.log(dist / d) / sigma) ** 2)
        L = np.where(self.fine_inside, 0.3, L)
        eng, k = self.eng, self.k
        return L.reshape(eng.ny, k, eng.nx, k).mean(axis=(1, 3)).ravel()

    def at(self, lat, lon):
        """Ground truth at a point (for rehearsal and tests)."""
        x, y = self.eng.db.to_xy(lat, lon)
        i = int(np.argmin((self.eng.X - x) ** 2 + (self.eng.Y - y) ** 2))
        r = int((y - self.y0) // FINE)
        cidx = int((x - self.x0) // FINE)
        H, W = self.fine_dist.shape
        r, cidx = min(max(r, 0), H - 1), min(max(cidx, 0), W - 1)
        return {"cell": i, "inside": bool(self.fine_inside[r, cidx]),
                "facade_m": float(self.fine_dist[r, cidx]),
                "P_setting": dict(zip(config.SETTINGS, self.P_setting[i].round(3).tolist())),
                "exposure": {g: round(float(v[i]), 2) for g, v in self.exposure.items()}}


_sc = None


def get_soundscape(eng=None):
    global _sc
    if _sc is None:
        from .localise import get_engine
        _sc = Soundscape(eng or get_engine())
    return _sc
