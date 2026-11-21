"""Likelihood-grid localisation: where is the speaker, given what they see?

The search area is a grid of cells (25 m). The speaker's heading (where their
12 o'clock points) is unknown, so we also try 72 headings (every 5 degrees).

For every (cell, heading) we multiply the likelihoods of all constraints:
  - bearing:   "church at my 2 o'clock"   (needs heading)
  - visible:   "I can / can't see a railway"
  - here:      "we're in a tree line"
  - sun:       "sun at my 1 o'clock"      (fixes the heading)
  - answers to questions (distance band, left/right, named feature visible)
  - gps (optional)

Then we sum over headings to get a probability map over cells, find the
blobs (possible areas) and an ellipse for each.

Everything is in local metres: x = east, y = north, origin = centre of BBOX.
"""
import base64
import math
from collections import OrderedDict

import numpy as np
from scipy import ndimage
from scipy.special import erf
from scipy.spatial import cKDTree

from . import config
from .landmarks import get_db
from .sun import sun_position


def wrap180(a):
    """Wrap angles (degrees) to (-180, 180]."""
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def soft_inside(d, radius):
    """~1 when d << radius, ~0 when d >> radius (smooth step)."""
    return 1.0 / (1.0 + np.exp(np.clip((d - radius) / (0.25 * radius), -50, 50)))


