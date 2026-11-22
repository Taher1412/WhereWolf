"""Data over a voice radio: a few bytes as audio tones (no internet, no data link needed).

Like amateur radio's APRS: two tones inside the radio's 300-3400 Hz band, 1200 Hz for a 1
bit and 2200 Hz for a 0 bit (continuous phase), at 400 bits per second. A 40-byte packet is
~1 s of tones. The phone plays them into the radio's microphone; the laptop hears them on
the radio's speaker output (and the other way round for the route).

Frame: preamble 0x55 x 6 | sync 0x2D 0xD4 | length | payload | CRC-16 (CCITT)
The same modem is in frontend/modem.js. Caveat: encrypted digital radios use speech vocoders
that can garble tones; test on the real radio (analog FM radios are fine).
"""
import numpy as np

BAUD = 400
F_MARK, F_SPACE = 1200.0, 2200.0
PREAMBLE = bytes([0x55] * 6)
SYNC = bytes([0x2D, 0xD4])


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def _bits(data: bytes):
    return [(b >> (7 - i)) & 1 for b in data for i in range(8)]     # MSB first


def frame_bits(payload: bytes, copies=2):
    """Preamble, then `copies` x (sync + length + payload + CRC). Two copies let the
    receiver add them up bit by bit: a 20 ms dropout rarely hits the same bits twice."""
    if len(payload) > 255:
        raise ValueError("payload too long")
    c = crc16(payload)
    body = SYNC + bytes([len(payload)]) + payload + bytes([c >> 8, c & 0xFF])
    return _bits(PREAMBLE + body * copies)


def encode(payload: bytes, sr=16000, amp=0.6, copies=2) -> np.ndarray:
    """Bytes -> float32 audio (with 50 ms of silence around it)."""
    bits = frame_bits(payload, copies)
    spb = sr / BAUD
    n = int(round(len(bits) * spb))
    t_bit = (np.arange(n) / spb).astype(int).clip(0, len(bits) - 1)
    f = np.where(np.array(bits)[t_bit] == 1, F_MARK, F_SPACE)
    phase = 2 * np.pi * np.cumsum(f) / sr                        # continuous phase
    x = amp * np.sin(phase)
    ramp = int(0.005 * sr)                                       # soft edges
    x[:ramp] *= np.linspace(0, 1, ramp)
    x[-ramp:] *= np.linspace(1, 0, ramp)
    pad = np.zeros(int(0.05 * sr))
    return np.r_[pad, x, pad].astype(np.float32)


def _tone_energy(x, f, sr, spb):
    t = np.arange(len(x)) / sr
    z = x * np.exp(-2j * np.pi * f * t)
    k = max(1, int(round(spb)))
    c = np.cumsum(np.r_[0, z])
    return np.abs(c[k:] - c[:-k])        # |sum over one bit|, starting at each sample


def _try(soft, p, ln):
    """Soft bits from position p (after the sync) -> payload if the CRC fits."""
    end = p + 8 + 8 * (ln + 2)
    if end > len(soft):
        return None
    body = np.packbits((soft[p + 8:end] > 0).astype(np.uint8)).tobytes()
    payload, c = body[:ln], (body[ln] << 8) | body[ln + 1]
    return payload if crc16(payload) == c else None


def _len(soft, p):
    return int(np.packbits((soft[p:p + 8] > 0).astype(np.uint8))[0]) if p + 8 <= len(soft) else -1


def decode(x, sr=16000):
    """Audio -> list of payloads (bytes) found in it, CRC checked. Robust to where the
    packet starts, level, radio hiss and short dropouts (copies are added up)."""
    x = np.asarray(x, np.float64)
    spb = sr / BAUD
    if len(x) < spb * 8 * (len(PREAMBLE) + 5):
        return []
    d = _tone_energy(x, F_MARK, sr, spb) - _tone_energy(x, F_SPACE, sr, spb)
    d = d / (np.percentile(np.abs(d), 90) + 1e-12)
    sync_bits = np.array(_bits(SYNC))
    found, seen = [], set()
    for phase in np.arange(0, spb, spb / 8):
        idx = (phase + np.arange(int((len(d) - phase) // spb)) * spb).astype(int)
        idx = idx[idx < len(d)]
        soft = d[idx]
        bits = (soft > 0).astype(np.int8)
        if len(bits) < 16:
            continue
        win = np.lib.stride_tricks.sliding_window_view(bits, 16)
        score = (win == sync_bits).sum(axis=1)
        hits = np.where(score >= 15)[0]              # sync word, at most 1 bit wrong
        for h in hits:
            p = h + 16
            cands = []
            lens = {_len(soft, p)}
            for h2 in hits:                           # length from the gap to the next copy
                gap = h2 - h - 16 - 8
                if gap > 16 and gap % 8 == 0 and gap // 8 - 2 <= 255:
                    lens.add(gap // 8 - 2)
            for ln in lens:
                if ln < 0:
                    continue
                span = 16 + 8 + 8 * (ln + 2)          # one copy, sync included
                cands.append((p, ln, None))
                for q in (p + span, p - span):        # add the other copy if it is there
                    if 0 <= q and q + 8 + 8 * (ln + 2) <= len(soft) and p + 8 + 8 * (ln + 2) <= len(soft):
                        cands.append((p, ln, q))
            for p0, ln, q in cands:
                s2 = soft.copy()
                if q is not None:
                    n = 8 + 8 * (ln + 2)
                    s2[p0:p0 + n] = soft[p0:p0 + n] + soft[q:q + n]
                pl = _try(s2, p0, ln)
                if pl is not None and pl not in seen:
                    seen.add(pl)
                    found.append((int(idx[h]), pl))
    found.sort()
    return [pl for _, pl in found]
