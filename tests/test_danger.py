"""Danger zones: words -> threats, threats -> zones, overlapping reports -> source area."""
import math

from backend import danger
from backend.extract import rules_extract


def types(text):
    return [d["type"] for d in danger.from_text(text)]


def test_threat_words_en_fr():
    assert types("Drone overhead.") == ["drone"]
    assert types("Sniper at my 2 o'clock.") == ["sniper"]
    assert types("Taking fire from the north.") == ["small_arms"]
    assert types("Mortar rounds landing nearby.") == ["explosion"]
    assert types("Mines on the track.") == ["mines"]
    assert types("Des tirs venant du nord. Tireur d'élite à 2 heures.") == ["small_arms", "sniper"]


def test_not_threats():
    assert types("No drones in sight.") == []
    assert types("One casualty, gunshot to the chest, blast injury to the leg.") == []
    assert types("I see the water tank at my 3 o'clock.") == []
    assert types("That one is mine.") == []


def test_directions():
    d = danger.from_text("Sniper at my 2 o'clock.")[0]
    assert d["clock"] == 2 and d["bearing_abs"] is None
    assert danger.from_text("Taking fire, from my 3 o'clock.")[0]["clock"] == 3
    assert danger.from_text("Tank to the north east.")[0]["bearing_abs"] == 45
    assert danger.from_text("Il est blessé, des tirs.")[0]["bearing_abs"] is None   # "est" = is
    assert danger.from_text("Drone overhead.")[0]["here"]


def test_threat_sentence_does_not_change_mist():
    ex = rules_extract("One casualty, gunshot to the chest. Drone overhead, church at my 11 o'clock.")
    assert ex["casualties"][0]["mechanism"] == "gunshot"
    assert [o["landmark_type"] for o in ex["observations"]] == ["church"]
    assert rules_extract("Sniper at my 2 o'clock.")["observations"] == []
    # ...but a casualty hurt by a drone keeps it
    assert rules_extract("The drone hit him, he is wounded.")["casualties"][0]["mechanism"] == "blast"


def test_dedupe():
    ev = []
    danger.add(ev, {"type": "drone", "source": "voice", "conf": 0.9, "ms": 0, "clock": 3, "bearing_abs": None})
    danger.add(ev, {"type": "drone", "source": "voice", "conf": 0.9, "ms": 60_000, "clock": None, "bearing_abs": None})
    assert len(ev) == 1 and ev[0]["clock"] == 3 and ev[0]["ms"] == 60_000
    danger.add(ev, {"type": "drone", "source": "audio", "conf": 0.7, "ms": 60_000})
    assert len(ev) == 2


POS = {"lat": 48.845, "lon": 2.435, "radius_m": 50.0, "heading_deg": 90.0, "heading_conf": 9.0}


def test_zone_shapes():
    circle = danger.zone({"type": "small_arms"}, POS)
    assert circle["shape"] == "circle" and circle["radius_m"] == 50 + 400
    wedge = danger.zone({"type": "sniper", "clock": 3}, POS)       # facing east, 3 o'clock = south
    assert wedge["shape"] == "wedge" and wedge["bearing_deg"] == 180
    unknown_heading = danger.zone({"type": "sniper", "clock": 3}, {**POS, "heading_conf": 1.0})
    assert unknown_heading["shape"] == "circle"
    compass = danger.zone({"type": "armour", "bearing_abs": 45}, {**POS, "heading_conf": 1.0})
    assert compass["shape"] == "wedge" and compass["bearing_deg"] == 45


def _rep(rid, lat, lon, dangers):
    return {"id": rid, "callsign": rid, "position": {**POS, "lat": lat, "lon": lon}, "dangers": dangers}


def test_overlap_marks_likely_source():
    now = 1_000_000
    ev = lambda: [{"type": "small_arms", "source": "voice", "conf": 0.9, "ms": now}]   # noqa: E731
    dx = 600 / (111320 * math.cos(math.radians(48.845)))      # two units 600 m apart, both hear shots
    out = danger.zones([_rep("A", 48.845, 2.435, ev()), _rep("B", 48.845, 2.435 + dx, ev())], now)
    assert len(out["zones"]) == 2
    (h,) = out["hotspots"]
    assert h["n_reports"] == 2 and h["radius_m"] < 450
    assert abs(h["lon"] - (2.435 + dx / 2)) < dx * 0.15        # between the two units
    # far apart: no overlap, no source area
    far = danger.zones([_rep("A", 48.845, 2.435, ev()), _rep("B", 48.845, 2.435 + 5 * dx, ev())], now)
    assert far["hotspots"] == []


def test_unsure_reporter_is_not_drawn():
    now = 0
    ev = [{"type": "drone", "source": "voice", "conf": 0.9, "ms": now}]
    zs = danger.zones([{"id": "A", "position": {**POS, "radius_m": 1400.0}, "dangers": ev}], now)["zones"]
    assert not zs[0]["placed"]
    assert danger.near(_rep("B", 48.845, 2.435, []), zs) == []


def test_expired_and_near():
    now = 10 * 60_000 * 6
    old = [{"type": "drone", "source": "voice", "conf": 0.9, "ms": 0}]          # 60 min > 10 min ttl
    assert danger.zones([_rep("A", 48.845, 2.435, old)], now)["zones"] == []
    fresh = [{"type": "drone", "source": "voice", "conf": 0.9, "ms": now}]
    zs = danger.zones([_rep("A", 48.845, 2.435, fresh)], now)["zones"]
    assert danger.near(_rep("B", 48.8455, 2.435, []), zs) == ["drone"]          # 55 m away
    assert danger.near(_rep("C", 48.86, 2.435, []), zs) == []                   # 1.7 km away
