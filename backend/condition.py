"""Casualty condition: how bad is it now, and how long until it gets worse?

Decision support for trained medics, NOT a diagnosis. It organises what was said and
heard (signs, wounds, how it happened, treatments, casualty sounds, the casualty's own
voice when they report themselves) into:

  - a state per MARCH item: Massive bleeding, Airway, Respiration, Circulation (shock),
    Hypothermia / Head, with what it is based on;
  - the casualty's distress (pain / panic): their own voice when they are the speaker,
    screaming / crying / groaning heard on the clips, or the words of the buddy;
  - an overall condition: stable / serious / critical / very critical (0-100);
  - the active threats, each with a time window ("worse within ~3-10 min of injury") and
    the time left, counted from the injury (said, or the tourniquet time, or at the latest
    the first report);
  - where hidden injuries may be, from how it happened (blast: ears, lungs, head...).

The time windows are textbook orders of magnitude from trauma care (TCCC / ATLS style:
an untreated arterial bleed kills in minutes, a blocked airway in ~4 min, tourniquet
safe ~2 h, non-compressible torso bleeding needs surgery within ~1 h, a tension
pneumothorax develops over minutes to tens of minutes). They are placeholders in
WINDOWS below, to check with the medical mentor; they are not predictions for one person.
"""
import time

# id: (label, MARCH letter, window (min, max) in minutes, counted from, what helps)
WINDOWS = {
    "bleed_uncontrolled": ("Massive bleeding not controlled", "M", (3, 10), "injury",
                           "tourniquet / packing and pressure now"),
    "bleed_noncompressible": ("Torso or junctional bleeding (can't be tourniqueted)", "M", (30, 60), "injury",
                              "pack junctional wounds; surgery is the fix: evacuate first"),
    "bleed_minor": ("Bleeding, not massive", "M", (30, 90), "injury", "pressure bandage, check it"),
    "tourniquet": ("Tourniquet on: limb ischaemia", "M", (120, 360), "tourniquet",
                   "re-check; convert within 2 h if trained and the casualty is stable"),
    "airway": ("Airway at risk (unconscious or noisy breathing)", "A", (3, 5), "now",
               "recovery position / airway adjunct, watch continuously"),
    "breathing": ("Breathing problem", "R", (5, 30), "now", "chest seal if wound; decompression by a medic"),
    "shock": ("Signs of shock (pale, cold, sweaty, confused)", "C", (15, 45), "now",
              "stop bleeding, keep warm, flat, evacuate"),
    "head": ("Head injury or blast with reduced consciousness", "H", (30, 120), "injury",
             "watch AVPU every few minutes, protect airway"),
    "hypothermia": ("Hypothermia (November, lying still, blood loss)", "H", (30, 90), "injury",
                    "insulate from the ground, cover, keep dry"),
    "unknown_bleed": ("Bleeding: not known if controlled", "M", (10, 30), "injury",
                      "ask / check the bleeding"),
}
AVPU_LABEL = {"A": "alert, talking", "V": "responds to voice / confused", "P": "responds to pain only",
              "U": "unresponsive"}
JUNCTIONAL = ("groin", "neck", "armpit", "axilla", "aine", "cou", "aisselle")
TORSO_SEGS = {"chest", "abdomen", "pelvis"}
# Mechanism -> body parts (backend/bodygraph.py ids) to check for hidden injuries.
MECH_SUSPECT = {
    "blast": [("ears", "eardrums"), ("eyes", "eye fragments"), ("chest", "blast lung"),
              ("scalp", "concussion / TBI"), ("abdomen", "blast abdomen")],
    "fall": [("nape", "neck / spine"), ("lower_back", "spine"), ("pelvis", "pelvic ring"), ("scalp", "head injury")],
    "vehicle": [("nape", "neck / spine"), ("ribs", "ribs / lungs"), ("pelvis", "pelvic ring"), ("chest", "chest")],
    "gunshot": [],     # exit wound: handled from the wound site
}
EXIT_OF = {"chest": "upper_back", "abdomen": "lower_back", "upper_back": "chest", "lower_back": "abdomen"}


