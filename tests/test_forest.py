"""Woods: canopy-aware visibility, ground answers, dead reckoning, compass, forest acoustics."""
import numpy as np
import pytest

from backend import config
from backend.extract import extract, to_constraints
from backend.localise import get_engine


@pytest.fixture(scope="module")
def fo():
    from backend.forest import get_forest
    f = get_forest(get_engine())
    if not f.ok:
        pytest.skip("no data/twin/forest.geojson (python scripts/fetch_forest.py)")
    return f


def test_trees_hide_the_keep(fo):
    """Canopy model alone (no 3D buildings): at the same distance from the keep, it is seen
    far less often under trees than in the open."""
    eng = get_engine()
    old = config.VIEWSHED_ENABLED
    config.VIEWSHED_ENABLED = False
    v = eng.visibility("keep")
    config.VIEWSHED_ENABLED = old
    kx, ky = eng.db.to_xy(48.8427, 2.4358)
    d = np.hypot(eng.X - kx, eng.Y - ky)
    ring = (d > 300) & (d < 900)
    assert np.median(v[ring & (fo.wood > 0.6)]) < 0.6 * np.median(v[ring & (fo.wood < 0.05)])


def test_under_trees_moves_mass_into_the_woods(fo):
    eng = get_engine()
    res = eng.run([{"kind": "ground", "what": "cover", "value": "trees", "source": "voice"}])
    woods = fo.wood > 0.6
    assert res["post"][woods].sum() > 3 * woods.mean()


def test_spoken_ground_and_dead_reckoning():
    ex, _ = extract("We are in the woods on a dirt track, 10 minutes north of the castle keep")
    cons = to_constraints(ex)
    ground = {(c["what"], c["value"]) for c in cons if c["kind"] == "ground"}
    assert ground == {("cover", "trees"), ("surface", "unpaved")}
    off = [c for c in cons if c["kind"] == "offset"]
    assert off and off[0]["type"] == "keep" and off[0]["bearing"] == 0 and off[0]["distance_m"] == 750
    assert not any(c["kind"] in ("bearing", "visible") and c.get("type") == "keep" for c in cons)


def test_offset_peaks_at_the_right_place():
    eng = get_engine()
    kx, ky = eng.db.to_xy(48.8427, 2.4358)
    res = eng.run([{"kind": "offset", "type": "keep", "bearing": 180.0, "distance_m": 400.0, "sigma_log": 0.35}])
    k = int(np.argmax(res["post"]))
    assert abs(eng.Y[k] - (ky - 400)) < 120 and abs(eng.X[k] - kx) < 120


def test_compass_fixes_the_heading():
    eng = get_engine()
    res = eng.run([{"kind": "compass", "deg": 200.0, "sigma": config.SIGMA_COMPASS}])
    ph = res["joint"].sum(axis=0)
    assert abs(((eng.headings[int(np.argmax(ph))] - 200) + 180) % 360 - 180) <= 5


def test_trees_soak_up_road_noise_and_echoes_are_neutral(fo):
    from backend.surround import get_places
    pl = get_places(get_engine())
    if not pl.ok:
        pytest.skip("no buildings")
    P0 = np.array([[100.0, 100.0]], np.float32)
    d = np.array([300.0], np.float32)
    # along a line fully in the woods vs fully in the open
    wood_px = np.argwhere(fo.px_wood)
    open_px = np.argwhere(~fo.px_wood)
    a = wood_px[len(wood_px) // 2] * 5.0
    db_wood = pl._forest_db(np.array([[a[1], a[0]]], np.float32), np.array([[a[1] + 1, a[0] + 1]], np.float32), d)
    assert db_wood[0] > 5
    b = open_px[0] * 5.0
    assert pl._forest_db(np.array([[b[1], b[0]]], np.float32), np.array([[b[1] + 1, b[0]]], np.float32), d)[0] == 0
    # Three echoes no wall explains: woods score above open streets with no matching wall.
    L = pl.echo_like({"refl": [{"m": 4.0}, {"m": 9.0}, {"m": 17.0}]}).reshape(-1, 9).mean(axis=1)
    woods = fo.wood > 0.8
    assert np.median(L[woods]) > np.median(L[(fo.wood < 0.05) & ~pl.spot_in.reshape(-1, 9).any(axis=1)])


def test_ground_and_traffic_questions_parse():
    from backend.questions import answer_to_constraint, parse_answer
    assert parse_answer({"kind": "ground", "type": "cover"}, "under the trees") == "trees"
    assert parse_answer({"kind": "ground", "type": "surface"}, "gravel") == "unpaved"
    assert parse_answer({"kind": "ground", "type": "water"}, "no") == "no"
    q = {"kind": "hear_dir", "type": "traffic"}
    assert parse_answer(q, "around nine") == 9
    c = answer_to_constraint(q, 9)
    assert c["kind"] == "bearing" and c["heard"] and c["beta"] == 270
    assert answer_to_constraint(q, parse_answer(q, "nothing"))["q"] == 0.0
