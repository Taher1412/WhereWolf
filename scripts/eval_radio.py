"""Does threat detection survive a radio link, and does the phone-sized model keep up?

Systems
  big         the laptop pipeline today: YAMNet + AST (86M) + drone AST (86M)
  ced-tiny    the plain 5.5M phone-sized model (AudioSet classes only, no drone class)
  near-small  CED-tiny fine-tuned by scripts/train_small.py (drone head + distilled from AST
              on radio-degraded audio)
Conditions  clean (phone microphone), analog radio, digital radio (backend/radiosim.py)
Test clips (never used in training)
  88 real gunshots | 150 drone clips (DADS shard 20) | 150 no-drone DADS clips (held out of
  shard 0) | 85 ESC-50 clips with no danger (helicopter, airplane, engine, rain, wind, ...)

    python -m scripts.eval_radio [--quick] [--only near-small]
"""
import glob
import sys

import numpy as np
import soundfile as sf

from backend import acoustic, config, smallaudio
from backend.radiosim import radio
from scripts.eval_danger import EVAL, GUN, parquet_clips, to16k
from scripts.train_small import N_PER_CLASS, load

GROUPS = smallaudio.GROUPS


def big(w):
    if w.size < 16000:
        w = np.tile(w, int(np.ceil(16000 * 1.5 / w.size)))
    return {a["class"] for a in acoustic._analyse_wave(w, "ambient")["alerts"]}


_plain = None


def plain_ced(w):
    global _plain
    import torch
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    if _plain is None:
        m = AutoModelForAudioClassification.from_pretrained(smallaudio.CED_ID, trust_remote_code=True,
                                                            local_files_only=True).eval()
        fe = AutoFeatureExtractor.from_pretrained(smallaudio.CED_ID, trust_remote_code=True, local_files_only=True)
        _plain = (m, fe, {m.config.id2label[i]: i for i in range(527)})
    m, fe, lab = _plain
    w = w if len(w) >= 16000 else np.pad(w, (0, 16000 - len(w)))
    chunks = [w[i:i + 160000] for i in range(0, max(1, len(w) - 8000), 160000)]
    with torch.no_grad():
        p = m(input_values=smallaudio.features(chunks, fe)).logits.max(0).values.numpy()
    return {c for c, names in GROUPS.items() if max(p[lab[n]] for n in names) >= config.DANGER_SOUND_MIN}


def near_small(w):
    return {t["class"] for t in smallaudio.threats(w)}


def main():
    quick = "--quick" in sys.argv
    n = 40 if quick else 150
    sets = {"gunshots": list(parquet_clips(GUN))[: (30 if quick else 999)],
            "drones": [np.asarray(x, np.float32) for x in load(20, n, 7)],
            "no-drone DADS": [np.asarray(x, np.float32) for x in load(0, n, 2, skip=N_PER_CLASS)]}
    esc = sorted(glob.glob(str(EVAL / "esc50" / "*.wav")))
    sets["ESC-50 no danger"] = [to16k(*sf.read(p, dtype="float32")[::1]) for p in esc][: (30 if quick else 999)]
    systems = {"big": big, "ced-tiny": plain_ced, "near-small": near_small}
    if "--only" in sys.argv:                  # e.g. --only near-small (after retraining)
        keep = sys.argv[sys.argv.index("--only") + 1].split(",")
        systems = {k: v for k, v in systems.items() if k in keep}
    rng = np.random.default_rng(0)
    conds = {"clean": lambda w: w, "analog radio": lambda w: radio(w, "analog", rng=rng),
             "digital radio": lambda w: radio(w, "digital", rng=rng)}
    print(f"thresholds: gunfire/explosion >= {config.DANGER_SOUND_MIN}, drone >= {config.DRONE_MIN}")
    rows = []
    for cname, cf in conds.items():
        degraded = {k: [cf(w) for w in v] for k, v in sets.items()}
        for sname, f in systems.items():
            res = {k: [f(w) for w in v] for k, v in degraded.items()}
            gun = np.mean([bool(r & {"small_arms", "explosion"}) for r in res["gunshots"]])
            dro = np.mean(["drone" in r for r in res["drones"]])
            fa1 = np.mean([bool(r) for r in res["no-drone DADS"]])
            fa2 = np.mean([bool(r) for r in res["ESC-50 no danger"]])
            rows.append((cname, sname, gun, dro, fa1, fa2))
            print(f"{cname:14} {sname:11} gunfire {gun:4.0%}  drone {dro:4.0%}  "
                  f"false alarm: DADS {fa1:4.0%}  ESC-50 {fa2:4.0%}", flush=True)
    print("\n| condition | system | gunshots detected | drones detected | false alarms (no-drone DADS) | false alarms (ESC-50) |")
    print("|---|---|---|---|---|---|")
    for c, s, g, d, a, b in rows:
        print(f"| {c} | {s} | {g:.0%} | {d:.0%} | {a:.0%} | {b:.0%} |")


if __name__ == "__main__":
    main()
