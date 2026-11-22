"""Compact binary packets for links with no internet: radio data mode, mesh radio, or the
audio modem over the voice channel (modem.py). Same format in frontend/packet.js.

REPORT (phone -> coordinator), ~10-40 bytes: what the phone measured, never raw audio.
  0     type 1 | version 1  (one byte: 0x11)
  1     callsign length n, then n ASCII bytes ("B2")
  .     minutes since midnight UTC (11 bits) + sequence (5 bits)      2 bytes
  .     field mask                                                    2 bytes
  then, in mask order, only the fields present:
  bit 0 compass, where "12 o'clock" points          1 B  (deg x 256 / 360)
  bit 1 aims (Aim & tap)                            1 B n, n x (az 1 B, elevation x 4 1 B)
  bit 2 step count                                  2 B
  bit 3 kind of space (4 probabilities)             2 B  (4 x 4 bits, x 15)
  bit 4 noise level dB(A)                           1 B
  bit 5 echoes (wall distances)                     1 B n, n x (metres x 4) 1 B
  bit 6 sounds heard (rail, traffic, bells,         1 B n, n x (group 3 bits | score 5 bits)
        machinery, nature)
  bit 7 threats heard (drone, small arms,           1 B mask + 1 B score per threat
        explosion)
  bit 8 guidance event (reached / arrived / lost)   1 B event + 1 B leg
  bit 9 strength of the space clues                 1 B (x 255)

ROUTE (coordinator -> phone): legs to walk, the phone guides offline with its compass and
step counter. type 0x21 | callsign | route id 1 B | n legs 1 B | n x (bearing 1 B,
length 2 B, landmark index 2 B (0xFFFF none), cue side 1 B)
"""
import struct
import time

SPACES = ["indoor_small", "indoor_large", "outdoor_enclosed", "outdoor_open"]
SOUNDS = ["rail", "traffic", "bells", "machinery", "nature"]
THREATS = ["drone", "small_arms", "explosion"]
EVENTS = ["reached", "arrived", "lost"]
SIDES = [None, "left", "right", "ahead"]
REPORT, ROUTE = 0x11, 0x21


def _call(cs):
    cs = (cs or "").encode("ascii", "ignore")[:8]
    return bytes([len(cs)]) + cs


def encode_report(r: dict, seq=0) -> bytes:
    t = time.gmtime(r.get("time", time.time()))
    out = bytearray([REPORT]) + _call(r.get("callsign"))
    out += struct.pack(">H", ((t.tm_hour * 60 + t.tm_min) << 5) | (seq & 31))
    mask, body = 0, bytearray()
    if r.get("compass") is not None:
        mask |= 1 << 0
        body.append(int(round(r["compass"] % 360 * 256 / 360)) % 256)
    if r.get("aims"):
        mask |= 1 << 1
        aims = r["aims"][:6]
        body.append(len(aims))
        for a in aims:
            body += bytes([int(round(a["az"] % 360 * 256 / 360)) % 256, max(0, min(255, int(round(a["el"] * 4))))])
    if r.get("steps") is not None:
        mask |= 1 << 2
        body += struct.pack(">H", int(r["steps"]) & 0xFFFF)
    if r.get("space"):
        mask |= 1 << 3
        q = [max(0, min(15, int(round(r["space"].get(k, 0) * 15)))) for k in SPACES]
        body += bytes([(q[0] << 4) | q[1], (q[2] << 4) | q[3]])
    if r.get("dba") is not None:
        mask |= 1 << 4
        body.append(max(0, min(255, int(round(r["dba"])))))
    if r.get("echoes"):
        mask |= 1 << 5
        e = r["echoes"][:6]
        body.append(len(e))
        body += bytes(max(0, min(255, int(round(m * 4)))) for m in e)
    if r.get("sounds"):
        mask |= 1 << 6
        s = [(SOUNDS.index(k), v) for k, v in r["sounds"].items() if k in SOUNDS][:5]
        body.append(len(s))
        body += bytes((i << 5) | max(0, min(31, int(round(v * 31)))) for i, v in s)
    if r.get("threats"):
        mask |= 1 << 7
        m, sc = 0, bytearray()
        for i, k in enumerate(THREATS):
            if k in r["threats"]:
                m |= 1 << i
                sc.append(max(0, min(255, int(round(r["threats"][k] * 255)))))
        body += bytes([m]) + sc
    if r.get("guide"):
        mask |= 1 << 8
        body += bytes([EVENTS.index(r["guide"]["event"]), int(r["guide"].get("leg", 0)) & 0xFF])
    if r.get("space_strength") is not None:
        mask |= 1 << 9
        body.append(max(0, min(255, int(round(r["space_strength"] * 255)))))
    return bytes(out + struct.pack(">H", mask) + body)


