"""Heart rate from audio: the phone's microphone pressed on the casualty's chest.

The heart sounds (S1 "lub", S2 "dub", 25-200 Hz) come through a phone microphone held
firmly on the chest, left of the breastbone (like stethoscope apps do). We take the
Shannon energy envelope of the 25-200 Hz band, then the beat period from its
autocorrelation (40-200 bpm), check the half / double period (S1-S2 pairs can fool a
simple peak pick), and give a quality score. Rhythm regularity comes from the beat
intervals.

Not possible from ordinary speech: a voice recording carries no reliable heart-rate
signal (published voice-only estimates are research models with ~10 bpm errors in the lab).
So the dashboard shows a measured value only from a chest recording, with its age; voice
stress is shown beside it as context, never as a heart rate.

Decision support: thresholds in config.HR_BANDS (tachycardia > 100, > 120 shock range,
> 140 severe; < 50 slow), to check with the medical mentor.
"""
import numpy as np
from scipy import signal

SR = 4000            # plenty for < 200 Hz


def _shannon_env(x, sr):
    x = x / (np.max(np.abs(x)) + 1e-9)
    e = -(x ** 2) * np.log(x ** 2 + 1e-10)
    win = int(0.04 * sr)
    e = np.convolve(e, np.ones(win) / win, mode="same")
    step = sr // 100                                 # 100 Hz envelope
    e = e[::step]
    return (e - e.mean()) / (e.std() + 1e-9)


def heart_rate(wave, sr=16000):
    """-> {bpm, quality 0..1, regular, beats, ok, reason}. wave: chest-contact recording."""
    w = np.asarray(wave, np.float64)
    if sr != SR:
        w = signal.resample_poly(w, SR, sr)
    if w.size < 5 * SR:
        return {"ok": False, "reason": "recording too short (need 5 s or more)"}
    w = w[int(0.5 * SR):]                             # drop the first half second (handling noise)
    band = signal.sosfiltfilt(signal.butter(4, [25, 200], btype="band", fs=SR, output="sos"), w)
    # Clip loud bumps (fingers, movement) so they don't dominate.
    lim = 4 * np.median(np.abs(band)) / 0.6745 + 1e-9
    band = np.clip(band, -lim, lim)
    env = _shannon_env(band, SR)
    fs = 100.0
    ac = np.correlate(env, env, mode="full")[env.size - 1:]
    ac = ac / (ac[0] + 1e-9)
    lo, hi = int(fs * 60 / 200), int(fs * 60 / 40)   # 0.3 s .. 1.5 s
    seg = ac[lo:hi]
    if seg.size == 0:
        return {"ok": False, "reason": "no signal"}
    # Candidates: local peaks of the autocorrelation in the 40-200 bpm range. Score = mean
    # autocorrelation at all multiples of the lag (up to 4 s): the true period lines up at
    # every multiple, half the period fails every second one. Between a period and its
    # double (same multiples), take the shorter when it scores nearly as well.
    def comb(L):
        ms = np.arange(1, max(2, int(4.0 * fs / L)) + 1)
        idx = np.rint(ms * L).astype(int)
        idx = idx[idx < ac.size - 1]
        # allow a little beat-to-beat drift: best value within +-4 % of each multiple
        vals = [ac[max(lo, int(i * 0.96)):int(i * 1.04) + 2].max() for i in idx]
        return float(np.mean(vals)) if vals else 0.0
    cand = [i for i in range(lo + 1, min(hi, ac.size - 1)) if ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1] and ac[i] > 0.05]
    if not cand:
        cand = [int(np.argmax(seg)) + lo]
    scored = sorted(((comb(L), L) for L in cand), reverse=True)
    best_s, k = scored[0]
    for sc_, L in scored[1:]:
        if L < k and abs(k / L - 2) < 0.15 and sc_ >= 0.85 * best_s:   # its half is as good
            k, best_s = L, sc_
    fold_q = best_s
    # Parabolic refinement.
    if 1 <= k < ac.size - 1:
        a0, a1, a2 = ac[k - 1], ac[k], ac[k + 1]
        d = a0 - 2 * a1 + a2
        kf = k + (0.5 * (a0 - a2) / d if abs(d) > 1e-9 else 0.0)
    else:
        kf = float(k)
    bpm = 60.0 * fs / kf
    quality = float(np.clip((0.5 * ac[k] + 0.5 * fold_q - 0.08) / 0.4, 0, 1))
    # Beats: envelope peaks at least 0.6 period apart -> regularity of intervals.
    peaks, _ = signal.find_peaks(env, distance=max(1, int(0.6 * kf)), prominence=0.5)
    iv = np.diff(peaks) / fs
    T = kf / fs
    iv = iv[(iv > 0.6 * T) & (iv < 1.4 * T)]           # beat-to-beat only (not S1-S2 gaps)
    # Rhythm (regular / irregular) is NOT reported: on test signals the beat intervals from a
    # 10 s phone recording could not tell a regular rhythm from a 25 % irregular one.
    regular = None
    ok = quality >= 0.15          # synthetic tests: half flagged, 92 % of those within 5 bpm
    return {"ok": ok, "bpm": round(bpm), "quality": round(quality, 2), "regular": regular,
            "beats": int(peaks.size), "reason": None if ok else "heart sounds unclear: press firmly, keep still"}


def band(bpm, bands):
    """'slow' / 'normal' / 'fast' / 'shock range' / 'severe' from config.HR_BANDS."""
    if bpm is None:
        return None
    if bpm < bands["slow"]:
        return "slow"
    if bpm <= bands["fast"]:
        return "normal"
    if bpm <= bands["shock"]:
        return "fast"
    if bpm <= bands["severe"]:
        return "shock range"
    return "severe"


def synth_pcg(bpm, dur=10.0, sr=16000, noise=0.05, seed=0, jitter=0.03):
    """Synthetic chest recording: S1 / S2 bursts at the given rate, with noise (tests, demo)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * sr)) / sr
    y = np.zeros_like(t)
    T = 60.0 / bpm
    beat = 0.2
    while beat < dur - 0.5:
        for off, f, d, a in ((0.0, 55, 0.06, 1.0), (0.3 * T ** 0.5 * 0.55, 85, 0.04, 0.6)):
            s = int((beat + off) * sr)
            n = int(d * sr)
            if s + n < y.size:
                tt = np.arange(n) / sr
                y[s:s + n] += a * np.sin(2 * np.pi * f * tt) * np.hanning(n)
        beat += T * (1 + rng.normal(0, jitter))
    y += noise * rng.standard_normal(y.size)
    y += 0.3 * np.sin(2 * np.pi * 0.25 * t)            # breathing / movement drift
    return (0.4 * y / np.abs(y).max()).astype(np.float32)
