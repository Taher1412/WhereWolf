"""Export Near-small for the phone: ONE ONNX file, raw 16 kHz audio in, threats out.

The mel spectrogram is computed inside the graph (STFT as a convolution with a fixed DFT
basis), so the phone needs no audio code: onnxruntime-web runs it offline in the browser.
  input  wave   (1, samples) float32, 16 kHz, 1-10 s
  output audioset (1, 527) probabilities, heads (1, 2) probabilities: drone, gunfire
Then int8 weights (dynamic quantisation) to shrink it for the phone.

    python -m scripts.export_small
"""
import numpy as np
import torch
import torchaudio

from backend import smallaudio as S

OUT = S.MODEL_DIR


class MelFront(torch.nn.Module):
    """Same numbers as CED's MelSpectrogram(n_fft 512, hop 160, 64 mels) + AmplitudeToDB(top_db 120)."""

    def __init__(self, n_fft=512, hop=160, n_mels=64, sr=16000):
        super().__init__()
        self.n_fft, self.hop = n_fft, hop
        win = torch.hann_window(n_fft, periodic=True)
        k = torch.arange(n_fft // 2 + 1)[:, None].float()
        t = torch.arange(n_fft)[None, :].float()
        ang = 2 * torch.pi * k * t / n_fft
        self.register_buffer("cosb", (torch.cos(ang) * win)[:, None, :])
        self.register_buffer("sinb", (-torch.sin(ang) * win)[:, None, :])
        fb = torchaudio.functional.melscale_fbanks(n_fft // 2 + 1, 0.0, sr / 2, n_mels, sr)
        self.register_buffer("fb", fb)            # (257, 64)

    def forward(self, wave):                      # (1, n)
        x = torch.nn.functional.pad(wave[:, None, :], (self.n_fft // 2, self.n_fft // 2), mode="reflect")
        re = torch.nn.functional.conv1d(x, self.cosb, stride=self.hop)
        im = torch.nn.functional.conv1d(x, self.sinb, stride=self.hop)
        power = re * re + im * im                 # (1, 257, frames)
        mel = torch.matmul(power.transpose(1, 2), self.fb).transpose(1, 2)   # (1, 64, frames)
        db = 10 * torch.log10(torch.clamp(mel, min=1e-10))
        return torch.maximum(db, db.amax(dim=(1, 2), keepdim=True) - 120.0)


class Phone(torch.nn.Module):
    """AudioSet classes from plain CED-tiny (keeps gunfire: 58 % of test gunshots on clean
    audio, the fine-tuned one forgot them), drone and gunfire heads from Near-small."""

    def __init__(self, m, head, plain):
        super().__init__()
        self.front, self.m, self.head, self.plain = MelFront(), m, head, plain

    def forward(self, wave):
        mel = self.front(wave)
        _, d = S.forward(self.m, self.head, mel)
        a = self.plain.outputlayer(self.plain.encoder(mel).logits.mean(1)).sigmoid()
        return a, torch.sigmoid(d)


def main():
    M = S.load()
    assert M["trained"], "train first: python -m scripts.train_small"
    plain, _ = S.build()
    net = Phone(M["m"], M["head"], plain.eval()).eval()
    w = (np.random.default_rng(0).normal(size=32000) * 0.1).astype(np.float32)
    ref = S.features([w], M["fe"])
    mine = net.front(torch.from_numpy(w)[None])
    print("mel front matches CED:", float((ref - mine[:, :, :ref.shape[2]]).abs().max()), "dB max difference")
    path = OUT / "near_small.onnx"
    torch.onnx.export(net, torch.from_numpy(w)[None], str(path), input_names=["wave"],
                      output_names=["audioset", "heads"], dynamic_axes={"wave": {1: "n"}}, opset_version=17)
    from onnxruntime.quantization import QuantType, quantize_dynamic
    q = OUT / "near_small.int8.onnx"
    quantize_dynamic(str(path), str(q), weight_type=QuantType.QUInt8)
    import onnxruntime as ort
    for p in (path, q):
        s = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        a, d = s.run(None, {"wave": w[None]})
        with torch.no_grad():
            ta, td = net(torch.from_numpy(w)[None])
        print(f"{p.name}: {p.stat().st_size / 1e6:.1f} MB, max diff vs torch {np.abs(a - ta.numpy()).max():.4f}, heads {np.round(d[0], 3)} vs {np.round(td[0].numpy(), 3)}")
    names = [M["names"][i] for i in range(527)]
    import json
    from backend import acoustic
    json.dump({"labels": names, "groups": S.GROUPS,
               "sounds": {g: acoustic.GROUPS[g] for g in acoustic.GEO_GROUPS if g in acoustic.GROUPS},
               "scenes": {"indoor_small": ["Inside, small room"],
                          "indoor_large": ["Inside, large room or hall", "Inside, public space"],
                          "outdoor_enclosed": ["Outside, urban or manmade"],
                          "outdoor_open": ["Outside, rural or natural"]}},
              open(OUT / "labels.json", "w"))
    print("labels ->", OUT / "labels.json")


if __name__ == "__main__":
    main()
