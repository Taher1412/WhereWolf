"""Acoustic spatial sensing on synthetic rooms where we know the answer.

A room = direct sound + floor echo + wall echoes + an exponentially decaying
reverberant tail (RT60). We play the chirp / a voice-like signal through it and
check what spatial.py recovers.
"""
import numpy as np
import pytest
from scipy import signal

from backend import spatial

C = 343.0
SR = 48000


def room_ir(sr, rt, walls, floor=1.3, seed=0):
    rng = np.random.default_rng(seed)
    n = int(sr * max(rt * 1.5, 0.3))
    h = np.zeros(n)
    h[0] = 1.0
    for d, a in [(floor, 0.5)] + walls:
        k = int(2 * d / C * sr)
        if k < n:
            h[k] += a / (2 * d)
    if rt > 0:
        t = np.arange(n) / sr
        tail = rng.standard_normal(n) * np.exp(-6.91 * t / rt) * 0.08 * (1 - np.exp(-t / 0.015))
        tail[: int(0.004 * sr)] = 0
        h += tail
    return h


def voice_like(sr, dur=4.0, seed=1):
    """Syllable-like bursts of band-limited noise with abrupt ends."""
    rng = np.random.default_rng(seed)
    x, t = np.zeros(int(sr * dur)), 0.2
    sos = signal.butter(4, [300, 3500], btype="band", fs=sr, output="sos")
    while t < dur - 0.5:
        L = rng.uniform(0.12, 0.35)
        k0, k1 = int(t * sr), int((t + L) * sr)
        x[k0:k1] = signal.sosfilt(sos, rng.standard_normal(k1 - k0)) * rng.uniform(0.3, 1)
        t += L + rng.uniform(0.15, 0.4)
    return x / np.abs(x).max() * 0.5


def chirp_recording(h, latency=0.037, noise_db=-55, seed=2):
    rng = np.random.default_rng(seed)
    x, _ = spatial.make_sweep(SR)
    rec = np.zeros(int(SR * 3.0))
    k = int((1.0 + latency) * SR)
    y = signal.fftconvolve(x, h)[: rec.size - k]
    rec[k:k + y.size] += 0.3 * y
    return rec + rng.standard_normal(rec.size) * 10 ** (noise_db / 20)


@pytest.mark.parametrize("rt", [0.45, 0.8, 1.8])
def test_rt60_from_chirp_and_voice(rt):
    h = room_ir(SR, rt, [(3.0, 0.7)])
    pr = spatial.probe(chirp_recording(h), SR, 1.0)
    assert pr["ok"]
    assert abs(pr["rt60_s"] - rt) / rt < 0.2, pr["rt60_s"]
    sr16 = 16000
    v = signal.fftconvolve(voice_like(sr16), room_ir(sr16, rt, [(3.0, 0.7)]))
    est, decays = spatial.blind_rt60(v, sr16)
    assert est is not None and abs(est - rt) / rt < 0.25, (est, len(decays))


@pytest.mark.parametrize("facade", [4.0, 8.0, 15.0])
def test_street_facade_distance(facade):
    pr = spatial.probe(chirp_recording(room_ir(SR, 0.0, [(facade, 0.6)])), SR, 1.0)
    assert pr["ok"] and pr["wall_reliable"]
    assert abs(pr["nearest_wall_m"] - facade) < 0.3, pr["reflections"]
    assert pr["floor_or_ceiling_m"] == pytest.approx(1.3, abs=0.1)   # ground echo, not a wall


def test_settings():
    open_ = spatial.probe(chirp_recording(room_ir(SR, 0.0, [])), SR, 1.0)
    street = spatial.probe(chirp_recording(room_ir(SR, 0.0, [(8.0, 0.6)])), SR, 1.0)
    hall = spatial.probe(chirp_recording(room_ir(SR, 1.8, [(7.0, 0.7)])), SR, 1.0)
    small = spatial.probe(chirp_recording(room_ir(SR, 0.45, [(2.2, 0.7)])), SR, 1.0)
    best = lambda pr: max((p := spatial.setting_probs(None, None, pr)[0]), key=p.get)  # noqa: E731
    assert best(open_) == "outdoor_open"
    assert best(street) == "outdoor_enclosed"
    assert best(hall) == "indoor_large"
    assert best(small) == "indoor_small"


def test_no_clue_is_uniform():
    p, clues, strength = spatial.setting_probs(None, None, None)
    assert strength < 0.01 and not clues
    assert all(abs(v - 0.25) < 1e-6 for v in p.values())


def test_chirp_missing_is_reported():
    rng = np.random.default_rng(3)
    pr = spatial.probe(rng.standard_normal(SR * 3) * 0.01, SR, 1.0)   # no chirp recorded
    assert not pr["ok"] and pr["why"]


@pytest.mark.parametrize("rt", [0.25, 0.3, 0.4])
def test_dry_own_voice_is_not_proof_of_outdoors(rt):
    """Close-talk voice in a furnished room sounds dry: it must not read as outdoors."""
    p = spatial.setting_probs(rt, None, None, close_talk=True)[0]
    assert p["outdoor_enclosed"] + p["outdoor_open"] < 0.7
    assert p["indoor_small"] >= p["outdoor_open"]


def test_long_tail_on_own_voice_is_indoors():
    p = spatial.setting_probs(1.2, None, None, close_talk=True)[0]
    assert p["indoor_small"] + p["indoor_large"] > 0.7
