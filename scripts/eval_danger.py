"""How well do we hear danger? Real recordings, no synthetic audio.

  gunfire    88 real gunshot recordings (HEAR "Gunshot triangulation", mteb/GunshotTriangulationHear)
  drone      150 drone clips (DADS, geronimobasso/drone-audio-detection-samples, one shard)
  no danger  85 ESC-50 clips (dogs, rain, wind, door knocks, helicopter, airplane, engine,
             train, bells, hand saw...): every alert on them is a false alarm

Downloads (once, ~90 MB, gitignored under data/eval/):
  python -m scripts.eval_danger --fetch
Run:
  python -m scripts.eval_danger

Caveat: the drone detector may have been trained on DADS (its card does not say), so the
drone recall is optimistic; the ESC-50 false-alarm rate is the honest number.
"""
import glob
import io
import sys
from collections import Counter, defaultdict

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from backend import acoustic, config

EVAL = config.DATA_DIR / "eval"
GUN = EVAL / "gunshot" / "data" / "train-00000-of-00001.parquet"
DADS = EVAL / "dads" / "data" / "train-00004-of-00039.parquet"
ESC_NAMES = {0: "dog", 10: "rain", 11: "sea waves", 13: "crickets", 14: "birds", 16: "wind",
             30: "door knock", 32: "keyboard", 38: "clock tick", 40: "helicopter", 42: "siren",
             43: "car horn", 44: "engine", 45: "train", 46: "church bells", 47: "airplane",
             49: "hand saw"}


def fetch():
    from huggingface_hub import hf_hub_download, snapshot_download
    hf_hub_download("mteb/GunshotTriangulationHear", "data/train-00000-of-00001.parquet",
                    repo_type="dataset", local_dir=EVAL / "gunshot")
    hf_hub_download("geronimobasso/drone-audio-detection-samples", "data/train-00004-of-00039.parquet",
                    repo_type="dataset", local_dir=EVAL / "dads")
    snapshot_download(acoustic.DRONE_ID, allow_patterns=["*.json", "model.safetensors"])
    print("ESC-50 clips: python -m scripts.eval_audio --fetch")


def to16k(w, sr):
    w = w.mean(axis=1) if w.ndim > 1 else w
    return (resample_poly(w, 16000, sr) if sr != 16000 else w).astype(np.float32)


def parquet_clips(path, n=None, seed=0):
    import pyarrow.parquet as pq
    rows = pq.read_table(path).to_pylist()
    if n and n < len(rows):
        rows = [rows[i] for i in np.random.default_rng(seed).choice(len(rows), n, replace=False)]
    for r in rows:
        w, sr = sf.read(io.BytesIO(r["audio"]["bytes"]), dtype="float32")
        yield to16k(w, sr)


def classes(wave):
    """Danger classes the pipeline raises on this clip (same code path as /api/audio)."""
    if wave.size < 16000:                       # analyse() needs >= 1 s: loop short clips
        wave = np.tile(wave, int(np.ceil(16000 * 1.5 / wave.size)))
    return {a["class"] for a in acoustic._analyse_wave(wave, "ambient")["alerts"]}


def main():
    if "--fetch" in sys.argv:
        fetch()
        return
    print(f"thresholds: gunfire/explosion score >= {config.DANGER_SOUND_MIN}, drone p >= {config.DRONE_MIN}")
    print("AST:", "on" if acoustic._load_ast() else "off", "| drone detector:",
          "on" if acoustic._load_drone() else "OFF (not downloaded)")

    if GUN.exists():
        res = [classes(w) for w in parquet_clips(GUN)]
        hit = np.mean(["small_arms" in r for r in res])
        any_ = np.mean([bool(r & {"small_arms", "explosion"}) for r in res])
        print(f"\nGunshots ({len(res)} real recordings): small-arms alert {hit:.0%}, "
              f"small-arms or explosion {any_:.0%}")

    if DADS.exists() and acoustic._load_drone():
        res = [classes(w) for w in parquet_clips(DADS, n=150)]
        print(f"Drones (150 DADS clips): drone alert {np.mean(['drone' in r for r in res]):.0%}")

    esc = sorted(glob.glob(str(EVAL / "esc50" / "*.wav")))
    if esc:
        fa, per = Counter(), defaultdict(list)
        for p in esc:
            c = int(p.rsplit("-", 1)[1][:-4])
            w, sr = sf.read(p, dtype="float32")
            r = classes(to16k(w, sr))
            per[ESC_NAMES.get(c, c)].append(bool(r))
            fa.update(r)
        n = len(esc)
        rate = np.mean([x for v in per.values() for x in v])
        by_type = ", ".join(f"{k} {v / n:.0%}" for k, v in fa.items()) or "none"
        print(f"\nNo-danger ESC-50 ({n} clips): false alarm on {rate:.0%} of clips (by type: {by_type})")
        bad = {k: f"{sum(v)}/{len(v)}" for k, v in per.items() if any(v)}
        if bad:
            print("  false alarms on:", bad)


if __name__ == "__main__":
    main()
