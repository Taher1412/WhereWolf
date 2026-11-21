"""Can the casualty move? walks | assisted | litter | trapped | unknown

1. SAID first (English + French), latest mention wins:
     trapped   "pinned under rubble", "trapped", "coincé", "bloqué"
     litter    "can't walk", "can't stand", "can't move his legs", "needs a stretcher", "ne peut pas marcher"
     assisted  "limping", "needs help to walk", "leaning on me", "il boite"
     walks     "can walk", "walking wounded", "on his feet", "peut marcher"
2. Otherwise INFERRED from the report (marked as inferred):
     unconscious, massive bleeding, breathing problem       -> litter
     thigh / pelvis wound, leg fracture, tourniquet on a leg -> litter
     wound to the lower leg or foot only                     -> assisted
     standing, or "conscious" said and no leg wound         -> walks
     nothing to go on                                        -> unknown (plan a stretcher)

Decision support: what was said always wins; inferred states are a planning default.
"""
import re

STATES = ["walks", "assisted", "litter", "trapped", "unknown"]
LABEL = {"walks": "can walk", "assisted": "needs help to walk", "litter": "stretcher needed",
         "trapped": "trapped: extraction needed", "unknown": "mobility unknown (plan a stretcher)"}
LABEL_FR = {"walks": "peut marcher", "assisted": "marche avec aide", "litter": "brancard nécessaire",
            "trapped": "coincé : désincarcération", "unknown": "mobilité inconnue"}
CODE = {"walks": "W", "assisted": "A", "litter": "L", "trapped": "T", "unknown": "U"}

SAID = [
    ("trapped", r"\btrapped|\bpinned|stuck under|under (the )?rubble|can'?t (get|pull) (him|her|them) out|"
                r"coinc[ée]|bloqu[ée]|ensevel|sous les d[ée]combres"),
    ("litter", r"can'?t walk|cannot walk|unable to walk|not able to walk|can'?t stand|cannot stand|"
               r"can'?t move (his|her|their|my) legs?|can'?t get up|needs? (a )?(stretcher|litter)|"
               r"\bparaly|ne (peut|peux) (pas|plus) marcher|ne marche (pas|plus)|ne tient pas debout|"
               r"besoin d'un brancard|brancard|civi[eè]re"),
    ("assisted", r"\blimp|\bhobbl|needs? help (to )?walk|walk(s|ing)? with help|leaning on|with support|"
                 r"\bboite|marche avec (de l')?aide|soutenu"),
    ("walks", r"can walk|able to walk|walking wounded|(he|she|they)( i|')?s walking|is walking|"
              r"on (his|her|their|my) feet|walks? (by|on) (him|her|them)sel|"
              r"(peut|peux) marcher|marche seul|il marche|elle marche|bless[ée]s? l[ée]gers?"),
]


def said(texts):
    """(state, phrase) from the latest mention in the transcripts, or None.
    A match inside a longer one is ignored ("ne marche pas" is not "marche")."""
    joined = " . ".join(texts).lower()
    hits = []
    for state, pat in SAID:
        for m in re.finditer(pat, joined):
            hits.append((m.start(), m.end(), state, m.group(0)))
    hits = [h for h in hits if not any(o[0] <= h[0] and h[1] <= o[1] and o != h for o in hits)]
    if not hits:
        return None
    s, e, state, phrase = max(hits, key=lambda h: h[0])
    return state, phrase


LEG_HEAVY = ("thigh", "pelvis")
LEG_LIGHT = ("lower_leg", "foot")


def _base(seg):
    return seg[2:] if seg[1:2] == "_" else seg


def infer(cas, posture):
    """State + reasons from one casualty of body.twin()."""
    s = cas.get("signs") or {}
    reasons = []
    if s.get("conscious") is False:
        reasons.append("unconscious")
    if s.get("massive_bleeding"):
        reasons.append("massive bleeding")
    if s.get("breathing") is False:
        reasons.append("breathing problem")
    legs_tq = [t for t in cas.get("tourniquets") or [] if _base(t["segment"]) in ("thigh", "lower_leg")]
    if legs_tq:
        reasons.append("tourniquet on a leg")
    heavy, light = [], []
    for inj in cas.get("injuries") or []:
        for seg in inj["segments"]:
            b = _base(seg)
            if b in LEG_HEAVY or (b in LEG_LIGHT and inj["kind"] in ("fracture", "gunshot", "amputation")):
                heavy.append(f"{inj['kind']} {b.replace('_', ' ')}")
            elif b in LEG_LIGHT:
                light.append(f"{inj['kind']} {b.replace('_', ' ')}")
    if heavy:
        reasons.append("leg/pelvis wound: " + ", ".join(dict.fromkeys(heavy)))
    if reasons:
        return "litter", reasons
    if light:
        return "assisted", ["lower leg / foot wound: " + ", ".join(dict.fromkeys(light))]
    if posture == "standing":
        return "walks", ["standing / walking (said)"]
    if cas.get("injuries") and s.get("conscious") is True:
        return "walks", ["conscious (said), no leg wound"]
    return "unknown", ["nothing said about walking or consciousness"]


def assess(rep, cas, posture):
    """Mobility of one casualty: what was said wins, else inferred."""
    texts = [t["text"] for t in rep.get("transcripts", [])]
    s = said(texts)
    if s:
        state, phrase = s
        inferred, why = infer(cas, posture)
        out = {"state": state, "source": "said", "evidence": [f"“{phrase}”"]}
        # Said "walks" but the report says unconscious / tourniquet on a leg: flag it.
        if state in ("walks", "assisted") and inferred == "litter":
            out["conflict"] = "said walking, but " + "; ".join(why)
            out["plan"] = "litter"          # plan the stretcher anyway, to be safe
    else:
        state, why = infer(cas, posture)
        out = {"state": state, "source": "inferred", "evidence": why}
    out.setdefault("plan", out["state"])  # what the team is sized for
    out["label"] = LABEL[out["state"]]
    out["label_fr"] = LABEL_FR[out["state"]]
    out["code"] = CODE[out["state"]]
    return out


def worst(states):
    """For the read-back: the hardest case among several casualties."""
    order = ["trapped", "litter", "unknown", "assisted", "walks"]
    return min(states, key=order.index) if states else None
