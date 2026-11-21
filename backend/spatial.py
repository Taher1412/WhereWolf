"""Acoustic spatial sensing: what kind of space is the phone in?

Four settings:  indoor_small | indoor_large | outdoor_enclosed (street, courtyard) | outdoor_open

Three independent clues, each optional:

1. PASSIVE, from any recording, best from the operator's own voice.
   When a word ends, the sound in a room does not stop at once: it dies away at a
   rate set by the room (the reverberation time, RT60 = time to fall by 60 dB).
   We find those free decays in the energy envelope, fit their slope and keep the
   fast ones (a room cannot make sound die faster than its own decay).
   Outdoors there is almost no tail; a small furnished room ~0.3-0.6 s;
   a hall or church 1-5 s.

2. ACTIVE (optional): the phone plays a 0.5 s chirp and records at the same time.
   Deconvolving the recording with the chirp gives the room impulse response:
     - the echo delays  -> distance to each reflecting surface, d = c * delay / 2
       (one microphone = distance only, never direction)
     - its energy decay -> RT60 (Schroeder integration), more reliable than passive
     - direct-to-reverberant ratio (DRR) and clarity C50
   A reflection near 0.8-1.8 m is usually the floor/ground or ceiling, so it is
   reported but not treated as a wall.

3. YAMNet scene scores (acoustic.py): "Inside, small room", "Inside, large room or
   hall", "Inside, public space", "Outside, urban or manmade", "Outside, rural or natural".

setting_probs() multiplies the clues (each tempered) into probabilities over the
four settings. They are heuristic likelihoods, not calibrated probabilities:
the numbers below are starting points to calibrate on real recordings.
"""
import math

import numpy as np
from scipy import signal

from . import config

C = config.SPEED_OF_SOUND
SETTINGS = config.SETTINGS
FLOOR_BAND_M = (0.8, 1.8)      # likely floor / ground / ceiling, not a wall
TEMPER = 0.7                    # each clue counts a bit less than full (they overlap)

# RT60 per setting: log-normal (median s, sigma of log). "Outdoor" values are the
# apparent decay our blind method sees outdoors (measurement floor ~0.1-0.2 s).
# Reverberation only separates indoor from outdoor: a street and a field both
# have almost no tail. The echo distance (WALL_MODEL) tells those two apart.
RT_MODEL = {"indoor_small": (0.45, 0.45), "indoor_large": (1.6, 0.55),
            "outdoor_enclosed": (0.12, 0.6), "outdoor_open": (0.12, 0.6)}
# Blind estimate from voice / ambient sound: real sources have their own decay, so
# open air reads ~0.3 s, not ~0.1 s (scripts/eval_audio.py on ESC-50 sounds:
# dry -> 0.30 s, 0.3 s room -> 0.38 s, 0.6 -> 0.59, 1.2 -> 1.12, 2.4 -> 2.14).
RT_MODEL_PASSIVE = {"indoor_small": (0.55, 0.4), "indoor_large": (1.6, 0.5),
                    "outdoor_enclosed": (0.28, 0.35), "outdoor_open": (0.28, 0.35)}
# YAMNet/AST scene labels hardly move with reverberation in that test (inside share
# 40 -> 57 % YAMNet, 73 -> 87 % AST from dry to 2.4 s): weak clue, lower weight.
SCENE_TEMPER = 0.4
# Nearest wall-like reflection per setting (median m, sigma of log).
WALL_MODEL = {"indoor_small": (1.8, 0.6), "indoor_large": (6.0, 0.6),
              "outdoor_enclosed": (6.0, 0.7), "outdoor_open": (22.0, 0.5)}
# Probe found NO reflection within range (except floor/ground): how likely per setting.
# Kept mild: a dense reverberant room can hide its first echo, so "none found"
# must not force "large hall".
NO_WALL = {"indoor_small": 0.25, "indoor_large": 0.45, "outdoor_enclosed": 0.3, "outdoor_open": 1.0}


def _lognorm(x, med, s):
    return math.exp(-0.5 * (math.log(max(x, 1e-3) / med) / s) ** 2)


