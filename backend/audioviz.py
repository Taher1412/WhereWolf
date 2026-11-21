"""Pictures of the sound analysis, for the /pipeline page (step 1: Listen).

spectrogram(wave)   log-mel spectrogram as a small uint8 image (base64)
timeline(...)       per-window classifier scores (YAMNet windows, 0.48 s apart)
synth_clip(...)     rehearsal only: a fake clip built from the simulated events,
                    so the page has something real-looking to show. The pictures
                    of a simulated clip are computed by the same code as real ones,
                    but the sounds themselves are synthetic and labelled so.
"""
import base64
import math

import numpy as np

from . import config

SR = 16000
FMIN, FMAX = 50.0, 8000.0


def _mel(f):
    return 2595 * np.log10(1 + f / 700.0)


def _mel_inv(m):
    return 700 * (10 ** (m / 2595.0) - 1)


def spectrogram(wave, sr=SR, cols=360, rows=80):
    """Log-mel spectrogram. Row 0 = highest frequency. dB range [-80, 0] -> 0..255."""
    if wave.size < 1024:
        return None
    n_fft, hop = 1024, 160                         # 64 ms window, 10 ms hop
    frames = np.lib.stride_tricks.sliding_window_view(wave, n_fft)[::hop] * np.hanning(n_fft)
    pw = np.abs(np.fft.rfft(frames, axis=1)) ** 2  # (t, f)
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    # Triangular mel filters.
    edges = _mel_inv(np.linspace(_mel(FMIN), _mel(min(FMAX, sr / 2)), rows + 2))
    fb = np.zeros((rows, f.size))
    for i in range(rows):
        lo, c, hi = edges[i], edges[i + 1], edges[i + 2]
        fb[i] = np.clip(np.minimum((f - lo) / (c - lo + 1e-9), (hi - f) / (hi - c + 1e-9)), 0, None)
    mel = pw @ fb.T                                 # (t, rows)
    # Max-pool time down to `cols` so short events stay visible.
    t = mel.shape[0]
    if t > cols:
        k = int(math.ceil(t / cols))
        pad = k * cols - t
        mel = np.pad(mel, ((0, pad), (0, 0)), mode="edge").reshape(cols, k, rows).max(axis=1)
    db = 10 * np.log10(mel + 1e-12)
    db = np.clip(db - db.max(), -80, 0)
    img = ((db + 80) / 80 * 255).astype(np.uint8).T[::-1]   # (rows, cols), high freq on top
    return {"w": int(img.shape[1]), "h": int(img.shape[0]), "fmin": FMIN, "fmax": min(FMAX, sr / 2),
            "dur_s": round(wave.size / sr, 2), "data": base64.b64encode(img.tobytes()).decode()}


def timeline(gs, keep, hop_s, groups, shift=None):
    """Per-window scores for the groups we show. shift(t) maps a time in the
    (chirp-removed) analysed clip back to the original recording."""
    n = len(keep)
    ts = [round(i * hop_s + 0.4875, 2) for i in range(n)]       # window centres
    if shift:
        ts = [round(shift(t), 2) for t in ts]
    return {"t": ts, "kept": [bool(k) for k in keep],
            "groups": {g: [round(float(v), 2) for v in gs[g]] for g in groups if g in gs}}


# ===================================================================== rehearsal
def _sweep(sr, t0, n):
    from .spatial import make_sweep
    x, _ = make_sweep(sr)
    out = np.zeros(n)
    a = int(t0 * sr)
    out[a:a + x.size] = x[: max(0, min(x.size, n - a))]
    return out


def synth_clip(events, facade_m, rng, ping_at=0.3, dur=4.8):
    """Synthetic Listen clip: chirp + echo, then the simulated sound events.
    Returns (wave16k, rec48k, timeline). Deterministic for a given rng."""
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.cumsum(nrng.normal(0, 1, n)) * 0.0004          # brown-ish background
    x -= np.convolve(x, np.ones(800) / 800, mode="same")  # remove drift
    x += nrng.normal(0, 0.002, n)
    lanes = {g: np.zeros(n) for g in ("speech", "rail", "traffic", "bells", "machinery", "nature")}
    start = ping_at + config.PROBE["dur"] + 0.6           # sounds after the chirp
    on = t >= start

    for g in events:
        if g == "traffic":
            env = (0.5 + 0.5 * np.sin(2 * math.pi * t / 2.7 + rng.random() * 6)) * on
            rum = np.convolve(nrng.normal(0, 1, n), np.ones(40) / 40, mode="same")
            x += 0.05 * env * rum
            lanes[g] = env
        elif g == "rail":
            env = np.exp(-0.5 * ((t - (start + 1.6)) / 0.9) ** 2)
            clack = (np.sin(2 * math.pi * 1.7 * t) > 0.97).astype(float)
            noise = nrng.normal(0, 1, n)
            x += env * (0.04 * np.convolve(noise, np.ones(6) / 6, mode="same") + 0.08 * clack * noise)
            lanes[g] = env
        elif g == "bells":
            for k in np.arange(start + 0.2, dur, 1.1):
                d = np.clip(t - k, 0, None) * (t >= k)
                env = np.exp(-d / 0.8) * (t >= k)
                x += 0.05 * env * sum(np.sin(2 * math.pi * f * t) / (j + 1)
                                      for j, f in enumerate((523, 1046, 1310, 1568)))
                lanes[g] = np.maximum(lanes[g], env)
        elif g == "nature":
            for _ in range(9):
                k = rng.uniform(start, dur - 0.2)
                m = (t >= k) & (t < k + 0.09)
                tt = t[m] - k
                x[m] += 0.03 * np.sin(2 * math.pi * (3200 * tt + 18000 * tt ** 2)) * np.hanning(m.sum())
                lanes[g][m] = 1.0
        elif g == "machinery":
            for k in np.arange(start + 0.3, start + 2.3, 0.125):
                m = (t >= k) & (t < k + 0.01)
                x[m] += nrng.normal(0, 0.15, m.sum())
                lanes[g][(t >= k) & (t < k + 0.12)] = 1.0

    # Chirp, its ground echo (~1.3 m) and the facade echo, at 48 kHz for the probe.
    sr48 = config.PROBE["sr"]
    n48 = int(dur * sr48)
    C = config.SPEED_OF_SOUND
    rec = _sweep(sr48, ping_at, n48) * 0.5
    for d, g_ in ((1.3, 0.25), (facade_m, 0.18)) if facade_m else ((1.3, 0.25),):
        rec += np.roll(_sweep(sr48, ping_at, n48), int(2 * d / C * sr48)) * 0.5 * g_
    rec += np.random.default_rng(1).normal(0, 0.0015, n48)
    x += rec[:: sr48 // SR][:n] * 0.6                     # the chirp is visible in the spectrogram too

    # Timeline at YAMNet's rhythm (0.975 s windows every 0.48 s): mean of each lane.
    win, hop = int(0.975 * SR), int(0.48 * SR)
    gs = {g: [] for g in lanes}
    for s in range(0, n - win + 1, hop):
        for g, v in lanes.items():
            gs[g].append(float(v[s:s + win].mean()) * 0.85)
    keep = [True] * len(gs["speech"])
    tl = timeline({g: np.array(v) for g, v in gs.items()}, keep, 0.48,
                  ["speech", "rail", "traffic", "bells", "machinery", "nature"])
    return x.astype(np.float32), rec, tl