def _injury_ms(cas, rep):
    """When it happened: said ("hit 10 minutes ago"), else before the tourniquet, else at
    the latest the first report. Returns (epoch ms, basis)."""
    from .casualty import tourniquet_epoch_ms
    if cas.get("injury_ago_ms"):
        return cas["injury_ago_ms"], "said"
    tqs = [tourniquet_epoch_ms(t.get("time")) for t in cas.get("treatments") or []
           if t.get("type") == "tourniquet" and t.get("time")]
    tqs = [t for t in tqs if t]
    first = rep["transcripts"][0]["ms"] if rep.get("transcripts") else int(time.time() * 1000)
    if tqs:
        return min(min(tqs), first), "before the tourniquet"
    return first, "first report (at the latest)"


RANK = {None: -1, "unknown": -1, "low": 0, "elevated": 1, "high": 2}


def _distress(cas, rep, sounds):
    """Casualty's distress (pain / panic): own voice if self-report, sounds, words. Each
    source can only raise the level (a calm-sounding voice does not cancel "in pain")."""
    s = cas.get("signs") or {}
    src, level = [], None

    def up(lv):
        nonlocal level
        if RANK[lv] > RANK[level]:
            level = lv
    if cas.get("self_report") and rep.get("stress") and rep["stress"].get("level") not in (None, "unknown"):
        up(rep["stress"]["level"])
        src.append(f"own voice: {rep['stress']['level']}")
    vocal = [lab for lab, sc in sounds if lab in ("Screaming", "Crying, sobbing", "Wail, moan", "Groan", "Whimper")]
    if vocal:
        up("high" if any(v in ("Screaming", "Crying, sobbing") for v in vocal) else "elevated")
        src.append("heard: " + ", ".join(v.lower() for v in vocal))
    if s.get("distress"):
        up(s["distress"])
        src.append(f"said: {s['distress']}")
    if s.get("pain"):
        up("elevated")
        src.append("said: in pain")
    return level or "unknown", src


