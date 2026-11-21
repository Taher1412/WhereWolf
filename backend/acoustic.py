"""Environmental sound -> structured acoustic observations. Runs locally, no cloud.

analyse(audio_bytes) -> dict:
  events     sound groups the classifier heard (rail, traffic, bells, machinery, nature),
             each with the raw model score and the labels behind it
  context    groups that are only described, never used for position
             (aircraft, sirens, crowd): they move, or are heard everywhere
  alerts     explosion / gunfire-like sounds (shown to the coordinator, never used for position)
  features   spectral numbers computed from the STFT (descriptive only)
  audio_quality  good | poor | unusable, with the reasons

How:
  1. ffmpeg decodes whatever the phone sent (webm/opus, mp4/aac, wav) to 16 kHz mono.
  2. YAMNet (Google, trained on AudioSet, 521 classes, 4 MB) scores 0.975 s windows
     every 0.48 s.
  3. Windows where speech dominates are dropped, so the operator's voice (or our own
     read-back) is not taken as the environment.
  4. Per group, score = mean of the 2 best remaining windows (one loud frame is not enough).

The scores are YAMNet outputs, NOT calibrated probabilities. to_constraints()
turns them into soft evidence with conservative thresholds that still need
calibrating on real field recordings.
"""
import subprocess
import time

import numpy as np

from . import config

SR = 16000
WIN = 15600          # YAMNet input: 0.975 s
HOP = 7680           # 0.48 s
MODEL_PATH = config.DATA_DIR / "models" / "yamnet.tflite"
LABELS_PATH = config.DATA_DIR / "models" / "yamnet_labels.txt"

# AudioSet label names -> our groups. Names, not indices, so this survives model swaps.
GROUPS = {
    # used for position (see soundscape.py)
    "rail": ["Rail transport", "Train", "Train whistle", "Train horn", "Railroad car, train wagon",
             "Train wheels squealing"],
    "traffic": ["Traffic noise, roadway noise", "Motor vehicle (road)", "Car", "Car passing by",
                "Truck", "Bus", "Motorcycle", "Vehicle horn, car horn, honking",
                "Air horn, truck horn", "Accelerating, revving, vroom"],
    "bells": ["Church bell", "Bell", "Tubular bells", "Change ringing (campanology)"],
    "machinery": ["Jackhammer", "Power tool", "Drill", "Sawing", "Hammer"],
    "nature": ["Bird", "Bird vocalization, bird call, bird song", "Chirp, tweet", "Pigeon, dove",
               "Crow", "Insect", "Cricket", "Rustling leaves"],
    # described only
    "aircraft": ["Aircraft", "Aircraft engine", "Jet engine", "Helicopter",
                 "Fixed-wing aircraft, airplane"],
    "siren": ["Siren", "Civil defense siren", "Emergency vehicle", "Police car (siren)",
              "Ambulance (siren)", "Fire engine, fire truck (siren)"],
    "crowd": ["Crowd", "Children playing", "Children shouting", "Chatter"],
    # alert only
    "explosion": ["Explosion", "Gunshot, gunfire", "Machine gun", "Artillery fire", "Boom"],
    # used to clean the clip
    "speech": ["Speech", "Child speech, kid speaking", "Conversation", "Narration, monologue",
               "Babbling", "Speech synthesizer", "Hubbub, speech noise, speech babble"],
    "wind": ["Wind noise (microphone)", "Wind"],
}
GEO_GROUPS = ["rail", "traffic", "bells", "machinery", "nature"]
CONTEXT_GROUPS = ["aircraft", "siren", "crowd"]

SPEECH_DROP = 0.45   # drop a window when its speech score is above this


class AcousticUnavailable(Exception):
    pass


# ------------------------------------------------------------------ model
_model = None


def _load():
    global _model
    if _model is not None:
        return _model
    if not MODEL_PATH.exists():
        raise AcousticUnavailable("YAMNet model missing: run python scripts/fetch_models.py")
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
    import os
    # 1 thread: ~270 ms per window; 8 threads: ~110 ms (measured on the team laptop).
    it = Interpreter(model_path=str(MODEL_PATH), num_threads=min(8, os.cpu_count() or 4))
    it.allocate_tensors()
    labels = LABELS_PATH.read_text(encoding="utf-8").splitlines()
    idx = {name: i for i, name in enumerate(labels)}
    groups = {g: [idx[n] for n in names if n in idx] for g, names in GROUPS.items()}
    _model = {"it": it, "in": it.get_input_details()[0]["index"],
              "out": it.get_output_details()[0]["index"], "labels": labels, "groups": groups}
    return _model


