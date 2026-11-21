"""From the casualty report to the response: impact graph, kit list, team size.

Built on the casualty twin (body.py), so the input is the same voice report:

  Report  ->  Body region  ->  Possibly impacted structures  ->  MARCH threats  ->  Kit
  "left leg    L thigh         L femoral artery, femur           M massive bleeding   tourniquet x2
   bleeding"                                                                           hemostatic gauze

- "reported" = said by the medic; "possible" = what that kind of wound in that
  place can involve, to CHECK (anatomy + mechanism, e.g. blast -> eardrums, lungs).
- MARCH = the military casualty-care order (Massive bleeding, Airway, Respiration,
  Circulation, Hypothermia / Head). The kit follows it.
- Team = stretcher carry rules (4 bearers, 2 for a short carry, relief for a long one)
  + medics for urgent casualties, kept as small as possible (exposure to drones).

DECISION SUPPORT ONLY. It organises what was reported into a checklist; it does not
diagnose. Every rule below is a placeholder to validate with a medical mentor.
Ideas reused from the earlier image project (3D POSE EST: injury_graph.py hierarchy
and status colours, firstaidtools.json), rewritten deterministic and offline.
"""
from . import body as body_mod

# ------------------------------------------------------------------ anatomy
# Segment -> structures a wound there can involve: (id, label, type).
ANATOMY = {
    "head": [("brain", "brain", "organ"), ("skull", "skull", "bone"), ("eyes", "eyes / face", "organ"),
             ("airway_upper", "upper airway", "airway")],
    "neck": [("airway_upper", "upper airway", "airway"), ("neck_vessels", "carotid / jugular vessels", "vessel"),
             ("c_spine", "cervical spine", "bone")],
    "chest": [("lungs", "lungs", "organ"), ("heart", "heart", "organ"), ("ribs", "ribs", "bone"),
              ("chest_vessels", "great vessels", "vessel")],
    "abdomen": [("liver", "liver / spleen", "organ"), ("bowel", "bowel", "organ"), ("kidneys", "kidneys", "organ")],
    "pelvis": [("pelvic_ring", "pelvic ring", "bone"), ("junctional", "groin (junctional) vessels", "vessel"),
               ("bladder", "bladder", "organ")],
    "upper_arm": [("brachial", "brachial artery", "vessel"), ("humerus", "humerus", "bone")],
    "forearm": [("forearm_art", "radial / ulnar arteries", "vessel"), ("radius_ulna", "radius / ulna", "bone")],
    "hand": [("hand", "hand", "bone")],
    "thigh": [("femoral", "femoral artery", "vessel"), ("femur", "femur", "bone")],
    "lower_leg": [("leg_art", "popliteal / tibial arteries", "vessel"), ("tibia", "tibia / fibula", "bone")],
    "foot": [("foot", "foot", "bone")],
}
# Which structure types each kind of wound puts at risk.
KIND_THREAT = {
    "bleeding": {"vessel"}, "amputation": {"vessel", "bone"},
    "gunshot": {"vessel", "organ", "bone"}, "shrapnel": {"vessel", "organ"},
    "fracture": {"bone", "vessel"}, "burn": {"airway"}, "injury": {"bone"},
}
# Mechanism -> hidden injuries to check, even where no wound was named.
MECHANISM_CHECK = {
    "blast": [("eardrums", "eardrums (hearing)", "head", "organ"), ("lungs", "lungs (blast lung)", "chest", "organ"),
              ("brain", "brain (concussion / TBI)", "head", "organ"), ("eyes", "eyes (fragments)", "head", "organ"),
              ("other_wounds", "other fragment wounds: full body sweep", "body", "skin")],
    "gunshot": [("exit_wound", "exit wound: check the opposite side", "body", "skin")],
    "fall": [("c_spine", "spine", "neck", "bone"), ("pelvic_ring", "pelvic ring", "pelvis", "bone"),
             ("brain", "head injury", "head", "organ")],
    "vehicle": [("c_spine", "spine", "neck", "bone"), ("ribs", "chest (ribs, lungs)", "chest", "bone"),
                ("pelvic_ring", "pelvic ring", "pelvis", "bone")],
}
MARCH = {
    "M": "Massive bleeding", "A": "Airway", "R": "Respiration (breathing)",
    "C": "Circulation (shock)", "H": "Hypothermia / Head injury",
}

