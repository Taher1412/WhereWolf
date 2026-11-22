"""The ask-back loop: a truthful fake speaker answers our questions.
The uncertainty should shrink and the truth should stay inside a blob."""
import math
from datetime import datetime, timezone

import numpy as np
import pytest

from backend import questions as Q
from backend.landmarks import get_db
from backend.localise import get_engine
from backend.simulate import observe

NOON = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True, scope="module")
def ideal_visibility():
    """These tests check the resection geometry with landmarks the speaker can see. The 3D
    line of sight (who can actually see what) is tested in test_geomatics.py."""
    from backend import config, simulate
    old_obs, old_vs = simulate.observe, config.VIEWSHED_ENABLED
    config.VIEWSHED_ENABLED = False
    get_engine()._cache.clear()
    globals()["observe"] = lambda *a, **k: old_obs(*a, **{**k, "trees": False})
    yield
    config.VIEWSHED_ENABLED = old_vs
    globals()["observe"] = old_obs
    get_engine()._cache.clear()


def truthful_answer(q, eng, lat, lon, heading):
    """What a speaker standing at the true spot would answer."""
    if q["kind"] == "hear_type":                                # sound: say it, then parse it
        from backend.simulate import _space_answer
        return Q.parse_answer(q, _space_answer(q, lat, lon))
    if q["kind"] in ("setting3", "room_size"):   # the cell's most likely answer, like the others
        x, y = get_db().to_xy(lat, lon)
        cell = np.array([int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))])
        probs = Q.answer_probs(q, eng, cell, NOON)
        a = int(np.argmax([float(np.ravel(p)[0]) for p in probs]))
        return (["indoor", "built", "open"] if q["kind"] == "setting3" else ["small", "large"])[a]
    if q["kind"] in ("ground", "hear_dir", "which_see", "feature_dir"):   # say it, then parse it
        from backend.simulate import truthful_answer as say
        return Q.parse_answer(q, say(q, lat, lon, heading, NOON))
    x, y = get_db().to_xy(lat, lon)
    cell = np.array([int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))])
    h = int(round(heading / 5)) % eng.H
    probs = Q.answer_probs(q, eng, cell, NOON)
    vals = [float(np.broadcast_to(p, (1, eng.H))[0, h]) for p in probs]
    a = int(np.argmax(vals))
    if q["kind"] in ("visible_type", "visible_feature"):
        return a == 0
    if q["kind"] == "left_right":
        return "right" if a == 0 else "left"
    if q["kind"] == "sun":
        return a + 1
    if q["kind"] == "compass":            # 16 sectors of 22.5 deg, then "no compass"
        return a * 22.5 + 11.25 if a < 16 else "none"
    return [80, 180, 350, 700, 1500][a]  # dist band -> metres


@pytest.mark.parametrize("lat,lon,heading", [
    (48.8445, 2.4330, 120),
    (48.8470, 2.4395, 200),
    (48.8420, 2.4250, 270),
])
def test_questions_shrink(lat, lon, heading):
    eng = get_engine()
    cons, sentence = observe(lat, lon, heading, n=2, noise_deg=8, with_sun=False,
                             when=NOON, seed=4)
    res = eng.run(cons, when=NOON)
    start = res["radius_m"]
    asked, log = [], [f"{sentence} r={start:.0f}"]
    for _ in range(3):
        q, why = Q.choose(cons, asked, res, eng, NOON)
        if q is None:
            break
        asked.append(q)
        val = truthful_answer(q, eng, lat, lon, heading)
        c = Q.answer_to_constraint(q, val)
        if c:
            cons.append(c)
        res = eng.run(cons, when=NOON)
        log.append(f"{Q.phrase(q)} -> {val}  r={res['radius_m']:.0f} "
                   f"mass={res['main_mass']:.2f} gain={q['gain_bits']}")
    print("\n".join(log))
    x, y = get_db().to_xy(lat, lon)
    b = res["blobs"][0]
    bx, by = get_db().to_xy(b["lat"], b["lon"])
    err = math.hypot(bx - x, by - y)
    print("final error", round(err), "m")
    assert res["radius_m"] < start
    assert err < max(150, b["r2"])


def test_parse_answers():
    assert Q.parse_answer({"kind": "visible_type"}, "No, I can't see it") is False
    assert Q.parse_answer({"kind": "visible_type"}, "yes I can") is True
    assert Q.parse_answer({"kind": "visible_type"}, "oui je la vois") is True
    assert Q.parse_answer({"kind": "left_right"}, "it's on my left") == "left"
    assert Q.parse_answer({"kind": "sun"}, "sun is at eleven") == 11
    assert Q.parse_answer({"kind": "dist_band"}, "about 300 metres") == 300
    assert Q.parse_answer({"kind": "dist_band"}, "less than 200") == 140