# ------------------------------------------------------------------ AST (second opinion)
# Audio Spectrogram Transformer (MIT, AudioSet mAP 0.459 vs ~0.31 for YAMNet),
# 87 M parameters: slower, more accurate. Scores the whole clip at once.
AST_ID = "MIT/ast-finetuned-audioset-10-10-0.4593"
_ast = None


def _load_ast():
    """Returns the AST bundle, or None if it is off / not downloaded."""
    global _ast
    if _ast is not None:
        return _ast or None
    if not config.AST_ENABLED:
        _ast = False
        return None
    try:
        import torch
        from transformers import ASTFeatureExtractor, ASTForAudioClassification
        fe = ASTFeatureExtractor.from_pretrained(AST_ID, local_files_only=True)
        m = ASTForAudioClassification.from_pretrained(AST_ID, local_files_only=True).eval()
        dev = "cuda" if torch.cuda.is_available() and config.AST_DEVICE != "cpu" else "cpu"
        if dev == "cuda":
            m = m.half()
        m.to(dev)
        labels = [m.config.id2label[i] for i in range(m.config.num_labels)]
        idx = {n: i for i, n in enumerate(labels)}
        groups = {g: [idx[n] for n in names if n in idx] for g, names in GROUPS.items()}
        _ast = {"fe": fe, "m": m, "dev": dev, "labels": labels, "groups": groups, "idx": idx, "torch": torch}
    except Exception as e:     # not downloaded, no torch...: YAMNet alone
        print("AST unavailable, YAMNet only:", e)
        _ast = False
    return _ast or None


def ast_scores(wave):
    """(527,) AST sigmoid scores for a 16 kHz clip, or None."""
    a = _load_ast()
    if a is None or wave.size < SR * 0.5:
        return None
    x = a["fe"](wave.astype(np.float32), sampling_rate=SR, return_tensors="pt")["input_values"]
    x = x.to(a["dev"], dtype=next(a["m"].parameters()).dtype)
    with a["torch"].no_grad():
        logits = a["m"](input_values=x).logits[0].float()
    return a["torch"].sigmoid(logits).cpu().numpy()


def scores(wave):
    """(n_windows, 521) YAMNet scores for a 16 kHz mono float32 wave."""
    m = _load()
    if wave.size < WIN:
        wave = np.pad(wave, (0, WIN - wave.size))
    out = []
    for s in range(0, wave.size - WIN + 1, HOP):
        m["it"].set_tensor(m["in"], wave[s:s + WIN].astype(np.float32))
        m["it"].invoke()
        out.append(m["it"].get_tensor(m["out"])[0].copy())
    return np.array(out)


# ------------------------------------------------------------------ audio in
def decode(data: bytes, sr=SR) -> np.ndarray:
    """Any audio file -> mono float32 in [-1, 1] at `sr` (via ffmpeg)."""
    try:
        p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                            "-f", "f32le", "-ac", "1", "-ar", str(sr), "pipe:1"],
                           input=data, capture_output=True, timeout=20)
    except FileNotFoundError:
        raise AcousticUnavailable("ffmpeg not found on PATH")
    if p.returncode != 0:
        raise ValueError("could not decode audio: " + p.stderr.decode(errors="ignore")[:200])
    return np.frombuffer(p.stdout, np.float32).copy()


# ------------------------------------------------------------------ features
def spectral_features(wave):
    """Classic STFT features. Descriptive: they tell you what the clip is like,
    not where it was recorded."""
    if wave.size < 2048:
        return {}
    n_fft, hop = 1024, 512
    frames = np.lib.stride_tricks.sliding_window_view(wave, n_fft)[::hop] * np.hanning(n_fft)
    mag = np.abs(np.fft.rfft(frames, axis=1)) + 1e-10        # |STFT|, shape (t, f)
    f = np.fft.rfftfreq(n_fft, 1 / SR)
    p = mag / mag.sum(axis=1, keepdims=True)
    centroid = (p * f).sum(axis=1)
    bandwidth = np.sqrt((p * (f - centroid[:, None]) ** 2).sum(axis=1))
    cum = np.cumsum(mag ** 2, axis=1)
    rolloff = f[np.argmax(cum >= 0.85 * cum[:, -1:], axis=1)]
    flatness = np.exp(np.log(mag).mean(axis=1)) / mag.mean(axis=1)
    energy = (mag ** 2).sum(axis=1)
    low = (mag[:, f < 250] ** 2).sum(axis=1) / energy
    zcr = np.mean(np.abs(np.diff(np.sign(wave))) > 0)
    # Temporal pattern: how steady is the loudness? (traffic hum is steady, a passing train is not)
    db = 10 * np.log10(energy + 1e-12)
    return {
        "spectral_centroid_hz": round(float(np.median(centroid)), 0),
        "spectral_bandwidth_hz": round(float(np.median(bandwidth)), 0),
        "rolloff85_hz": round(float(np.median(rolloff)), 0),
        "spectral_flatness": round(float(np.median(flatness)), 3),
        "low_freq_ratio": round(float(np.median(low)), 3),      # share of energy below 250 Hz
        "zero_crossing_rate": round(float(zcr), 4),
        "loudness_spread_db": round(float(np.percentile(db, 90) - np.percentile(db, 10)), 1),
        # A single phone mic in an unknown room gives no reliable blind reverberation
        # estimate, so we do not report one.
        "reverberation_estimate": None,
    }


