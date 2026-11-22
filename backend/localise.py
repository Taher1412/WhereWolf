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
        self._small = {}                              # per-cell (N,) maps: visibility, offsets

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
                c.get("sigma"), c.get("distance_m"), bool(c.get("heard")))

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
        if c.get("heard"):   # by ear: hearing range, and trees don't hide a sound
            R = config.HEARD_BEARING_RADIUS.get(c["type"], config.VIS_RADIUS.get(c["type"], config.VIS_RADIUS_DEFAULT))
            w = np.exp(-0.5 * (dist / R) ** 2)
        else:
            R = config.VIS_RADIUS.get(c["type"], config.VIS_RADIUS_DEFAULT)
            w = np.exp(-0.5 * (dist / R) ** 2)
            w = w * self.obstruction(np.arange(self.N) if rows is None else rows, idx, bear, dist, c["type"])
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

    # ------------------------------------------------------- seeing through trees
    def canopy(self, cells, bear, dist, ltype):
        """Chance trees don't block the line of sight (1 when there's no forest data).
        cells (n,), bear / dist (n, m) or (n,)."""
        from .forest import get_forest
        fo = get_forest(self)
        if not fo.ok or ltype in config.NO_CANOPY_TYPES or not config.CANOPY_ENABLED:
            return 1.0
        cells = np.asarray(cells)
        if np.ndim(bear) == 2:
            cells = cells[:, None]
        return fo.transmission(cells, bear, dist, tall=ltype in config.TALL_TYPES).astype(np.float32)

    def obstruction(self, cells, idx, bear, dist, ltype):
        """(n, m) chance nothing blocks the view from cells to landmarks idx: the true 3D
        line of sight (viewshed.py: buildings, terrain, trees) where known, else the
        canopy model (forest.py)."""
        base = self.canopy(cells, bear, dist, ltype)
        if not config.VIEWSHED_ENABLED:
            return base
        from .viewshed import get_viewshed
        vs = get_viewshed(self)
        if not vs.ok:
            return base
        S = vs.sight(cells, idx)
        base = np.broadcast_to(base, S.shape if np.ndim(bear) == 2 else (S.shape[0],)).astype(np.float32)
        if np.ndim(bear) == 1:
            S = S[:, 0]
            base2 = base[:, None]
        else:
            base2 = base
        # Cells entirely inside buildings: maybe a view from a window, less likely than outside.
        indoor = vs.indoor[np.asarray(cells)][:, None] & vs.has(idx)[None, :]
        if np.ndim(bear) == 1:
            indoor = indoor[:, 0]
            base2 = base
        fill = np.where(indoor, config.INDOOR_SIGHT * base2, base2)
        return np.where(np.isnan(S), fill, S)

    def see_feature(self, i):
        """P(landmark i is in sight) from every cell: close enough, nothing in the way."""
        ltype = self.db.types[i]
        R = config.VIS_RADIUS.get(ltype, config.VIS_RADIUS_DEFAULT)
        dx, dy = self.db.x[i] - self.X, self.db.y[i] - self.Y
        d = np.hypot(dx, dy)
        bear = np.degrees(np.arctan2(dx, dy)) % 360.0
        return soft_inside(d, R) * self.obstruction(np.arange(self.N), np.array([i]), bear, d, ltype)

    def visibility(self, ltype, name=None, R=None):
        """P(at least one landmark of that type is in sight), per cell (cached).
        None if there is no such landmark in the area."""
        def build():
            idx = self.db.candidates(ltype, name, limit=100000)
            if len(idx) == 0:
                return None
            RR = R or config.VIS_RADIUS.get(ltype, config.VIS_RADIUS_DEFAULT)
            if ltype in config.NO_CANOPY_TYPES or not (config.CANOPY_ENABLED or config.VIEWSHED_ENABLED):
                d, _ = self._nearest(ltype, name)            # nothing hides it: nearest one
                return soft_inside(d, RR)
            cx, cy = self._cand_xy(idx)
            p = np.zeros(self.N)
            grid = np.arange(self.N).reshape(self.ny, self.nx)
            x0, y0, c = self.X[0], self.Y[0], config.CELL_M
            reach = int(math.ceil(2.0 * RR / c))           # soft_inside is ~0 beyond 2 R
            for k, (x, y) in enumerate(zip(cx, cy)):
                i, j = int(round((y - y0) / c)), int(round((x - x0) / c))
                rows = grid[max(0, i - reach): i + reach + 1, max(0, j - reach): j + reach + 1].ravel()
                if rows.size == 0:
                    continue
                dx, dy = x - self.X[rows], y - self.Y[rows]
                d = np.hypot(dx, dy)
                bear = np.degrees(np.arctan2(dx, dy)) % 360.0
                q = soft_inside(d, RR) * self.obstruction(rows, idx[k:k + 1], bear, d, ltype)
                p[rows] = np.maximum(p[rows], q)
            return p
        key = ("vis", ltype, name, R, config.CANOPY_ENABLED, config.VIEWSHED_ENABLED)
        if key not in self._small:
            self._small[key] = build()
        return self._small[key]

    def _offset_like(self, c):
        """Per cell: best fit over landmarks of that type for 'd metres toward bearing b'."""
        idx = self.db.candidates(c["type"], c.get("name"), limit=100000)
        p = np.zeros(self.N)
        if len(idx) == 0:
            return p + 1.0
        cx, cy = self._cand_xy(idx)
        s = c.get("sigma_log", 0.4)
        for x, y in zip(cx, cy):
            dx, dy = self.X - x, self.Y - y
            d = np.maximum(np.hypot(dx, dy), 5.0)
            b = np.degrees(np.arctan2(dx, dy)) % 360.0
            q = np.exp(-0.5 * (np.log(d / c["distance_m"]) / s) ** 2) * \
                np.exp(-0.5 * (wrap180(b - c["bearing"]) / config.SIGMA_CARDINAL) ** 2)
            np.maximum(p, q, out=p)
        return p

    # ------------------------------------------------------- aimed with the phone
    def _seen_weights(self, ltype, name=None):
        """(idx, d, bear, w): landmarks of a type, distance / bearing from every cell, and
        the chance each is in sight (range x 3D line of sight)."""
        idx = self.db.candidates(ltype, name, limit=100000)
        if len(idx) == 0:
            return idx, None, None, None
        cx, cy = self._cand_xy(idx)
        dx = (cx[None, :] - self.X[:, None]).astype(np.float32)
        dy = (cy[None, :] - self.Y[:, None]).astype(np.float32)
        d = np.hypot(dx, dy)
        bear = np.degrees(np.arctan2(dx, dy)) % 360.0
        R = config.VIS_RADIUS.get(ltype, config.VIS_RADIUS_DEFAULT)
        w = np.exp(-0.5 * (d / R) ** 2) * self.obstruction(np.arange(self.N), idx, bear, d, ltype)
        return idx, d, bear, w

    def _elevation_like(self, c):
        """Phone tilted up at the top of a landmark: trigonometric levelling. Per cell, the
        best landmark of that type that is in sight and has that elevation angle."""
        from .viewshed import get_viewshed
        vs = get_viewshed(self)
        idx, d, _, w = self._seen_weights(c["type"], c.get("name"))
        if not vs.ok or len(idx) == 0 or not vs.has(idx).any():
            return None
        E = vs.elevation(np.arange(self.N), idx)
        s = np.sqrt((c.get("sigma") or config.SIGMA_TILT) ** 2 + np.degrees(config.SIGMA_TOP_M / np.maximum(d, 20.0)) ** 2)
        g = np.where(np.isnan(E), 0.0, np.exp(-0.5 * ((E - c["deg"]) / s) ** 2))
        L = (w * g).max(axis=1)
        return np.where(vs.indoor, 0.2, L)

    def _angle_like(self, c):
        """Angle between two landmarks swept with the gyroscope (resection, no heading
        needed): best pair of landmarks in sight with that angle, per cell."""
        ia, _, ba, wa = self._seen_weights(c["a"]["type"], c["a"].get("name"))
        ib, _, bb, wb = self._seen_weights(c["b"]["type"], c["b"].get("name"))
        if len(ia) == 0 or len(ib) == 0:
            return None
        sig = c.get("sigma") or config.SIGMA_SWEEP
        L = np.zeros(self.N, np.float32)
        for j in range(len(ia)):
            diff = wrap180(bb - ba[:, j:j + 1] - c["deg"])
            q = wa[:, j:j + 1] * wb * np.exp(-0.5 * (diff / sig) ** 2)
            if c["a"]["type"] == c["b"]["type"]:
                q = np.where((ib == ia[j])[None, :], 0, q)      # two different churches
            np.maximum(L, q.max(axis=1), out=L)
        return L

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
                s = self.visibility(c["type"], c.get("name"), c.get("radius"))
                p = 0.05 + 0.9 * s if c.get("value", True) else 0.95 - 0.9 * s
            return np.log(floor + (1 - floor) * p)[:, None]

        if kind == "feature_visible":
            s = self.see_feature(c["feature"])
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

        if kind in ("hear", "setting", "reflector", "echoes", "ambient"):   # acoustic evidence
            if kind in ("echoes", "ambient"):         # matched against real walls / noise map
                from .surround import get_places
                L = get_places(self).likelihood(c)
            else:                                     # soundscape.py
                from .soundscape import get_soundscape
                L = get_soundscape(self).likelihood(c)
            if L is None:
                return np.zeros((1, 1))
            w = c.get("w", 1.0) * (config.ACOUSTIC_WEIGHT if c.get("source") != "voice" else 1.0)
            return (w * np.log(floor + (1 - floor) * L))[:, None]

        if kind in ("elevation", "angle_between"):   # aimed with the phone (tilt / gyroscope)
            if kind == "elevation":
                key = ("elev", c["type"], c.get("name"), round(c["deg"], 1), c.get("sigma"), config.VIEWSHED_ENABLED)
                fn = lambda: self._elevation_like(c)  # noqa: E731
            else:
                key = ("angle", c["a"]["type"], c["a"].get("name"), c["b"]["type"], c["b"].get("name"),
                       round(c["deg"], 1), c.get("sigma"), config.VIEWSHED_ENABLED)
                fn = lambda: self._angle_like(c)  # noqa: E731
            if key not in self._small:
                self._small[key] = fn()
            L = self._small[key]
            if L is None:
                return np.zeros((1, 1))
            return np.log(floor + (1 - floor) * L)[:, None]

        if kind == "multi":     # several answers given together ("I see the lake, not the church")
            ll = np.zeros((1, 1))
            for it in c["items"]:
                ll = ll + self.loglik(it, when)
            return ll

        if kind == "compass":   # phone compass: where the speaker's 12 o'clock points
            diff = wrap180(self.headings - c["deg"])
            p = np.exp(-0.5 * (diff / (c.get("sigma") or config.SIGMA_COMPASS)) ** 2)
            return np.log(floor + (1 - floor) * p)[None, :]

        if kind == "last_fix":  # last GPS fix before jamming: within walking range of it
            gx, gy = self.db.to_xy(c["lat"], c["lon"])
            d = np.hypot(self.X - gx, self.Y - gy)
            r = max(c.get("acc") or 30.0, config.CELL_M) + config.WALK_M_PER_S * (c.get("age_s") or 0)
            p = 0.03 + 0.97 * soft_inside(d, r)
            return np.log(floor + (1 - floor) * p)[:, None]

        if kind == "offset":    # "10 minutes north of the church"
            key = ("offset", c["type"], c.get("name"), c["bearing"], c["distance_m"])
            if key not in self._small:
                self._small[key] = self._offset_like(c)
            return np.log(floor + (1 - floor) * self._small[key])[:, None]

        if kind == "ground":   # "under trees", "on a dirt track", "I can see a pond"
            from .forest import get_forest
            fo = get_forest(self)
            P = fo.ground_probs(c["what"]) if fo.ok else None
            if not P or c["value"] not in P:
                return np.zeros((1, 1))
            return np.log(floor + (1 - floor) * P[c["value"]])[:, None]

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
        for b in blobs:   # which way the speaker most likely faces, if they are in this area
            b["heading_deg"] = float(self.headings[int(np.argmax(joint[b.pop("cell")]))])
        heading = joint.sum(axis=0)
        h_best = float(self.headings[int(np.argmax(heading))])
        hyps = self.hypotheses(grid)
        for h in hyps:
            h["heading_deg"] = float(self.headings[int(np.argmax(joint[h.pop("cell")]))])
        return {
            "post": post, "joint": joint, "blobs": blobs, "hyps": hyps, "constraints_used": used,
            "radius_m": main["r80"] if main else None,
            "main_mass": main["mass"] if main else 0.0,
            # Pin = most likely cell of the main blob (closer than the mean on fan shapes).
            "lat": main["peak_lat"] if main else None, "lon": main["peak_lon"] if main else None,
            "heading_deg": h_best,
            "heading_conf": float(heading.max() * self.H),   # 1 = uniform
            "heat": self.heat(grid),
        }

    def hypotheses(self, grid, k=3, sep=300.0, min_mass=0.04):
        """Up to k distinct likely spots, even inside one broad area: peaks of the map at
        least `sep` metres apart. Every likely cell goes to its nearest peak, which gives
        each spot its share of the probability and its size."""
        flat = grid.ravel()
        if flat.max() <= 0:
            return []
        size = 2 * int(math.ceil(sep / config.CELL_M / 2)) + 1
        peaks = np.where((ndimage.maximum_filter(grid, size=size, mode="constant") == grid).ravel()
                         & (flat >= 0.02 * flat.max()))[0]
        peaks = peaks[np.argsort(flat[peaks])[::-1]]
        chosen = []
        for p in peaks:
            if all(math.hypot(self.X[p] - self.X[q], self.Y[p] - self.Y[q]) >= sep for q in chosen):
                chosen.append(int(p))
            if len(chosen) >= k:
                break
        order = np.argsort(flat)[::-1]
        n = int(np.searchsorted(np.cumsum(flat[order]), 0.99)) + 1
        cells = order[:n]
        cx, cy = self.X[chosen], self.Y[chosen]
        near = np.argmin((self.X[cells, None] - cx[None, :]) ** 2 + (self.Y[cells, None] - cy[None, :]) ** 2, axis=1)
        out = []
        for j, p in enumerate(chosen):
            sel = cells[near == j]
            m = float(flat[sel].sum())
            if m < min_mass:
                continue
            w = flat[sel] / m
            d = np.hypot(self.X[sel] - self.X[p], self.Y[sel] - self.Y[p])
            o = np.argsort(d)
            r80 = float(d[o][min(np.searchsorted(np.cumsum(w[o]), 0.8), len(o) - 1)])
            lat, lon = self.db.to_latlon(self.X[p], self.Y[p])
            out.append({"lat": float(lat), "lon": float(lon), "peak_lat": float(lat), "peak_lon": float(lon),
                        "mass": m, "r80": max(r80 + config.CELL_M / 2, config.CELL_M),
                        "r2": max(2 * float(np.sqrt((w * d ** 2).sum())), config.CELL_M), "cell": p})
        out.sort(key=lambda h: -h["mass"])
        tot = sum(h["mass"] for h in out) or 1.0
        for h, L in zip(out, "ABC"):
            h["label"] = L
            h["share"] = h["mass"] / tot      # of what the listed spots hold
        return out

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
                "cell": int(k),
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
