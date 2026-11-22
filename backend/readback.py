"""Spoken read-back and the compact radio packet."""
import time

from . import config


def _round_r(r):
    if r is None:
        return None
    return int(max(20, round(r / 10.0) * 10))


def position_state(pos):
    """'none' | 'ambiguous' | 'rough' | 'confirmed'."""
    if not pos or not pos.get("blobs"):
        return "none"
    big = [b for b in pos["blobs"] if b["mass"] >= 0.08]
    if pos["main_mass"] < 0.45 or (len(big) >= 2 and pos["main_mass"] < 0.6):
        return "ambiguous"
    if pos["radius_m"] <= config.TARGET_RADIUS_M:
        return "confirmed"
    return "rough"


SPACE_FR = {"indoor_small": "à l'intérieur, petite pièce", "indoor_large": "à l'intérieur, grand volume",
            "outdoor_enclosed": "dehors, entre des bâtiments", "outdoor_open": "dehors, terrain dégagé"}
SPACE_CODE = {"indoor_small": "IS", "indoor_large": "IL", "outdoor_enclosed": "OE", "outdoor_open": "OO"}


def _space(report):
    """Latest confident acoustic verdict on the kind of space, or None."""
    for a in reversed(report.get("acoustic") or []):
        sp = a.get("space") or {}
        if sp.get("strength", 0) >= 0.15 and sp.get("p_best", 0) >= 0.5:
            return sp
    return None


def _space_line(report, lang):
    sp = _space(report)
    if not sp:
        return ""
    if lang == "fr":
        txt = f"D'après le son : {SPACE_FR[sp['best']]}."
        wall = (sp.get("probe") or {}).get("nearest_wall_m")
        if wall and (sp.get("probe") or {}).get("wall_reliable"):
            txt += f" Paroi à environ {wall:.0f} mètres."
        return txt
    txt = f"Sound says {sp['label']}."
    pr = sp.get("probe") or {}
    if pr.get("nearest_wall_m") and pr.get("wall_reliable"):
        txt += f" Nearest wall about {pr['nearest_wall_m']:.0f} metres."
    return txt


def _mobility(report):
    """Hardest mobility state among the report's casualties, or None."""
    from .body import twin
    from .mobility import worst
    if not report.get("casualties"):
        return None
    tw = twin(report)
    return worst([c["mobility"]["state"] for c in tw["casualties"]])


def _alternatives(report, lang):
    """'Also possible: area B, 400 m north-east.' from the distinct likely spots."""
    import math
    hs = ((report.get("position") or {}).get("hyps") or [])
    if len(hs) < 2:
        return ""
    a = hs[0]
    names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
    noms = ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"]
    parts = []
    for h in hs[1:]:
        if h["mass"] < 0.08:
            continue
        dy = (h["lat"] - a["lat"]) * 110540
        dx = (h["lon"] - a["lon"]) * 111320 * math.cos(math.radians(a["lat"]))
        d = int(round(math.hypot(dx, dy) / 50.0) * 50)
        k = int(round((math.degrees(math.atan2(dx, dy)) % 360) / 45)) % 8
        parts.append(f"zone {h['label']}, {d} mètres {noms[k]}" if lang == "fr" else
                     f"area {h['label']}, {d} metres {names[k]}")
    if not parts:
        return ""
    return ("Aussi possible : " if lang == "fr" else "Also possible: ") + "; ".join(parts) + "."


def _urgent(report, lang):
    """The threat that gets worse soonest, if within ~15 min (backend/condition.py)."""
    from .condition import assess
    best = None
    for i, c in enumerate(report.get("casualties") or []):
        w = assess(c, report, i)["worse_in"]
        if w and w["min"] <= 15 and (best is None or w["min"] < best["min"]):
            best = w
    if not best:
        return ""
    lo, hi = int(round(best["min"])), max(1, int(round(best["max"])))
    if lang == "fr":
        when = "maintenant" if best["overdue"] else (f"dans les {hi} prochaines minutes" if lo < 1 else f"d'ici {lo} à {hi} minutes")
    else:
        when = "now" if best["overdue"] else (f"within the next {hi} minutes" if lo < 1 else f"within {lo} to {hi} minutes")
    if lang == "fr":
        return f"Attention, état critique {when} : {best['threat'].lower()}."
    return f"Warning, critical {when}: {best['threat'].lower()}."


