"""Approximate scene reconstruction: what does the place around the speaker look like?

Two scenes, drawn the same way on the coordinator page (frontend/scene3d.js):

1. GUESSED, from the report alone (voice + microphone), never from the map:
   - kind of space (room, hall, street, open ground) from what was said and the audio
   - nearest facade from the chirp echo, room size from the reverberation
   - landmarks at their clock directions (distance said, or a typical one)
   - trees / railway / road / water from "we're in a tree line" or sounds heard
   It is deliberately rough: a sketch of the kind of place, not a model of it.
   Things that are only assumed (building heights, street orientation) are marked.

2. REAL, for each likely area the localiser found: the actual buildings (IGN
   footprints + heights), landmarks and lines around that spot, turned so that
   12 o'clock points the way the speaker most likely faces. Each clue gets a
   match score, so the coordinator sees WHY an area fits.

Frame for both: observer at (0, 0), +y = 12 o'clock (ahead), +x = 3 o'clock, metres.
"""
import json
import math
import random

import numpy as np
from scipy.spatial import cKDTree

from . import config
from .landmarks import get_db, spoken

R_OUT = 130.0       # radius of an outdoor scene (m)
R_IN = 14.0         # radius of an indoor scene (m)

# When no distance was said: a typical distance at which people name each landmark.
TYPICAL_DIST = {"keep": 400, "castle": 400, "castle_tower": 300, "church": 250, "mosque": 200,
                "tower": 450, "water_tower": 500, "station": 200, "hospital": 250,
                "townhall": 200, "stadium": 300, "school": 150, "bridge": 150}
# Rough heights for drawing (m). The keep of Vincennes is 52 m.
LANDMARK_H = {"keep": 52, "castle": 25, "castle_tower": 30, "church": 32, "mosque": 25,
              "tower": 45, "water_tower": 35, "station": 10, "hospital": 20, "townhall": 18,
              "stadium": 15, "school": 12, "bridge": 6, "monument": 10}
LINE_TYPES = {"railway": "rail", "main_road": "road", "river": "water", "lake": "water"}
TREE_TYPES = ("wood", "park", "cemetery")
SOUND_LABEL = {"rail": "trains", "traffic": "road traffic", "bells": "church bells",
               "machinery": "machinery", "nature": "birds / nature"}
SETTING_LABEL = {"indoor_small": "indoors, small room", "indoor_large": "indoors, large hall",
                 "outdoor_enclosed": "outdoors, between buildings",
                 "outdoor_open": "outdoors, open ground", "outdoor": "outdoors",
                 "unknown": "surroundings not described yet"}


# ====================================================================== helpers
def _polar(beta, r):
    b = math.radians(beta)
    return [round(r * math.sin(b), 1), round(r * math.cos(b), 1)]


def _rect(cx, cy, w, d, ang=0.0):
    """Rectangle centred on (cx, cy), w along x, d along y, rotated by ang (deg)."""
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for ux, uy in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        pts.append([round(cx + ux * ca - uy * sa, 1), round(cy + ux * sa + uy * ca, 1)])
    return pts


def _to_view(dx, dy, heading):
    """World offsets (east, north) -> observer frame (right, ahead)."""
    t = math.radians(heading)
    c, s = math.cos(t), math.sin(t)
    return dx * c - dy * s, dx * s + dy * c


def _clock(beta):
    k = (beta % 360) / 30.0
    k = 12 if round(k * 2) / 2 in (0, 12) else round(k * 2) / 2
    return f"{k:g} o'clock"


def _clip_circle(pts, r, n=48):
    """Clip a polygon to a circle of radius r (Sutherland-Hodgman on an n-gon),
    so a huge footprint (the castle walls) stays inside the scene."""
    if max(math.hypot(x, y) for x, y in pts) <= r:
        return pts
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        ex0, ey0 = r * math.cos(a0), r * math.sin(a0)
        ex1, ey1 = r * math.cos(a1), r * math.sin(a1)
        inside = lambda p: (ex1 - ex0) * (p[1] - ey0) - (ey1 - ey0) * (p[0] - ex0) >= 0   # noqa: E731

        def cut(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]
            den = (ex1 - ex0) * dy - (ey1 - ey0) * dx
            t = ((ex1 - ex0) * (ey0 - p[1]) - (ey1 - ey0) * (ex0 - p[0])) / den if den else 0.0
            return [p[0] + t * dx, p[1] + t * dy]
        out = []
        for i, q in enumerate(pts):
            p = pts[i - 1]
            if inside(q):
                if not inside(p):
                    out.append(cut(p, q))
                out.append(q)
            elif inside(p):
                out.append(cut(p, q))
        pts = out
        if len(pts) < 3:
            return []
    return pts


