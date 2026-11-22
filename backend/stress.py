"""How stressed does the speaker sound? (decision support for the question loop)

From the push-to-talk clip (the operator's own voice) and the words of the report:

  pitch raised above the speaker's own floor (semitones), and wide pitch range
  brighter voice: more energy at 1-5 kHz than at 50 Hz-1 kHz (alpha ratio)
  fast articulation (syllables per second of speech)
  choppy speech: many short bursts between pauses
  words: "hurry", "he's dying", "please", "vite", repetitions, swearing, exclamations

These are the usual acoustic correlates of stress / arousal in the speech literature
(raised F0 and F0 range, flatter spectral tilt, faster rate; e.g. Scherer 2003, Hansen &
Patil 2007, Giddens et al. 2013). The thresholds below are rule-of-thumb reference values,
NOT a trained or validated model. Two big confounds:
  - shouting over noise (Lombard effect) raises pitch and brightness too, so voice cues
    count less when the background is loud (low speech-to-noise ratio);
  - a high-pitched or fast talker sounds "stressed" on absolute values. Within one report
    the change from the speaker's first clip is used as well.
It only changes HOW we ask (fewer, simpler, shorter questions); it never touches medical
priority.
"""
import math
import re

import numpy as np
from scipy import signal

SR = 16000
HOP = 160            # 10 ms
WIN = 512            # 32 ms
LEVELS = ((0.35, "low"), (0.62, "elevated"), (1.01, "high"))

# Reference values (calm -> clearly stressed), placeholders until checked on recordings.
REF = {
    "f0_rise_st": (3.0, 7.0),       # median pitch above the speaker's own 10th percentile
    "f0_range_st": (5.0, 10.0),     # 10th-90th percentile pitch range
    "alpha_db": (-20.0, -9.0),      # energy 1-5 kHz vs 50 Hz-1 kHz
    "rate_syl_s": (4.2, 6.2),       # articulation rate
    "burst_s": (2.2, 0.9),          # mean speech burst length (short = choppy)
}
WEIGHT = {"f0_rise_st": 1.0, "f0_range_st": 0.8, "alpha_db": 0.8, "rate_syl_s": 0.8, "burst_s": 0.5,
          "words": 1.2, "trend": 1.0}

PANIC = (r"\b(hurry|quick(ly)?|fast|now|help|please|dying|he'?s dying|she'?s dying|bleeding out|oh god|"
         r"jesus|shit|fuck|damn|can'?t stop|losing him|losing her|vite|aidez|au secours|il meurt|elle meurt|"
         r"d[ée]p[êe]chez|putain|merde|s'il vous pla[iî]t|urgence|urgent)\b")