def make(report):
    lang = report.get("lang", "en")
    mob = _mobility(report)
    s = report["summary"]
    pos = report.get("position")
    q = report.get("question")
    st = position_state(pos)
    r = _round_r(pos["radius_m"]) if pos and pos.get("radius_m") else None
    n_areas = max(2, len([b for b in (pos or {}).get("blobs", []) if b["mass"] >= 0.08]))
    space = _space_line(report, lang)
    alert = bool(report.get("alerts"))
    if (report.get("stress") or {}).get("level") == "high":
        space = ""                            # stressed speaker: essentials only
    alt = _alternatives(report, lang)
    if alt:
        space = alt + (" " + space if space else "")
    urgent = _urgent(report, lang)
    if urgent:
        space = urgent + (" " + space if space else "")
    aimed = report.pop("aim_note", None)     # once, right after the taps were used
    if aimed:
        space = ((f"Visées utilisées : {aimed}." if lang == "fr" else
                  f"Used {aimed} aimed landmark{'s' if aimed > 1 else ''}.") + (" " + space if space else ""))
    from . import danger
    now = int(time.time() * 1000)
    mine = []    # threats this unit reported, newest first, no repeats
    for d in sorted(danger.active(report.get("dangers", []), now), key=lambda d: -d["ms"]):
        if d["type"] not in mine:
            mine.append(d["type"])
    near = [t for t in report.get("danger_near", []) if t not in mine]

    if lang == "fr":
        pri = {"urgent": "urgent", "priority": "prioritaire", "routine": "non urgent"}
        parts = ["Reçu."]
        if s["count"]:
            parts.append(f"{s['count']} blessé{'s' if s['count'] > 1 else ''} "
                         f"{pri.get(s['priority'], '')}"
                         + (f", garrot {s['tq_time'].replace(':', 'h')}" if s["tq_time"] else "") + ".")
        if mob in ("litter", "trapped", "walks", "assisted"):
            from .mobility import LABEL_FR
            parts.append(LABEL_FR[mob][0].upper() + LABEL_FR[mob][1:] + ".")
        if st == "none":
            parts.append("Pas encore de position.")
        elif st == "ambiguous":
            parts.append(f"{n_areas} zones possibles, la meilleure à {r} mètres près.")
        elif st == "confirmed":
            parts.append(f"Position confirmée à {r} mètres près.")
        else:
            parts.append(f"Position à {r} mètres près.")
        if space:
            parts.append(space)
        if mine:
            parts.append(f"Danger noté : {danger.spoken(mine, 'fr')}.")
        if near:
            parts.append(f"Attention : {danger.spoken(near, 'fr')} signalé près de vous.")
        if q:
            parts.append("Question : " + q["text"])
        elif s["count"]:
            parts.append(f"Priorité d'évacuation {s['rank']}.")
        return " ".join(parts)

    parts = ["Copy."]
    if s["count"]:
        word = "casualty" if s["count"] == 1 else "casualties"
        parts.append(f"{s['count']} {s['priority'] or ''} {word}"
                     + (f", tourniquet {s['tq_time']}" if s["tq_time"] else "") + ".")
    if mob in ("litter", "trapped", "walks", "assisted"):
        from .mobility import LABEL
        parts.append(LABEL[mob][0].upper() + LABEL[mob][1:] + ".")
    if st == "none":
        parts.append("No position yet.")
    elif st == "ambiguous":
        parts.append(f"{n_areas} possible areas, best one within {r} metres.")
    elif st == "confirmed":
        parts.append(f"Position confirmed within {r} metres.")
    else:
        parts.append(f"Position within about {r} metres.")
    if space:
        parts.append(space)
    if mine:
        parts.append(f"Danger logged: {danger.spoken(mine)}.")
    if near:
        parts.append(f"Warning: {danger.spoken(near)} reported near you.")
    if q:
        parts.append("Question: " + q["text"])
    elif s["count"]:
        parts.append(f"Evacuation priority {s['rank']}.")
    return " ".join(parts).replace("  ", " ")


def packet(report):
    """Compact text message for a jammed / low-bandwidth link (target < 120 bytes).
    NR1|callsign|P1|lat,lon|r60|TQ1432|n1"""
    s = report["summary"]
    pos = report.get("position") or {}
    fields = ["NR1", (report.get("callsign") or report["id"])[:10].replace(" ", "")]
    fields.append(f"P{s['rank']}" if s["count"] else "P-")
    if pos.get("lat") is not None:
        fields.append(f"{pos['lat']:.4f},{pos['lon']:.4f}")      # ~10 m resolution
        fields.append(f"r{_round_r(pos['radius_m'])}")
    if s["tq_time"]:
        fields.append("TQ" + s["tq_time"].replace(":", ""))
    sp = _space(report)
    if sp:
        fields.append("S" + SPACE_CODE[sp["best"]])      # e.g. SOE = outdoors between buildings
    mob = _mobility(report)
    if mob:
        from .mobility import CODE
        fields.append("M" + CODE[mob])                   # MW walks, MA assisted, ML litter, MT trapped
    from . import danger
    codes = sorted({danger.TYPES[d["type"]]["code"] for d in danger.active(report.get("dangers", []),
                                                                           int(time.time() * 1000))})
    if codes:
        fields.append("D" + "".join(codes))           # e.g. DGU = gunfire + drone
    fields.append(f"n{s['count']}")
    text = "|".join(fields)
    return {"text": text, "bytes": len(text.encode("utf-8"))}
