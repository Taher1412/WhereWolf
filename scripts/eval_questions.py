"""Question selection: which objective localises best, and what stress adaptation costs.

  python -m scripts.eval_questions [n]

Same simulated casualties (3D line of sight, streets around the chateau) for every row:
  entropy   old objective: bits of uncertainty removed
  spread    metres of expected position error removed
  blend     half of each (the default)
  blend + elevated / high stress: harder questions cost more, fewer questions when high
Two spot sets: random street spots, and spots where at least one landmark is truly in sight.
"""
import random
import sys
import time

import numpy as np

from backend import config, questions as Q
import scripts.eval_geomatics as G

ROWS = [("entropy (old)", "entropy", "low"), ("spread (metres)", "spread", "low"),
        ("blend (default)", "blend", "low"), ("blend, elevated stress", "blend", "elevated"),
        ("blend, high stress", "blend", "high")]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 40
    config.VIEWSHED_ENABLED = True
    orig = Q.choose
    log = []

    def choose(*a, **k):
        q, why = orig(*a, **{**k, "stress": STATE["stress"]})
        if q:
            log.append(Q.load_of(q))
        return q, why
    Q.choose = choose
    t0 = time.time()
    for label, seen in (("random street spots", False), ("street spots that see a landmark", True)):
        G.SEEN_ONLY = seen
        spots = G.spots_for("streets", n, random.Random(21 if seen else 22))
        print(f"\n{label}: {n} casualties")
        print(f"{'':26s} {'median err':>10s} {'<=50 m':>7s} {'<=100 m':>8s} {'<=250 m':>8s} {'questions':>10s} {'mean effort':>12s}")
        for name, obj, stress in ROWS:
            Q.OBJECTIVE, STATE["stress"] = obj, stress
            log.clear()
            out = [G.trial(s, 1, 900 + i, False) for i, s in enumerate(spots)]
            e = np.array([o["err"] for o in out])
            print(f"{name:26s} {np.median(e):9.0f}m {np.mean(e <= 50) * 100:6.0f}% {np.mean(e <= 100) * 100:7.0f}% "
                  f"{np.mean(e <= 250) * 100:7.0f}% {len(log) / n:10.1f} {np.mean(log) if log else 0:12.2f}")
    Q.choose, Q.OBJECTIVE = orig, "blend"
    print(f"({time.time() - t0:.0f} s)")


STATE = {"stress": "low"}

if __name__ == "__main__":
    main()