# ===================================================================== 1. passive
def blind_rt60(wave, sr):
    """Reverberation time from free decays in any recording (no test signal).
    Returns (rt60 or None, list of individual decay estimates)."""
    if wave.size < sr * 0.5:
        return None, []
    n_fft, hop = int(0.032 * sr), int(0.010 * sr)
    f, _, Z = signal.stft(wave, sr, nperseg=n_fft, noverlap=n_fft - hop, boundary=None,
                          padded=False)
    band = (f >= 400) & (f <= 4000)                 # where voices and rooms both matter
    db = 10 * np.log10((np.abs(Z[band]) ** 2).sum(axis=0) + 1e-12)
    db = np.convolve(db, np.ones(3) / 3, mode="same")
    floor = np.percentile(db, 5)
    fps = sr / hop
    # Decay-rate distribution: fit a line to every stretch of the envelope (three
    # lengths, so both fast and slow rooms fit), keep the clean straight falls,
    # then take the steep end: sound can't die faster than the room lets it.
    decays = []
    for win_s in (0.08, 0.2, 0.4):
        w = int(win_s * fps)
        if w < 5 or w >= db.size:
            continue
        t = np.arange(w) / fps
        tc = t - t.mean()
        frames = np.lib.stride_tricks.sliding_window_view(db, w)[::2]
        yc = frames - frames.mean(axis=1, keepdims=True)
        slope = (yc * tc).sum(axis=1) / (tc ** 2).sum()
        r2 = (slope ** 2) * (tc ** 2).sum() / ((yc ** 2).sum(axis=1) + 1e-12)
        drop = frames[:, 0] - frames[:, -1]
        ok = (slope < -10) & (r2 > 0.85) & (drop >= 6) & (frames[:, -1] > floor + 3)
        decays += list(60.0 / -slope[ok])
    if len(decays) < 3:
        return None, decays
    return float(np.percentile(decays, 20)), decays


# ===================================================================== 2. active
def make_sweep(sr, f0=None, f1=None, dur=None):
    """Exponential sine sweep with 5 ms fades (field.js builds the very same one)."""
    p = config.PROBE
    f0, f1, dur = f0 or p["f0"], f1 or p["f1"], dur or p["dur"]
    t = np.arange(int(dur * sr)) / sr
    L = dur / math.log(f1 / f0)
    x = np.sin(2 * math.pi * f0 * L * (np.exp(t / L) - 1))
    nf = int(0.005 * sr)
    fade = 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, nf))
    x[:nf] *= fade
    x[-nf:] *= fade[::-1]
    return x, L


def impulse_response(rec, sr):
    """Farina deconvolution: recording * inverse sweep -> impulse response."""
    x, L = make_sweep(sr)
    t = np.arange(x.size) / sr
    inv = x[::-1] * np.exp(-t[::-1] / L)            # time-reversed, -6 dB/octave
    inv /= np.abs(signal.fftconvolve(x, inv)).max()
    return signal.fftconvolve(rec, inv, mode="full")


