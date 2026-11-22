"""True 3D line of sight: from which cells can the top of each landmark be seen?

3D model (2 m), best source first:
  data/twin/lidar.npz   IGN LiDAR HD ground (MNT) + height of what stands on it (MNH):
                        buildings, trees, street trees, spires   (scripts/fetch_lidar.py)
  fallback              ground interpolated from IGN building altitudes, building heights,
                        OSM woods at 12 m
Buildings and terrain block the view; vegetation only partly (exp(-metres / lambda), the
canopy model of forest.py: bare trees in November let some sight through).

For every landmark that has a top (keep, towers, churches, schools, stations...), and every
cell within its visibility radius:  T[landmark, cell] = chance its top part is in sight
from eye height at the cell's most open spot. Also used for elevation angles (the top's
altitude and each cell's eye altitude).

Cached in data/twin/viewshed_cache.npz (built once, ~1 min).
"""
import json
import math
import time

import numpy as np

from . import config

RES = 2.0             # 3D model resolution (m)
STEP = 4.0            # sample the sight line every 4 m
EYE = 1.6             # eye height (m)
NEAR_SKIP = 6.0       # your own spot (you stand next to things, not inside them)
FAR_SKIP = 15.0       # the landmark's own footprint
FALLBACK_CANOPY = 12.0
MODEL_FLOOR = 0.04    # the 3D model can be wrong; glimpses through gaps
NO_SIGHT_TYPES = {"wood", "park", "lake", "main_road", "railway", "bridge", "cemetery", "river"}
VERSION = 2