class Engine:
    def __init__(self, db=None):
        self.db = db or get_db()
        s, w, n, e = config.BBOX
        x0, y0 = self.db.to_xy(s, w)
        x1, y1 = self.db.to_xy(n, e)
        c = config.CELL_M
        self.nx = int(math.ceil((x1 - x0) / c))
        self.ny = int(math.ceil((y1 - y0) / c))
        xs = x0 + c * (np.arange(self.nx) + 0.5)
        ys = y0 + c * (np.arange(self.ny) + 0.5)
        gx, gy = np.meshgrid(xs, ys)                 # shape (ny, nx), row 0 = south
        self.X, self.Y = gx.ravel(), gy.ravel()       # one entry per cell
        self.N = self.X.size
        self.H = 360 // config.HEADING_STEP
        self.headings = np.arange(self.H) * config.HEADING_STEP
        self.bounds = {"south": s, "west": w, "north": n, "east": e}
        self._cache = OrderedDict()                   # constraint key -> arrays

    # ------------------------------------------------------------------ helpers
    def _cand_xy(self, idx):
        return self.db.x[idx], self.db.y[idx]

    def _nearest(self, ltype, name=None):
        """Distance and index of the nearest candidate of a type, for every cell."""
        idx = self.db.candidates(ltype, name, limit=100000)
        if len(idx) == 0:
            return None, None
        cx, cy = self._cand_xy(idx)
        tree = cKDTree(np.c_[cx, cy])
        d, j = tree.query(np.c_[self.X, self.Y])
        return d, idx[j]

    def bearing_to(self, fx, fy):
        """Bearing (deg from north) from every cell to point(s) (fx, fy)."""
        return np.degrees(np.arctan2(fx - self.X, fy - self.Y)) % 360.0

    def _cached(self, key, fn):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        val = fn()
        self._cache[key] = val
        while len(self._cache) > 12:
            self._cache.popitem(last=False)
        return val

    # ------------------------------------------------------- bearing observation
    @staticmethod
    def _key(c):
        return ("bearing", c["type"], c.get("name"), round(c["beta"], 1),
                c.get("sigma"), c.get("distance_m"))

    def bearing_like(self, c):
        """Likelihood (N, H) of one bearing observation (cached)."""
        return self._cached(self._key(c), lambda: self._bearing(c, None)[0])

    def bearing_match(self, c, rows=None):
        """Distance (n, H) to the landmark that best explains the observation,
        for each cell in `rows` and each heading. Used by distance questions."""
        if rows is None:
            key = ("match",) + self._key(c)
            return self._cached(key, lambda: self._bearing(c, None, want_match=True)[1])
        return self._bearing(c, rows, want_match=True)[1]

    def _bearing(self, c, rows, want_match=False):
        idx = self.db.candidates(c["type"], c.get("name"))
        H, step = self.H, config.HEADING_STEP
        X = self.X if rows is None else self.X[rows]
        Y = self.Y if rows is None else self.Y[rows]
        n = X.size
        if len(idx) == 0:
            return np.ones((n, H), np.float32), np.full((n, H), 5000.0, np.float32)
        cx, cy = self._cand_xy(idx)
        dx = (cx[None, :] - X[:, None]).astype(np.float32)
        dy = (cy[None, :] - Y[:, None]).astype(np.float32)
        dist = np.hypot(dx, dy)
        bear = np.degrees(np.arctan2(dx, dy)) % 360.0

        # Weight of each candidate: could it be seen from here? does the said distance fit?
        R = config.VIS_RADIUS.get(c["type"], config.VIS_RADIUS_DEFAULT)
        w = np.exp(-0.5 * (dist / R) ** 2)
        if c.get("distance_m"):
            ratio = np.log(np.maximum(dist, 5.0) / c["distance_m"])
            w = w * np.exp(-0.5 * (ratio / config.SIGMA_DIST_LOG) ** 2)

        # Heading that would put this candidate at the spoken direction.
        hbin = np.rint(((bear - c["beta"]) % 360.0) / step).astype(int) % H

        # best[cell, heading-bin] = max weight of a candidate in that bin.
        best = np.zeros((n, H), np.float32)
        bestd = np.full((n, H), 5000.0, np.float32)
        r_all = np.arange(n)
        for j in range(len(idx)):
            col = hbin[:, j]
            upd = w[:, j] > best[r_all, col]
            r = r_all[upd]
            best[r, col[upd]] = w[upd, j]
            if want_match:
                bestd[r, col[upd]] = dist[upd, j]

        # Spread over headings with the angular noise (a "max-convolution").
        sigma = c.get("sigma") or config.SIGMA_CLOCK
        half = int(math.ceil(3 * sigma / step))
        ext = np.concatenate([best[:, H - half:], best, best[:, :half]], axis=1)
        exd = np.concatenate([bestd[:, H - half:], bestd, bestd[:, :half]], axis=1)
        like = np.zeros((n, H), np.float32)
        match = np.full((n, H), 5000.0, np.float32) if want_match else None
        tmp = np.empty((n, H), np.float32)
        for s in range(-half, half + 1):
            g = math.exp(-0.5 * (s * step / sigma) ** 2)
            np.multiply(ext[:, half + s: half + s + H], g, out=tmp)
            if want_match:
                match = np.where(tmp > like, exd[:, half + s: half + s + H], match)
            np.maximum(like, tmp, out=like)
        return like, match

    # ------------------------------------------------------------- one constraint
    def loglik(self, c, when=None):
        """Log-likelihood of one constraint, broadcastable to (N, H)."""
        floor = config.OUTLIER_FLOOR
        kind = c["kind"]

        if kind == "bearing":
            return np.log(floor + (1 - floor) * self.bearing_like(c))

        if kind in ("visible", "here"):
            d, _ = self._nearest(c["type"], c.get("name"))
            if d is None:
                # Nothing of that type in the area: "I see X" can't be used, "no X" is free.
                return np.zeros((self.N, 1))
            if kind == "here":
                p = 0.05 + 0.95 * soft_inside(d, config.HERE_RADIUS)
            else:
                R = c.get("radius") or config.VIS_RADIUS.get(c["type"], config.VIS_RADIUS_DEFAULT)
                s = soft_inside(d, R)
                p = 0.05 + 0.9 * s if c.get("value", True) else 0.95 - 0.9 * s
            return np.log(floor + (1 - floor) * p)[:, None]

        if kind == "feature_visible":
            f = self.db.feature(c["feature"])
            fx, fy = self.db.to_xy(f["lat"], f["lon"])
            d = np.hypot(self.X - fx, self.Y - fy)
            R = config.VIS_RADIUS.get(f["type"], config.VIS_RADIUS_DEFAULT)
            s = soft_inside(d, R)
            p = 0.05 + 0.9 * s if c["value"] else 0.95 - 0.9 * s
            return np.log(floor + (1 - floor) * p)[:, None]

        if kind == "sun":
            az, elev = self.sun(when)
            if elev < 2:
                return np.zeros((1, self.H))           # sun is down: ignore
            theta = az - c["clock"] * 30.0              # heading that fits
            diff = wrap180(self.headings - theta)
            p = np.exp(-0.5 * (diff / (c.get("sigma") or config.SIGMA_SUN)) ** 2)
            return np.log(floor + (1 - floor) * p)[None, :]

        if kind == "distance":   # "the keep is about 300 metres away"
            d = np.maximum(self.ref_distance(c["ref"]), 5.0)
            p = np.exp(-0.5 * (np.log(d / c["distance_m"]) / config.SIGMA_DIST_LOG) ** 2)
            return np.log(floor + (1 - floor) * p)

        if kind == "left_right":
            p_right = self.left_right_prob(c["a"], c["b"])
            p = p_right if c["value"] == "right" else 1.0 - p_right
            return np.log(floor + (1 - floor) * p)[:, None]

        if kind in ("hear", "setting", "reflector"):   # acoustic evidence (soundscape.py)
            from .soundscape import get_soundscape
            L = get_soundscape(self).likelihood(c)
            if L is None:
                return np.zeros((1, 1))
            w = c.get("w", 1.0) * (config.ACOUSTIC_WEIGHT if c.get("source") != "voice" else 1.0)
            return (w * np.log(floor + (1 - floor) * L))[:, None]

        if kind == "gps":
            gx, gy = self.db.to_xy(c["lat"], c["lon"])
            d2 = (self.X - gx) ** 2 + (self.Y - gy) ** 2
            acc = max(c.get("acc") or 30.0, config.CELL_M)
            return np.log(floor + (1 - floor) * np.exp(-0.5 * d2 / acc ** 2))[:, None]

        return np.zeros((1, 1))

    # ------------------------------------------- helpers shared with questions.py
    def sun(self, when=None):
        return sun_position(self.db.lat0, self.db.lon0, when)

    def ref_distance(self, ref, rows=None):
        """Distance from each cell (and heading) to the landmark the speaker meant.
        ref is a bearing constraint (the landmark that best fits the direction)
        or a visible/here one (the nearest landmark of that type)."""
        if ref.get("kind") == "bearing":
            return self.bearing_match(ref, rows)
        d, _ = self._nearest(ref["type"], ref.get("name"))
        d = np.full(self.N, 5000.0) if d is None else d
        return (d if rows is None else d[rows])[:, None]

    DIST_EDGES = (120.0, 250.0, 500.0, 1000.0)   # answer bins for "how far?"

    def dist_band_probs(self, ref, rows=None):
        """P(spoken estimate falls in each bin | cell, heading). People misjudge
        distance, so the estimate is log-normal around the true distance."""
        d = np.maximum(self.ref_distance(ref, rows), 5.0)
        s = config.SIGMA_DIST_LOG
        cdf = [0.5 * (1 + erf(np.log(e / d) / (s * math.sqrt(2)))) for e in self.DIST_EDGES]
        cdf = [np.zeros_like(d)] + cdf + [np.ones_like(d)]
        return [cdf[i + 1] - cdf[i] for i in range(len(cdf) - 1)]

    def left_right_prob(self, a, b):
        """P("b is on the right of a") for every cell, using nearest candidates."""
        _, ia = self._nearest(a["type"], a.get("name"))
        _, ib = self._nearest(b["type"], b.get("name"))
        if ia is None or ib is None:
            return np.full(self.N, 0.5)
        ba = self.bearing_to(self.db.x[ia], self.db.y[ia])
        bb = self.bearing_to(self.db.x[ib], self.db.y[ib])
        ang = wrap180(bb - ba)
        return 0.5 * (1 + erf(ang / (20.0 * math.sqrt(2))))

    # -------------------------------------------------------------- main entry
    def run(self, constraints, when=None):
        """Combine all constraints. Returns a result dict (see summarise)."""
        ll = np.zeros((self.N, self.H))
        used = 0
        for c in constraints:
            try:
                ll = ll + self.loglik(c, when)
                used += 1
            except Exception as e:  # one bad constraint must not kill the fix
                print("constraint skipped:", c.get("kind"), e)
        ll -= ll.max()
        joint = np.exp(ll)
        joint /= joint.sum()
        post = joint.sum(axis=1)
        return self.summarise(post, joint, used)

    def summarise(self, post, joint, used=0):
        grid = post.reshape(self.ny, self.nx)
        blobs = self.find_blobs(grid)
        main = blobs[0] if blobs else None
        heading = joint.sum(axis=0)
        h_best = float(self.headings[int(np.argmax(heading))])
        return {
            "post": post, "joint": joint, "blobs": blobs, "constraints_used": used,
            "radius_m": main["r80"] if main else None,
            "main_mass": main["mass"] if main else 0.0,
            # Pin = most likely cell of the main blob (closer than the mean on fan shapes).
            "lat": main["peak_lat"] if main else None, "lon": main["peak_lon"] if main else None,
            "heading_deg": h_best,
            "heading_conf": float(heading.max() * self.H),   # 1 = uniform
            "heat": self.heat(grid),
        }

    def find_blobs(self, grid, mass=0.7, max_blobs=3):
        """Connected areas that together hold `mass` of the probability."""
        flat = grid.ravel()
        order = np.argsort(flat)[::-1]
        cum = np.cumsum(flat[order])
        k = int(np.searchsorted(cum, mass)) + 1
        mask = np.zeros(flat.size, bool)
        mask[order[:k]] = True
        labels, n = ndimage.label(mask.reshape(grid.shape), structure=np.ones((3, 3)))
        blobs = []
        lab = labels.ravel()
        for i in range(1, n + 1):
            sel = lab == i
            m = flat[sel].sum()
            if m < 0.03:
                continue
            w = flat[sel] / m
            x, y = self.X[sel], self.Y[sel]
            mx, my = (w * x).sum(), (w * y).sum()
            cov = np.cov(np.vstack([x, y]), aweights=w + 1e-12) if sel.sum() > 2 else np.eye(2)
            cov = cov + np.eye(2) * (config.CELL_M ** 2 / 12)   # cell size floor
            vals, vecs = np.linalg.eigh(cov)
            vals = np.maximum(vals, 1.0)
            major = vecs[:, 1]
            angle = math.degrees(math.atan2(major[0], major[1]))  # from north
            lat, lon = self.db.to_latlon(mx, my)
            k = np.argmax(np.where(sel, flat, -1))             # most likely cell of the blob
            plat, plon = self.db.to_latlon(self.X[k], self.Y[k])
            # Radius around the peak holding 80 % of this blob (what we say out loud).
            dpk = np.hypot(x - self.X[k], y - self.Y[k])
            o = np.argsort(dpk)
            r80 = float(dpk[o][min(np.searchsorted(np.cumsum(w[o]), 0.8), len(o) - 1)])
            r80 = max(r80 + config.CELL_M / 2, config.CELL_M)
            blobs.append({
                "lat": float(lat), "lon": float(lon), "mass": float(m),
                "peak_lat": float(plat), "peak_lon": float(plon),
                "sx": float(math.sqrt(vals[1])), "sy": float(math.sqrt(vals[0])),
                "angle": float(angle), "r2": float(2 * math.sqrt(vals[1])), "r80": r80,
            })
        blobs.sort(key=lambda b: -b["mass"])
        return blobs[:max_blobs]

    def heat(self, grid):
        """Posterior as a small uint8 image (row 0 = north), base64 encoded."""
        g = grid / grid.max() if grid.max() > 0 else grid
        img = (g * 255).astype(np.uint8)[::-1]          # linear: peaks stand out
        return {"w": self.nx, "h": self.ny, "bounds": self.bounds,
                "data": base64.b64encode(img.tobytes()).decode()}


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine
