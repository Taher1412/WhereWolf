"""What a tactical voice radio does to sound, roughly (for tests, evaluation and training).

  analog FM  : band 300-3400 Hz, automatic gain + soft clipping, 8 kHz, hiss
  digital    : same band, 8 kHz, 8-bit mu-law, plus lost 20 ms frames (bad link)
This is a simplification. Real military radios use low-bitrate vocoders (e.g. MELPe) that
model speech and can smear other sounds further: check on the real radio before trusting it.
"""
import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

SR = 16000
_SOS = butter(4, [300, 3400], btype="band", fs=SR, output="sos")


def radio(wave, kind="analog", snr_db=None, rng=None):
    """16 kHz mono float32 -> the same sound after a radio link (16 kHz, band-limited)."""
    rng = rng or np.random.default_rng()
    x = sosfilt(_SOS, np.asarray(wave, np.float64))
    # automatic gain control + soft clipping: radios keep the level up, loud bangs saturate
    x = x / (np.percentile(np.abs(x), 99) + 1e-6) * 0.5
    x = np.tanh(2.0 * x) / np.tanh(2.0)
    x = resample_poly(x, 1, 2)                       # 8 kHz telephone band
    if kind == "digital":
        mu = 255.0
        y = np.sign(x) * np.log1p(mu * np.abs(np.clip(x, -1, 1))) / np.log1p(mu)
        y = np.round(y * 127) / 127                   # 8-bit
        x = np.sign(y) * ((1 + mu) ** np.abs(y) - 1) / mu
        frame = 160                                   # 20 ms at 8 kHz
        n = len(x) // frame
        lost = rng.random(n) < 0.03
        for i in np.where(lost)[0]:
            x[i * frame:(i + 1) * frame] = 0
    snr = snr_db if snr_db is not None else rng.uniform(15, 30)
    p = np.mean(x ** 2) + 1e-12
    x = x + rng.normal(0, np.sqrt(p / 10 ** (snr / 10)), len(x))
    x = resample_poly(x, 2, 1)
    return np.clip(x, -1, 1).astype(np.float32)