# ------------------------------------------------------------------ kit
# id: (name, who uses it, quantity per casualty, why)
KIT = {
    "tourniquet": ("Tourniquet (CAT)", "buddy", 2, "limb bleeding: one on, one spare"),
    "tq_check": ("Spare tourniquet + marker", "buddy", 1, "a tourniquet is on: check it, write the time"),
    "hemostatic": ("Hemostatic gauze", "buddy", 1, "pack wounds a tourniquet can't reach"),
    "pressure_bandage": ("Pressure bandage", "buddy", 1, "cover and compress each bleeding wound"),
    "dressing": ("Trauma dressing", "buddy", 1, "cover open wounds of the head, neck, abdomen or pelvis"),
    "junctional": ("Junctional tourniquet / wound packing", "medic", 1, "groin, armpit or neck bleeding"),
    "chest_seal": ("Vented chest seal", "buddy", 2, "chest or back wound: entry and exit"),
    "needle_decomp": ("Needle decompression kit", "medic", 1, "chest wound + breathing problem (tension pneumothorax)"),
    "npa": ("Nasopharyngeal airway", "medic", 1, "unconscious casualty: keep the airway open"),
    "pelvic_binder": ("Pelvic binder", "buddy", 1, "suspected pelvic injury (blast to the lower body, fall, crash)"),
    "splint": ("SAM splint", "buddy", 1, "suspected fracture"),
    "burn_dressing": ("Burn dressing", "buddy", 1, "burns"),
    "eye_shield": ("Rigid eye shield", "buddy", 1, "eye or face wound, or blast"),
    "iv_txa": ("IV/IO access + TXA", "medic", 1, "shock risk from blood loss"),
    "collar": ("Cervical collar", "medic", 1, "blunt mechanism (fall, crash) with head/neck injury or unconscious"),
    "hypothermia": ("Hypothermia prevention kit", "buddy", 1, "every serious casualty: blood loss + cold kill"),
    "litter": ("Litter (stretcher)", "team", 1, "cannot walk (or mobility unknown)"),
    "extrication": ("Extrication tools (pry bar, cutters, heavy gloves)", "team", 1, "casualty trapped"),
    "basics": ("Gloves, shears, casualty card", "buddy", 1, "always"),
}

# ------------------------------------------------------------------ team rules (placeholders)
TEAM = {"litter_bearers": 4, "litter_bearers_short": 2, "short_carry_m": 100,
        "long_carry_m": 500, "relief_bearers": 2, "urgent_per_medic": 2,
        "walking_per_escort": 3, "helpers_per_assisted": 1, "extrication_extra": 2,
        "vehicle_over_m": 1000}
CARRY = {"walks": "walks with escort", "assisted": "walks with a helper", "litter": "litter",
         "trapped": "free, then litter", "unknown": "litter (mobility unknown)"}


def _base(s):
    """'l_thigh' -> 'thigh'; 'chest' -> 'chest'."""
    return s[2:] if s[1:2] == "_" else s


def _seg_label(s):
    """'l_thigh' -> 'L thigh'."""
    side = {"l_": "L ", "r_": "R "}.get(s[:2], "")
    return side + _base(s).replace("_", " ")


