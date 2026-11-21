"""Measure the whole find-me loop on random synthetic soldiers.

  python -m scripts.eval_loop [n_trials]          landmarks + all questions
  python -m scripts.eval_loop 30 --compare       A/B/C on the same soldiers:
      A landmarks only, B + space/sound questions, C + a simulated Listen clip
      (C is drawn from our own sound model: it tests the matching, not the mic)

For each trial: random spot near the château, random heading, the simulator
describes 2-3 landmarks (+ sun), then answers our questions truthfully.
Prints the median error and how often the truth is in the main blob.
"""
import math
import random
import sys
import time
from datetime import datetime, timezone

import numpy as np

from backend import config, questions as Q
from backend.landmarks import get_db
from backend.localise import get_engine
from backend.simulate import observe, truthful_answer
from backend.extract import rules_extract, _clean

WHEN = datetime(2026, 11, 21, 13, 0, tzinfo=timezone.utc)   # early afternoon
AREA = (48.838, 2.425, 48.852, 2.447)                          # around the château


def trial(rng, with_sun=True, n_obs=3, listen=False):
    eng, db = get_engine(), get_db()
    lat = rng.uniform(AREA[0], AREA[2])
    lon = rng.uniform(AREA[1], AREA[3])
    hd = rng.uniform(0, 360)
    cons, sentence = observe(lat, lon, hd, n=n_obs, with_sun=with_sun, when=WHEN,
                             seed=rng.randint(0, 10**6))
    if len([c for c in cons if c["kind"] == "bearing"]) < 2:
        return None
    if listen:
        from backend.acoustic import to_constraints as audio_cons
        from backend.simulate import simulate_audio
        from backend.state import merge_acoustic
        cons = merge_acoustic(cons, audio_cons(simulate_audio(lat, lon, rng)))
    res = eng.run(cons, when=WHEN)
    r0 = res["radius_m"]
    asked = []
    for _ in range(config.MAX_QUESTIONS):
        q, _ = Q.choose(cons, asked, res, eng, WHEN)
        if not q:
            break
        asked.append(q)
        text = truthful_answer(q, lat, lon, hd, WHEN)
        val = Q.parse_answer(q, text)
        c = Q.answer_to_constraint(q, val)
        if c:
            cons.append(c)
        res = eng.run(cons, when=WHEN)
    x, y = db.to_xy(lat, lon)
    bx, by = db.to_xy(res["lat"], res["lon"])
    err = math.hypot(bx - x, by - y)
    b0 = res["blobs"][0]
    px, py = db.to_xy(b0["peak_lat"], b0["peak_lon"])
    return {"err": err, "peak_err": math.hypot(px - x, py - y), "r0": r0, "r": res["radius_m"], "mass": res["main_mass"],
            "inside": err <= max(b0["r2"], 50), "in_r": err <= res["radius_m"], "n_q": len(asked),
            "kinds": [q["kind"] for q in asked]}


def run(n, listen=False):
    rng = random.Random(42)
    out = []
    while len(out) < n:
        state = rng.getstate()
        r = trial(rng, listen=listen)
        if r:
            out.append(r)
        # same soldier positions in every mode: the listen draw must not shift the sequence
        rng.setstate(state)
        for _ in range(4):
            rng.random()
        rng.randint(0, 10**6)
    return out


def compare(n):
    rows = []
    for name, space_q, listen in (("A landmarks only", False, False),
                                  ("B + space/sound questions", True, False),
                                  ("C + simulated Listen clip", True, True)):
        Q.ENABLE_SPACE_QUESTIONS = space_q
        out = run(n, listen)
        e = np.array([r["err"] for r in out])
        rows.append((name, np.median(e), np.percentile(e, 80), np.median([r["r"] for r in out]),
                     np.mean([r["in_r"] for r in out]) * 100))
    print(f"{n} soldiers each (same spots, headings and landmark callouts)")
    print(f"{'':28s} {'median err':>10s} {'80th pct':>9s} {'radius':>7s} {'truth in r':>10s}")
    for name, med, p80, rad, inr in rows:
        print(f"{name:28s} {med:9.0f}m {p80:8.0f}m {rad:6.0f}m {inr:9.0f}%")
    Q.ENABLE_SPACE_QUESTIONS = True


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    if "--compare" in sys.argv:
        return compare(n)
    t0 = time.time()
    out = run(n)
    errs = np.array([r["err"] for r in out])
    print(f"{n} trials in {time.time() - t0:.0f}s")
    print(f"median error {np.median(errs):.0f} m, 80th pct {np.percentile(errs, 80):.0f} m")
    pe = np.array([r["peak_err"] for r in out])
    print(f"(peak instead of mean) median {np.median(pe):.0f} m, 80th pct {np.percentile(pe, 80):.0f} m")
    print(f"truth inside main 2-sigma: {np.mean([r['inside'] for r in out]) * 100:.0f} %")
    print(f"truth within the spoken radius: {np.mean([r['in_r'] for r in out]) * 100:.0f} % (target ~80 % x mass)")
    print(f"median radius before/after questions: {np.median([r['r0'] for r in out]):.0f} / "
          f"{np.median([r['r'] for r in out]):.0f} m")
    print(f"median main-blob mass after: {np.median([r['mass'] for r in out]):.2f}")
    kinds = {}
    for r in out:
        for k in r["kinds"]:
            kinds[k] = kinds.get(k, 0) + 1
    print("questions asked:", kinds)


if __name__ == "__main__":
    main()