SCENE_LABELS = ["Inside, small room", "Inside, large room or hall", "Inside, public space",
                "Outside, urban or manmade", "Outside, rural or natural"]


# ------------------------------------------------------------------ main entry
def analyse(data: bytes, ping_at=None, kind="ambient"):
    """kind: 'ambient' (Listen button, operator quiet) or 'voice' (a push-to-talk
    report: the voice itself is the test signal for the room's reverberation).
    ping_at: seconds into the clip where the phone played the chirp, or None."""
    from . import spatial
    t0 = time.time()
    wave = decode(data)
    probe_res = None
    if ping_at is not None:
        probe_res = spatial.probe(decode(data, config.PROBE["sr"]), config.PROBE["sr"], ping_at)
        # Cut the chirp (and its echo tail) out before classifying / measuring decays.
        a, b = int((ping_at - 0.05) * SR), int((ping_at + config.PROBE["dur"] + 0.6) * SR)
        wave = np.concatenate([wave[:max(a, 0)], wave[b:]])
    out = _analyse_wave(wave, kind)
    # ---- spatial: what kind of space?
    passive_rt, decays = spatial.blind_rt60(wave, SR)
    scene = out.pop("_scene", None)
    p, clues, strength = spatial.setting_probs(passive_rt, scene, probe_res)
    no_wall = dict(probe_res, nearest_wall_m=None, wall_reliable=False) if probe_res else None
    p_nw, _, strength_nw = spatial.setting_probs(passive_rt, scene, no_wall)
    rt = (probe_res or {}).get("rt60_s") or passive_rt
    out["space"] = {
        "p": p, "clues": clues, "strength": strength, **spatial.describe(p),
        "rt60_passive_s": round(passive_rt, 2) if passive_rt else None,
        "n_decays": len(decays), "probe": probe_res,
        "room_size_m": spatial.size_range_m(rt) if p["indoor_small"] + p["indoor_large"] > 0.5 else None,
        "scene_scores": scene,
        "_p_for_grid": p_nw, "_strength_for_grid": strength_nw,   # wall clue used separately
    }
    out["kind"] = kind
    out["ms"] = int((time.time() - t0) * 1000)
    return out