def _lognorm(x, med, s):
    return math.exp(-0.5 * (math.log(max(x, 0.5) / med) / s) ** 2)


# ====================================================================== buildings
class Buildings:
    """IGN footprints in local metres, with a KD-tree on centroids."""

    def __init__(self):
        db = get_db()
        path = config.TWIN_DIR / "buildings.geojson"
        if not path.exists():
            path = config.TWIN_DIR / "buildings_osm.geojson"
        feats = json.loads(path.read_text(encoding="utf-8"))["features"]
        self.polys, self.h, cx, cy = [], [], [], []
        for f in feats:
            ring = np.array(f["geometry"]["coordinates"][0], float)
            if len(ring) < 4:
                continue
            if len(ring) > 25:                       # thin out detailed outlines
                ring = ring[np.linspace(0, len(ring) - 1, 25).astype(int)]
            x, y = db.to_xy(ring[:, 1], ring[:, 0])
            self.polys.append(np.c_[x, y])
            h = (f.get("properties") or {}).get("h")
            self.h.append(float(h) if h else 9.0)
            cx.append(x.mean())
            cy.append(y.mean())
        self.tree = cKDTree(np.c_[cx, cy])
        self.median_h = float(np.median(self.h)) if self.h else 12.0

    def around(self, x, y, heading, radius, limit=140):
        idx = self.tree.query_ball_point([x, y], radius * 2.5)   # big footprints reach in from afar
        idx.sort(key=lambda i: (self.tree.data[i][0] - x) ** 2 + (self.tree.data[i][1] - y) ** 2)
        out = []
        for i in idx[:limit]:
            p = self.polys[i]
            vx, vy = _to_view(p[:, 0] - x, p[:, 1] - y, heading)
            pts = _clip_circle(list(zip(vx.tolist(), vy.tolist())), radius)
            if len(pts) >= 3:
                out.append({"pts": [[round(a, 1), round(b, 1)] for a, b in pts], "h": round(self.h[i], 1)})
        return out


_bld = None


def get_buildings():
    global _bld
    if _bld is None:
        try:
            _bld = Buildings()
        except FileNotFoundError:
            _bld = False
    return _bld or None


# ====================================================================== evidence
def _setting_from(rep):
    """Combine every 'kind of space' clue into probabilities (or None)."""
    p = np.ones(len(config.SETTINGS))
    n = 0
    for c in rep["constraints"]:
        if c["kind"] == "setting":
            p *= np.array([c["p"].get(s, 0.0) for s in config.SETTINGS]) + 0.03
            n += 1
    if not n:
        return None
    p /= p.sum()
    return dict(zip(config.SETTINGS, p.round(3).tolist()))


def _latest_space(rep):
    for a in reversed(rep.get("acoustic") or []):
        sp = a.get("space") or {}
        if sp:
            return sp
    return {}