def decode_report(b: bytes) -> dict:
    if not b or b[0] != REPORT:
        raise ValueError("not a report packet")
    i = 1
    n = b[i]
    cs = b[i + 1:i + 1 + n].decode("ascii", "ignore")
    i += 1 + n
    tm, mask = struct.unpack(">HH", b[i:i + 4])
    i += 4
    r = {"callsign": cs or None, "minute": tm >> 5, "seq": tm & 31}
    if mask & 1:
        r["compass"] = b[i] * 360 / 256
        i += 1
    if mask & 2:
        k = b[i]
        r["aims"] = [{"az": b[i + 1 + 2 * j] * 360 / 256, "el": b[i + 2 + 2 * j] / 4} for j in range(k)]
        i += 1 + 2 * k
    if mask & 4:
        r["steps"] = struct.unpack(">H", b[i:i + 2])[0]
        i += 2
    if mask & 8:
        q = [b[i] >> 4, b[i] & 15, b[i + 1] >> 4, b[i + 1] & 15]
        tot = sum(q) or 1
        r["space"] = {k: v / tot for k, v in zip(SPACES, q)}
        i += 2
    if mask & 16:
        r["dba"] = float(b[i])
        i += 1
    if mask & 32:
        k = b[i]
        r["echoes"] = [b[i + 1 + j] / 4 for j in range(k)]
        i += 1 + k
    if mask & 64:
        k = b[i]
        r["sounds"] = {SOUNDS[b[i + 1 + j] >> 5]: (b[i + 1 + j] & 31) / 31 for j in range(k)}
        i += 1 + k
    if mask & 128:
        m = b[i]
        i += 1
        r["threats"] = {}
        for j, k in enumerate(THREATS):
            if m >> j & 1:
                r["threats"][k] = b[i] / 255
                i += 1
    if mask & 256:
        r["guide"] = {"event": EVENTS[b[i]], "leg": b[i + 1]}
        i += 2
    if mask & 512:
        r["space_strength"] = b[i] / 255
        i += 1
    return r


def encode_route(callsign, route_id, legs) -> bytes:
    out = bytearray([ROUTE]) + _call(callsign) + bytes([route_id & 0xFF, min(len(legs), 40)])
    for lg in legs[:40]:
        cue = lg.get("cue") or {}
        out += bytes([int(round(lg["bearing"] % 360 * 256 / 360)) % 256])
        out += struct.pack(">HH", min(65535, int(round(lg["length_m"]))), cue.get("idx", 0xFFFF) if cue else 0xFFFF)
        out.append(SIDES.index(cue.get("side")) if cue else 0)
    return bytes(out)


def decode_route(b: bytes) -> dict:
    if not b or b[0] != ROUTE:
        raise ValueError("not a route packet")
    n = b[1]
    cs = b[2:2 + n].decode("ascii", "ignore")
    i = 2 + n
    rid, k = b[i], b[i + 1]
    i += 2
    legs = []
    for _ in range(k):
        brg = b[i] * 360 / 256
        ln, cue = struct.unpack(">HH", b[i + 1:i + 5])
        legs.append({"bearing": brg, "length_m": ln, "cue_idx": None if cue == 0xFFFF else cue,
                     "side": SIDES[b[i + 5]] if b[i + 5] < len(SIDES) else None})
        i += 6
    return {"callsign": cs or None, "route_id": rid, "legs": legs}