# ------------------------------------------------------------------ build
def build(rep, distance_m=None):
    tw = body_mod.twin(rep)
    nodes, edges = {}, []

    def node(nid, label, col, status, group, detail=""):
        n = nodes.get(nid)
        rank = {"info": 0, "possible": 1, "mild": 2, "severe": 3, "critical": 4}
        if n is None:
            nodes[nid] = {"id": nid, "label": label, "col": col, "status": status, "group": group,
                          "detail": detail}
        elif rank[status] > rank[n["status"]]:
            n["status"] = status
        return nid

    def edge(a, b, kind):
        if (a, b) not in {(e["from"], e["to"]) for e in edges}:
            edges.append({"from": a, "to": b, "type": kind})

    threats = {k: set() for k in MARCH}      # MARCH letter -> structure / report node ids
    kit_need = {}                            # kit id -> set of reasons (node ids)
    team_rows, n_cas = [], 0

    def need(kid, why):
        kit_need.setdefault(kid, set()).add(why)

    for c in tw["casualties"]:
        n_cas += c["count"]
        s = c["signs"]
        crit = c["priority"] == "urgent"
        cid = f"c{c['index']}"
        pre = f"{cid}:"
        # Mechanism "checks" only add kit for a serious casualty: a walking casualty
        # after a fall does not need a collar and a pelvic binder.
        serious = crit or s.get("conscious") is False
        shock = False                       # this casualty has a circulation (shock) threat
        # ---- column 0: what was reported
        if c["mechanism"]:
            m = node(pre + "mech", f"{c['mechanism']}", 0, "severe", "report", "mechanism (said)")
            for sid, label, where, typ in MECHANISM_CHECK.get(c["mechanism"], []):
                st = node(pre + sid, label, 2, "possible", typ, f"check: {c['mechanism']} can cause this")
                edge(m, st, "possible")
                if sid in ("lungs",):
                    threats["R"].add(st)
                if sid in ("brain",):
                    threats["H"].add(st)
                if sid in ("eyes",):
                    need("eye_shield", st)
                if sid == "pelvic_ring" and serious:
                    need("pelvic_binder", st); threats["C"].add(st); shock = True
                if sid == "c_spine" and serious:
                    need("collar", st)
            # Blast with leg wounds: consider a pelvic binder (dismounted blast pattern).
            legs_hit = any(_base(sg) in ("thigh", "lower_leg", "foot", "pelvis")
                           for inj in c["injuries"] for sg in inj["segments"])
            if c["mechanism"] == "blast" and legs_hit and serious:
                st = node(pre + "pelvic_ring", "pelvic ring (blast + leg wounds)", 2, "possible", "bone",
                          "check: blast with leg wounds can injure the pelvis")
                edge(m, st, "possible"); need("pelvic_binder", st); threats["C"].add(st); shock = True
        for i, inj in enumerate(c["injuries"]):
            sev = "critical" if inj.get("massive") or inj["kind"] == "amputation" else \
                "severe" if inj["kind"] in ("gunshot", "shrapnel", "fracture", "bleeding") else "mild"
            r = node(pre + f"inj{i}", f"“{inj['text']}”", 0, sev, "report", f"{inj['kind']} (said)")
            for seg in inj["segments"]:
                pale = inj["side"] is None and seg[1:2] == "_"
                g = node(pre + seg, _seg_label(seg) + (" ?" if pale else ""), 1, sev, "region",
                         "side not said" if pale else "")
                edge(r, g, "reported")
                base = _base(seg)
                surface_back = inj.get("surface") == "back"
                for sid, label, typ in ANATOMY.get(base, []):
                    if typ not in KIND_THREAT.get(inj["kind"], set()):
                        continue
                    side = seg[:2].upper().replace("_", " ") if seg[1:2] == "_" else ""
                    lab = (side + label) if side else label
                    if surface_back and base in ("chest", "abdomen"):
                        lab += " (from the back)"
                    st = node(pre + f"{seg}:{sid}", lab, 2, "possible", typ, "possibly involved: check")
                    edge(g, st, "possible")
                    if typ == "vessel" and inj["kind"] in ("bleeding", "amputation", "gunshot", "shrapnel"):
                        if base in ("upper_arm", "forearm", "thigh", "lower_leg"):
                            threats["M"].add(st); need("tourniquet", st); need("pressure_bandage", st)
                        elif base in ("pelvis", "neck"):        # junctional: tourniquet can't reach
                            threats["M"].add(st); need("junctional", st); need("hemostatic", st)
                        else:                                    # inside chest/abdomen: can't compress
                            threats["C"].add(st); shock = True
                    if base in ("chest",) and inj["kind"] in ("gunshot", "shrapnel"):
                        threats["R"].add(st); need("chest_seal", st)
                    if base == "abdomen" and inj["kind"] in ("gunshot", "shrapnel"):
                        threats["C"].add(st); shock = True
                    if typ == "bone" and inj["kind"] in ("fracture", "gunshot"):
                        if sid in ("humerus", "radius_ulna", "femur", "tibia", "hand", "foot"):
                            need("splint", st)                    # limbs only, never ribs
                        if sid in ("femur", "pelvic_ring"):
                            threats["C"].add(st); shock = True   # big hidden blood loss
                    if sid == "pelvic_ring":
                        need("pelvic_binder", st)
                    if sid == "airway_upper":
                        threats["A"].add(st)
                    if sid == "eyes":
                        need("eye_shield", st)
                    if sid == "brain":
                        threats["H"].add(st)
                if inj["kind"] in ("gunshot", "shrapnel", "bleeding") and base in ("head", "neck", "abdomen", "pelvis"):
                    need("dressing", g)          # chest wounds get a chest seal instead
                if inj["kind"] == "burn":
                    need("burn_dressing", g)
                    if base in ("head", "neck"):
                        threats["A"].add(g)
                if base in ("chest", "abdomen") and surface_back and inj["kind"] in ("gunshot", "shrapnel"):
                    need("chest_seal", g); threats["R"].add(g)
        for t in c["tourniquets"]:
            tq = node(pre + "tq", f"tourniquet {t['time'] or ''}".strip(), 0, "critical", "report",
                      f"on {_seg_label(t['segment'])} (said)")
            g = node(pre + t["segment"], _seg_label(t["segment"]), 1, "critical", "region")
            edge(tq, g, "reported"); threats["M"].add(tq); need("tq_check", tq)
        # ---- signs
        if s.get("massive_bleeding"):
            mb = node(pre + "sign_mb", "massive bleeding", 0, "critical", "report", "sign (said)")
            threats["M"].add(mb); threats["C"].add(mb); shock = True
        if s.get("conscious") is False:
            un = node(pre + "sign_unc", "unconscious", 0, "critical", "report", "sign (said)")
            threats["A"].add(un); threats["H"].add(un); need("npa", un)
            if c["mechanism"] in ("fall", "vehicle"):
                need("collar", un)
        if s.get("breathing") is False:
            br = node(pre + "sign_br", "breathing problem", 0, "critical", "report", "sign (said)")
            threats["R"].add(br)
            if any(_base(sg) == "chest" for inj in c["injuries"] for sg in inj["segments"]) or c["mechanism"] in ("gunshot", "blast"):
                need("needle_decomp", br)
        if shock:
            need("iv_txa", "C")
        if crit or c["priority"] == "priority":
            threats["H"].add(pre + "hypo")
            node(pre + "hypo", "blood loss + cold", 0, "severe", "report", "inferred from priority")
            need("hypothermia", pre + "hypo")
        need("basics", "always")

        # ---- team for this casualty, from the mobility state (mobility.py)
        mob = c["mobility"]
        mstate = mob["plan"]                # = said state, unless it conflicts with the injuries
        team_rows.append({"casualty": c["index"] + 1, "count": c["count"], "priority": c["priority"],
                          "mobility": mstate, "carry": CARRY[mstate], "source": mob["source"],
                          "why": "; ".join(mob["evidence"]), "conflict": mob.get("conflict")})
        mn = node(pre + "mobility", mob["label"], 0,
                  {"trapped": "critical", "litter": "severe", "unknown": "possible"}.get(mstate, "mild"),
                  "report", f"mobility ({mob['source']}): " + "; ".join(mob["evidence"]))
        if mstate in ("litter", "trapped", "unknown"):
            need("litter", mn)
        if mstate == "trapped":
            need("extrication", mn)

    # ---- column 3: MARCH threats, column 4: kit
    for k, srcs in threats.items():
        if not srcs:
            continue
        mid = node("march:" + k, f"{k} · {MARCH[k]}", 3, "critical" if k in ("M", "A", "R") else "severe", "march")
        for sid in srcs:
            if sid in nodes:
                edge(sid, mid, "threatens")
    KIT_MARCH = {"tourniquet": "M", "tq_check": "M", "hemostatic": "M", "pressure_bandage": "M", "dressing": "M",
                 "junctional": "M", "npa": "A", "collar": "A", "chest_seal": "R", "needle_decomp": "R",
                 "iv_txa": "C", "pelvic_binder": "C", "hypothermia": "H", "eye_shield": "H"}
    kit = []
    for kid, whys in kit_need.items():
        name, who, qty, why = KIT[kid]
        q = qty * max(1, sum(1 for w in whys if w not in ("always", "C"))) if kid in ("pressure_bandage", "hemostatic") else qty
        per = 1 if kid in ("litter",) else n_cas
        total = q * per if kid != "litter" else sum(r["count"] for r in team_rows
                                                     if r["mobility"] in ("litter", "trapped", "unknown"))
        letter = KIT_MARCH.get(kid)
        kit.append({"id": kid, "name": name, "who": who, "qty": int(total), "why": why, "march": letter})
        if kid not in ("basics",):
            kn = node("kit:" + kid, f"{name} ×{int(total)}", 4, "info", "kit", why)
            if letter and ("march:" + letter) in nodes:
                edge("march:" + letter, kn, "needs")
            else:
                for w in whys:
                    if w in nodes:
                        edge(w, kn, "needs")
    order = "MARCH"
    kit.sort(key=lambda k: (order.index(k["march"]) if k["march"] else 9, k["who"] != "buddy"))

    return {"report_id": rep["id"], "nodes": list(nodes.values()), "edges": edges,
            "kit": kit, "team": team(team_rows, distance_m), "casualties": n_cas,
            "columns": ["Reported", "Body region", "Possibly impacted (check)", "MARCH threat", "Bring"],
            "disclaimer": "Decision support: organises what was reported. Rules to validate with a medical mentor."}


