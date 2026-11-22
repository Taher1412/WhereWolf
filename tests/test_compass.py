"""Spoken compass bearings (degrees, mils, digit by digit): parsing, position, questions."""
import math

import numpy as np

from backend import danger, questions
from backend.extract import _compass_bearing, rules_extract, to_constraints
from backend.landmarks import get_db
from backend.localise import get_engine


def test_parse_bearings():
    assert _compass_bearing("a church at bearing 240 degrees") == 240
    assert _compass_bearing("church bearing 4200 mils") == 236.2
    assert _compass_bearing("le château d'eau, azimut 3200 millièmes") == 180
    assert _compass_bearing("keep bearing two four zero") == 240
    assert _compass_bearing("church 300 metres ahead") is None
    assert _compass_bearing("keep at my 2 o'clock") is None


def test_bearing_attaches_to_landmark():
    ex = rules_extract("I see the castle keep, bearing 1100 mils, and a church at bearing 240 degrees.")
    cons = [c for c in to_constraints(ex) if c["kind"] == "abs_bearing"]
    assert [c["type"] for c in cons] == ["keep", "church"]
    assert abs(cons[0]["said_deg"] - 61.9) < 0.1


def test_threat_bearing():
    d = danger.from_text("Sniper, bearing 1600 mils.")[0]
    assert d["type"] == "sniper" and abs(d["bearing_abs"] - 92) < 1


def test_two_named_bearings_locate():
    db, eng = get_db(), get_engine()
    truth = (48.8440, 2.4330)
    x0, y0 = db.to_xy(*truth)
    named = [i for t in ("keep", "church", "station", "tower", "townhall") for i in db.candidates(t)
             if db.feats[int(i)].get("name")]
    d = [(math.hypot(db.x[i] - x0, db.y[i] - y0), i) for i in named]
    picks = []
    for dist, i in sorted(d):
        b = math.degrees(math.atan2(db.x[i] - x0, db.y[i] - y0)) % 360
        if 80 < dist < 900 and all(abs((b - pb + 180) % 360 - 180) > 35 for _, pb in picks):
            picks.append((i, b))
        if len(picks) == 2:
            break
    cons = [{"kind": "abs_bearing", "type": db.feats[int(i)]["type"], "name": db.feats[int(i)]["name"],
             "deg": b, "sigma": 6.0, "distance_m": None} for i, b in picks]
    res = eng.run(cons)
    x1, y1 = db.to_xy(res["lat"], res["lon"])
    assert np.hypot(x1 - x0, y1 - y0) < 150


def test_compass_question():
    q = {"kind": "compass", "ref": {"type": "keep", "name": None}, "type": "keep"}
    assert "bearing" in questions.phrase(q)
    assert questions.parse_answer(q, "two four zero, bearing two four zero") == 240
    assert questions.parse_answer(q, "4200 mils") == 236.25 or abs(questions.parse_answer(q, "4200 mils") - 236.2) < 0.1
    assert questions.parse_answer(q, "no compass") == "none"
    assert questions.answer_to_constraint(q, "none") is None
    assert questions.answer_to_constraint(q, 240.0)["kind"] == "abs_bearing"
