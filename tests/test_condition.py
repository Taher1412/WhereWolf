"""Casualty condition (MARCH states, threats with time windows), health questions, and
several likely spots instead of one."""
import math
import time

from backend import questions as Q
from backend.condition import assess
from backend.state import Store


def rep_with(text):
    s = Store()
    r = s.new_report()
    return s, s.process(r["id"], text)


def test_uncontrolled_bleeding_is_critical_with_minutes_left():
    _, r = rep_with("One casualty, blast, hit 6 minutes ago, left thigh bleeding heavily")
    c = assess(r["casualties"][0], r)
    assert c["state"] in ("critical", "very critical")
    assert c["worse_in"]["threat"].startswith("Massive bleeding") and c["worse_in"]["max"] <= 4.5
    assert c["march"]["M"].startswith("massive, NOT")


def test_tourniquet_controls_and_starts_the_limb_clock():
    hhmm = time.strftime("%H:%M", time.localtime(time.time() - 20 * 60))
    _, r = rep_with(f"One casualty, left leg bleeding heavily, tourniquet on the left thigh at {hhmm}, conscious and breathing")
    c = assess(r["casualties"][0], r)
    ids = {t["id"]: t for t in c["threats"]}
    assert "bleed_uncontrolled" not in ids and ids["tourniquet"]["status"] == "controlled"
    assert 95 <= ids["tourniquet"]["left_min"][0] <= 105          # ~2 h minus ~20 min


def test_unconscious_means_airway_threat():
    _, r = rep_with("One casualty, fell from a wall, unconscious, gurgling")
    c = assess(r["casualties"][0], r)
    assert c["avpu"] == "U" and c["march"]["A"] == "AT RISK"
    assert c["worse_in"]["threat"].startswith("Airway") and c["state"] in ("critical", "very critical")
    assert any(p == "nape" for p, _ in c["suspect"])               # fall: check the spine


def test_self_report_and_distress():
    _, r = rep_with("I'm hit, my leg is bleeding, I'm in a lot of pain")
    cas = r["casualties"][0]
    assert cas["self_report"] and cas["signs"]["avpu"] == "A"
    c = assess(cas, r)
    assert c["self_report"] and c["distress"] in ("elevated", "high")


def test_blast_marks_hidden_injuries_in_the_body_graph():
    from backend.body import twin
    _, r = rep_with("One casualty, blast, shrapnel in the left leg")
    parts = {n["id"]: n["status"] for n in twin(r)["casualties"][0]["parts"]}
    assert parts["ears"] == "suspected" and parts["chest"] == "suspected" and parts["l_leg"] == "affected"


def test_health_questions_in_march_order_and_in_the_right_voice():
    s, r = rep_with("One casualty, left thigh bleeding heavily. I see the castle keep at my 11 o'clock")
    assert r["question"]["kind"] == "med_bleed"
    r = s.process(r["id"], "No")
    assert r["casualties"][0]["signs"]["bleeding_controlled"] is False
    assert r["question"]["kind"] == "med_avpu"
    r = s.process(r["id"], "Yes")
    assert r["question"]["kind"] == "med_breath"
    _, r2 = rep_with("I'm hit, my left thigh is bleeding heavily")
    assert r2["question"]["text"].startswith("Has your bleeding stopped")


def test_several_likely_spots_and_more_questions():
    s, r = rep_with("One casualty, blast, left leg wound, conscious and breathing. I see the castle keep at my 11 o'clock")
    hs = r["position"]["hyps"]
    assert len(hs) >= 2 and [h["label"] for h in hs][:2] == ["A", "B"]
    d = math.hypot((hs[0]["lat"] - hs[1]["lat"]) * 110540, (hs[0]["lon"] - hs[1]["lon"]) * 73000)
    assert d >= 290
    assert Q.STRESS_POLICY["low"]["max_q"] >= 6
