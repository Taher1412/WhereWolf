"""Acoustic evidence on the map: does it move the probability where it should,
and stay weak when it should?"""
import numpy as np

from backend.extract import extract, to_constraints
from backend.localise import get_engine
from backend.questions import parse_answer
from backend.soundscape import get_soundscape
from backend.state import merge_acoustic


def _mass(post, mask):
    return float(post[mask].sum())


def test_layers_loaded():
    sc = get_soundscape(get_engine())
    assert sc.ok and sc.n_buildings > 10000
    assert np.allclose(sc.P_setting.sum(axis=1), 1)


def test_indoor_moves_mass_into_buildings():
    eng, sc = get_engine(), get_soundscape()
    indoor = sc.P_setting[:, 0] + sc.P_setting[:, 1] > 0.5
    base = eng.run([])["post"]
    p = {"indoor_small": 0.6, "indoor_large": 0.3, "outdoor_enclosed": 0.05, "outdoor_open": 0.05}
    post = eng.run([{"kind": "setting", "p": p, "source": "audio", "w": 1.0}])["post"]
    assert _mass(post, indoor) > _mass(base, indoor) + 0.15


def test_facade_echo_prefers_streets_of_that_width():
    eng, sc = get_engine(), get_soundscape()
    post = eng.run([{"kind": "reflector", "distance_m": 6.0, "source": "audio", "w": 1.0}])["post"]
    open_cells = sc.P_setting[:, 3] > 0.8      # far from any facade
    base = eng.run([])["post"]
    assert _mass(post, open_cells) < 0.6 * _mass(base, open_cells)


def test_train_heard_vs_not_heard():
    eng, sc = get_engine(), get_soundscape()
    near_rail = sc.exposure["rail"] > 0.5
    base = _mass(eng.run([])["post"], near_rail)
    heard = _mass(eng.run([{"kind": "hear", "cls": "rail", "q": 1.0, "source": "audio", "w": 1.0}])["post"], near_rail)
    silent = _mass(eng.run([{"kind": "hear", "cls": "rail", "q": 0.0, "source": "audio", "w": 1.0}])["post"], near_rail)
    assert heard > 2 * base                       # a train is strong evidence
    assert silent > 0.8 * base                    # 4 s of no train is weak evidence


def test_parser_hearing_and_surroundings():
    ex, _ = extract("I can hear a train at my 3 o'clock and trucks. We are surrounded by buildings.")
    got = {(h["cls"], h["heard"]) for h in ex["hearing"]}
    assert ("rail", True) in got and ("traffic", True) in got
    assert any(o["landmark_type"] == "railway" and o.get("heard") for o in ex["observations"])
    assert ex["surroundings"] == "built"
    kinds = [c["kind"] for c in to_constraints(ex)]
    assert "hear" in kinds and "setting" in kinds
    # Sounds must not leak into the casualty card.
    ex, _ = extract("One casualty, leg wound. I hear explosions and trucks.")
    assert ex["casualties"][0]["mechanism"] is None
    ex, _ = extract("J'entends des cloches, pas de train.")
    got = {(h["cls"], h["heard"]) for h in ex["hearing"]}
    assert ("bells", False) in got or ("bells", True) in got


def test_answers():
    assert parse_answer({"kind": "setting3"}, "we're inside a building") == "indoor"
    assert parse_answer({"kind": "setting3"}, "in a street between buildings") == "built"
    assert parse_answer({"kind": "setting3"}, "in the open, near the woods") == "open"
    assert parse_answer({"kind": "room_size"}, "a big hall") == "large"
    assert parse_answer({"kind": "hear_type", "type": "rail"}, "no, haven't heard any") is False
    assert parse_answer({"kind": "hear_type", "type": "rail"}, "yes I heard one") is True


def test_no_double_counting():
    a1 = {"kind": "hear", "cls": "rail", "q": 0.4, "source": "audio", "w": 1.0}
    a2 = {"kind": "hear", "cls": "rail", "q": 0.9, "source": "audio", "w": 1.0}
    v = {"kind": "hear", "cls": "rail", "q": 0.0, "source": "voice", "w": 1.0}
    cons = merge_acoustic([], [a1])
    cons = merge_acoustic(cons, [a2])
    assert [c["q"] for c in cons] == [0.9]       # strongest clip kept, not both
    cons = merge_acoustic(cons, [v])
    assert cons == [v]                           # the operator's answer wins
    cons = merge_acoustic(cons, [a1])
    assert cons == [v]
