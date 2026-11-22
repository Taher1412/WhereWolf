"""Radio mode, no internet: callsigns, packets, the tone modem, packets -> evidence."""
import numpy as np

from backend import modem, packet, radio
from backend.radiosim import radio as channel
from backend.state import Store


def test_callsign():
    assert radio.callsign("This is Bravo two, one casualty") == "BRAVO 2"
    assert radio.callsign("Ici Charlie 3, un blessé") == "CHARLIE 3"
    assert radio.callsign("Bravo 2. Left. Over.") == "BRAVO 2"
    assert radio.callsign("One casualty, left leg") is None
    assert radio.strip_procedure("Left. Over.") == "Left"


def test_packet_roundtrip():
    r = {"callsign": "B2", "compass": 75, "aims": [{"az": 10, "el": 12.5}], "steps": 1234,
         "space": {"outdoor_enclosed": 0.8, "outdoor_open": 0.2}, "dba": 62, "echoes": [3.5, 9.0],
         "sounds": {"traffic": 0.7}, "threats": {"drone": 0.85}, "guide": {"event": "reached", "leg": 2},
         "space_strength": 0.5}
    b = packet.encode_report(r)
    assert len(b) < 40
    d = packet.decode_report(b)
    assert d["callsign"] == "B2" and abs(d["compass"] - 75) < 1.5 and d["steps"] == 1234
    assert d["echoes"] == [3.5, 9.0] and abs(d["threats"]["drone"] - 0.85) < 0.01
    assert d["guide"] == {"event": "reached", "leg": 2}
    legs = [{"bearing": 45, "length_m": 120, "cue": {"idx": 7, "side": "left"}}]
    rt = packet.decode_route(packet.encode_route("B2", 3, legs))
    assert rt["legs"][0]["length_m"] == 120 and rt["legs"][0]["cue_idx"] == 7


def test_modem_through_radio():
    rng = np.random.default_rng(0)
    ok = 0
    for _ in range(10):
        p = bytes(rng.integers(0, 256, 30, dtype=np.uint8))
        x = np.r_[np.zeros(3000), modem.encode(p) * 0.5, np.zeros(2000)].astype(np.float32)
        ok += p in modem.decode(channel(x, "digital", snr_db=15, rng=rng))
        assert p in modem.decode(channel(x, "analog", snr_db=12, rng=rng))
    assert ok >= 9


def test_packet_becomes_evidence():
    S = Store()
    p = packet.decode_report(packet.encode_report({
        "callsign": "B2", "compass": 75, "space": {"outdoor_enclosed": 0.9, "outdoor_open": 0.1},
        "space_strength": 0.6, "dba": 64, "echoes": [3.5, 9.0], "sounds": {"traffic": 0.8},
        "threats": {"drone": 0.9}}))
    rep = radio.apply_packet(S, None, p, "B2")
    kinds = {c["kind"] for c in rep["constraints"]}
    assert {"compass", "setting", "ambient", "echoes", "hear"} <= kinds
    assert [d["type"] for d in rep["dangers"]] == ["drone"]
    assert rep["callsign"] == "B2"
    # the same callsign later goes to the same report
    assert radio.find_report(S, "B2")["id"] == rep["id"]
