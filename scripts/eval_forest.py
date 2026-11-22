"""How well does the find-me loop work for a casualty inside the woods?

  python -m scripts.eval_forest [n_trials]

Random spots in wooded cells of the Bois de Vincennes (inside the map), random heading.
The simulated speaker sees through the trees with the canopy model (landmarks behind
trees are often not called out, the low sun is often hidden), then answers questions
truthfully. Same spots and draws for every condition:

  A  before: distance-only visibility, no ground questions
  B  + canopy-aware visibility ("can't see the keep" means trees, not distance)
  C  + "we're in the woods, on a dirt track" in the report, and ground questions
  D  + the phone compass for the heading (+-25 deg)

Honest caveat: the speaker is simulated with the same canopy model the localiser
uses, so B-D are optimistic until the model is checked on a walk in the Bois.
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
from backend.simulate import observe, truthful_answer

WHEN = datetime(2026, 11, 21, 13, 0, tzinfo=timezone.utc)


def truth_answer(q, lat, lon, hd, rng):
    """The speaker's answer. Visibility questions use the canopy (reality), even when
    the localiser under test does not."""
    eng, db = get_engine(), get_db()
    x, y = db.to_xy(lat, lon)
    cell = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
    if q["kind"] in ("visible_type", "visible_feature"):
        old = config.CANOPY_ENABLED
        config.CANOPY_ENABLED = True
        if q["kind"] == "visible_type":
            p = eng.visibility(q["type"])[cell]
        else:
            f = db.feature(q["feature"])
            fx, fy = db.to_xy(f["lat"], f["lon"])
            p = eng.see_feature(q["feature"])[cell]
        config.CANOPY_ENABLED = old
        return "Yes, I can see it" if rng.random() < p else "No, I can't see it"
    return truthful_answer(q, lat, lon, hd, WHEN)


def trial(spot, cond, seed):
    eng, db, fo = get_engine(), get_db(), get_forest()
    rng = random.Random(seed)
    lat, lon, hd = spot
    cons, _ = observe(lat, lon, hd, n=3, with_sun=True, when=WHEN, seed=seed, trees=True)
    x, y = db.to_xy(lat, lon)
    cell = fo.cell_of(x, y)
    if cond >= 2:   # "we're in the woods, on a dirt track"
        cons.append({"kind": "ground", "what": "cover", "value": fo.truth(cell, "cover"), "source": "voice"})
        cons.append({"kind": "ground", "what": "surface", "value": fo.truth(cell, "surface"), "source": "voice"})
    if cond >= 3:
        cons.append({"kind": "compass", "deg": (hd + rng.gauss(0, config.SIGMA_COMPASS)) % 360,
                     "sigma": config.SIGMA_COMPASS})
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
    d = np.hypot(eng.X - x, eng.Y - y)
    return {"err": math.hypot(bx - x, by - y), "r": res["radius_m"],
            "m100": float(res["post"][d <= 100].sum()), "m250": float(res["post"][d <= 250].sum()),
            "n_bear": sum(c["kind"] == "bearing" for c in cons), "kinds": [q["kind"] for q in asked]}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    eng, fo = get_engine(), get_forest()
    db = get_db()
    rng = random.Random(7)
    woods = np.where(fo.wood > 0.6)[0]
    spots = []
    for _ in range(n):
        c = int(rng.choice(woods))
        lat, lon = db.to_latlon(eng.X[c] + rng.uniform(-10, 10), eng.Y[c] + rng.uniform(-10, 10))
        spots.append((float(lat), float(lon), rng.uniform(0, 360)))
    names = ["A before (distance-only visibility)", "B + canopy-aware visibility",
             "C + 'in the woods, dirt track' + ground questions", "D + phone compass"]
    t0 = time.time()
    print(f"{n} casualties in wooded cells, same spots / headings / draws in every row")
    print(f"{'':52s} {'median err':>10s} {'<=75 m':>7s} {'<=150 m':>8s} {'mass<=100m':>10s} {'mass<=250m':>10s}")
    for k, name in enumerate(names):
        config.CANOPY_ENABLED = k >= 1
        Q.ENABLE_GROUND_QUESTIONS = k >= 2
        eng._cache.clear()
        out = [trial(s, k, 1000 + i) for i, s in enumerate(spots)]
        e = np.array([o["err"] for o in out])
        print(f"{name:52s} {np.median(e):9.0f}m {np.mean(e <= 75) * 100:6.0f}% {np.mean(e <= 150) * 100:7.0f}% "
              f"{np.mean([o['m100'] for o in out]) * 100:9.1f}% {np.mean([o['m250'] for o in out]) * 100:9.1f}%")
        if k == 0:
            nb = [o["n_bear"] for o in out]
            print(f"{'':52s} landmarks called out: median {np.median(nb):.0f}, none in {np.mean(np.array(nb) == 0) * 100:.0f}% of spots")
        kinds = {}
        for o in out:
            for q in o["kinds"]:
                kinds[q] = kinds.get(q, 0) + 1
        print(f"{'':52s} questions: {kinds}")
    config.CANOPY_ENABLED, Q.ENABLE_GROUND_QUESTIONS = True, True
    print(f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
