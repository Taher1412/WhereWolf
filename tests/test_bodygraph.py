"""Body parts graph: every part a node, red = said affected, orange = no data."""
from backend.bodygraph import match, parts_graph


def affected(g):
    return {n["id"] for n in g if n["status"] == "affected"}


def test_specific_parts_and_sides():
    assert match("right knee and shin") == (["r_lower_leg", "r_knee"], False)
    assert match("genou droit")[0] == ["r_knee"]
    assert match("back of the neck")[0] == ["nape"]
    assert match("shrapnel in the face and eyes")[0] == ["face", "eyes"]


def test_region_only_and_unknown_side():
    ids, unknown = match("arm wound")
    assert ids == ["l_arm", "r_arm"] and unknown
    assert match("left leg bleeding")[0] == ["l_leg"]      # where on the leg: no data


def test_graph_colours():
    g = parts_graph({"injuries": ["left knee bleeding", "I am very hurt"],
                     "treatments": [{"type": "tourniquet", "location": "left thigh"}]})
    assert len(g) == 47
    assert affected(g) == {"body", "l_leg", "l_knee", "l_thigh"}
    knee = [n for n in g if n["id"] == "l_knee"][0]
    assert knee["direct"] and "left knee bleeding" in knee["said"][0]
    body = [n for n in g if n["id"] == "body"][0]
    assert any("no body part" in s for s in body["said"])
    assert all(n["status"] == "nodata" for n in g if n["id"].startswith("r_"))
