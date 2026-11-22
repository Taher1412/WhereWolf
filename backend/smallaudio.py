"""Phone-sized sound model: CED-tiny (5.5M parameters, AudioSet 527 classes) + drone and
gunfire heads.

Fine-tuned by scripts/train_small.py ("Near-small"):
  - drone / no drone, trained on DADS; gunfire / no gunfire, trained on the tropical-forest
    gunshot set (Katsis et al. 2022, augmented: aazmaine25/tropical-gunshot-wda-dataset);
  - distilled from the big AST model: AST hears the CLEAN clip, the small model hears the
    same clip after a simulated radio link (radiosim.py) and learns to give AST's answers,
    so it keeps AST's accuracy AND copes with radio audio.
Runs in ~15 ms per clip on a CPU, so it fits a phone (exported to ONNX) and the laptop
uses it on audio received over the radio, where the big models were never trained.
"""
import numpy as np

from . import config

MODEL_DIR = config.DATA_DIR / "models" / "near-small"
CED_ID = "mispeech/ced-tiny"
SR = 16000
GROUPS = {"small_arms": ["Gunshot, gunfire", "Machine gun", "Fusillade", "Cap gun"],
          "explosion": ["Explosion", "Artillery fire", "Boom"]}

_m = None


class NearSmall:
    def __init__(self, base, head):
        self.base, self.head = base, head


def build(trainable=True):
    """CED-tiny + 2 heads, drone and gunfire (LayerNorm + Linear on the mean-pooled 192-d features)."""
    import torch
    from transformers import AutoModelForAudioClassification
    m = AutoModelForAudioClassification.from_pretrained(CED_ID, trust_remote_code=True, local_files_only=True)
    head = torch.nn.Sequential(torch.nn.LayerNorm(192), torch.nn.Linear(192, 2))
    return m, head


def forward(m, head, mel):
    """mel (B, 64, T) -> (AudioSet probabilities (B, 527), logits (B, 2): drone, gunfire)."""
    h = m.encoder(mel).logits                 # (B, tokens, 192)
    pooled = h.mean(1)
    audioset = m.outputlayer(pooled).sigmoid()
    return audioset, head(pooled)


def features(waves, fe=None):
    from transformers import AutoFeatureExtractor
    fe = fe or AutoFeatureExtractor.from_pretrained(CED_ID, trust_remote_code=True, local_files_only=True)
    return fe([np.asarray(w, np.float32) for w in waves], sampling_rate=SR, return_tensors="pt")["input_values"]


def load():
    """The fine-tuned model if trained, else plain CED-tiny (no drone head)."""
    global _m
    if _m is None:
        import torch
        from transformers import AutoFeatureExtractor
        m, head = build()
        p = MODEL_DIR / "near_small.pt"
        trained = p.exists()
        if trained:
            sd = torch.load(p, map_location="cpu")
            m.load_state_dict(sd["ced"])
            head.load_state_dict(sd["head"])
        m.eval(), head.eval()
        fe = AutoFeatureExtractor.from_pretrained(CED_ID, trust_remote_code=True, local_files_only=True)
        names = [m.config.id2label[i] for i in range(len(m.config.id2label))]
        _m = {"m": m, "head": head if trained else None, "fe": fe, "names": names, "trained": trained}
    return _m


def scores(wave, win_s=10.0):
    """One clip -> {"audioset": (527,), "drone": p or None}. Long clips: max over 10 s windows."""
    import torch
    M = load()
    w = np.asarray(wave, np.float32)
    n = int(win_s * SR)
    chunks = [w[i:i + n] for i in range(0, max(1, len(w) - SR // 2), n)] or [w]
    chunks = [c if len(c) >= SR else np.pad(c, (0, SR - len(c))) for c in chunks]
    mel = features(chunks, M["fe"])
    with torch.no_grad():
        if M["head"] is not None:
            a, d = forward(M["m"], M["head"], mel)
        else:
            a, d = M["m"](input_values=mel).logits, None      # plain CED-tiny: probabilities
    out = {"audioset": a.max(0).values.numpy(), "drone": None, "gunfire": None}
    if d is not None:
        p = torch.sigmoid(d).max(0).values
        out["drone"], out["gunfire"] = float(p[0]), float(p[1])
    return out


def threats(wave, sound_min=None, drone_min=None):
    """Danger classes for one clip, like acoustic.danger_sounds but with the small model."""
    M = load()
    s = scores(wave)
    lab = {n: i for i, n in enumerate(M["names"])}
    out = []
    for cls, names in GROUPS.items():
        v = max(float(s["audioset"][lab[n]]) for n in names if n in lab)
        hit = v >= (sound_min or config.DANGER_SOUND_MIN)          # AudioSet classes (distilled from AST)
        if cls == "small_arms" and s.get("gunfire") is not None and s["gunfire"] >= config.SMALL_GUN_MIN:
            v, hit = max(v, s["gunfire"]), True                     # or the trained gunfire head
        if hit:
            out.append({"class": cls, "score": round(v, 2), "model": "near-small"})
    if s["drone"] is not None and s["drone"] >= (drone_min or config.SMALL_DRONE_MIN):
        out.append({"class": "drone", "score": round(s["drone"], 2), "model": "near-small"})
    return out
