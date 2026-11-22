"""Danger zones: which threats were heard or reported, and roughly where.

Two sources:
  audio  the sound classifiers on a clip from the phone (acoustic.danger_sounds):
         gunfire, explosions, drones
  voice  words in the spoken report: "drone overhead", "sniper at my 2 o'clock",
         "taking fire from the north", "mines on the track"

One phone never tells where the shooter or the drone is. So a danger is pinned to
the REPORTER's estimated position, and its zone is how far that kind of threat is
usually heard or seen from (RANGE_M below: placeholders to validate with a mentor),
plus the reporter's own position uncertainty.
- The speaker gives a direction and we know which way they face (sun compass, or a
  compass word like "north"): the zone becomes a wedge in that direction.
- Two or more reports of the same threat that overlap: the overlap is drawn as the
  likely source area.
"""
import math
import re

import numpy as np

# label, colour on the map, typical distance it is heard / seen from (m),
# how long a report stays relevant (min), one-letter code for the radio packet.
TYPES = {
    "drone":      {"label": "Drone", "fr": "drone", "color": "#ff4fd8", "range_m": 150, "ttl_min": 10, "code": "U"},
    "small_arms": {"label": "Small-arms fire", "fr": "tirs", "color": "#ff453a", "range_m": 400, "ttl_min": 15, "code": "G"},
    "sniper":     {"label": "Sniper", "fr": "tireur d'élite", "color": "#ff9f0a", "range_m": 600, "ttl_min": 30, "code": "S"},
    "explosion":  {"label": "Explosions / shelling", "fr": "explosions", "color": "#ffd60a", "range_m": 800, "ttl_min": 30, "code": "X"},
    "armour":     {"label": "Armour", "fr": "blindés", "color": "#bf5af2", "range_m": 500, "ttl_min": 20, "code": "A"},
    "mines":      {"label": "Mines / IED", "fr": "mines", "color": "#ac8e68", "range_m": 60, "ttl_min": 24 * 60, "code": "M"},
}
ORDER = list(TYPES)

# Spoken words, English and French. Injury words ("gunshot wound", "blast") are left
# out on purpose: they describe how the casualty was hurt, not an active threat.
WORDS = {
    "drone": r"\b(drones?|fpv|quadcopters?|uavs?|quadricopt[eè]res?)\b",
    "sniper": r"\b(snipers?|tireurs? d'[ée]lite|tireurs? embusqu[ée]s?)\b",
    "small_arms": (r"(\bunder fire\b|\btaking fire\b|\bincoming fire\b|\bgunfire\b|\bshots? fired\b|"
                   r"\bshooting\b|\bmachine ?guns?\b|\bsmall[- ]arms\b|\bfusillade\b|\bsous le feu\b|"
                   r"\bon se fait tirer\b|\bdes tirs\b|\btirs? (?:de|ennemis?|nourris?)\b|\bmitrailleuses?\b|"
                   r"\bcoups? de feu\b|\bon nous tire\b)"),
    "explosion": (r"\b(explosions?|shelling|artillery|mortars?|incoming rounds?|rounds? landing|"
                  r"bombing|air ?strikes?|obus|artillerie|mortiers?|bombardements?|frappes?)\b"),
    "armour": r"\b(?<!water )(tanks?|armou?red vehicles?|apcs?|ifvs?|bmps?|btrs?|chars? d'assaut|blind[ée]s)\b",
    "mines": (r"\b(mines|minefield|land ?mines?|an? mine|ieds?|booby[- ]?traps?|champ de mines|"
              r"engins? explosifs?|pi[eè]g[ée]s?)\b"),
}
NEG = r"\b(no|not|without|zero|clear of|pas de|pas d'|aucune?|sans|plus de)\b[^.,;]{0,25}$"
CASUALTY = (r"(casualt|wounded|injur|hurt|\bhit\b|bless|touch[ée]|victim|patient|bleed|saign|wound|"
            r"shrapnel|[ée]clat|\b(man|guy|one|soldier)s? down\b|\btook\b|amput|burn|br[uû]l)")
OVERHEAD = (r"\b(overhead|above us|over us|on us|on our position|right here|here|"
            r"au-dessus|sur nous|sur notre position|ici)\b")
COMPASS = {"north": 0, "north east": 45, "east": 90, "south east": 135, "south": 180,
           "south west": 225, "west": 270, "north west": 315,
           "nord": 0, "nord est": 45, "est": 90, "sud est": 135, "sud": 180, "sud ouest": 225,
           "ouest": 270, "nord ouest": 315}
COMPASS_EN = r"\b(north|south)[- ]?(east|west)?\b|\b(east|west)\b"
# French "est" is also "is": only after a preposition.
COMPASS_FR = r"\b(?:au|du|vers le|le)\s+(nord|sud)(?:[- ](est|ouest))?\b|\b(?:à l'|a l'|de l'|vers l')\s*(est|ouest)\b"