def estimate(rep, sun_elev=None):
    """The guessed scene, from the report only."""
    cons = rep["constraints"]
    rng = random.Random(rep["id"])
    bld = get_buildings()
    typical_h = bld.median_h if bld else 12.0
    notes = []

    # --- kind of space
    p = _setting_from(rep)
    sees = any(c["kind"] == "bearing" and not c.get("heard") for c in cons)
    has_sun = any(c["kind"] == "sun" for c in cons)
    if p:
        best = max(p, key=p.get)
        if p["outdoor_enclosed"] + p["outdoor_open"] > 0.7 and abs(p["outdoor_enclosed"] - p["outdoor_open"]) < 0.25:
            best = "outdoor"
    elif sees or has_sun:
        best = "outdoor"
        p = {"indoor_small": 0.0, "indoor_large": 0.0, "outdoor_enclosed": 0.5, "outdoor_open": 0.5}
        notes.append("sees landmarks or the sun, so outdoors")
    else:
        best = "unknown"

    reflector = next((c["distance_m"] for c in reversed(cons) if c["kind"] == "reflector"), None)
    space = _latest_space(rep)
    room = space.get("room_size_m")

    scene = {"radius": R_OUT, "buildings": [], "rooms": [], "trees": [], "strips": [],
             "landmarks": [], "sounds": [], "sun": None, "said": [],
             "setting": {"best": best, "label": SETTING_LABEL[best], "p": p},
             "facade_m": reflector, "notes": notes, "guess": True}

    # --- the space itself
    def block_row(x_face, side, length=R_OUT):
        """A row of facades along the y axis, front face at x = x_face."""
        y = -length
        while y < length:
            L = rng.uniform(12, 30)
            if rng.random() < 0.12:                  # a side street
                y += rng.uniform(10, 16)
                continue
            d = rng.uniform(12, 18)
            cx = x_face + side * d / 2
            scene["buildings"].append({"pts": _rect(cx, y + L / 2, d, L - 1.0),
                                       "h": round(typical_h * rng.uniform(0.7, 1.3), 1),
                                       "guess": True})
            y += L

    if best == "outdoor_enclosed":
        f = reflector or 7.0
        width = min(max(3 * f, 12.0), 30.0)
        block_row(-f, -1)
        block_row(width - f, 1)
        notes.append(f"nearest facade ~{f:.0f} m" + (" (chirp echo)" if reflector else " (typical)"))
        notes.append(f"street ~{width:.0f} m wide, orientation unknown (drawn ahead)")
    elif best == "outdoor":
        f = reflector or 25.0
        block_row(-f, -1)
        notes.append("buildings on one side (side unknown), open on the other")
    elif best == "outdoor_open":
        for _ in range(5):
            b, r = rng.uniform(0, 360), rng.uniform(70, 120)
            x, y = _polar(b, r)
            scene["buildings"].append({"pts": _rect(x, y, rng.uniform(12, 25), rng.uniform(12, 25), b),
                                       "h": round(typical_h * rng.uniform(0.6, 1.1), 1), "guess": True})
        notes.append("open ground, no facade within ~40 m")
    elif best in ("indoor_small", "indoor_large"):
        scene["radius"] = R_IN if best == "indoor_small" else 30.0
        if best == "indoor_small":
            w = sum(room) / 2 if room else 4.5
            scene["rooms"].append({"pts": _rect(0, 0, w, w * 1.2), "h": 2.8})
            scene["buildings"].append({"pts": _rect(1.5, 2, w + 8, w * 1.2 + 6), "h": round(typical_h, 1),
                                       "guess": True, "shell": True})
            notes.append(f"room ~{w:.0f} m across" + (" (from reverberation)" if room else " (typical)"))
        else:
            w = max(sum(room) / 2, 15.0) if room else 20.0
            scene["rooms"].append({"pts": _rect(0, 0, w, w * 1.4), "h": 9.0})
            notes.append(f"large hall ~{w:.0f} m across" + (" (from reverberation)" if room else ""))
    if scene["buildings"] and best != "indoor_small":
        notes.append(f"building heights ~{typical_h:.0f} m (area typical, assumed)")

    # --- landmarks seen (or heard) at clock directions
    for c in cons:
        if c["kind"] != "bearing":
            continue
        d_said = c.get("distance_m")
        d = d_said or TYPICAL_DIST.get(c["type"], 250)
        scene["landmarks"].append({
            "type": c["type"], "label": c.get("name") or spoken(c["type"]),
            "beta": c["beta"], "sigma": c["sigma"], "dist": d, "dist_said": bool(d_said),
            "h": LANDMARK_H.get(c["type"], 15), "heard": bool(c.get("heard")),
            "text": f"{_clock(c['beta'])}, " + (f"~{d:.0f} m (said)" if d_said else "distance not said"),
        })

    # --- "we're in a tree line", "next to the railway"
    for c in cons:
        if c["kind"] != "here":
            continue
        t = c["type"]
        if t in TREE_TYPES:
            for _ in range(40):
                b = rng.uniform(-100, 100) if best.startswith("outdoor") else rng.uniform(0, 360)
                scene["trees"].append(_polar(b, rng.uniform(6, 45)))
            notes.append(f"in or at the edge of a {spoken(t)}")
        elif t in LINE_TYPES:
            scene["strips"].append({"kind": LINE_TYPES[t], "pts": [[-R_OUT, -20], [R_OUT, -20]],
                                    "w": 14 if t != "railway" else 8, "guess": True})
            notes.append(f"next to a {spoken(t)} (direction unknown)")

    # --- sounds
    for c in cons:
        if c["kind"] != "hear":
            continue
        heard = c.get("q", 1.0) >= 0.5
        scene["sounds"].append({"cls": c["cls"], "label": SOUND_LABEL.get(c["cls"], c["cls"]),
                                "heard": heard, "source": c.get("source")})
        if heard and c["cls"] == "nature" and not scene["trees"] and best.startswith("outdoor"):
            for _ in range(18):
                scene["trees"].append(_polar(rng.uniform(0, 360), rng.uniform(25, 90)))

    sun = next((c for c in cons if c["kind"] == "sun"), None)
    if sun and (sun_elev is None or sun_elev > 2):
        scene["sun"] = {"beta": sun["clock"] * 30.0 % 360, "elev": round(sun_elev or 25.0, 1)}

    if best == "unknown" and not scene["landmarks"]:
        notes.append("nothing described yet: ask what they see, or press Listen")
    return scene


