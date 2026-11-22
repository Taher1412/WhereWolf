"""What the ground is like in every grid cell, for people inside a wood or park.

From data/twin/forest.geojson (scripts/fetch_forest.py, OpenStreetMap), rasterised
at 5 m, then summarised per 25 m cell:

  wood      share of the cell under trees (landuse=forest / natural=wood|scrub)
  open      share of the cell that is grass, meadow, pitch or playground
  water     share of the cell that is water
  d_path    distance (m) from the cell centre to the nearest footpath / track
  d_paved   ... to the nearest paved path or road inside the park
  d_dirt    ... to the nearest unpaved path / track
  d_edge    distance to the wood edge (positive inside the wood, negative outside)
  d_water   distance to open water (lake, pond, stream)
  d_open    distance to the nearest open area seen from inside the trees
  d_fence   distance to a fence or wall

Everything here is optional: no file, no forest cues.
"""
import json
import time

import numpy as np

from . import config

RES = 5.0          # raster resolution (m)
VERSION = 2
PROF_DIRS = 36     # line-of-sight profiles: one per 10 degrees
PROF_STEP = 10.0   # sample every 10 m along the line
PROF_D = np.array([0, 25, 50, 100, 150, 200, 300, 400, 600, 800, 1100, 1500], float)


class Forest:
    def __init__(self, eng):
        self.eng = eng
        self.ok = False
        path = config.TWIN_DIR / "forest.geojson"
        if not path.exists():
            print("forest cues disabled: run  python scripts/fetch_forest.py")
            return
        t0 = time.time()
        s, w, _, _ = config.BBOX
        self.x0, self.y0 = eng.db.to_xy(s, w)
        self.W = int(eng.nx * config.CELL_M / RES)
        self.H = int(eng.ny * config.CELL_M / RES)
        key = np.array([VERSION, path.stat().st_size, eng.nx, eng.ny], np.int64)
        cache = config.TWIN_DIR / "forest_cache.npz"
        z = np.load(cache) if cache.exists() else None
        if z is None or not np.array_equal(z["key"], key):
            feats = self._rasterise(json.loads(path.read_text(encoding="utf-8"))["features"])
            np.savez_compressed(cache, key=key, **feats)
            z = np.load(cache)
        for k in z.files:
            if k != "key":
                setattr(self, k, z[k])
        self.ok = True
        print(f"forest ready in {time.time() - t0:.1f} s "
              f"({int((self.wood > 0.5).sum())} wooded cells of {eng.N})")

    # ------------------------------------------------------------------ build
    def _px(self, coords):
        c = np.asarray(coords, float)
        x, y = self.eng.db.to_xy(c[:, 1], c[:, 0])
        return list(zip((x - self.x0) / RES, (y - self.y0) / RES))

    def _rasterise(self, feats):
        from PIL import Image, ImageDraw
        from scipy.ndimage import distance_transform_edt as edt

        layers = {k: Image.new("1", (self.W, self.H), 0) for k in
                  ("wood", "open", "water", "path", "paved", "dirt", "fence")}
        draw = {k: ImageDraw.Draw(v) for k, v in layers.items()}
        for f in feats:
            p, g = f["properties"], f["geometry"]
            kind = p.get("kind")
            if g["type"] == "Polygon" and kind in ("wood", "open", "water"):
                draw[kind].polygon(self._px(g["coordinates"][0]), fill=1)
            elif g["type"] == "LineString":
                pts = self._px(g["coordinates"])
                if kind == "path":
                    draw["path"].line(pts, fill=1, width=1)
                    draw["paved" if p.get("paved") else "dirt"].line(pts, fill=1, width=1)
                elif kind == "stream":
                    draw["water"].line(pts, fill=1, width=1)
                elif kind == "fence":
                    draw["fence"].line(pts, fill=1, width=1)
        A = {k: np.array(v, bool) for k, v in layers.items()}   # [row = y (south first), col = x]
        # Water and open ground are not wood, even when a wood polygon covers them.
        A["wood"] &= ~(A["water"] | A["open"])

        def dist(mask):
            if not mask.any():
                return np.full(mask.shape, 1e4, np.float32)
            return (edt(~mask) * RES).astype(np.float32)

        D = {k: dist(A[k]) for k in ("path", "paved", "dirt", "water", "fence", "open")}
        d_in = dist(~A["wood"])          # inside the wood: distance to its edge
        d_out = dist(A["wood"])          # outside: distance to the nearest trees
        edge = np.where(A["wood"], d_in, -d_out)

        # Per cell: shares of the 5x5 pixels, distances at the centre pixel.
        k = int(round(config.CELL_M / RES))
        ny, nx = self.eng.ny, self.eng.nx

        def share(m):
            return m[:ny * k, :nx * k].reshape(ny, k, nx, k).mean(axis=(1, 3)).ravel().astype(np.float32)

        def centre(a):
            return a[k // 2:ny * k:k, k // 2:nx * k:k][:ny, :nx].ravel().astype(np.float32)

        out = {"wood": share(A["wood"]), "open": share(A["open"]), "water": share(A["water"]),
               "d_edge": centre(edge)}
        for name in ("path", "paved", "dirt", "water", "open", "fence"):
            out["d_" + name] = centre(D[name])
        # Full-resolution layers for the plan view.
        out["px_wood"], out["px_path"], out["px_water"] = A["wood"], A["path"], A["water"]
        out["prof"] = self._wood_profiles(A["wood"])
        return out

    def _wood_profiles(self, wood):
        """Metres of wood crossed from each cell centre along 36 directions, at the
        distances PROF_D. Lets visibility through trees be looked up in O(1)."""
        eng = self.eng
        ang = np.radians(np.arange(PROF_DIRS) * 360.0 / PROF_DIRS)
        sa, ca = np.sin(ang), np.cos(ang)
        steps = np.arange(PROF_STEP / 2, PROF_D[-1], PROF_STEP)
        bins = np.searchsorted(steps, PROF_D)          # samples before each distance
        cx, cy = (eng.X - self.x0) / RES, (eng.Y - self.y0) / RES
        out = np.zeros((eng.N, PROF_DIRS, len(PROF_D)), np.float16)
        for a in range(0, eng.N, 1500):
            px = cx[a:a + 1500, None, None] + steps[None, None, :] / RES * sa[None, :, None]
            py = cy[a:a + 1500, None, None] + steps[None, None, :] / RES * ca[None, :, None]
            ix, iy = px.astype(np.int32), py.astype(np.int32)
            ok = (ix >= 0) & (ix < self.W) & (iy >= 0) & (iy < self.H)
            w = np.zeros(ix.shape, np.float32)
            w[ok] = wood[iy[ok], ix[ok]]
            cum = np.concatenate([np.zeros(w.shape[:2] + (1,), np.float32), np.cumsum(w, axis=2)], axis=2)
            out[a:a + 1500] = (cum[:, :, bins] * PROF_STEP).astype(np.float16)
        return out

    # ------------------------------------------------------------- visibility
    def wood_between(self, cells, bearing, dist):
        """Metres of wood on the line of sight from cell(s) to targets at
        (bearing deg, dist m). Arrays broadcast together."""
        cells = np.asarray(cells)
        k = np.rint(np.asarray(bearing) / (360.0 / PROF_DIRS)).astype(int) % PROF_DIRS
        d = np.clip(np.asarray(dist, float), 0, PROF_D[-1])
        j = np.clip(np.searchsorted(PROF_D, d), 1, len(PROF_D) - 1)
        d0, d1 = PROF_D[j - 1], PROF_D[j]
        p = self.prof
        v0 = p[cells, k, j - 1].astype(np.float32)
        v1 = p[cells, k, j].astype(np.float32)
        return v0 + (v1 - v0) * (d - d0) / (d1 - d0)

    def transmission(self, cells, bearing, dist, tall=False):
        """Chance the line of sight is not blocked by trees: exp(-wood / lambda).
        Tall landmarks (keep, towers, church spires) show over the trees a bit more."""
        lam = config.CANOPY_LAMBDA_M * (config.CANOPY_TALL_FACTOR if tall else 1.0)
        return np.exp(-self.wood_between(cells, bearing, dist) / lam)

    # ------------------------------------------------------------- ground answers
    # What the speaker can say about the ground, and the chance of each answer per cell.
    ANSWERS = {"cover": ("trees", "open"),
               "surface": ("paved", "unpaved", "none"),
               "water": ("yes", "no")}

    def ground_probs(self, what):
        """{answer: (N,) probability} for one ground question, with people's mistakes."""
        e = config.GROUND_ERROR
        if what == "cover":            # under trees vs in the open (lawn, street, square)
            t = np.clip(self.wood * 1.15, 0, 1)
            P = {"trees": t, "open": 1 - t}
        elif what == "surface":        # tarmac / gravel-or-dirt / no path at all
            sp = np.exp(-0.5 * (self.d_paved / 10.0) ** 2)
            su = np.exp(-0.5 * (self.d_dirt / 10.0) ** 2)
            paved = sp
            unpaved = su * (1 - 0.6 * sp)
            none = np.maximum((1 - sp) * (1 - su), 0.02)
            tot = paved + unpaved + none
            P = {"paved": paved / tot, "unpaved": unpaved / tot, "none": none / tot}
        elif what == "water":          # a lake / pond / stream in sight: trees hide it sooner
            R = 220.0 - 140.0 * self.wood
            s = 1.0 / (1.0 + np.exp(np.clip((self.d_water - R) / (0.25 * R), -50, 50)))
            P = {"yes": s, "no": 1 - s}
        else:
            return None
        k = len(P)
        return {a: (1 - e) * p + e / k for a, p in P.items()}

    def truth(self, cell, what):
        """What a person standing in this cell would most likely answer (simulation)."""
        P = self.ground_probs(what)
        return max(P, key=lambda a: P[a][cell])

    # ------------------------------------------------------------------ queries
    def cell_of(self, x, y):
        return int(np.argmin((self.eng.X - x) ** 2 + (self.eng.Y - y) ** 2))

    def describe(self, cell):
        """Plain numbers for one cell (simulation, checks, the panel)."""
        return {k: round(float(getattr(self, k)[cell]), 2) for k in
                ("wood", "open", "water", "d_path", "d_paved", "d_dirt", "d_edge", "d_water",
                 "d_open", "d_fence")}


_forest = None


def get_forest(eng=None):
    global _forest
    if _forest is None:
        from .localise import get_engine
        _forest = Forest(eng or get_engine())
    return _forest