NEXT_DIR = r"(from|at my|to my|du|de l'|depuis|à mes|a mes|venant)\b"

DEDUPE_MS = 120_000     # same threat, same source, same report within 2 min = one event
HEADING_KNOWN = 5.0      # heading_conf (1 = uniform over 72 headings) above which a clock becomes a bearing
WEDGE_HALF_DEG = 25.0
PLACE_MAX_M = 500.0     # reporter less sure of their position than this: threat listed, not drawn as an area


# ------------------------------------------------------------------ from speech
def _clauses(text):
    return [c.strip() for c in re.split(r"[.;!?,]| and | but | et | mais ", text) if c.strip()]


def threat_only(sentence):
    """True for a sentence about a threat that says nothing about a casualty
    ("Drone overhead"): kept out of the casualty parser (MIST mechanism)."""
    s = sentence.lower()
    return any(re.search(p, s) for p in WORDS.values()) and not re.search(CASUALTY, s)


def _compass(clause):
    c = clause.lower()
    m = re.search(COMPASS_FR, c)
    if m:
        key = m.group(1) or m.group(3)
        return COMPASS[f"{key} {m.group(2)}" if m.group(2) else key]
    m = re.search(COMPASS_EN, c)
    if m:
        key = f"{m.group(1)} {m.group(2)}" if m.group(2) else (m.group(1) or m.group(3))
        return COMPASS[key]
    return None


def from_text(text):
    """Threats named in a spoken report -> [{type, clock, bearing_abs, here, text}]."""
    from .extract import _clock
    out = []
    cls = _clauses(text)
    for j, cl in enumerate(cls):
        lc = cl.lower()
        for t, pat in WORDS.items():
            m = re.search(pat, lc)
            if not m or re.search(NEG, lc[:m.start()]):
                continue
            if any(d["type"] == t for d in out):
                continue
            clock, comp = _clock(cl), _compass(cl)
            # "Taking fire, from my 3 o'clock": the direction is in the next clause.
            nxt = cls[j + 1] if j + 1 < len(cls) else ""
            if clock is None and comp is None and re.match(NEXT_DIR, nxt.lower()):
                clock, comp = _clock(nxt), _compass(nxt)
            out.append({"type": t, "clock": clock, "bearing_abs": comp,
                        "here": bool(re.search(OVERHEAD, lc)), "text": cl[:80]})
    return out


# ------------------------------------------------------------------ events
def add(dangers, new):
    """Append one danger event; the same threat from the same source within
    DEDUPE_MS is one event (keep the newest, the strongest, any direction)."""
    for i, d in enumerate(dangers):
        if (d["type"] == new["type"] and d["source"] == new["source"]
                and new["ms"] - d["ms"] < DEDUPE_MS):
            keep_dir = {k: d.get(k) for k in ("clock", "bearing_abs") if d.get(k) is not None}
            merged = {**d, **new, "conf": max(d["conf"], new["conf"])}
            for k, v in keep_dir.items():
                if merged.get(k) is None:
                    merged[k] = v
            dangers[i] = merged
            return dangers
    dangers.append(new)
    return dangers


def from_audio(alerts, ms):
    """acoustic alerts -> danger events (wind on the mic makes 'explosions' doubtful)."""
    out = []
    for a in alerts:
        if a["class"] not in TYPES:
            continue
        out.append({"type": a["class"], "source": "audio", "conf": float(a["score"]), "ms": ms,
                    "clock": None, "bearing_abs": None, "here": False,
                    "text": ", ".join(f"{n} {s}" for n, s in a.get("labels", [])[:2]) or None,
                    "doubt": a.get("doubt")})
    return out


def active(dangers, now):
    return [d for d in dangers if now - d["ms"] < TYPES[d["type"]]["ttl_min"] * 60_000]


# ------------------------------------------------------------------ geometry
def _bearing(d, pos):
    """Absolute bearing of the threat, or None if we cannot say."""
    if d.get("bearing_abs") is not None:
        return float(d["bearing_abs"])
    if d.get("clock") and pos.get("heading_deg") is not None and (pos.get("heading_conf") or 0) >= HEADING_KNOWN:
        return (pos["heading_deg"] + d["clock"] * 30.0) % 360
    return None


def zone(d, pos):
    """One event + the reporter's position -> a circle or a wedge on the map."""
    T = TYPES[d["type"]]
    pos_r = float(pos.get("radius_m") or 0)
    b = _bearing(d, pos)
    z = {"lat": pos["lat"], "lon": pos["lon"], "pos_r": pos_r, "placed": pos_r <= PLACE_MAX_M}
    if d.get("here") and b is None:
        z.update(shape="circle", radius_m=pos_r + 0.5 * T["range_m"])
    elif b is not None:
        z.update(shape="wedge", bearing_deg=round(b, 1), half_deg=WEDGE_HALF_DEG,
                 radius_m=pos_r + 1.5 * T["range_m"])
    else:
        z.update(shape="circle", radius_m=pos_r + T["range_m"])
    return z