# ====================================================================== real
def real(rep, blob, heading, est, eng):
    """The actual surroundings of one candidate area + how well each clue fits."""
    db = get_db()
    x, y = db.to_xy(blob["peak_lat"], blob["peak_lon"])
    x, y = float(x), float(y)
    R = est["radius"] if est["radius"] > R_IN else 40.0
    bld = get_buildings()
    scene = {"radius": R, "buildings": bld.around(x, y, heading, R) if bld else [],
             "rooms": [], "trees": [], "strips": [], "landmarks": [], "sounds": [],
             "sun": est["sun"], "said": [], "notes": [], "guess": False}
    checks = []

    # Lines and trees from the landmark cache (sampled points).
    near = np.where(np.hypot(db.x - x, db.y - y) < R * 1.1)[0]
    for i in near:
        t = db.types[i]
        vx, vy = _to_view(db.x[i] - x, db.y[i] - y, heading)
        if t in TREE_TYPES and len(scene["trees"]) < 60:
            scene["trees"].append([round(vx, 1), round(vy, 1)])
        elif t in LINE_TYPES:
            scene["strips"].append({"kind": LINE_TYPES[t], "pts": [[round(vx, 1), round(vy, 1)]],
                                    "w": 8, "dots": True})

    # What the twin says about this exact spot.
    here = None
    try:
        from .soundscape import get_soundscape
        sc = get_soundscape(eng)
        if sc.ok:
            here = sc.at(blob["peak_lat"], blob["peak_lon"])
    except Exception as e:      # the scene is a view: never fail the request for it
        print("scene: soundscape unavailable:", e)
    if here:
        Ps = here["P_setting"]
        best_here = max(Ps, key=Ps.get)
        scene["setting"] = {"best": best_here, "label": SETTING_LABEL[best_here], "p": Ps}
        scene["facade_m"] = round(here["facade_m"], 1)
        scene["notes"].append(("inside a building" if here["inside"] else
                               f"nearest facade {here['facade_m']:.0f} m"))
        p = est["setting"]["p"]
        if p:
            s = sum(p[k] * Ps[k] for k in p) / max(max(Ps.values()), 1e-6)
            checks.append({"label": "kind of space", "score": round(min(s, 1.0), 2),
                           "text": f"guessed {est['setting']['label']}, here {SETTING_LABEL[best_here]}"})
        if est.get("facade_m"):
            s = 0.3 if here["inside"] else _lognorm(max(here["facade_m"], 1.5), est["facade_m"], 0.35)
            checks.append({"label": "echo distance", "score": round(s, 2),
                           "text": f"echo {est['facade_m']:.0f} m, facade here {here['facade_m']:.0f} m"})
        for snd in est["sounds"]:
            ex = here["exposure"].get(snd["cls"])
            if ex is None or snd["cls"] not in config.HEAR_MODEL:
                continue
            # Same hearing model as the localiser: P(heard) rises from `far` to `near`
            # with exposure. Score 1 = the best any place could explain this clue.
            src = "voice" if snd["source"] == "voice" else "audio"
            near_p, far_p = config.HEAR_MODEL[snd["cls"]][src]
            ph = float(sc.p_heard(snd["cls"], src)[here["cell"]])
            s = ph / max(near_p, far_p) if snd["heard"] else (1 - ph) / max(1 - near_p, 1 - far_p)
            checks.append({"label": snd["label"], "score": round(min(s, 1.0), 2), "w": 0.5,
                           "text": ("heard" if snd["heard"] else "not heard") +
                           f", {snd['label']} source exposure here {ex:.0%}"})
    else:
        scene["setting"] = {"best": "unknown", "label": "no building data", "p": None}

    # Landmarks: which real one best explains each spoken direction?
    for c in rep["constraints"]:
        if c["kind"] == "bearing":
            idx = db.candidates(c["type"], c.get("name"))
            scene["said"].append({"beta": c["beta"], "sigma": c["sigma"], "label": spoken(c["type"])})
            if len(idx) == 0:
                checks.append({"label": spoken(c["type"]), "score": 0.0, "w": 2.0,
                               "text": "none in the area data"})
                continue
            dx, dy = db.x[idx] - x, db.y[idx] - y
            dist = np.hypot(dx, dy)
            rel = (np.degrees(np.arctan2(dx, dy)) - heading) % 360
            err = (rel - c["beta"] + 180) % 360 - 180
            vis = config.VIS_RADIUS.get(c["type"], config.VIS_RADIUS_DEFAULT)
            fit = np.exp(-0.5 * (err / c["sigma"]) ** 2) * (dist < vis * 1.2)
            if c.get("distance_m"):
                fit = fit * np.exp(-0.5 * (np.log(np.maximum(dist, 5) / c["distance_m"]) / config.SIGMA_DIST_LOG) ** 2)
            j = int(np.argmax(fit))
            f = db.feature(idx[j])
            scene["landmarks"].append({
                "type": c["type"], "label": f.get("name") or spoken(c["type"]),
                "beta": float(rel[j]), "dist": float(dist[j]), "dist_said": True,
                "h": LANDMARK_H.get(c["type"], 15),
                "text": f"{_clock(rel[j])}, {dist[j]:.0f} m"})
            checks.append({"label": spoken(c["type"]), "score": round(float(fit[j]), 2), "w": 2.0,
                           "text": f"said {_clock(c['beta'])}, here {_clock(rel[j])} "
                                   f"({abs(err[j]):.0f}° off), {dist[j]:.0f} m"
                                   + (f" (said {c['distance_m']:.0f})" if c.get("distance_m") else "")})
        elif c["kind"] in ("here", "visible"):
            d, _ = eng._nearest(c["type"], c.get("name"))
            if d is None:
                continue
            i = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
            dd = float(d[i])
            if c["kind"] == "here":
                s = 1.0 if dd < config.HERE_RADIUS else max(0.0, 1 - (dd - config.HERE_RADIUS) / 200)
                txt = f"nearest {spoken(c['type'])} {dd:.0f} m"
            else:
                R_v = c.get("radius") or config.VIS_RADIUS.get(c["type"], config.VIS_RADIUS_DEFAULT)
                inside = dd < R_v
                s = 1.0 if inside == c.get("value", True) else 0.15
                txt = f"{'sees' if c.get('value', True) else 'does not see'} {spoken(c['type'])}, nearest {dd:.0f} m"
            checks.append({"label": spoken(c["type"]), "score": round(s, 2), "text": txt})
    return scene, checks


# ====================================================================== entry
def build(rep, res, eng, when=None):
    """Guessed scene + real scenes for up to 3 candidate areas."""
    sun_elev = None
    try:
        sun_elev = float(eng.sun(when)[1])
    except Exception:
        pass
    est = estimate(rep, sun_elev)
    cands = []
    for k, b in enumerate((res or {}).get("blobs", [])[:3]):
        h = b.get("heading_deg", (res or {}).get("heading_deg") or 0.0)
        sc, checks = real(rep, b, h, est, eng)
        # Landmarks count double, sounds half: directions are the strongest clue.
        w = [c.get("w", 1.0) for c in checks]
        fit = float(np.average([c["score"] for c in checks], weights=w)) if checks else None
        cands.append({"label": "ABC"[k], "mass": round(b["mass"], 3), "lat": b["peak_lat"],
                      "lon": b["peak_lon"], "heading": h, "radius_m": round(b["r80"]),
                      "fit": round(fit, 2) if fit is not None else None,
                      "scene": sc, "checks": checks})
    return {"report_id": rep["id"], "estimate": est, "candidates": cands}
