"""3D line of sight (viewshed) and aiming with the phone (tilt, turn between taps)."""
import math
import random

import numpy as np
import pytest

from backend import config
from backend.localise import get_engine


@pytest.fixture(scope="module")
def vs():
    from backend.viewshed import get_viewshed
    v = get_viewshed(get_engine())
    if not v.ok:
        pytest.skip("no 3D model (data/twin/buildings.geojson)")
    return v


def keep_index():
    db = get_engine().db
    return [i for i in range(len(db.types)) if db.types[i] == "keep"][0]


def test_buildings_hide_the_keep(vs):
    """In streets the keep is seen from a minority of spots in range, far fewer than the
    old distance rule assumed, and almost always from close by."""
    eng = get_engine()
    i = keep_index()
    T = vs.T[vs.col[i]] / 255.0
    d = np.hypot(eng.X - eng.db.x[i], eng.Y - eng.db.y[i])
    area = (d < 1500) & ~vs.indoor
    assert 0.02 < (T[area] > 0.5).mean() < 0.3
    assert (T[area & (d < 200)] > 0.5).mean() > 3 * (T[area & (d > 600)] > 0.5).mean()


def test_keep_top_altitude(vs):
    """LiDAR: the keep is ~52 m tall on ~51 m ground."""
    top = float(vs.top[vs.col[keep_index()]])
    assert 95 < top < 115


def test_elevation_angle_ranges_the_keep(vs):
    """Tilt to the keep's top measured at a spot that sees it: the likelihood peaks at
    about the right distance from the keep."""
    eng = get_engine()
    i = keep_index()
    T = vs.T[vs.col[i]] / 255.0
    d = np.hypot(eng.X - eng.db.x[i], eng.Y - eng.db.y[i])
    cells = np.where((T > 0.8) & (d > 250) & (d < 500))[0]
    c = int(cells[len(cells) // 2])
    el = float(vs.elevation(np.array([c]), np.array([i]))[0, 0])
    L = eng._elevation_like({"type": "keep", "name": None, "deg": el, "sigma": 1.5})
    good = L > 0.5 * L.max()
    assert abs(np.median(d[good]) - d[c]) < 0.25 * d[c]


def test_angle_between_is_heading_free(vs):
    """The turn between two landmarks is likelier at the true spot than at most others."""
    eng = get_engine()
    db = eng.db
    i = keep_index()
    j = [k for k in range(len(db.types)) if db.feats[k]["name"] == "Sainte-Chapelle de Vincennes"][0]
    both = (vs.T[vs.col[i]] > 200) & (vs.T[vs.col[j]] > 200)
    c = int(np.where(both)[0][0])
    bi = math.degrees(math.atan2(db.x[i] - eng.X[c], db.y[i] - eng.Y[c]))
    bj = math.degrees(math.atan2(db.x[j] - eng.X[c], db.y[j] - eng.Y[c]))
    deg = ((bj - bi) + 180) % 360 - 180
    L = eng._angle_like({"a": {"type": "keep"}, "b": {"type": "church", "name": "Sainte-Chapelle de Vincennes"},
                         "deg": deg, "sigma": 2.0})
    assert (L > L[c]).mean() < 0.02


def test_aims_become_constraints():
    from backend.state import Store
    s = Store()
    r = s.new_report()
    r = s.process(r["id"], "I see the castle keep at my 11 o'clock and a church at my 2 o'clock",
                  aims=[{"az": 0, "el": 8.0}, {"az": 95.0, "el": 4.0}])
    kinds = [c["kind"] for c in r["constraints"]]
    assert kinds.count("elevation") == 2 and kinds.count("angle_between") == 1
    ab = [c for c in r["constraints"] if c["kind"] == "angle_between"][0]
    assert ab["a"]["type"] == "keep" and ab["b"]["type"] == "church" and ab["deg"] == 95.0


def test_aims_wait_for_named_landmarks():
    from backend.state import Store
    s = Store()
    r = s.new_report()
    r = s.process(r["id"], "One casualty, leg wound", aims=[{"az": 0, "el": 7.0}])
    assert r.get("pending_aims") and not any(c["kind"] == "elevation" for c in r["constraints"])
    r = s.process(r["id"], "I see the castle keep at my 12 o'clock")
    assert any(c["kind"] == "elevation" for c in r["constraints"])


def test_simulated_speaker_only_sees_what_is_in_sight(vs):
    from backend.simulate import observe
    eng = get_engine()
    i = keep_index()
    T = vs.T[vs.col[i]]
    d = np.hypot(eng.X - eng.db.x[i], eng.Y - eng.db.y[i])
    hidden = np.where((T == 0) & (d < 600) & ~vs.indoor)[0][:10]
    for c in hidden:
        lat, lon = eng.db.to_latlon(eng.X[c], eng.Y[c])
        picks = []
        observe(float(lat), float(lon), 0.0, n=3, with_sun=False, seed=1, picks_out=picks)
        assert not any(p["type"] == "keep" for p in picks)
