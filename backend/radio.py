"""Radio mode: the coordinator's laptop listens to the tactical radio. No internet, no GPS,
no phone needed in the field.

  radio speaker out -> laptop audio in -> map page cuts each transmission -> /api/radio
  for each transmission:
    1. data tones (modem.py): a phone's measurement packet (packet.py) -> same evidence as a
       Listen clip: kind of space, echoes, noise level, sounds, threats, compass, steps...
    2. speech -> local Whisper -> text -> the same pipeline as the field phone
    3. threats in the background sound (drone, gunfire, explosion) -> Near-small, the
       phone-sized model fine-tuned on radio-degraded audio (smallaudio.py)
    4. callsign ("this is Bravo 2") -> which casualty report it belongs to
  -> the reply (read-back + next question) is spoken back into the radio by the map page,
     after the operator approves it. A route for a walker with a phone can follow as tones.
"""
import re
import time

import numpy as np

from . import config, modem, packet
from .spatial import LABELS

ACTIVE_S = 15 * 60     # a transmission with no callsign goes to the report heard in the last 15 min

CALLSIGN = re.compile(r"\b(?:this is|ici|de)\s+([A-Za-z]+(?:[\s-]?\d{1,2}|\s+(?:one|two|three|four|five|six|seven|eight|nine))?)",
                      re.I)
NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
       "eight": "8", "nine": "9", "too": "2", "to": "2"}


def callsign(text):
    """'This is Bravo two, ...' -> 'BRAVO 2'."""
    m = CALLSIGN.search(text or "")
    if not m:
        m = re.match(r"\s*([A-Za-z]+)[\s-]+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|too)\b[.,]?",
                     text or "", re.I)      # "Bravo 2. Left. Over."
        if not m or m.group(1).lower() in ("one", "two", "the", "i", "we", "a"):
            return None
        return f"{m.group(1).upper()} {NUM.get(m.group(2).lower(), m.group(2))}"
    w = m.group(1).split()
    name = w[0].upper()
    if len(w) > 1 or re.search(r"\d", m.group(1)):
        num = re.sub(r"\D", "", m.group(1)) or NUM.get(w[-1].lower(), "")
        return f"{name} {num}".strip()
    return name


def strip_procedure(text):
    """Radio words that are not content: 'this is Bravo 2', 'over', 'out', 'roger'."""
    t = re.sub(r"\b(over and out|over|out|roger|copy that|wilco|à vous|terminé)\b[.!]?", "", text or "", flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" .,")


def find_report(store, cs):
    """Report for this callsign, else the one being talked to on the radio right now."""
    now = time.time() * 1000
    live = [r for r in store.reports.values() if not r.get("evacuated")]
    if cs:
        same = [r for r in live if (r.get("callsign") or "").upper().replace("-", " ") == cs]
        if same:
            return max(same, key=lambda r: r["updated_ms"])
        return None                        # a new unit: new report
    recent = [r for r in live if r.get("_radio_ms") and now - r["_radio_ms"] < ACTIVE_S * 1000]
    return max(recent, key=lambda r: r["_radio_ms"]) if recent else None


def packet_to_analysis(p):
    """Measurement packet -> the same analysis dict a Listen clip gives (acoustic.py)."""
    sp = p.get("space")
    an = {"kind": "ambient", "source": "radio packet", "audio_quality": "good", "level_dbfs": -30.0,
          "speech_fraction": 0.0, "quality_notes": ["measured on the phone, sent as a radio packet"],
          "events": [{"class": k, "score": round(v, 2)} for k, v in (p.get("sounds") or {}).items()],
          "context": [], "features": {},
          "alerts": [{"class": k, "score": round(v, 2), "per_model": {"phone": round(v, 2)}}
                     for k, v in (p.get("threats") or {}).items()]}
    if sp:
        best = max(sp, key=sp.get)
        an["space"] = {"p": sp, "_p_for_grid": sp, "_strength_for_grid": p.get("space_strength", 0.3),
                       "best": best, "label": LABELS[best], "p_best": sp[best], "clues": ["measured on the phone"]}
    if p.get("echoes"):
        an.setdefault("space", {"p": {}, "clues": []})["probe"] = {
            "ok": True, "drr_db": 3.0, "reflections": [{"m": m, "db": -12.0} for m in p["echoes"]],
            "nearest_wall_m": min(p["echoes"]), "wall_reliable": True}
    if p.get("dba") is not None:
        an["ambient"] = {"dba": p["dba"], "sigma": 8.0, "ref": "measured on the phone"}
    has_audio = bool(sp or p.get("echoes") or p.get("dba") is not None or p.get("sounds") or p.get("threats"))
    return an if has_audio else None


