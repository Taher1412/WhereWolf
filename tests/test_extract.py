"""Rule-based extraction (no API key needed)."""
from backend.extract import rules_extract, to_constraints, _clean


def ex(text, ctx=None):
    return _clean(rules_extract(text, ctx))


def test_demo_sentence():
    e = ex("One casualty, blast, left leg bleeding, tourniquet on at 14:32, conscious and "
           "breathing. We're in a tree line. I see the castle keep at my 11 o'clock, a church "
           "at 2 o'clock, sun at my 1 o'clock.")
    c = e["casualties"][0]
    assert c["mechanism"] == "blast"
    assert c["treatments"][0]["time"] == "14:32"
    kinds = [(x["kind"], x.get("type")) for x in to_constraints(e)]
    assert ("bearing", "keep") in kinds and ("bearing", "church") in kinds
    assert ("here", "wood") in kinds and ("sun", None) in kinds


def test_french():
    e = ex("Un blessé par balle au bras, garrot posé à 15h10, inconscient. Je vois le donjon "
           "à 10 heures et une église à 3 heures, le soleil à midi.")
    assert e["lang"] == "fr"
    assert e["casualties"][0]["treatments"][0]["time"] == "15:10"
    assert e["casualties"][0]["signs"]["conscious"] is False
    assert e["sun"] == {"clock": 12}
    assert [o["landmark_type"] for o in e["observations"]] == ["keep", "church"]


def test_callsign_and_negative():
    e = ex("This is Bravo two, two casualties, no railway in sight, water tower on my left.")
    assert e["callsign"] == "BRAVO TWO"
    assert e["casualties"][0]["count"] == 2
    obs = {o["landmark_type"]: o for o in e["observations"]}
    assert obs["railway"]["visible"] is False
    assert obs["water_tower"]["relative"] == "left"


def test_answer():
    e = ex("Negative, I can't see it", {"last_question": {"id": "q1", "kind": "visible_type",
                                                          "type": "railway"}})
    assert e["answer_to_question"]["value"] is False
