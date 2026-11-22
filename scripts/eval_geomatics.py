"""Geomatics: does the 3D line of sight and aiming with the phone improve the fix?

  python -m scripts.eval_geomatics [n_per_area]

Reality is the 3D model (IGN LiDAR HD: buildings, trees, terrain): the simulated speaker
only calls out landmarks whose top is truly in sight, and answers "can you see X?" from
it. Same spots, headings and draws in every row:

  A  before: distance + canopy visibility
  B  + true 3D line of sight (viewshed.py)
  C  + Aim & tap: tilt to each top (+-1.5 deg) and turn between taps (+-2 deg)

Two areas: streets around the chateau, and wooded cells of the Bois (the speaker says
"we're in the woods" and the path surface there, as the app now asks).
Caveat: the 3D model plays reality and is also what B and C use, so B/C are optimistic
where the model is wrong (street furniture, parked trucks, leaves in summer).
"""
import math
import random
import sys
import time
from datetime import datetime, timezone

import numpy as np

from backend import config, questions as Q
from backend.extract import _clean, rules_extract, to_constraints
from backend.forest import get_forest
from backend.landmarks import get_db
from backend.localise import get_engine
from backend.simulate import aim_constraints, observe, truthful_answer

WHEN = datetime(2026, 11, 21, 13, 0, tzinfo=timezone.utc)
CITY = (48.838, 2.425, 48.852, 2.447)


def truth_answer(q, lat, lon, hd, rng):
    eng, db = get_engine(), get_db()
    x, y = db.to_xy(lat, lon)
    cell = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
    if q["kind"] in ("visible_type", "visible_feature"):      # reality: the 3D model
        old = config.VIEWSHED_ENABLED
        config.VIEWSHED_ENABLED = True
        p = eng.visibility(q["type"])[cell] if q["kind"] == "visible_type" else eng.see_feature(q["feature"])[cell]
        config.VIEWSHED_ENABLED = old
        return "Yes, I can see it" if rng.random() < p else "No, I can't see it"
    return truthful_answer(q, lat, lon, hd, WHEN)


def trial(spot, cond, seed, woods):
    eng, db, fo = get_engine(), get_db(), get_forest()
    rng = random.Random(seed)
    lat, lon, hd = spot
    picks = []
    cons, _ = observe(lat, lon, hd, n=3, with_sun=True, when=WHEN, seed=seed, trees=True, picks_out=picks)
    x, y = db.to_xy(lat, lon)
    if woods:
        cell = fo.cell_of(x, y)
        for what in ("cover", "surface"):
            cons.append({"kind": "ground", "what": what, "value": fo.truth(cell, what), "source": "voice"})
    if cond >= 2:
        cons += aim_constraints(lat, lon, picks, rng)
    res = eng.run(cons, when=WHEN)
    asked = []
    for _ in range(config.MAX_QUESTIONS):
        q, _ = Q.choose(cons, asked, res, eng, WHEN)
        if not q:
            break
        asked.append(q)
        text = truth_answer(q, lat, lon, hd, rng)
        if q["kind"] == "describe":
            cons += to_constraints(_clean(rules_extract(text)))
        else:
            c = Q.answer_to_constraint(q, Q.parse_answer(q, text))
            if c:
                cons.append(c)
        res = eng.run(cons, when=WHEN)
    bx, by = db.to_xy(res["lat"], res["lon"])
    err = math.hypot(bx - x, by - y)
    return {"err": err, "in_r": err <= res["radius_m"], "n": len(picks)}


def sees_something(lat, lon, hd):
    picks = []
    observe(lat, lon, hd, n=3, with_sun=False, when=WHEN, seed=123, trees=True, picks_out=picks)
    return bool(picks)


SEEN_ONLY = "--seen" in sys.argv     # only spots where a landmark top is truly in sight


def spots_for(area, n, rng):
    if SEEN_ONLY:
        out = []
        while len(out) < n:
            out += [s for s in _spots(area, n, rng) if sees_something(*s)]
        return out[:n]
    return _spots(area, n, rng)


def _spots(area, n, rng):
    eng, db, fo = get_engine(), get_db(), get_forest()
    out = []
    if area == "woods":
        woods = np.where(fo.wood > 0.6)[0]
        for _ in range(n):
            c = int(rng.choice(woods))
            lat, lon = db.to_latlon(eng.X[c] + rng.uniform(-10, 10), eng.Y[c] + rng.uniform(-10, 10))
            out.append((float(lat), float(lon), rng.uniform(0, 360)))
    else:
        from backend.viewshed import get_viewshed
        vs = get_viewshed()
        while len(out) < n:
            lat, lon = rng.uniform(CITY[0], CITY[2]), rng.uniform(CITY[1], CITY[3])
            x, y = db.to_xy(lat, lon)
            c = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
            if vs.ok and vs.indoor[c]:
                continue                       # standing in the street, not inside a building
            out.append((lat, lon, rng.uniform(0, 360)))
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 40
    get_engine()
    names = ["A before (distance + canopy)", "B + true 3D line of sight", "C + Aim & tap (tilt, turn)"]
    t0 = time.time()
    for area in ("streets", "woods"):
        spots = spots_for(area, n, random.Random(11 if area == "streets" else 7))
        print(f"\n{area}: {n} casualties, same spots / headings / draws in every row")
        print(f"{'':32s} {'median err':>10s} {'<=50 m':>7s} {'<=100 m':>8s} {'<=250 m':>8s} {'truth in radius':>16s}"
              f" {'saw a landmark':>15s} {'saw none':>9s}")
        for k, name in enumerate(names):
            config.VIEWSHED_ENABLED = k >= 1
            get_engine()._cache.clear()
            out = [trial(s, k, 500 + i, area == "woods") for i, s in enumerate(spots)]
            e = np.array([o["err"] for o in out])
            seen = np.array([o["n"] > 0 for o in out])
            med = lambda m: f"{np.median(e[m]):.0f}m" if m.any() else "-"  # noqa: E731
            print(f"{name:32s} {np.median(e):9.0f}m {np.mean(e <= 50) * 100:6.0f}% {np.mean(e <= 100) * 100:7.0f}% "
                  f"{np.mean(e <= 250) * 100:7.0f}% {np.mean([o['in_r'] for o in out]) * 100:15.0f}%"
                  f" {med(seen):>15s} {med(~seen):>9s}")
            if k == 0:
                nb = np.array([o["n"] for o in out])
                print(f"{'':32s} landmarks truly in sight and called out: median {np.median(nb):.0f}, none at {np.mean(nb == 0) * 100:.0f}% of spots")
    config.VIEWSHED_ENABLED = True
    print(f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