def analyse_ir(ir, sr):
    """Numbers from an impulse response. Distances are from the phone."""
    # Echo timing uses 2-10 kHz only: sharp pulses, mirror-like wall reflections,
    # and no ringing from the chirp's low band edge.
    hi_f = min(10000.0, 0.45 * sr)
    sos = signal.butter(4, [2000.0, hi_f], btype="band", fs=sr, output="sos")
    env = np.abs(signal.hilbert(signal.sosfiltfilt(sos, ir)))
    k0 = int(np.argmax(env))                          # direct path (speaker -> mic)
    w = max(int(0.0002 * sr), 1)
    sm = np.convolve(env, np.ones(w) / w, mode="same")
    rel = 20 * np.log10(sm / sm[k0] + 1e-12)
    to_k = lambda d: int(round(2 * d / C * sr))      # noqa: E731
    tail = rel[k0 + int(0.35 * sr): k0 + int(0.6 * sr)]
    noise = float(np.median(tail)) if tail.size > 10 else -60.0
    lo, hi = k0 + to_k(0.4), min(k0 + to_k(25.0), rel.size - 1)   # skip phone body / hand
    seg = rel[lo:hi]
    # Direct-to-reverberant ratio: > 0 dB = dry (outdoors / damped), < 0 = reverberant.
    e = ir[k0:] ** 2
    d = int(0.0025 * sr)
    drr = float(10 * np.log10(e[:d].sum() / (e[d:].sum() + 1e-15)))
    refl = []
    if seg.size > 10:
        # A reflection must stand out from its neighbourhood (indoors the dense
        # reverberant tail is full of small random peaks) and from the noise.
        from scipy.ndimage import median_filter
        local = median_filter(rel, size=max(int(0.004 * sr), 3))[lo:hi]
        pk, _ = signal.find_peaks(seg - local, height=8, distance=max(int(0.0005 * sr), 1))
        pk = [k for k in pk if seg[k] >= max(-35.0, noise + 10)]
        dist = lambda k: (lo + k - k0) / sr * C / 2                    # noqa: E731
        is_floor = lambda k: FLOOR_BAND_M[0] <= dist(k) <= FLOOR_BAND_M[1]  # noqa: E731
        if drr <= 0:
            # Reverberant: keep only echoes close to the strongest wall-like one.
            wl = [seg[k] for k in pk if not is_floor(k)]
            if wl:
                pk = [k for k in pk if is_floor(k) or seg[k] >= max(wl) - 6]
        refl = [{"m": round(dist(k), 2), "db": round(float(seg[k]), 1)} for k in pk]
    walls = [r for r in refl if not FLOOR_BAND_M[0] <= r["m"] <= FLOOR_BAND_M[1]]
    floorish = [r for r in refl if FLOOR_BAND_M[0] <= r["m"] <= FLOOR_BAND_M[1]]

    # Schroeder backward integration -> energy decay curve -> RT60 (T20, else T10).
    # Background noise would look like an endless tail, so: estimate the noise from
    # the end of the response, cut where the decay reaches it, subtract it.
    blk = int(0.01 * sr)
    nb = e.size // blk
    env_db = 10 * np.log10(e[:nb * blk].reshape(nb, blk).mean(axis=1) + 1e-20)
    # Noise from just BEFORE the direct sound (the clip starts 150 ms before the
    # chirp): the end of the response can still be ringing in a big hall.
    pre = ir[max(0, k0 - int(0.12 * sr)): max(0, k0 - int(0.01 * sr))] ** 2
    noise_e = float(pre.mean()) if pre.size > int(0.04 * sr) else float(e[int(0.8 * e.size):].mean())
    noise_db_e = 10 * np.log10(noise_e + 1e-20)
    above = np.where(env_db[1:] < noise_db_e + 5)[0]
    cut_blocks = int(above[0]) + 1 if above.size else nb
    dry = cut_blocks <= 5                    # tail hits the noise within ~50 ms
    ec = np.clip(e[:cut_blocks * blk] - noise_e, 0, None)
    edc = np.cumsum(ec[::-1])[::-1]
    edc_db = 10 * np.log10(edc / (edc[0] + 1e-20) + 1e-15)
    rt = None
    if not dry:
        for a, b, method in ((-5, -25, "T20"), (-5, -15, "T10")):
            idx = np.where((edc_db <= a) & (edc_db >= b))[0]
            if idx.size > 10 and edc_db.min() < b - 3:
                slope = np.polyfit(idx / sr, edc_db[idx], 1)[0]
                if slope < 0:
                    rt = (round(60.0 / -slope, 2), method)
                    break
    k50 = int(0.05 * sr)
    return {
        # In a reverberant room (DRR < 0 dB) the first echo hides in the tail:
        # we still show the distance but do not use it as evidence.
        "wall_reliable": bool(walls) and drr > 0,
        "rt60_s": rt[0] if rt else None, "rt60_method": rt[1] if rt else ("dry" if dry else None),
        "dry": bool(dry),
        "drr_db": round(drr, 1),
        "c50_db": round(float(10 * np.log10(e[:k50].sum() / (e[k50:].sum() + 1e-15))), 1),
        "reflections": refl[:8],
        "nearest_wall_m": walls[0]["m"] if walls else None,
        "floor_or_ceiling_m": floorish[0]["m"] if floorish else None,
        "noise_db": round(noise, 1),
    }