def _analyse_wave(wave, kind):
    dur = wave.size / SR
    out = {"model": "YAMNet (AudioSet, 521 classes), local", "duration_s": round(dur, 2),
           "events": [], "context": [], "alerts": [], "features": {}, "audio_quality": "unusable",
           "quality_notes": [], "speech_fraction": None, "usable_s": 0.0}
    if dur < 1.0:
        out["quality_notes"].append("clip shorter than 1 s")
        return out

    rms = float(np.sqrt(np.mean(wave ** 2)))
    rms_db = 20 * np.log10(rms + 1e-9)
    clip_frac = float(np.mean(np.abs(wave) > 0.99))
    out["level_dbfs"] = round(rms_db, 1)
    if rms_db < -70:
        out["quality_notes"].append("near silence: microphone muted or blocked?")
        return out

    S = scores(wave)
    m = _load()
    g = m["groups"]
    gs = {name: S[:, ids].max(axis=1) if ids else np.zeros(len(S)) for name, ids in g.items()}
    # Scene scores describe the space, with or without speech: median over all windows.
    lab = {n: i for i, n in enumerate(m["labels"])}
    out["_scene"] = {n: round(float(np.median(S[:, lab[n]])), 3) for n in SCENE_LABELS if n in lab}

    speech = gs["speech"]
    keep = speech < SPEECH_DROP
    out["speech_fraction"] = round(float(1 - keep.mean()), 2)
    usable = float(keep.sum()) * HOP / SR
    out["usable_s"] = round(usable, 2)

    notes = out["quality_notes"]
    if clip_frac > 0.01:
        notes.append(f"clipping on {clip_frac:.0%} of samples")
    wind = float(np.median(gs["wind"]))
    if wind > 0.3:
        notes.append("wind noise on the microphone")
    if keep.mean() < 0.5 and kind == "ambient":
        notes.append("mostly speech: ask the operator to stay quiet while listening")
    if usable < 1.0:
        notes.append("less than 1 s without speech")
        out["audio_quality"] = "unusable"
    else:
        out["audio_quality"] = "poor" if notes else "good"

    # Explosion-like sounds: checked on every window (they are loud and short).
    ex = float(gs["explosion"].max())
    if ex >= 0.3:
        top = _top_labels(S, g["explosion"], np.ones(len(S), bool))
        out["alerts"].append({"class": "explosion_or_gunfire", "score": round(ex, 2), "labels": top})

    if out["audio_quality"] != "unusable":
        # Second opinion from AST on the same speech-free audio.
        A = ast_scores(wave if keep.all() else _kept_audio(wave, keep)) if config.AST_ENABLED else None
        a = _load_ast() if A is not None else None
        if A is not None:
            out["model"] = f"YAMNet + AST ensemble (weights {1 - config.AST_WEIGHT:.1f}/{config.AST_WEIGHT:.1f}), local"
            scene = out["_scene"]
            for n in SCENE_LABELS:
                if n in a["idx"]:
                    scene[n] = round((1 - config.AST_WEIGHT) * scene.get(n, 0) + config.AST_WEIGHT * float(A[a["idx"][n]]), 3)
            ex_a = float(A[a["groups"]["explosion"]].max()) if a["groups"]["explosion"] else 0.0
            if ex_a >= 0.3 and not out["alerts"]:
                out["alerts"].append({"class": "explosion_or_gunfire", "score": round(ex_a, 2), "labels": [["AST", round(ex_a, 2)]]})
        out["per_model"] = {}
        for name in GEO_GROUPS + CONTEXT_GROUPS:
            v = np.sort(gs[name][keep])[::-1]
            y = float(v[:2].mean()) if v.size else 0.0
            sc = y
            if A is not None and a["groups"][name]:
                s_ast = float(A[a["groups"][name]].max())
                sc = (1 - config.AST_WEIGHT) * y + config.AST_WEIGHT * s_ast
                out["per_model"][name] = {"yamnet": round(y, 2), "ast": round(s_ast, 2)}
            if sc < 0.05:
                continue
            ev = {"class": name, "score": round(sc, 2), "labels": _top_labels(S, g[name], keep)}
            (out["events"] if name in GEO_GROUPS else out["context"]).append(ev)
        out["events"].sort(key=lambda e: -e["score"])
        out["context"].sort(key=lambda e: -e["score"])
        out["features"] = spectral_features(wave if keep.all() else _kept_audio(wave, keep))
    return out


def _kept_audio(wave, keep):
    parts = [wave[i * HOP: i * HOP + WIN] for i in np.where(keep)[0]]
    return np.concatenate(parts) if parts else wave[:0]


def _top_labels(S, ids, keep, n=3):
    if not ids or not keep.any():
        return []
    labels = _load()["labels"]
    sub = S[keep][:, ids].max(axis=0)
    order = np.argsort(sub)[::-1][:n]
    return [[labels[ids[i]], round(float(sub[i]), 2)] for i in order if sub[i] >= 0.05]


# ------------------------------------------------------------------ -> evidence
def to_constraints(an):
    """Acoustic analysis -> 'hear' constraints for the localisation grid.

    q = how sure we are the sound was really there, from the raw score with
    conservative thresholds (ACOUSTIC_SCORE_LO/HI in config). Groups that were
    NOT heard also give (weak) evidence, but only when the clip is good: a quiet
    4 s clip near a railway is normal, so soundscape.py makes that evidence weak.
    """
    out = []
    sp = an.get("space") or {}
    # Kind of space: only if the clues say something (strength), never from a dead clip.
    if sp and sp.get("_strength_for_grid", 0) >= 0.05 and an.get("level_dbfs", -99) > -70:
        out.append({"kind": "setting", "p": sp["_p_for_grid"], "source": "audio", "w": 1.0})
    pr = sp.get("probe") or {}
    p = sp.get("p") or {}
    if pr.get("ok") and pr.get("wall_reliable") and p.get("outdoor_enclosed", 0) + p.get("outdoor_open", 0) > 0.5:
        out.append({"kind": "reflector", "distance_m": pr["nearest_wall_m"], "source": "audio", "w": 1.0})
    if an.get("audio_quality") == "unusable" or an.get("kind") == "voice":
        return out          # sound events only from a quiet Listen clip
    lo, hi = config.ACOUSTIC_SCORE_LO, config.ACOUSTIC_SCORE_HI
    good = an["audio_quality"] == "good"
    heard = {e["class"]: e["score"] for e in an["events"]}
    for g in GEO_GROUPS:
        s = heard.get(g, 0.0)
        q = float(np.clip((s - lo[g]) / (hi[g] - lo[g]), 0, 1))
        if q == 0 and not good:
            continue
        out.append({"kind": "hear", "cls": g, "q": round(q, 2), "source": "audio",
                    "w": 1.0 if good else 0.5, "score": s})
    return out
