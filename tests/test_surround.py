"""Close surroundings from audio: the measurements are right, and the matching
against the real walls / noise map prefers the true spot."""
import random

import numpy as np
import pytest

from backend import audioviz, surround
from backend.localise import get_engine


@pytest.fixture(scope="module")
def places():
    pl = surround.get_places(get_engine())
    if not pl.ok:
        pytest.skip("no building footprints in data/twin")
    return pl


def test_ambient_level_from_own_voice():
    """Voice at the reference level + road noise at 62 dB(A): measured within ~3 dB."""
    from backend.simulate import synth_report
    wave, _, _, ping = synth_report(62.0, [], False, random.Random(1))
    cut = (int((ping - 0.05) * 16000), int((ping + 1.1) * 16000))
    a = surround.measure_ambient(np.r_[wave[:cut[0]], wave[cut[1]:]], 16000, True)
    assert a["ref"] == "own voice"
    assert abs(a["dba"] - 62.0) < 4.0


def test_echoes_detected_at_wall_distances():
    """The real chirp code finds synthetic walls at 3.5 and 11 m."""
    from backend import config, spatial
    from backend.simulate import synth_report
    _, rec, _, ping = synth_report(55.0, [(3.5, 0.2), (11.0, 0.1)], False, random.Random(2))
    pr = spatial.probe(rec, config.PROBE["sr"], ping)
    walls = [r["m"] for r in pr["reflections"] if r["m"] > 1.8]
    assert pr["ok"] and pr["drr_db"] > 0
    assert any(abs(m - 3.5) < 0.3 for m in walls) and any(abs(m - 11.0) < 0.3 for m in walls)


def test_echo_match_ranks_true_cell_high(places):
    """Clean echoes measured at a real street spot: the true cell is in the top 5 %."""
    rng = np.random.default_rng(0)
    out = np.where(~places.spot_in)[0]
    ranks = []
    for _ in range(12):
        x, y = places.spot_xy[int(rng.choice(out))]
        here = places.at_point(float(x), float(y))
        refl = [{"m": e["m"]} for e in here["echoes"] if 1.8 < e["m"] <= 25]
        if len(refl) < 2:
            continue
        p = places.likelihood({"kind": "echoes", "refl": refl})
        ranks.append((p > p[here["cell"]]).mean())
    assert ranks and np.median(ranks) < 0.05


def test_no_echo_favours_open_ground(places):
    """'No wall within 25 m' should score open spots above narrow streets."""
    L = places.echo_like({"refl": []})
    near = np.isfinite(places.e_dist[:, 0]) & (places.e_dist[:, 0] < 8) & ~places.spot_in
    open_ = ~np.isfinite(places.e_dist[:, 0]) & ~places.spot_in
    assert L[open_].mean() > 2 * L[near].mean()


def test_noise_map_louder_near_big_roads(places):
    assert places.l_out.max() > 70 and np.percentile(places.l_out, 10) < 55


def test_spectrogram_time_axis_covers_clip():
    """Pooling must not stretch the time axis (it used to pad to 360 columns)."""
    sr = 16000
    wave = np.zeros(6 * sr, np.float32)
    wave[int(4.0 * sr): int(4.1 * sr)] = 0.5           # a click at 4.0 s
    sp = audioviz.spectrogram(wave)
    import base64
    img = np.frombuffer(base64.b64decode(sp["data"]), np.uint8).reshape(sp["h"], sp["w"])
    col = int(np.argmax(img.mean(axis=0)))
    assert abs(col / sp["w"] * sp["dur_s"] - 4.0) < 0.15


def test_cue_bits():
    assert surround.cue_bits(np.ones(1024)) == 0.0
    L = np.full(1024, 1e-6); L[:4] = 1
    assert surround.cue_bits(L) > 7.5