def probe(rec, sr, ping_at_s):
    """Recording that contains the chirp starting near ping_at_s -> IR analysis."""
    a = max(int((ping_at_s - 0.15) * sr), 0)
    b = min(int((ping_at_s + config.PROBE["dur"] + 0.8) * sr), rec.size)
    seg = rec[a:b]
    if seg.size < sr * (config.PROBE["dur"] + 0.3):
        return {"ok": False, "why": "recording too short around the chirp"}
    ir = impulse_response(seg, sr)
    out = analyse_ir(ir, sr)
    # Was the chirp actually recorded? Its deconvolved peak must stand out.
    env = np.abs(ir)
    snr = 20 * np.log10(env.max() / (np.median(env) + 1e-12))
    out["ok"] = bool(snr > 25)
    out["peak_snr_db"] = round(float(snr), 1)
    if not out["ok"]:
        out["why"] = "chirp not picked up clearly (volume too low, or echo cancellation on)"
    return out


# ===================================================================== 3. fusion
def size_range_m(rt60):
    """Very rough room size from RT60 (Sabine, cube room, mean absorption 0.15-0.35):
    side ~ 37 * alpha * RT60. Wide on purpose: we do not know the furnishing."""
    if not rt60:
        return None
    return [round(37 * 0.15 * rt60, 1), round(37 * 0.35 * rt60, 1)]


def setting_probs(passive_rt=None, scene=None, probe_res=None):
    """Combine whatever clues we have -> (probs dict, clues list, strength 0..1)."""
    like = np.ones(len(SETTINGS))
    clues = []
    if scene:
        s_small = scene.get("Inside, small room", 0.0)
        s_large = max(scene.get("Inside, large room or hall", 0.0), scene.get("Inside, public space", 0.0))
        s_urban = scene.get("Outside, urban or manmade", 0.0)
        s_rural = scene.get("Outside, rural or natural", 0.0)
        top = max(s_small, s_large, s_urban, s_rural)
        if top >= 0.08:     # below that YAMNet has no opinion
            v = np.array([s_small, s_large, 0.5 * s_urban, 0.5 * s_urban + s_rural]) + 0.05
            like *= (v / v.sum() * 4) ** SCENE_TEMPER
            clues.append(f"sound scene: {max(scene, key=scene.get)} ({top:.2f})")
    if passive_rt:
        like *= np.array([_lognorm(passive_rt, *RT_MODEL_PASSIVE[s]) + 0.02 for s in SETTINGS]) ** TEMPER
        clues.append(f"reverberation from voice ~{passive_rt:.2f} s")
    if probe_res and probe_res.get("ok"):
        if probe_res.get("rt60_s"):
            rt = probe_res["rt60_s"]
            like *= np.array([_lognorm(rt, m, s * 0.8) + 0.02 for m, s in RT_MODEL.values()]) ** TEMPER
            clues.append(f"reverberation from chirp {rt:.2f} s")
        elif probe_res.get("dry"):
            like *= np.array([_lognorm(0.1, m, s * 0.8) + 0.02 for m, s in RT_MODEL.values()]) ** TEMPER
            clues.append("chirp: no reverberant tail (dry, like open air)")
        wall = probe_res.get("nearest_wall_m")
        if wall and probe_res.get("wall_reliable"):
            like *= np.array([_lognorm(wall, *WALL_MODEL[s]) + 0.03 for s in SETTINGS]) ** TEMPER
            clues.append(f"nearest reflecting surface ~{wall:.1f} m")
        elif wall:
            clues.append(f"possible echo at ~{wall:.1f} m (reverberant room: low confidence, not used)")
        elif (probe_res.get("drr_db") or 0) > 0:   # dry: an echo would have been visible
            like *= np.array([NO_WALL[s] for s in SETTINGS]) ** TEMPER
            clues.append("no echo from a wall within ~25 m")
    p = like / like.sum()
    # strength: 0 = no information (uniform), 1 = certain
    ent = -(p * np.log(p + 1e-12)).sum() / math.log(len(p))
    return {s: round(float(v), 3) for s, v in zip(SETTINGS, p)}, clues, round(1 - float(ent), 3)


LABELS = {"indoor_small": "indoors, small room", "indoor_large": "indoors, large hall",
          "outdoor_enclosed": "outdoors, between buildings", "outdoor_open": "outdoors, open ground"}


def describe(p):
    best = max(p, key=p.get)
    indoor = p["indoor_small"] + p["indoor_large"]
    return {"best": best, "label": LABELS[best], "p_best": p[best], "p_indoor": round(indoor, 3)}