def handle(store, wave, lang=None):
    """One radio transmission (16 kHz mono) -> what was understood and the reply to send."""
    from .stt import local_available, transcribe_wave
    out = {"packets": [], "transcript": "", "callsign": None, "report_id": None, "reply": None,
           "threats": [], "notes": []}
    # 1. data tones
    for raw in modem.decode(wave):
        try:
            p = packet.decode_report(raw)
        except (ValueError, IndexError):
            continue
        out["packets"].append(p)
    # 2. speech
    if local_available():
        txt = transcribe_wave(wave, lang)
        txt = "" if re.fullmatch(r"[\W_]*|(beep|♪|music|\[.*?\])+", txt.strip().lower()) else txt
        out["transcript"] = txt
    else:
        out["notes"].append("no local speech-to-text model: run python -m scripts.fetch_models")
    # 3. threats in the background of the transmission (radio-trained small model)
    # Measured over simulated radio (scripts/eval_radio.py): the big models keep 60-67 % of
    # gunshots but only 6-9 % of drones; Near-small (radio-trained) gets 100 % of drones.
    if not out["packets"] and len(wave) >= 16000:   # tones would confuse them
        try:
            from . import acoustic
            out["threats"] = [a for a in acoustic.danger_sounds_only(wave) if a["class"] != "drone"]
        except Exception as e:
            out["notes"].append(f"big sound models unavailable ({e.__class__.__name__})")
        try:
            from .smallaudio import threats
            out["threats"] += [t for t in threats(wave) if t["class"] == "drone"]
        except Exception as e:                 # model missing: the rest still works
            out["notes"].append(f"small sound model unavailable ({e.__class__.__name__})")

    cs = callsign(out["transcript"]) or next((p["callsign"] for p in out["packets"] if p.get("callsign")), None)
    out["callsign"] = cs
    rep = find_report(store, cs)
    rid = rep["id"] if rep else None
    text = strip_procedure(re.sub(r"(?i)^\s*(this is|ici)\s+\w+(\s+\w+)?[.,]?\s*", "", out["transcript"]))
    if cs:
        text = re.sub(rf"(?i)^\s*{re.escape(cs.split()[0])}[\s-]*\w*[.,]?\s*", "", text)

    for p in out["packets"]:
        rep = apply_packet(store, rid, p, cs)
        rid = rep["id"]
    if text:
        rep = store.process(rid, text, source="radio", lang_hint=lang)
        rid = rep["id"]
    if out["threats"] and rid:
        from . import danger
        from .state import LOCK, now_ms
        with LOCK:
            r = store.reports[rid]
            for d in danger.from_audio([{**t} for t in out["threats"]], now_ms()):
                d["source"] = "audio"
                d["doubt"] = d.get("doubt") or "heard over the radio"
                danger.add(r["dangers"], d)
            store.version += 1
    if rid:
        r = store.reports[rid]
        if cs and not r.get("callsign"):
            r["callsign"] = cs
        r["_radio_ms"] = time.time() * 1000
        out["report_id"] = rid
        out["reply"] = reply_text(r, cs)
    return out


def apply_packet(store, rid, p, cs=None):
    """A phone's measurement packet: compass, aims, steps, guidance events, sound evidence."""
    from .state import LOCK
    with LOCK:
        rep = store.get_or_create(rid)
        if cs and not rep.get("callsign"):
            rep["callsign"] = cs
        if p.get("compass") is not None:
            rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "compass"]
            rep["constraints"].append({"kind": "compass", "deg": float(p["compass"]) % 360,
                                       "sigma": config.SIGMA_COMPASS})
        if p.get("aims"):
            rep["pending_aims"] = p["aims"]        # matched to the landmarks of the next spoken report
        rep["_radio_ms"] = time.time() * 1000
        rid = rep["id"]
    an = packet_to_analysis(p)
    if an:
        rep = store.process_audio(rid, an)
    if p.get("steps") is not None and rep.get("guide"):
        rep = store.guide_action(rid, "steps", p["steps"])
    if p.get("guide"):
        rep = store.guide_action(rid, p["guide"]["event"])
    return store.reports[rid]


def reply_text(rep, cs):
    """What the coordinator says back on the radio (procedure words around the read-back)."""
    fr = rep.get("lang") == "fr"
    head = f"{cs.title()}, ici poste de secours." if (cs and fr) else (f"{cs.title()}, this is CCP." if cs else "")
    tail = " À vous." if fr else " Over."
    return (head + " " + (rep.get("readback") or "")).strip() + tail


def route_tones(rep, sr=16000):
    """The current route as data tones for a walker whose phone guides offline."""
    from .route import get_router
    g = rep.get("guide")
    if not g:
        return None
    R = get_router()
    legs = []
    for lg in g["legs"][g["leg"]:]:
        cue = lg.get("cue")
        legs.append({"bearing": lg["bearing"], "length_m": lg["s1"] - max(lg["s0"], g["s"]),
                     "cue": {"idx": cue["idx"], "side": cue["side"]} if cue and "idx" in cue else None})
    raw = packet.encode_route(rep.get("callsign") or rep["id"], g["reroutes"] & 0xFF, legs)
    return modem.encode(raw, sr=sr), raw, R
