"""Routes to the CCP away from danger, and a walker guided there with no GPS."""
import pytest

from backend import guide
from backend.route import get_router
from backend.state import Store, now_ms

START = (48.8440, 2.4330)
CCP = (48.8472, 2.4365)


def zone(lat, lon, r, t="small_arms"):
    return {"id": f"x:{lat}", "placed": True, "ms": now_ms(), "ttl_ms": 900_000, "lat": lat, "lon": lon,
            "type": t, "conf": 0.9, "shape": "circle", "radius_m": r, "pos_r": 50}


@pytest.fixture(scope="module")
def R():
    r = get_router()
    if not r.ok:
        pytest.skip("no walking network (data/twin)")
    return r


def test_route_avoids_danger(R):
    plain = R.route(START, CCP)
    assert 500 < plain["length_m"] < 1200 and plain["detour_m"] == 0
    z = zone(48.8456, 2.4348, 150)                 # right on the direct way
    safe = R.route(START, CCP, [z])
    assert safe["detour_m"] > 0
    assert safe["avoided"].get("small_arms", 0) > 50
    assert safe["exposure"].get("small_arms", 0) < plain["length_m"] * 0.1


def test_legs_are_spoken_with_landmarks(R):
    legs = R.legs(R.route(START, CCP))
    assert 2 <= len(legs) <= 15
    assert all(lg["turn"] is None for lg in legs[:1]) and all(lg["turn"] is not None for lg in legs[1:])
    assert any(lg["cue"] for lg in legs)


def _walker(rep_text="One casualty, cut on the arm, he can walk. I see the castle keep at my 11 o'clock."):
    S = Store()
    rep = S.process(None, rep_text, truth={"lat": START[0] + 1e-4, "lon": START[1] + 2e-4, "heading": 90})
    rep["position"].update(lat=START[0], lon=START[1], radius_m=90.0, state="rough", main_mass=0.8)
    return S, S.guide_action(rep["id"], "start")


def test_simulated_walk_reaches_ccp(R):
    S, rep = _walker()
    g = rep["guide"]
    assert g["state"] == "active" and "CCP" in rep["readback"]
    t0 = now_ms()
    said = []
    for k in range(1, 120):
        v = g["say_v"]
        guide.tick(rep, S.ccp, [], t0 + k * 5000)
        if g["say_v"] != v:
            said.append(g["instruction"])
        if g["state"] != "active":
            break
    assert g["state"] == "arrived" and rep["at_ccp"]
    assert S.distance_to_ccp(rep) < 20
    assert len(said) == len(set(said))            # nothing spoken twice in a row
    assert [e["kind"] for e in g["events"]].count("reached") == len(g["legs"])


def test_clock_only_waits_for_reached(R):
    S, rep = _walker()
    rep["truth"] = None                            # a real walker: no simulation
    g = rep["guide"]
    end = g["legs"][0]["s1"]
    guide.tick(rep, S.ccp, [], now_ms() + 600_000)  # 10 min later, no confirmation
    assert g["s"] <= end + 0.01 and g["leg"] == 0
    assert g["est"]["radius_m"] > 90               # but we are less and less sure
    S.guide_action(rep["id"], "reached")
    assert g["leg"] == 1 and g["est"]["radius_m"] < 90


def test_step_counter_moves_the_pin(R):
    S, rep = _walker()
    rep["truth"] = None
    g = rep["guide"]
    S.guide_action(rep["id"], "steps", steps=1000)
    S.guide_action(rep["id"], "steps", steps=1200)  # 200 steps = 140 m
    guide.tick(rep, S.ccp, [], now_ms())
    assert g["mode"] == "steps" and 120 < g["s"] < 160


def test_new_danger_reroutes(R):
    S, rep = _walker()
    rep["truth"] = None
    g = rep["guide"]
    n = g["reroutes"]
    # a sniper reported right across the rest of the route
    mid = len(g["route"]["lat"]) // 2
    z = zone(g["route"]["lat"][mid], g["route"]["lon"][mid], 120, "sniper")
    guide.tick(rep, S.ccp, [z], now_ms() + 2000)
    assert g["reroutes"] == n + 1 and g["route"]["exposure"].get("sniper", 0) < 30
    assert "danger" in g["instruction"].lower()


def test_voice_commands(R):
    assert guide.command("next") == "reached"
    assert guide.command("Je suis perdu") == "lost"
    assert guide.command("We're at the CCP") == "arrived"
    assert guide.command("One casualty, he can walk, church at my 2 o'clock, next to the road.") is None
    S, rep = _walker()
    rep = S.process(rep["id"], "I'm lost")
    assert rep["guide"]["state"] == "lost" and "clock" in rep["readback"]
    # a new landmark report re-locates the walker and restarts the route from there
    rep = S.process(rep["id"], "I see the castle keep at my 3 o'clock and a church at my 10 o'clock.")
    assert rep["guide"]["state"] == "active" and rep["guide"]["reroutes"] >= 1
    assert any(c["kind"] == "track" for c in rep["constraints"])


def test_dangers_stay_where_reported(R):
    S, rep = _walker()
    rep = S.process(rep["id"], "Drone overhead.")
    z0 = [z for z in S.zones() if z["report"] == rep["id"]][0]
    guide.tick(rep, S.ccp, [], now_ms() + 120_000)
    S.guide_action(rep["id"], "reached")
    z1 = [z for z in S.zones() if z["report"] == rep["id"]][0]
    assert (z0["lat"], z0["lon"]) == (z1["lat"], z1["lon"])


def test_medic_route_for_stretcher_case(R):
    S = Store()
    rep = S.process(None, "One casualty, unconscious, gunshot to the thigh. Church at my 2 o'clock.")
    rep["position"].update(lat=START[0], lon=START[1], radius_m=120.0, state="rough", main_mass=0.8)
    d = guide.dispatch(rep, S.ccp, [], now_ms())
    assert d and d["length_m"] > 300 and d["eta_back_s"] > d["eta_out_s"]
    assert rep.get("guide") is None


def test_radio_soldier_with_compass(R):
    """No phone: compass bearings in the instructions, pace count moves the pin."""
    S, rep = _walker("One casualty, cut on the arm, he can walk. Church, bearing 4200 mils.")
    rep["truth"] = None
    g = rep["guide"]
    assert "mils" in g["instruction"]
    lg = g["legs"][g["leg"]]
    rep = S.process(rep["id"], f"{int(min(lg['length_m'] - 5, 60))} metres done")
    assert g["leg"] == 0 and g["s"] > 10 and any(e["kind"] == "pace count" for e in g["events"])
