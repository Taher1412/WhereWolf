"""Heart rate from chest audio, the extraction fixes, and adaptive questions."""
import numpy as np

from backend import questions as Q
from backend.extract import extract, to_constraints
from backend.heart import heart_rate, synth_pcg


def test_heart_rate_from_chest_audio():
    for bpm in (55, 80, 115, 150):
        r = heart_rate(synth_pcg(bpm, noise=0.05, seed=1))
        assert abs(r["bpm"] - bpm) <= 5 and r["ok"]


def test_noise_is_not_a_heartbeat():
    r = heart_rate((np.random.default_rng(1).standard_normal(160000) * 0.1).astype(np.float32))
    assert not r["ok"]


def test_fast_heart_rate_feeds_the_condition():
    from backend.condition import assess
    from backend.state import Store
    s = Store()
    r = s.new_report()
    r = s.process(r["id"], "One casualty, gunshot to the chest, conscious")
    r = s.process_pulse(r["id"], heart_rate(synth_pcg(132, noise=0.05)), "test")
    c = assess(r["casualties"][0], r)
    assert c["heart"]["band"] == "shock range" and any(t["id"] == "shock" for t in c["threats"])


def test_hard_sentence_extraction():
    t = ("Okay so we got one guy down, he took shrapnel from a mortar in his right side and his arm, "
         "he is grey and sweating, kind of out of it. We are behind a low wall near a big water tower, "
         "the tower is maybe two hundred metres to my left, and I can hear the ring road ahead of me.")
    ex, _ = extract(t)
    c = ex["casualties"][0]
    assert c["mechanism"] == "blast" and c["signs"]["avpu"] == "V" and c["signs"]["shock_signs"]
    assert not any("ahead" in i for i in c["injuries"])                  # "ahead" is not a head wound
    obs = {(o["landmark_type"], o.get("relative"), o.get("distance_m"), bool(o.get("heard"))) for o in ex["observations"]}
    assert ("water_tower", "left", 200.0, False) in obs and ("main_road", "ahead", None, True) in obs
    assert len([o for o in ex["observations"] if "tower" in o["landmark_type"]]) == 1   # one tower, not two


def test_which_see_parsing():
    q = {"kind": "which_see", "opts": [1, 2, 3], "labels": ["the Sainte-Chapelle de Vincennes", "a tower", "the Tour des Salves"]}
    assert Q.parse_answer(q, "I can see the Sainte-Chapelle but not the tower") == 1
    assert Q.parse_answer(q, "I see the chapel and the tower") == 3
    assert Q.parse_answer(q, "none of them") == 0
    assert Q.parse_answer(q, "yes") is None
    c = Q.answer_to_constraint(q, 5)
    assert c["kind"] == "multi" and [it["value"] for it in c["items"]] == [True, False, True]


def test_adaptive_questions_name_real_features():
    from datetime import datetime, timezone
    from backend.localise import get_engine
    eng = get_engine()
    W = datetime(2026, 11, 21, 13, 0, tzinfo=timezone.utc)
    cons = [{"kind": "bearing", "type": "keep", "name": None, "beta": 330.0, "sigma": 15.0}]
    res = eng.run(cons, when=W)
    qs = Q._adaptive(cons, res, eng)
    kinds = {q["kind"] for q in qs}
    assert "which_see" in kinds and "feature_dir" in kinds
    assert not any("Donjon" in lab for q in qs for lab in q.get("labels", []) + [q.get("label", "")])   # keep already said