class Viewshed:
    def __init__(self, eng):
        self.eng = eng
        self.ok = False
        db = eng.db
        s, w, _, _ = config.BBOX
        self.x0, self.y0 = db.to_xy(s, w)
        bpath = config.TWIN_DIR / "buildings.geojson"
        if not bpath.exists():
            print("viewshed disabled: no building footprints")
            return
        lid = config.TWIN_DIR / "lidar.npz"
        self.source = "lidar" if lid.exists() else "buildings"
        self.cands = np.array([i for i in range(len(db.types)) if db.types[i] not in NO_SIGHT_TYPES], int)
        key = np.array([VERSION, len(db.types), len(self.cands), eng.nx, eng.ny,
                        int(lid.exists()), int(config.CANOPY_LAMBDA_M)], np.int64)
        cache = config.TWIN_DIR / "viewshed_cache.npz"
        z = np.load(cache) if cache.exists() else None
        t0 = time.time()
        if z is None or not np.array_equal(z["key"], key):
            print(f"viewshed: 3D line of sight for {len(self.cands)} landmarks ({self.source}, once, ~1 min)...")
            self._build_model(bpath, lid)
            T, top, eye, indoor, tx, ty = self._compute()
            np.savez_compressed(cache, key=key, T=T, top=top, eye=eye, indoor=indoor, tx=tx, ty=ty)
            z = np.load(cache)
        self.T, self.top, self.eye, self.indoor = z["T"], z["top"], z["eye"], z["indoor"]
        self.tx, self.ty = z["tx"], z["ty"]
        self.col = np.full(len(db.types), -1, int)
        self.col[self.cands] = np.arange(len(self.cands))
        self.ok = True
        print(f"viewshed ready in {time.time() - t0:.1f} s ({self.source}, {len(self.cands)} landmarks)")

    # ------------------------------------------------------------------ 3D model
    def _build_model(self, bpath, lid):
        from PIL import Image, ImageDraw
        eng, db = self.eng, self.eng.db
        W, H = int(eng.nx * config.CELL_M / RES), int(eng.ny * config.CELL_M / RES)
        img = Image.new("F", (W, H), 0.0)
        dr = ImageDraw.Draw(img)
        zs = []
        for f in json.loads(bpath.read_text(encoding="utf-8"))["features"]:
            c = np.array(f["geometry"]["coordinates"][0])
            if len(c) < 3:
                continue
            x, y = db.to_xy(c[:, 1], c[:, 0])
            px, py = (x - self.x0) / RES, (y - self.y0) / RES
            dr.polygon(list(zip(px, py)), fill=float(f["properties"].get("h") or 9.0))
            if f["properties"].get("z"):
                zs.append((px.mean(), py.mean(), float(f["properties"]["z"])))
        bh = np.array(img, np.float32)
        self.building = bh > 0
        if lid.exists():
            L = np.load(lid)
            mnt, mnh = self._regrid(L["mnt"], L["bbox"], W, H), self._regrid(L["mnh"], L["bbox"], W, H)
            mnt = np.where(np.isnan(mnt), np.nanmedian(mnt), mnt)
            self.ground = mnt.astype(np.float32)
            self.obj = mnh.astype(np.float32)
        else:
            from scipy.interpolate import griddata
            from .forest import get_forest
            zs = np.array(zs)
            gy, gx = np.mgrid[0:H, 0:W]
            dem = griddata(zs[:, :2], zs[:, 2], (gx, gy), method="linear")
            dem = np.where(np.isnan(dem), griddata(zs[:, :2], zs[:, 2], (gx, gy), method="nearest"), dem)
            fo = get_forest(eng)
            wood = np.zeros((H, W), bool)
            if fo.ok:
                wood = np.array(Image.fromarray(fo.px_wood.astype(np.uint8) * 255).resize((W, H), Image.NEAREST)) > 0
            self.ground = dem.astype(np.float32)
            self.obj = np.maximum(bh, wood * FALLBACK_CANOPY).astype(np.float32)
        self.W, self.H = W, H

    def _regrid(self, a, bbox, W, H):
        """LiDAR grid (its own bbox / size) -> our 2 m grid over config.BBOX (nearest)."""
        s, w, n, e = bbox
        S, Wd, N, E = config.BBOX
        eng = self.eng
        # our pixel centres in metres -> lat/lon -> LiDAR pixel
        xs = self.x0 + (np.arange(W) + 0.5) * RES
        ys = self.y0 + (np.arange(H) + 0.5) * RES
        lat, _ = eng.db.to_latlon(np.full(H, xs[0]), ys)
        _, lon = eng.db.to_latlon(xs, np.full(W, ys[0]))
        r = np.clip(((np.asarray(lat) - s) / (n - s) * a.shape[0]).astype(int), 0, a.shape[0] - 1)
        c = np.clip(((np.asarray(lon) - w) / (e - w) * a.shape[1]).astype(int), 0, a.shape[1] - 1)
        return a[r][:, c]

    # ------------------------------------------------------------------ sight lines
    def _observer_points(self):
        """Per cell: the most open point near the centre (5 m sub-grid), its eye altitude,
        and whether the whole cell is inside buildings."""
        eng = self.eng
        offs = [(0, 0), (5, 0), (-5, 0), (0, 5), (0, -5), (5, 5), (-5, 5), (5, -5), (-5, -5),
                (10, 0), (-10, 0), (0, 10), (0, -10)]
        cx, cy = (eng.X - self.x0) / RES, (eng.Y - self.y0) / RES
        px, py = cx.copy(), cy.copy()
        found = np.zeros(eng.N, bool)
        for dx, dy in offs:
            qx, qy = cx + dx / RES, cy + dy / RES
            ix, iy = np.clip(qx.astype(int), 0, self.W - 1), np.clip(qy.astype(int), 0, self.H - 1)
            free = ~self.building[iy, ix] & ~found
            px[free], py[free] = qx[free], qy[free]
            found |= free
        ix, iy = np.clip(px.astype(int), 0, self.W - 1), np.clip(py.astype(int), 0, self.H - 1)
        return px, py, (self.ground[iy, ix] + EYE).astype(np.float32), ~found

    def _target(self, i):
        """Top of landmark i: highest object pixel within 12 m of its point -> (px, py, altitude, height)."""
        x, y = self.eng.db.x[i], self.eng.db.y[i]
        cx, cy = int((x - self.x0) / RES), int((y - self.y0) / RES)
        r = int(12 / RES)
        a0, a1 = max(0, cy - r), min(self.H, cy + r + 1)
        b0, b1 = max(0, cx - r), min(self.W, cx + r + 1)
        if a0 >= a1 or b0 >= b1:
            return cx, cy, float("nan"), 0.0
        win = self.obj[a0:a1, b0:b1]
        k = np.unravel_index(int(np.argmax(win)), win.shape)
        ty, tx = a0 + k[0], b0 + k[1]
        h = float(win[k])
        return tx, ty, float(self.ground[ty, tx] + h), h

    def _compute(self):
        eng = self.eng
        px, py, eye, indoor = self._observer_points()
        dsm = self.ground + self.obj
        lam = config.CANOPY_LAMBDA_M
        K = len(self.cands)
        T = np.zeros((K, eng.N), np.uint8)
        top = np.full(K, np.nan, np.float32)
        txs, tys = np.zeros(K, np.float32), np.zeros(K, np.float32)
        for k, i in enumerate(self.cands):
            tx, ty, talt, h = self._target(i)
            txs[k], tys[k] = self.x0 + (tx + 0.5) * RES, self.y0 + (ty + 0.5) * RES
            if not np.isfinite(talt):
                continue
            top[k] = talt
            aim = talt - min(6.0, max(1.0, 0.25 * h))         # "see the top part"
            R = config.VIS_RADIUS.get(eng.db.types[i], config.VIS_RADIUS_DEFAULT)
            d = np.hypot(px - tx, py - ty) * RES
            sel = np.where((d < 2.0 * R) & ~indoor)[0]
            for a in range(0, sel.size, 3000):
                j = sel[a:a + 3000]
                dj = d[j]
                n = max(2, int(dj.max() / STEP))
                t = np.linspace(0, 1, n, dtype=np.float32)[None, :]
                sx = px[j, None] + (tx - px[j, None]) * t
                sy = py[j, None] + (ty - py[j, None]) * t
                line = eye[j, None] + (aim - eye[j, None]) * t
                ix, iy = np.clip(sx.astype(np.int32), 0, self.W - 1), np.clip(sy.astype(np.int32), 0, self.H - 1)
                along = t * dj[:, None]
                mid = (along > NEAR_SKIP) & ((1 - t) * dj[:, None] > FAR_SKIP) & (along <= dj[:, None])
                above = (dsm[iy, ix] > line) & mid
                hard = (above & (self.building[iy, ix] | (self.ground[iy, ix] > line))).any(axis=1)
                veg_m = (above & ~self.building[iy, ix]).sum(axis=1) * (dj / n)
                trans = np.where(hard, 0.0, np.exp(-veg_m / lam))
                T[k, j] = np.round(trans * 255).astype(np.uint8)
        return T, top, eye, indoor, txs, tys

    # ------------------------------------------------------------------ queries
    def has(self, idx):
        return self.col[np.asarray(idx)] >= 0

    def sight(self, cells, idx):
        """(n, m) chance the top of landmarks idx is in sight from cells (model floor
        included). NaN where unknown (landmark without a top, or a cell inside buildings)."""
        cells, idx = np.asarray(cells), np.asarray(idx)
        cols = self.col[idx]
        out = np.full((cells.size, idx.size), np.nan, np.float32)
        ok = cols >= 0
        if ok.any():
            out[:, ok] = MODEL_FLOOR + (1 - MODEL_FLOOR) * (self.T[cols[ok]][:, cells].T.astype(np.float32) / 255.0)
        out[self.indoor[cells]] = np.nan
        return out

    def elevation(self, cells, idx):
        """(n, m) elevation angle (deg) of the top of landmarks idx seen from cells."""
        cells, idx = np.asarray(cells), np.asarray(idx)
        cols = self.col[idx]
        out = np.full((cells.size, idx.size), np.nan, np.float32)
        ok = cols >= 0
        if ok.any():
            c = cols[ok]
            dx = self.tx[c][None, :] - self.eng.X[cells][:, None]
            dy = self.ty[c][None, :] - self.eng.Y[cells][:, None]
            d = np.maximum(np.hypot(dx, dy), 5.0)
            dz = self.top[c][None, :] - self.eye[cells][:, None]
            out[:, ok] = np.degrees(np.arctan2(dz, d))
        return out


_vs = None


def get_viewshed(eng=None):
    global _vs
    if _vs is None:
        from .localise import get_engine
        _vs = Viewshed(eng or get_engine())
    return _vs
