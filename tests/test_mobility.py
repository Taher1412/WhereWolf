"""Mobility state: what was said wins, otherwise a safe inference."""
import pytest

from backend.response import build
from backend.state import Store


def plan(text):
    rep = Store().process(None, text)
    row = build(rep, 300)["team"]["rows"][0]
    return row["mobility"], row["source"], row.get("conflict")


@pytest.mark.parametrize("text,state,source", [
    ("One casualty, gunshot to the right arm, he can walk.", "walks", "said"),
    ("Un blessé, il marche, plaie au bras gauche.", "walks", "said"),
    ("Un blessé, plaie à la jambe, il ne peut pas marcher.", "litter", "said"),   # not "marche"
    ("One casualty, he is limping, cut on the right calf.", "assisted", "said"),
    ("One casualty pinned under rubble, conscious, left leg injured.", "trapped", "said"),
    ("One casualty, blast, unconscious.", "litter", "inferred"),
    ("One casualty, shrapnel in the left foot, conscious.", "assisted", "inferred"),
    ("One casualty, bleeding from the head.", "unknown", "inferred"),           # consciousness not said
])
def test_states(text, state, source):
    s, src, _ = plan(text)
    assert (s, src) == (state, source)


def test_conflict_plans_a_stretcher():
    s, src, conflict = plan("One casualty, tourniquet left thigh at 14:00, he says he can walk.")
    assert s == "litter" and src == "said" and "tourniquet" in conflict


def test_trapped_adds_extraction():
    rep = Store().process(None, "One casualty trapped under rubble, unconscious.")
    out = build(rep, 300)
    assert out["team"]["extrication"] == 2
    assert any(k["id"] == "extrication" for k in out["kit"])
