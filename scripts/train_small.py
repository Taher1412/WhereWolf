"""Fine-tune the phone-sized sound model "Near-small" (CED-tiny + drone head).

  drone head      : drone / no drone, DADS shard 4 (drones) + shard 0 (no drone)
  gunfire head    : gunfire / forest background, tropical-gunshot-wda-dataset (another source
                    than the 88 test gunshots)
  distillation    : AST (86M) hears the CLEAN clip; the small model hears it after a simulated
                    radio link (backend/radiosim.py) and learns AST's 527 AudioSet answers
  test (never seen): DADS shard 20 drones + held-out no-drone clips, 88 real gunshots, ESC-50
Data (once, ~600 MB, gitignored): DADS shards 0, 4, 20 under data/eval/dads (eval_danger --fetch
gets shard 4; this script downloads 0 and 20 if missing).

    python -m scripts.train_small            # ~5 min on an RTX 4060
"""
import io
import random
import time

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F

from backend import config, smallaudio as S
from backend.radiosim import radio

SR = 16000
DADS = config.DATA_DIR / "eval" / "dads" / "data"
OUT = S.MODEL_DIR
CROP = 2 * SR
N_PER_CLASS = 3000
EPOCHS, BATCH = 2, 32
LAMBDA = 3.0           # weight of the distillation loss: keeps the 527 AudioSet answers close to AST
N_GUN = 2000           # gunshot clips and background clips each
GUN = config.DATA_DIR / "eval" / "gunwda" / "default" / "train" / "0000.parquet"


def load_gun(n, seed):
    import pyarrow.parquet as pq
    if not GUN.exists():
        from huggingface_hub import hf_hub_download
        hf_hub_download("aazmaine25/tropical-gunshot-wda-dataset", "default/train/0000.parquet", repo_type="dataset",
                        revision="refs/convert/parquet", local_dir=GUN.parents[2])
    rows = pq.read_table(GUN).to_pylist()
    rng = np.random.default_rng(seed)
    pos = [r for r in rows if r["label"] == 1]
    neg = [r for r in rows if r["label"] == 0]
    out = []
    for group, lab in ((pos, 1.0), (neg, 0.0)):
        for i in rng.permutation(len(group))[:n]:
            w, sr = sf.read(io.BytesIO(group[i]["audio"]["bytes"]), dtype="float32")
            w = w.mean(1) if w.ndim > 1 else w
            if sr != SR:
                from scipy.signal import resample_poly
                w = resample_poly(w, SR, sr)
            out.append((w[: 3 * SR].astype(np.float16), lab))
    return out


def shard(k):
    p = DADS / f"train-{k:05d}-of-00039.parquet"
    if not p.exists():
        from huggingface_hub import hf_hub_download
        hf_hub_download("geronimobasso/drone-audio-detection-samples", f"data/train-{k:05d}-of-00039.parquet",
                        repo_type="dataset", local_dir=DADS.parent)
    return p


def load(k, n, seed, skip=0, max_s=3.0):
    import pyarrow.parquet as pq
    rows = pq.read_table(shard(k)).to_pylist()
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows))[skip:skip + n]
    out = []
    for i in idx:
        w, sr = sf.read(io.BytesIO(rows[i]["audio"]["bytes"]), dtype="float32")
        w = w.mean(1) if w.ndim > 1 else w
        if len(w) > max_s * SR:
            a = rng.integers(0, len(w) - int(max_s * SR))
            w = w[a:a + int(max_s * SR)]
        out.append(w.astype(np.float16))
    return out


def crop(w, rng):
    w = np.asarray(w, np.float32)
    if len(w) < CROP:
        w = np.tile(w, int(np.ceil(CROP / max(1, len(w)))))
    a = rng.integers(0, len(w) - CROP + 1)
    return w[a:a + CROP] * rng.uniform(0.3, 1.5)


def degrade(w, rng):
    r = rng.random()
    if r < 0.35:
        return w                                   # phone microphone, no radio
    return radio(w, "analog" if r < 0.7 else "digital", rng=rng)


def main():
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    pos = load(4, N_PER_CLASS, 1)
    neg = load(0, N_PER_CLASS, 2)
    print(f"data: {len(pos)} drone + {len(neg)} no-drone clips ({time.time() - t0:.0f} s)")
    gun = load_gun(N_GUN, 3)
    print(f"      + {sum(1 for _, l in gun if l)} gunshot + {sum(1 for _, l in gun if not l)} forest-background clips")
    X = pos + neg + [w for w, _ in gun]
    # two labels per clip: (drone, gunfire)
    Y = np.array([[1, 0]] * len(pos) + [[0, 0]] * len(neg) + [[0, l] for _, l in gun], np.float32)

    from backend import acoustic
    teacher = acoustic._load_ast()                # AST on the GPU (fp16), the same one the server uses
    assert teacher, "AST not available"
    T, tfe = teacher["m"], teacher["fe"]
    m, head = S.build()
    m.to(dev).train()
    head.to(dev).train()
    from transformers import AutoFeatureExtractor
    fe = AutoFeatureExtractor.from_pretrained(S.CED_ID, trust_remote_code=True, local_files_only=True)
    opt = torch.optim.AdamW([{"params": m.parameters(), "lr": 2e-5},
                             {"params": head.parameters(), "lr": 1e-3}], weight_decay=1e-4)
    steps = EPOCHS * (len(X) // BATCH)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[2e-5, 1e-3], total_steps=steps, pct_start=0.1)
    step = 0
    for ep in range(EPOCHS):
        order = rng.permutation(len(X))
        for b in range(len(X) // BATCH):
            ids = order[b * BATCH:(b + 1) * BATCH]
            clean = [crop(X[i], rng) for i in ids]
            noisy = [degrade(w, rng) for w in clean]
            with torch.no_grad():
                tin = tfe(clean, sampling_rate=SR, return_tensors="pt")["input_values"].to(dev, T.dtype)
                tprob = torch.sigmoid(T(tin).logits.float())
            mel = S.features(noisy, fe).to(dev)
            a, d = S.forward(m, head, mel)
            y = torch.tensor(Y[ids], device=dev)
            l_drone = F.binary_cross_entropy_with_logits(d, y)        # both heads
            l_kd = F.binary_cross_entropy(a.clamp(1e-6, 1 - 1e-6), tprob)
            loss = l_drone + LAMBDA * l_kd
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            step += 1
            if step % 25 == 0:
                acc = float(((d > 0).float() == y).float().mean())
                print(f"ep {ep} step {step}/{steps}  heads loss {l_drone.item():.3f} (batch acc {acc:.2f})  "
                      f"distill {l_kd.item():.4f}  {time.time() - t0:.0f} s", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    m.cpu().eval()
    head.cpu().eval()
    torch.save({"ced": m.state_dict(), "head": head.state_dict(),
                "note": "CED-tiny + drone and gunfire heads, distilled from AST with radio augmentation (scripts/train_small.py)"},
               OUT / "near_small.pt")
    print("saved", OUT / "near_small.pt", f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
