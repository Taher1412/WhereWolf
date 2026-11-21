"""Synthetic scenes: put a fake observer somewhere, describe what they see,
and check that localise.py finds them again.  Run:  python -m pytest -q
"""
import math
import time
from datetime import datetime, timezone

import pytest

from backend.landmarks import get_db
from backend.localise import get_engine
from backend.simulate import observe

NOON = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)   # sun is up

# (lat, lon, heading) spots around the Château de Vincennes.
SPOTS = [
    (48.8445, 2.4330, 120),   # north-west of the château
    (48.8500, 2.4300, 0),     # north of the château, in town
    (48.8420, 2.4250, 270),   # west, by the Bois
    (48.8470, 2.4395, 200),   # near the town hall
    (48.8460, 2.4210, 80),    # Saint-Mandé
]


def error_m(res, lat, lon):
    """How far the true spot is outside the nearest blob's 2-sigma circle."""
    db = get_db()
    x, y = db.to_xy(lat, lon)
    best = math.inf
    for b in res["blobs"]:
        bx, by = db.to_xy(b["lat"], b["lon"])
        best = min(best, max(0.0, math.hypot(bx - x, by - y) - b["r2"]))
    return best


@pytest.mark.parametrize("lat,lon,heading", SPOTS)
def test_recovers_position(lat, lon, heading):
    cons, sentence = observe(lat, lon, heading, n=3, noise_deg=8, when=NOON, seed=1)
    assert len(cons) >= 3, sentence
    res = get_engine().run(cons, when=NOON)
    err = error_m(res, lat, lon)
    print(sentence, "->", round(err), "m, r2 =", round(res["radius_m"]))
    assert err < 50     # the truth is inside (or right next to) a blob


def test_fast_enough():
    cons, _ = observe(48.8445, 2.4330, 120, n=3, when=NOON, seed=2)
    eng = get_engine()
    eng._cache.clear()
    t = time.perf_counter()
    eng.run(cons, when=NOON)
    dt = time.perf_counter() - t
    print(f"localise: {dt * 1000:.0f} ms")
    assert dt < 2.0


def test_sun_fixes_heading():
    cons, _ = observe(48.8445, 2.4330, 120, n=2, when=NOON, seed=3)
    res = get_engine().run(cons, when=NOON)
    err = abs((res["heading_deg"] - 120 + 180) % 360 - 180)
    assert err < 30