# ------------------------------------------------------------------ voice
def _frames(x, win, hop):
    n = 1 + max(0, (x.size - win) // hop)
    return np.lib.stride_tricks.as_strided(x, shape=(win, n), strides=(x.strides[0], hop * x.strides[0]))


def pitch_track(wave, fmin=70.0, fmax=450.0, win=1024):
    """F0 (Hz) every 10 ms by normalised autocorrelation (0 where unvoiced). The window's
    own autocorrelation is divided out (Boersma 1993), the first lag within 85 % of the best
    peak is taken (avoids most octave-too-low errors) and refined by a parabola."""
    x = np.pad(wave.astype(np.float64), (win // 2, win // 2))
    w = np.hanning(win)
    F = _frames(x, win, HOP)
    F = (F - F.mean(axis=0)) * w[:, None]
    ac = np.fft.irfft(np.abs(np.fft.rfft(F, n=2 * win, axis=0)) ** 2, axis=0)[:win]
    aw = np.fft.irfft(np.abs(np.fft.rfft(w, n=2 * win)) ** 2)[:win]
    ac = ac / np.maximum(ac[0], 1e-12) / np.maximum(aw / aw[0], 1e-3)[:, None]
    lo, hi = int(SR / fmax), int(SR / fmin)
    seg = ac[lo:hi]
    best = seg.max(axis=0)
    lag = lo + np.argmax(seg >= 0.85 * best[None, :], axis=0)
    cols = np.arange(ac.shape[1])
    # the top of that peak: the best lag within the next 40 % of a period
    span = np.arange(0, 48)[:, None]
    idx = np.clip(lag[None, :] + np.minimum(span, (0.4 * lag[None, :]).astype(int)), lo, hi - 1)
    lag = idx[np.argmax(ac[idx, cols[None, :]], axis=0), cols]
    a0, a1, a2 = ac[np.clip(lag - 1, 0, win - 1), cols], ac[lag, cols], ac[np.clip(lag + 1, 0, win - 1), cols]
    den = a0 - 2 * a1 + a2
    frac = np.where(np.abs(den) > 1e-9, 0.5 * (a0 - a2) / den, 0.0)
    f0 = SR / (lag + np.clip(frac, -0.5, 0.5))
    return np.where(best > 0.45, f0, 0.0)


def voice_features(wave, sr=SR):
    """Features of the speaker's voice in a clip (chirp already removed). None if there is
    too little voiced speech (< 1.2 s)."""
    wave = np.asarray(wave, np.float32)
    if sr != SR:
        wave = signal.resample_poly(wave, SR, sr).astype(np.float32)
    if wave.size < SR:
        return None
    frames = _frames(np.pad(wave, (WIN // 2, WIN // 2)), WIN, HOP)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=0)) + 1e-9
    db = 20 * np.log10(rms)
    floor = np.percentile(db, 10)
    speech = db > floor + 12
    if speech.sum() < 80:                       # < 0.8 s above the noise
        return None
    snr = float(np.percentile(db[speech], 70) - floor)

    f0 = pitch_track(wave)
    n = min(len(f0), len(speech))
    f0, sp = f0[:n], speech[:n]
    st = 12 * np.log2(np.maximum(f0, 1) / 100.0)
    stable = np.r_[False, np.abs(np.diff(st)) < 1.0] & np.r_[np.abs(np.diff(st)) < 1.0, False]
    voiced = sp & stable & (f0 > 72) & (f0 < 440)
    if voiced.sum() < 120:                      # < 1.2 s of clean voicing
        return None
    sv = st[voiced]
    p10, p50, p90 = np.percentile(sv, [10, 50, 90])

    # Brightness: average spectrum of the speech frames.
    spec = np.abs(np.fft.rfft(frames[:, :n][:, sp] * np.hanning(WIN)[:, None], axis=0)) ** 2
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    lo = spec[(freqs >= 50) & (freqs < 1000)].sum()
    hi = spec[(freqs >= 1000) & (freqs < 5000)].sum()
    alpha = float(10 * np.log10(hi / max(lo, 1e-12)))

    # Articulation rate: peaks of the 300-2500 Hz envelope while speaking.
    sos = signal.butter(4, [300, 2500], btype="band", fs=SR, output="sos")
    env = np.abs(signal.sosfiltfilt(sos, wave))
    env = signal.sosfiltfilt(signal.butter(2, 10, fs=SR, output="sos"), env)[::HOP][:n]
    env = np.pad(env, (0, max(0, n - env.size)), mode="edge")
    env_db = 20 * np.log10(np.maximum(env, 1e-9))
    peaks, _ = signal.find_peaks(np.where(sp, env_db, env_db.min()), distance=11, prominence=4)
    speak_s = sp.sum() * HOP / SR
    rate = len(peaks) / max(speak_s, 0.5)

    # Bursts: runs of speech frames separated by pauses >= 250 ms.
    runs, cur, gap = [], 0, 0
    for s in sp:
        if s:
            cur += 1 + (gap if gap < 25 else 0)
            gap = 0
        else:
            gap += 1
            if gap == 25 and cur:
                runs.append(cur)
                cur = 0
    if cur:
        runs.append(cur)
    burst = float(np.mean(runs) * HOP / SR) if runs else speak_s

    return {"f0_hz": round(float(100 * 2 ** (p50 / 12)), 1),
            "f0_rise_st": round(float(p50 - p10), 2), "f0_range_st": round(float(p90 - p10), 2),
            "f0_median_st": round(float(p50), 2), "alpha_db": round(alpha, 1),
            "rate_syl_s": round(float(rate), 2), "burst_s": round(burst, 2),
            "voiced_s": round(float(voiced.sum() * HOP / SR), 1), "snr_db": round(snr, 1),
            "speech_s": round(float(speak_s), 1)}


# ------------------------------------------------------------------ words
def text_features(text):
    t = (text or "").lower()
    words = re.findall(r"[\w']+", t)
    panic = len(re.findall(PANIC, t))
    rep = sum(1 for a, b in zip(words, words[1:]) if a == b and len(a) > 2)     # "help help"
    excl = (text or "").count("!")
    clauses = [c for c in re.split(r"[.;,!?]", t) if c.strip()]
    short = sum(1 for c in clauses if len(c.split()) <= 2)
    return {"panic_words": panic, "repeats": rep, "exclamations": excl,
            "short_clauses": short, "n_words": len(words)}


# ------------------------------------------------------------------ estimate
def _z(name, v):
    a, b = REF[name]
    return (v - a) / (b - a)          # 0 = calm reference, 1 = clearly stressed


def estimate(voice=None, words=None, first_voice=None):
    """-> {level, score 0..1, confidence, cues: [...], source}. voice / first_voice from
    voice_features (this clip / the first clip of the same report), words from text_features."""
    cues, num, den = [], 0.0, 0.0
    if voice:
        # Shouting over noise also raises pitch and brightness: trust the voice less.
        trust = float(np.clip((voice["snr_db"] - 8.0) / 14.0, 0.25, 1.0))
        for name, label in (("f0_rise_st", "pitch raised"), ("f0_range_st", "pitch range"),
                            ("alpha_db", "bright / strained voice"), ("rate_syl_s", "fast speech"),
                            ("burst_s", "choppy speech")):
            z = float(np.clip(_z(name, voice[name]), -1.0, 2.0))
            w = WEIGHT[name] * (trust if name in ("f0_rise_st", "f0_range_st", "alpha_db") else 1.0)
            num += w * z
            den += w
            cues.append({"cue": label, "value": voice[name], "z": round(z, 2), "w": round(w, 2)})
        if first_voice and first_voice is not voice:
            d = voice["f0_median_st"] - first_voice["f0_median_st"]
            z = float(np.clip(0.5 + d / 4.0, -1.0, 2.0))          # +2 st above the first clip ~ 1
            num += WEIGHT["trend"] * z
            den += WEIGHT["trend"]
            cues.append({"cue": "pitch vs first report", "value": round(d, 1), "z": round(z, 2),
                         "w": WEIGHT["trend"]})
    if words:
        k = words["panic_words"] + 0.7 * words["repeats"] + 0.4 * min(words["exclamations"], 3) \
            + (0.5 if words["n_words"] >= 6 and words["short_clauses"] >= 3 else 0)
        z = float(np.clip(k / 2.0, 0.0, 2.0))
        # Words only count when something was said, and add evidence without dominating.
        w = WEIGHT["words"] if words["n_words"] >= 3 else 0.0
        num += w * z
        den += w
        cues.append({"cue": "words (urgency, repeats)", "value": round(k, 1), "z": round(z, 2), "w": w})
    if den == 0:
        return {"level": "unknown", "score": None, "confidence": 0.0, "cues": [], "source": "none"}
    m = num / den
    score = float(1 / (1 + math.exp(-4.0 * (m - 0.45))))
    level = next(l for th, l in LEVELS if score < th)
    conf = min(1.0, den / 5.0) * (min(1.0, voice["voiced_s"] / 4.0) if voice else 0.5)
    return {"level": level, "score": round(score, 2), "confidence": round(conf, 2), "cues": cues,
            "source": "voice + words" if voice else "words only"}