def _inside(z, x, y, x0, y0):
    """Soft membership (0..1) of points (x, y) in metres, zone centre at (x0, y0)."""
    dx, dy = x - x0, y - y0
    d = np.hypot(dx, dy)
    soft = 0.15 * z["radius_m"] + 25
    m = np.clip(1 - (d - z["radius_m"]) / soft, 0, 1)
    if z["shape"] == "wedge":
        ang = (np.degrees(np.arctan2(dx, dy)) - z["bearing_deg"] + 180) % 360 - 180
        m = m * np.clip(1 - (np.abs(ang) - z["half_deg"]) / 10, 0, 1)
        m = np.where(d < z["pos_r"] + 25, np.maximum(m, 0.5), m)   # the reporter may be anywhere in pos_r
    return m


def hotspots(zones):
    """Where reports of the same threat from different units overlap."""
    out = []
    for t in ORDER:
        zs = [z for z in zones if z["type"] == t and z["placed"]]
        reps = sorted({z["report"] for z in zs})
        if len(reps) < 2:
            continue
        lat0 = float(np.mean([z["lat"] for z in zs]))
        lon0 = float(np.mean([z["lon"] for z in zs]))
        kx, ky = 111320 * math.cos(math.radians(lat0)), 110540
        cen = {id(z): ((z["lon"] - lon0) * kx, (z["lat"] - lat0) * ky) for z in zs}
        R = max(z["radius_m"] for z in zs) + max(math.hypot(*c) for c in cen.values())
        g = np.arange(-R, R + 1, 20.0)
        X, Y = np.meshgrid(g, g)
        prod = np.ones_like(X)
        for rid in reps:   # product over units, max over each unit's own events
            prod *= np.max([_inside(z, X, Y, *cen[id(z)]) for z in zs if z["report"] == rid], axis=0)
        core = prod >= 0.5
        if not core.any():
            continue
        area = core.sum() * 400.0
        smallest = min(math.pi * z["radius_m"] ** 2 * (z["half_deg"] / 180 if z["shape"] == "wedge" else 1)
                       for z in zs)
        if area > 0.8 * smallest:      # the reports do not narrow it down
            continue
        w = prod * core
        cx, cy = float((X * w).sum() / w.sum()), float((Y * w).sum() / w.sum())
        out.append({"type": t, "label": TYPES[t]["label"], "color": TYPES[t]["color"],
                    "lat": lat0 + cy / ky, "lon": lon0 + cx / kx,
                    "radius_m": round(math.sqrt(area / math.pi)), "n_reports": len(reps),
                    "reports": reps})
    return out


def zones(reports, now):
    """Everything the map needs: one zone per active event + the overlaps."""
    out = []
    for r in reports:
        here = r.get("position") or {}
        for i, d in enumerate(active(r.get("dangers", []), now)):
            # A unit that walks away (guide.py) leaves its threats where it reported them.
            pos = d.get("at") or here
            if pos.get("lat") is None:
                continue
            T = TYPES[d["type"]]
            out.append({"id": f"{r['id']}:{i}", "report": r["id"], "callsign": r.get("callsign") or r["id"],
                        "type": d["type"], "label": T["label"], "color": T["color"],
                        "source": d["source"], "conf": round(d["conf"], 2), "ms": d["ms"],
                        "ttl_ms": T["ttl_min"] * 60_000, "text": d.get("text"), "doubt": d.get("doubt"),
                        **zone(d, pos)})
    return {"zones": out, "hotspots": hotspots(out),
            "types": {k: {"label": v["label"], "color": v["color"], "range_m": v["range_m"],
                          "ttl_min": v["ttl_min"]} for k, v in TYPES.items()}}


def near(rep, zs):
    """Threats reported by OTHER units whose zone covers this report's position."""
    pos = rep.get("position") or {}
    if pos.get("lat") is None:
        return []
    found = set()
    for z in zs:
        if z["report"] == rep["id"] or not z["placed"]:
            continue
        kx, ky = 111320 * math.cos(math.radians(z["lat"])), 110540
        x, y = (pos["lon"] - z["lon"]) * kx, (pos["lat"] - z["lat"]) * ky
        if float(_inside(z, np.array(x), np.array(y), 0.0, 0.0)) >= 0.5:
            found.add(z["type"])
    return [t for t in ORDER if t in found]


def spoken(types, lang="en"):
    return ", ".join(TYPES[t]["fr" if lang == "fr" else "label"].lower() for t in types)