def team(rows, distance_m):
    """How many people to send: bearers, escorts, medics. Smallest team that can carry."""
    T = TEAM
    litters = sum(r["count"] for r in rows if r["mobility"] in ("litter", "trapped", "unknown"))
    walking = sum(r["count"] for r in rows if r["mobility"] == "walks")
    assisted = sum(r["count"] for r in rows if r["mobility"] == "assisted")
    trapped = sum(r["count"] for r in rows if r["mobility"] == "trapped")
    urgent = sum(r["count"] for r in rows if r["priority"] == "urgent")
    d = distance_m
    per_litter = T["litter_bearers_short"] if d is not None and d < T["short_carry_m"] else T["litter_bearers"]
    relief = T["relief_bearers"] if d is not None and d > T["long_carry_m"] else 0
    bearers = litters * (per_litter + relief)
    escorts = (-(-walking // T["walking_per_escort"]) if walking else 0) + assisted * T["helpers_per_assisted"]
    extra = trapped * T["extrication_extra"]
    medics = -(-urgent // T["urgent_per_medic"]) if urgent else (1 if litters else 0)
    lines = []
    if litters:
        lines.append(f"{litters} litter casualt{'y' if litters == 1 else 'ies'} × {per_litter} bearers"
                     + (f" + {relief} relief (carry > {T['long_carry_m']} m)" if relief else "")
                     + (" (short carry < 100 m)" if per_litter == T["litter_bearers_short"] else ""))
    if walking:
        n = -(-walking // T["walking_per_escort"])
        lines.append(f"{walking} can walk: {n} escort{'s' if n > 1 else ''}")
    if assisted:
        lines.append(f"{assisted} need{'s' if assisted == 1 else ''} help to walk: "
                     f"{assisted * T['helpers_per_assisted']} helper{'s' if assisted > 1 else ''}")
    if trapped:
        lines.append(f"{trapped} trapped: +{extra} for extraction")
    if any(r["mobility"] == "unknown" for r in rows):
        lines.append("mobility not said: a stretcher is planned to be safe")
    if medics:
        lines.append(f"{medics} medic{'s' if medics > 1 else ''}" +
                     (f" ({urgent} urgent, 1 per {T['urgent_per_medic']})" if urgent else ""))
    notes = [f"casualty {r['casualty']}: {r['conflict']}: check" for r in rows if r.get("conflict")]
    if trapped:
        notes.append("trapped for a long time: tell the medic before freeing (crush injury)")
    if d is not None and d > T["vehicle_over_m"]:
        notes.append(f"{d / 1000:.1f} km to the collection point: request a vehicle if the route allows")
    notes.append("send the smallest team that can carry: every extra person is exposed (drones)")
    # A medic can also carry: the medic counts as one bearer when the team is minimal.
    total = bearers + escorts + medics + extra
    return {"total": total, "bearers": bearers, "escorts": escorts, "medics": medics, "extrication": extra,
            "rows": rows, "lines": lines, "notes": notes,
            "distance_m": round(d) if d is not None else None}
