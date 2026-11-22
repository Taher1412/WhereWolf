"""Walking routes on the real streets and paths, away from danger zones.

Graph: every OSM way you can walk on, already cached by the fetch scripts:
  - data/twin/lines.geojson   big roads (primary..tertiary; motorways and tunnels left out)
  - data/twin/forest.geojson  small ways (residential, footway, path, track, ...)
Points that share an OSM node have the same coordinates, so ways join there. Points
closer than SNAP_M are joined too, to fix small gaps in the drawing.

Cost of an edge = its length x (1 + risk), where risk adds, for every active danger zone
on the map, weight(type) x confidence x freshness x how much the edge is inside the zone.
A plain shortest path (Dijkstra) on that cost is the best route for this risk model.
See reports/Route planning and reinforcement learning.md for why we don't use RL here.
"""
import json
import math
import time

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

from . import config
from .landmarks import get_db

SNAP_M = 4.0            # join points closer than this (gaps in the OSM drawing)
SPLIT_M = 40.0          # cut long edges so the danger check along them is fine enough
SIMPLIFY_M = 12.0       # route wiggles smaller than this are not turns
CUE_TYPES = ("keep", "castle", "church", "station", "townhall", "water_tower", "tower",
             "hospital", "school")


class Router:
    def __init__(self):
        self.db = get_db()
        ways = []      # list of (xy array, name)
        try:
            for f in json.load(open(config.DATA_DIR / "twin" / "lines.geojson", encoding="utf-8"))["features"]:
                p = f["properties"]
                if p.get("kind") == "road" and p.get("cls", 4) >= 2 and not p.get("tunnel"):
                    ways.append((f["geometry"]["coordinates"], None))
        except FileNotFoundError:
            pass
        try:
            for f in json.load(open(config.DATA_DIR / "twin" / "forest.geojson", encoding="utf-8"))["features"]:
                p = f["properties"]
                if p.get("kind") == "path" and f["geometry"]["type"] == "LineString":
                    ways.append((f["geometry"]["coordinates"], p.get("name")))
        except FileNotFoundError:
            pass
        self.ok = bool(ways)
        if not self.ok:
            print("route: no walkable ways found (run scripts/fetch_twin.py and scripts/fetch_forest.py)")
            return

        # Nodes: one per distinct point (rounded to 0.5 m), long edges cut in pieces.
        index, xs, ys, edges, names = {}, [], [], [], []

        def node(x, y):
            k = (round(x * 2), round(y * 2))
            if k not in index:
                index[k] = len(xs)
                xs.append(x)
                ys.append(y)
            return index[k]

        for coords, name in ways:
            c = np.asarray(coords, float)
            x, y = self.db.to_xy(c[:, 1], c[:, 0])
            prev = node(x[0], y[0])
            for i in range(1, len(x)):
                seg = math.hypot(x[i] - x[i - 1], y[i] - y[i - 1])
                n = max(1, int(seg // SPLIT_M) + 1)
                for j in range(1, n + 1):
                    t = j / n
                    cur = node(x[i - 1] + t * (x[i] - x[i - 1]), y[i - 1] + t * (y[i] - y[i - 1]))
                    if cur != prev:
                        edges.append((prev, cur))
                        names.append(name)
                    prev = cur
        self.x, self.y = np.array(xs), np.array(ys)
        tree = cKDTree(np.c_[self.x, self.y])
        for a, b in tree.query_pairs(SNAP_M):
            edges.append((a, b))
            names.append(None)
        e = np.array(edges)
        self.ea, self.eb = e[:, 0], e[:, 1]
        self.names = names
        self.length = np.hypot(self.x[self.ea] - self.x[self.eb], self.y[self.ea] - self.y[self.eb])
        self.length = np.maximum(self.length, 0.1)
        self.mx = (self.x[self.ea] + self.x[self.eb]) / 2     # edge midpoints, for the danger check
        self.my = (self.y[self.ea] + self.y[self.eb]) / 2
        self.etree = cKDTree(np.c_[self.mx, self.my])
        n = len(self.x)
        # Keep only the biggest connected piece of the network for snapping.
        g = csr_matrix((np.ones(len(e)), (self.ea, self.eb)), shape=(n, n))
        _, lab = connected_components(g, directed=False)
        main = np.bincount(lab).argmax()
        self.main = np.where(lab == main)[0]
        self.tree = cKDTree(np.c_[self.x[self.main], self.y[self.main]])
        self._edge_name = {}
        for i, (a, b) in enumerate(edges):
            if names[i]:
                self._edge_name[(a, b)] = self._edge_name[(b, a)] = names[i]
        lm = [i for i, f in enumerate(self.db.feats) if f["type"] in CUE_TYPES and f.get("name")]
        self.cue_idx = np.array(lm, int)
        self._cache = {}
        print(f"route: {n} nodes, {len(e)} edges, main network {len(self.main)} nodes")

    # ------------------------------------------------------------ risk
    def edge_risk(self, zones, now_ms=None):
        """Per edge: the risk factor, and per danger type how much each edge is inside a zone."""
        from .danger import _inside
        now_ms = now_ms or int(time.time() * 1000)
        risk = np.zeros(len(self.length))
        inside = {}
        for z in zones:
            if not z.get("placed"):
                continue        # the reporter's own position is too vague to draw it
            fade = max(0.0, 1 - (now_ms - z["ms"]) / z["ttl_ms"])
            if fade <= 0:
                continue
            x0, y0 = self.db.to_xy(z["lat"], z["lon"])
            m = _inside(z, self.mx, self.my, float(x0), float(y0))
            w = config.ROUTE_RISK.get(z["type"], 10.0) * float(z.get("conf", 0.9)) * fade
            risk += w * m
            inside[z["type"]] = np.maximum(inside.get(z["type"], 0), m)
        return risk, inside

    def _matrix(self, weight):
        n = len(self.x)
        return csr_matrix((np.r_[weight, weight], (np.r_[self.ea, self.eb], np.r_[self.eb, self.ea])),
                          shape=(n, n))

    def snap(self, lat, lon):
        x, y = self.db.to_xy(lat, lon)
        d, i = self.tree.query([float(x), float(y)])
        return int(self.main[i]), float(d)

    # ------------------------------------------------------------ route
    def route(self, a, b, zones=(), now_ms=None):
        """Best walking route from a=(lat, lon) to b=(lat, lon) given the danger zones.
        Returns None when there is no network, else a dict with the path and what it avoids."""
        if not self.ok:
            return None
        ia, da = self.snap(*a)
        ib, db_ = self.snap(*b)
        risk, inside = self.edge_risk(zones, now_ms)
        key = (ia, ib, hash(risk.round(2).tobytes()))
        if key in self._cache:
            return self._cache[key]
        safe = self._path(self._matrix(self.length * (1 + risk)), ia, ib)
        short = self._path(self._matrix(self.length), ia, ib)
        if safe is None:
            return None
        out = self._describe(safe, inside, a, b, da, db_)
        if short is not None and short != safe:
            base = self._describe(short, inside, a, b, da, db_)
            out["shortest_m"] = base["length_m"]
            out["detour_m"] = round(out["length_m"] - base["length_m"])
            out["avoided"] = {t: round(base["exposure"].get(t, 0) - out["exposure"].get(t, 0))
                              for t in base["exposure"] if base["exposure"].get(t, 0) - out["exposure"].get(t, 0) > 20}
        else:
            out.update(shortest_m=out["length_m"], detour_m=0, avoided={})
        if len(self._cache) > 200:
            self._cache.clear()
        self._cache[key] = out
        return out

    def _path(self, M, ia, ib):
        dist, pred = dijkstra(M, directed=False, indices=ia, return_predecessors=True)
        if not np.isfinite(dist[ib]):
            return None
        path, cur = [ib], ib
        while cur != ia:
            cur = int(pred[cur])
            path.append(cur)
        return path[::-1]

    def _describe(self, path, inside, a, b, da, db_):
        px, py = self.x[path], self.y[path]
        ax, ay = self.db.to_xy(*a)
        bx, by = self.db.to_xy(*b)
        # Walk from the real start to the network and from the network to the real end.
        px = np.r_[float(ax), px, float(bx)]
        py = np.r_[float(ay), py, float(by)]
        seg = np.hypot(np.diff(px), np.diff(py))
        cum = np.r_[0, np.cumsum(seg)]
        # Metres of the route inside each danger type (membership >= 0.5 on the edge).
        exposure = {}
        if inside:
            _, ei = self.etree.query(np.c_[(px[1:] + px[:-1]) / 2, (py[1:] + py[:-1]) / 2])
            for t, m in inside.items():
                exposure[t] = float(seg[m[ei] >= 0.5].sum())
        lat, lon = self.db.to_latlon(px, py)
        names = [None] + [self._edge_name.get((path[i], path[i + 1])) for i in range(len(path) - 1)] + [None]
        return {"lat": lat.tolist(), "lon": lon.tolist(), "x": px.tolist(), "y": py.tolist(),
                "cum": cum.tolist(), "names": names, "length_m": round(float(cum[-1])),
                "off_network_m": round(da + db_), "exposure": {t: round(v) for t, v in exposure.items() if v > 0}}

    # ------------------------------------------------------------ legs
    def legs(self, r):
        """Cut the route into legs at the real turns: [{s0, s1, length_m, bearing, turn, name, cue}]."""
        x, y, cum = np.array(r["x"]), np.array(r["y"]), np.array(r["cum"])
        keep = _simplify(x, y, SIMPLIFY_M)
        legs = []
        for i0, i1 in zip(keep[:-1], keep[1:]):
            L = cum[i1] - cum[i0]
            if L < 1:
                continue
            brg = math.degrees(math.atan2(x[i1] - x[i0], y[i1] - y[i0])) % 360
            nm = [n for n in r["names"][i0:i1 + 1] if n]
            legs.append({"i0": int(i0), "i1": int(i1), "s0": float(cum[i0]), "s1": float(cum[i1]),
                         "length_m": float(L), "bearing": brg,
                         "name": max(set(nm), key=nm.count) if nm else None})
        # Merge nearly straight continuations and very short legs.
        out = []
        for lg in legs:
            if out:
                turn = _wrap(lg["bearing"] - out[-1]["bearing"])
                same = abs(turn) < 25 and (not lg["name"] or not out[-1]["name"] or lg["name"] == out[-1]["name"])
                if same or lg["length_m"] < 15:
                    p = out[-1]
                    w = p["length_m"] / (p["length_m"] + lg["length_m"])
                    if same:
                        p["bearing"] = (p["bearing"] + (1 - w) * turn) % 360
                    p.update(i1=lg["i1"], s1=lg["s1"], length_m=p["length_m"] + lg["length_m"],
                             name=p["name"] or lg["name"])
                    continue
            out.append(dict(lg))
        for k, lg in enumerate(out):
            lg["turn"] = None if k == 0 else _wrap(lg["bearing"] - out[k - 1]["bearing"])
            lg["cue"] = self.cue(x[lg["i1"]], y[lg["i1"]], lg["bearing"])
        return out

    def cue(self, x, y, heading, max_m=150.0):
        """A named landmark near a point, and on which side of the walker it is."""
        if not len(self.cue_idx):
            return None
        dx, dy = self.db.x[self.cue_idx] - x, self.db.y[self.cue_idx] - y
        d = np.hypot(dx, dy)
        i = int(np.argmin(d))
        if d[i] > max_m:
            return None
        rel = _wrap(math.degrees(math.atan2(dx[i], dy[i])) - heading)
        side = "ahead" if abs(rel) < 30 else ("right" if 0 < rel < 150 else "left" if -150 < rel < 0 else None)
        if side is None:
            return None
        f = self.db.feats[int(self.cue_idx[i])]
        return {"name": f["name"], "type": f["type"], "side": side, "dist_m": round(float(d[i])), "idx": i}

    def cues(self):
        """The named landmarks used in spoken legs, in index order (the phone keeps a copy)."""
        return [{"i": k, "name": self.db.feats[int(j)]["name"], "type": self.db.feats[int(j)]["type"],
                 "lat": self.db.feats[int(j)]["lat"], "lon": self.db.feats[int(j)]["lon"]}
                for k, j in enumerate(self.cue_idx)]


def point_at(r, s):
    """(lat, lon, bearing) at s metres along the route."""
    cum = np.array(r["cum"])
    s = float(np.clip(s, 0, cum[-1]))
    i = int(np.clip(np.searchsorted(cum, s) - 1, 0, len(cum) - 2))
    t = 0 if cum[i + 1] == cum[i] else (s - cum[i]) / (cum[i + 1] - cum[i])
    lat = r["lat"][i] + t * (r["lat"][i + 1] - r["lat"][i])
    lon = r["lon"][i] + t * (r["lon"][i + 1] - r["lon"][i])
    brg = math.degrees(math.atan2(r["x"][i + 1] - r["x"][i], r["y"][i + 1] - r["y"][i])) % 360
    return lat, lon, brg


def _wrap(a):
    return (a + 180) % 360 - 180


def _simplify(x, y, tol):
    """Douglas-Peucker: indices of the points that keep the shape within tol metres."""
    keep = {0, len(x) - 1}
    stack = [(0, len(x) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay, bx, by = x[i], y[i], x[j], y[j]
        L = math.hypot(bx - ax, by - ay) or 1e-9
        d = np.abs((bx - ax) * (ay - y[i + 1:j]) - (ax - x[i + 1:j]) * (by - ay)) / L
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep.add(m)
            stack += [(i, m), (m, j)]
    return sorted(keep)


_router = None


def get_router():
    global _router
    if _router is None:
        _router = Router()
    return _router