def assess(cas, rep, idx=0, now_ms=None):
    """Condition of one casualty (report casualty dict) -> dict for the dashboard."""
    from .body import regions
    now_ms = now_ms or int(time.time() * 1000)
    s = cas.get("signs") or {}
    sounds = rep.get("casualty_audio") or []
    t_inj, inj_basis = _injury_ms(cas, rep)
    since = max(0.0, (now_ms - t_inj) / 60000.0)
    tq = [t for t in cas.get("treatments") or [] if t.get("type") == "tourniquet"]
    from .casualty import tourniquet_epoch_ms
    tq_ms = min([m for m in (tourniquet_epoch_ms(t.get("time")) for t in tq) if m] or [None]) if tq else None
    wounds = [(w, regions(w)) for w in cas.get("injuries") or []]
    segs = {sg for _, r in wounds if r for sg in r["segments"]}
    kinds = {r["kind"] for _, r in wounds if r}
    limb = any(sg[2:] in ("thigh", "lower_leg", "upper_arm", "forearm", "hand", "foot") for sg in segs)
    torso = bool(segs & TORSO_SEGS) or any(j in w.lower() for w, _ in wounds for j in JUNCTIONAL)
    penetrating = bool(kinds & {"gunshot", "shrapnel"}) or cas.get("mechanism") in ("gunshot", "blast")
    bleeding = bool(kinds & {"bleeding", "amputation", "gunshot", "shrapnel"}) or s.get("massive_bleeding")

    # ---- heart rate (chest audio, backend/heart.py): the latest fresh, clear-enough reading
    from . import config as _cfg
    from .heart import band as _band
    hr = None
    for v in reversed(rep.get("vitals") or []):
        if v.get("bpm") and (v.get("ok") or (v.get("quality") or 0) >= 0.1) and \
                now_ms - v["ms"] <= _cfg.HR_FRESH_MIN * 60000:
            hr = {**v, "band": _band(v["bpm"], _cfg.HR_BANDS)}
            break
    hr_shock = bool(hr and hr["band"] in ("shock range", "severe"))

    # ---- MARCH states
    avpu = s.get("avpu") or ("U" if s.get("conscious") is False else "A" if s.get("conscious") else None)
    # Screaming / crying / groaning (said or heard): responsive, air is moving. Confirm.
    vocal = s.get("distress") == "high" or any(lab in ("Screaming", "Crying, sobbing", "Wail, moan", "Groan", "Whimper")
                                               for lab, _ in sounds)
    vocal_only = avpu is None and vocal      # shown as "responsive (confirm)", not scored as reduced
    airway_bad = avpu in ("P", "U") or s.get("airway") == "at risk" or \
        any(lab in ("Snoring", "Gasp") for lab, _ in sounds)
    breathing_bad = s.get("breathing") is False or any(lab in ("Wheeze", "Pant", "Gasp") for lab, _ in sounds)
    controlled = s.get("bleeding_controlled")
    march = {
        "M": ("massive, NOT controlled" if s.get("massive_bleeding") and not (tq and limb) and controlled is not True
              else "controlled (tourniquet)" if tq else "controlled" if controlled
              else "bleeding, control unknown" if bleeding else "no bleeding reported"),
        "A": ("AT RISK" if airway_bad else "open (talking)" if avpu == "A" else
              "open (vocalising, confirm)" if vocal else "unknown"),
        "R": ("PROBLEM" if breathing_bad else "breathing" if s.get("breathing") else "unknown"),
        "C": ("SHOCK SIGNS" + (f" · HR {hr['bpm']}" if hr else "") if s.get("shock_signs") or hr_shock and s.get("shock_signs") is not False
              else (f"HR {hr['bpm']} ({hr['band']})" if hr else "no shock signs said" if s.get("shock_signs") is False
                    else "unknown")),
        "H": ("head / reduced consciousness" if avpu in ("V", "P", "U") and ("head" in segs or cas.get("mechanism") == "blast")
              else "cold risk" if since > 0 or bleeding else "unknown"),
    }

    # ---- threats with time windows
    threats = []

    def add(tid, start_ms, basis, status="active"):
        label, letter, (lo, hi), _, helps = WINDOWS[tid]
        el = max(0.0, (now_ms - start_ms) / 60000.0)
        threats.append({"id": tid, "label": label, "march": letter, "status": status,
                        "window_min": [lo, hi], "elapsed_min": round(el, 1),
                        "left_min": [round(lo - el, 1), round(hi - el, 1)], "from": basis, "helps": helps,
                        # absolute times, so the dashboard can count down between updates
                        "at_ms": [int(start_ms + lo * 60000), int(start_ms + hi * 60000)]})

    if s.get("massive_bleeding") and controlled is not True and not (tq and limb and not torso):
        add("bleed_uncontrolled", t_inj, "injury, " + inj_basis)
    if torso and penetrating and bleeding:
        add("bleed_noncompressible", t_inj, "injury, " + inj_basis)
    if tq_ms:
        add("tourniquet", tq_ms, "tourniquet time", status="controlled")
    if bleeding and not s.get("massive_bleeding") and not tq and controlled is None and not torso:
        add("unknown_bleed", t_inj, "injury, " + inj_basis)
    elif bleeding and not s.get("massive_bleeding") and not tq and controlled is False:
        add("bleed_minor", t_inj, "injury, " + inj_basis)
    if airway_bad:
        add("airway", now_ms, "from now (keep watching)")
    if breathing_bad:
        add("breathing", now_ms, "from now")
    if s.get("shock_signs") or hr_shock:
        add("shock", now_ms, "from now" + (f" (heart rate {hr['bpm']})" if hr_shock else ""))
    if avpu in ("V", "P", "U") and ("head" in segs or cas.get("mechanism") in ("blast", "fall", "vehicle")):
        add("head", t_inj, "injury, " + inj_basis)
    if cas.get("injuries") or s.get("massive_bleeding") or cas.get("mechanism"):
        add("hypothermia", t_inj, "injury, " + inj_basis, status="watch")

    # ---- overall condition (0 = dying, 100 = stable), simple additive rules
    score = 100
    score -= {"U": 45, "P": 35, "V": 18}.get(avpu, 0)
    score -= 55 if any(t["id"] == "bleed_uncontrolled" for t in threats) else 0
    score -= 25 if any(t["id"] == "bleed_noncompressible" for t in threats) else 0
    score -= 12 if any(t["id"] == "unknown_bleed" for t in threats) else 0
    score -= 30 if breathing_bad else 0
    score -= 25 if airway_bad and avpu not in ("P", "U") else 0
    score -= 25 if s.get("shock_signs") else 0
    if hr:
        score -= {"severe": 25, "shock range": 15, "slow": 20, "fast": 5}.get(hr["band"], 0)
    score -= 10 if tq else 0
    score -= 10 if s.get("spinal") else 0
    score -= 5 if kinds & {"fracture", "burn"} else 0
    score = max(0, min(100, score))
    state = "very critical" if score < 25 else "critical" if score < 50 else "serious" if score < 75 else "stable"
    # A life threat that is due now (window reached) is critical whatever the sum says.
    # So is any airway or breathing threat.
    if score >= 50 and any(t["status"] == "active" and (t["left_min"][0] <= 0 and t["march"] in "MAR"
                                                       or t["march"] in "AR") for t in threats):
        score, state = 45, "critical"
    known = sum(v not in ("unknown",) for v in march.values())

    active = [t for t in threats if t["status"] == "active"]
    nxt = min(active, key=lambda t: t["left_min"][0], default=None)
    worse = None
    if nxt:
        lo, hi = nxt["left_min"]
        worse = {"threat": nxt["label"], "march": nxt["march"], "min": max(0.0, lo), "max": max(0.0, hi),
                 "overdue": hi <= 0, "helps": nxt["helps"], "at_ms": nxt["at_ms"]}

    # ---- where hidden injuries may be (body parts graph: "suspected")
    suspect = list(MECH_SUSPECT.get(cas.get("mechanism") or "", []))
    if penetrating:
        for sg in segs:
            if sg in EXIT_OF:
                suspect.append((EXIT_OF[sg], "exit wound / path"))
    if s.get("spinal"):
        suspect.append(("lower_back", "spine (can't feel / move limbs)"))

    distress, dsrc = _distress(cas, rep, sounds)
    if hr and hr["bpm"] and hr["bpm"] > 110 and RANK[distress] < RANK["elevated"]:
        distress = "elevated"                 # fear / pain raise the heart rate too (so does blood loss)
    if hr and hr["bpm"]:
        dsrc = dsrc + [f"heart rate {hr['bpm']} bpm"]
    return {"index": idx, "state": state, "score": score, "avpu": "V/A?" if vocal_only else avpu,
            "avpu_label": "vocalising: responsive at least to voice (confirm)" if vocal_only else AVPU_LABEL.get(avpu, "unknown"),
            "march": march, "distress": distress, "distress_from": dsrc, "mechanism": cas.get("mechanism"),
            "mechanism_known": bool(cas.get("mechanism")), "threats": threats, "worse_in": worse,
            "since_injury_min": round(since, 1), "injury_basis": inj_basis, "suspect": suspect,
            "known_items": known, "self_report": bool(cas.get("self_report")), "heart": hr,
            "note": "decision support: windows are textbook orders of magnitude to check with a medic"}


def worst_left(rep):
    """Minutes before the most urgent active threat of any casualty of the report (low end), or None."""
    out = []
    for i, c in enumerate(rep.get("casualties") or []):
        w = assess(c, rep, i)["worse_in"]
        if w:
            out.append(w["min"])
    return min(out) if out else None
