"""Follow-up reports about the same casualty update everything: signs, posture, change log.
Posture is never set by hand: it is estimated from what the audio gave."""
from backend import body
from backend.extract import rules_extract
from backend.state import Store


def cas0(rep):
    return body.twin(rep)["casualties"][0]


def test_followup_without_casualty_word_updates_signs():
    ex = rules_extract("He is now unconscious")
    assert ex["casualties"] and ex["casualties"][0]["signs"]["conscious"] is False
    ex = rules_extract("he stopped breathing")
    assert ex["casualties"][0]["signs"]["breathing"] is False


def test_posture_estimated_and_updated_per_report():
    s = Store()
    r = s.process(None, "One casualty, gunshot left thigh, conscious and breathing. Tourniquet on at 14:32.")
    p = cas0(r)["posture"]
    assert p["source"] == "estimated" and p["posture"] == "supine"
    assert abs(sum(p["p"].values()) - 1) < 0.01 and p["evidence"]

    r = s.process(r["id"], "He is now unconscious")
    assert cas0(r)["posture"]["posture"] == "recovery"          # unconscious + breathing

    r = s.process(r["id"], "we put him in the recovery position")
    assert cas0(r)["posture"]["source"] == "said"

    r = s.process(r["id"], "he stopped breathing")
    p = cas0(r)["posture"]
    assert p["posture"] == "supine" and p["source"] == "estimated"   # said posture is now stale


def test_walking_casualty_estimated_standing():
    s = Store()
    r = s.process(None, "One casualty, cut on the left forearm, conscious, he can walk.")
    assert cas0(r)["posture"]["posture"] == "standing"


def test_breathing_problem_sits_up():
    s = Store()
    r = s.process(None, "One casualty, chest wound, conscious, difficulty breathing.")
    assert cas0(r)["posture"]["posture"] == "sitting"


def test_change_log():
    s = Store()
    r = s.process(None, "One casualty, gunshot left thigh, conscious and breathing.")
    r = s.process(r["id"], "He is now unconscious")
    items = r["changes"][-1]["items"]
    assert any("conscious: yes → no" in x for x in items)
    assert any(x.startswith("posture:") for x in items)
    assert s.public()["reports"][0]["changes"]


def test_unlocated_injury_asks_where_the_wound_is():
    """'I am very hurt' names no body part: keep it, then ask where the wound is."""
    from backend.body import twin
    from backend.state import Store
    s = Store()
    r = s.new_report()
    r = s.process(r["id"], "I am very hurt. I'm breathing. I am indoors.")
    assert r["casualties"][0]["injuries"] == ["I am very hurt"]
    assert r["question"]["kind"] == "wound_where"
    r = s.process(r["id"], "Left leg")
    assert twin(r)["casualties"][0]["injuries"][0]["segments"] == ["l_thigh", "l_lower_leg"]
    assert r["question"]["kind"] == "describe"     # then the location questions
