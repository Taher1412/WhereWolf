"""Turn a spoken report into structured JSON.

extract(text, context) -> dict  (schema in CLAUDE.md section 6.2)

Uses Mistral (JSON output) when MISTRAL_API_KEY is set, otherwise (or if the
call fails) a rule-based parser for English and French. Both give the same shape.
"""
import json
import re
from datetime import datetime, timedelta

import httpx

from . import config
from .landmarks import SYNONYMS, _fold, normalise_type

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a": 1, "an": 1,
             "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six ": 6,
             "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "midi": 12}
NUM_RE = "|".join(sorted((k.strip() for k in NUM_WORDS), key=len, reverse=True))

FRENCH_HINTS = r"\b(je|nous|on|vois|blessé|blesse|garrot|heures|à|mon|ma|gauche|droite|église|soleil|oui|non)\b"


def empty():
    return {"callsign": None, "casualties": [], "observations": [], "sun": None,
            "answer_to_question": None, "lang": "en", "hearing": [], "surroundings": None}


# ---------------- what the operator says they HEAR (not see)
HEAR_VERB = r"(\bhear\b|\bhearing\b|\bheard\b|j'?entends|\bentend|on entend)"
HEAR_CLASSES = {
    "rail": r"\b(trains?|railway|tram|rer|locomotive|rails?)\b",
    "traffic": r"\b(traffic|cars?|trucks?|lorr(y|ies)|road noise|vehicles?|circulation|voitures?|camions?)\b",
    "bells": r"\b(bells?|cloches?|carillon)\b",
    "machinery": r"(machinery|machines?\b|\bdrill|jackhammer|construction|chantier|marteau|perceuse|power tool)",
    "nature": r"\b(birds?|oiseaux?|crickets?|insects?|grillons?)\b",
}
HEAR_NEG = r"(\bno\b|\bnot\b|don'?t|can'?t|cannot|haven'?t|didn'?t|nothing|\bpas\b|\brien\b|aucun|n'entends)"
# A heard direction points at the thing making the noise.
HEARD_LANDMARK = {"rail": "railway", "bells": "church", "traffic": "main_road"}
BUILT_SAID = (r"(surrounded by buildings|between buildings|built[- ]up|in a street|in the street|"
              r"between houses|entour[ée]s? d'immeubles|entour[ée]s? de b[âa]timents|entre (les|des) immeubles|"
              r"dans une rue|dans la rue|en ville)")
OPEN_SAID = (r"(in the open|open ground|open area|open field|no buildings|à découvert|a decouvert|"
             r"terrain d[ée]gag[ée]|en terrain ouvert|pas de b[âa]timents)")


MECH_WORDS = (r"(blast|explo|ied|mine|grenade|shell|mortar|drone|shrapnel|frag|obus|éclat|eclat|"
              r"shot|gunshot|gsw|bullet|sniper|balle|tir|fall|fell|chute|tomb|vehicle|crash|truck|"
              r"accident|véhicule|vehicule|burn|brûl|stab|couteau|crush|écras)")


def _hearing(clause):
    """[(group, heard?)] for a clause about sounds."""
    lc = clause.lower()
    neg = bool(re.search(HEAR_NEG, lc))
    return [(g, not neg) for g, pat in HEAR_CLASSES.items() if re.search(pat, lc)]


# ===================================================================== rules
def _num(s):
    s = s.strip().lower()
    return int(s) if s.isdigit() else NUM_WORDS.get(s)


def _find_landmarks(clause):
    """All (type, position) of landmark words in a clause, longest match first."""
    f = " " + _fold(clause) + " "
    found, taken = [], []
    pairs = sorted(((t, _fold(w)) for t, ws in SYNONYMS.items() for w in ws),
                   key=lambda p: -len(p[1]))
    for t, w in pairs:
        for m in re.finditer(rf"(?<![a-z]){re.escape(w)}(?![a-z])", f):
            a, b = m.span()
            if any(a < y and b > x for x, y in taken):
                continue
            taken.append((a, b))
            found.append((t, a))
    found.sort(key=lambda p: p[1])
    return found


def _clock(clause):
    if re.search(r"\b(à|a|at)\s+midi\b", clause, re.I):
        return 12
    m = re.search(rf"\b(1[0-2]|[1-9]|{NUM_RE})\s*(?:o'?\s*clock|oclock|o'clock|heures?\b|h\b(?!\s*\d))",
                  clause, re.I)
    if m:
        return _num(m.group(1))
    # Slang without "o'clock": "keep's off to my two", "church at ten".
    words = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    m = re.search(rf"\b(?:at|to|on)\s+(?:my\s+|your\s+)?(1[0-2]|[1-9]|{words})\b"
                  r"(?!\s*(?:m\b|meters?|metres?|mètres|min|minutes|km|:|h\d|%))", clause, re.I)
    return _num(m.group(1)) if m else None


def _relative(clause):
    c = clause.lower()
    if re.search(r"\b(behind|derri[eè]re|dans mon dos)\b", c):
        return "behind"
    if re.search(r"\b(left|gauche)\b", c):
        return "left"
    if re.search(r"\b(right|droite)\b", c):
        return "right"
    if re.search(r"\b(ahead|in front|straight|devant|en face|tout droit)\b", c):
        return "ahead"
    return None


def _distance(clause):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|kilom[eè]tres?|kilometers?)\b", clause, re.I)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    m = re.search(r"(\d+)\s*(m|meters?|metres?|mètres?)\b", clause, re.I)
    return float(m.group(1)) if m else None


def _times(text):
    """Times like 14:32, 14h32, 14 32, 1432, 2:32 pm."""
    out = []
    for m in re.finditer(r"\b(\d{1,2})\s*(?:[:h]|\s)\s*(\d{2})\b\s*(am|pm|a\.m\.|p\.m\.)?", text, re.I):
        h, mi = int(m.group(1)), int(m.group(2))
        if m.group(3) and "p" in m.group(3).lower() and h < 12:
            h += 12
        if h < 24 and mi < 60:
            out.append((f"{h:02d}:{mi:02d}", m.start()))
    for m in re.finditer(r"\b([01]\d|2[0-3])([0-5]\d)\b", text):
        out.append((f"{m.group(1)}:{m.group(2)}", m.start()))
    return out


def rules_extract(text, context=None):
    context = context or {}
    ex = empty()
    t = text.strip()
    low = t.lower()
    if len(re.findall(FRENCH_HINTS, low)) >= 2:
        ex["lang"] = "fr"
    # Sentences about sounds ("I hear explosions and trucks") must not feed the
    # casualty parser (mechanism "blast" / "vehicle").
    low = " . ".join(c for c in re.split(r"[.;!?]", low) if not re.search(HEAR_VERB, c))

    m = re.search(rf"\b(?:this is|ici)\s+([A-Za-z][\w-]{{1,20}}(?:\s+(?:\d+|{NUM_RE})\b)?)", t, re.I)
    if m:
        ex["callsign"] = m.group(1).upper()

    # ---------------- casualty
    cas = {"count": 1, "mechanism": None, "injuries": [], "signs": {}, "treatments": [],
           "priority_hint": None}
    has_casualty = False
    m = re.search(rf"\b(\d+|{NUM_RE})\s+(casualt|wounded|injured|bless|victim|patient|kia|cas\b)",
                  low)
    if m:
        cas["count"] = _num(m.group(1)) or 1
        has_casualty = True
    if re.search(r"\b(casualt|wounded|injured|bless[ée]|victim|patient|hurt|man down)", low):
        has_casualty = True

    mech = [("blast", r"(blast|explosion|ied|mine|grenade|shell|mortar|drone|obus|éclat|eclat)"),
            ("gunshot", r"(gunshot|gsw|shot|bullet|sniper|balle|par balle|tir)"),
            ("fall", r"\b(fall|fell|chute|tombé)"),
            ("vehicle", r"(vehicle|car crash|truck|accident|véhicule|vehicule)")]
    for name, pat in mech:
        if re.search(pat, low):
            cas["mechanism"] = name
            has_casualty = True
            break

    body = (r"(leg|arm|thigh|chest|head|abdomen|stomach|belly|neck|hand|foot|shoulder|back|face|"
            r"jambe|bras|cuisse|poitrine|t[eê]te|ventre|cou|main|pied|[ée]paule|dos|visage)")
    for clause in re.split(r"[.;,]| and | et ", t):
        cl = clause.strip()
        if re.search(body, cl.lower()) and not re.search(r"tourniquet|garrot", cl.lower()):
            cas["injuries"].append(cl)
            has_casualty = True

    sg = cas["signs"]
    if re.search(r"(unconscious|not conscious|unresponsive|inconscient|ne répond pas|passed out)", low):
        sg["conscious"] = False
    elif re.search(r"\b(conscious|awake|responsive|alert|conscient|réveillé)", low):
        sg["conscious"] = True
    if re.search(r"(not breathing|difficulty breathing|struggling to breathe|can'?t breathe|"
                 r"respire mal|ne respire pas|difficult[ée]s? respiratoire|breathing problem|labou?red)", low):
        sg["breathing"] = False
    elif re.search(r"\b(breathing|respire)", low):
        sg["breathing"] = True
    if re.search(r"(massive bleeding|heavy bleeding|bleeding heavily|arterial|spurting|"
                 r"hémorragie|hemorragie|saigne beaucoup)", low):
        sg["massive_bleeding"] = True
    elif re.search(r"(bleeding|saigne)", low):
        sg["massive_bleeding"] = None

    m = re.search(r"(tourniquet|garrot)", low)
    if m:
        has_casualty = True
        times = _times(t[m.start():]) or _times(t)
        when = times[0][0] if times else None
        ago = re.search(rf"(\d+|{NUM_RE}|fifteen|twenty|thirty|quinze|vingt|trente)\s*(?:minutes?|mins?)\s*(?:ago)?",
                        low[m.start():])
        if when is None and ago and re.search(r"(ago|il y a)", low[m.start():]):
            extra = {"fifteen": 15, "twenty": 20, "thirty": 30, "quinze": 15, "vingt": 20, "trente": 30}
            n = _num(ago.group(1)) or extra.get(ago.group(1))
            if n:
                when = (datetime.now() - timedelta(minutes=n)).strftime("%H:%M")
        if when is None and re.search(r"(just now|right now|now|maintenant|à l'instant)", low[m.start():]):
            when = datetime.now().strftime("%H:%M")
        loc = re.search(r"(left|right|gauche|droite)?\s*(leg|arm|thigh|jambe|bras|cuisse)",
                        low[max(0, m.start() - 40): m.start() + 60])
        cas["treatments"].append({"type": "tourniquet", "location": loc.group(0).strip() if loc else None,
                                  "time": when})
    for name, pat in [("chest seal", r"chest seal|pansement occlusif"),
                      ("pressure dressing", r"pressure (dressing|bandage)|pansement compressif|israeli"),
                      ("morphine", r"morphine"), ("airway", r"airway|canule")]:
        if re.search(pat, low):
            cas["treatments"].append({"type": name, "location": None, "time": None})

    if re.search(r"\b(urgent|critical|critique|urgence absolue|priority one|t1)\b", low):
        cas["priority_hint"] = "urgent"
    elif re.search(r"\b(priority|prioritaire|priority two|t2)\b", low):
        cas["priority_hint"] = "priority"
    elif re.search(r"\b(routine|minor|walking wounded|léger|leger|t3)\b", low):
        cas["priority_hint"] = "routine"
    if has_casualty:
        ex["casualties"].append(cas)

    # ---------------- surroundings ("surrounded by buildings", "in the open")
    if re.search(OPEN_SAID, t, re.I):
        ex["surroundings"] = "open"
    elif re.search(BUILT_SAID, t, re.I):
        ex["surroundings"] = "built"
    m = re.search(r"\b(inside|indoors|in a building|in a room|in a hall|à l'intérieur|dans un bâtiment|"
                  r"dans une pièce|dans une salle)\b", t, re.I)
    if m:
        ex["surroundings"] = "indoor"

    # ---------------- observations, clause by clause
    hear_ctx = False
    for clause in re.split(r"[.;,!?]|\band\b|\bet\b|\bthen\b|\bpuis\b", t):
        cl = clause.strip()
        if not cl:
            continue
        lc = cl.lower()
        k = _clock(cl)
        # Sounds: "I can hear a train (at my 3 o'clock)", "and trucks" right after.
        is_hear = bool(re.search(HEAR_VERB, lc))
        heard = _hearing(cl) if (is_hear or hear_ctx) else []
        if is_hear or (hear_ctx and heard):
            hear_ctx = True
            for g, yes in heard:
                ex["hearing"].append({"cls": g, "heard": yes})
                rel = _relative(cl)
                if yes and g in HEARD_LANDMARK and (k or rel):
                    ex["observations"].append({
                        "landmark_type": HEARD_LANDMARK[g], "landmark_name": None,
                        "direction": {"clock": k} if k else None, "relative": None if k else rel,
                        "distance_m": None, "visible": True, "heard": True})
            continue
        hear_ctx = False
        if re.search(r"\b(sun|soleil)\b", lc):
            if k:
                ex["sun"] = {"clock": k}
            elif re.search(r"(overcast|cloudy|no sun|nuageux|couvert)", lc):
                ex["sun"] = {"clock": None, "overcast": True}
            continue
        lms = _find_landmarks(cl)
        if not lms:
            continue
        neg = re.search(r"(can'?t see|cannot see|don'?t see|do not see|\bno\b|not see|"
                        r"ne vois pas|vois pas|pas de|aucun)", lc)
        here = re.search(r"\b(we'?re in|we are in|i'?m in|in the|in a|inside|at the edge|next to|"
                         r"beside|on the|under the|dans|à côté|a cote|près|pres|sous le|sur le|au bord)\b", lc)
        rel = _relative(cl)
        dist = _distance(cl)
        for ltype, _pos in lms:
            obs = {"landmark_type": ltype, "landmark_name": None, "direction": None,
                   "relative": None, "distance_m": dist, "visible": True}
            if neg:
                obs["visible"] = False
            elif k:
                obs["direction"] = {"clock": k}
            elif rel:
                obs["relative"] = rel
            elif here:
                obs["relative"] = "here"
            ex["observations"].append(obs)

    # ---------------- answer to the last question
    q = context.get("last_question")
    if q:
        from .questions import parse_answer
        val = parse_answer(q, t)
        if val is not None:
            ex["answer_to_question"] = {"question_id": q.get("id"), "value": val}
    return ex


# =================================================================== mistral
SYSTEM_PROMPT = """You turn battlefield casualty and position reports (English or French, \
transcribed from speech, may contain recognition errors) into JSON. Output ONLY JSON with this schema:
{
 "callsign": string|null,
 "lang": "en"|"fr",
 "casualties": [{"count": int, "mechanism": "blast|gunshot|fall|vehicle|other"|null,
   "injuries": [string], "signs": {"conscious": bool|null, "breathing": bool|null, "massive_bleeding": bool|null},
   "treatments": [{"type": string, "location": string|null, "time": "HH:MM"|null}],
   "priority_hint": "urgent|priority|routine"|null}],
 "observations": [{"landmark_type": string, "landmark_name": string|null,
   "direction": {"clock": int 1-12}|null, "relative": "left|right|behind|ahead|here"|null,
   "distance_m": number|null, "visible": bool}],
 "sun": {"clock": int 1-12}|null,
 "answer_to_question": {"question_id": string, "value": <see below>}|null
}
Rules:
- landmark_type must be one of: TYPES.
- Never invent landmarks or casualties. If something was not said, use null or an empty list.
- Keep the speaker's own words in the injuries strings.
- "at my 2 o'clock" / "à 2 heures" -> direction.clock = 2. "on my left" -> relative "left".
- "we are in a tree line / next to the railway" -> relative "here".
- "I can't see any X" / "no X here" -> visible false.
- Times are 24h local "HH:MM". "tourniquet just now" -> the current time given in context.
- The sun is NOT an observation: put it in "sun".
- If the context has a last_question and the speaker answers it, fill answer_to_question:
  yes/no questions -> true/false; left/right -> "left"/"right"; sun -> clock int;
  distance -> metres as a number (use 150 for "close", 800 for "far"); "don't know" -> "unknown".
- A report can contain both an answer and new observations.
"""


def mistral_extract(text, context):
    types = ", ".join(SYNONYMS.keys())
    q = context.get("last_question")
    ctx = {
        "now": datetime.now().strftime("%H:%M"),
        "last_question": {"id": q.get("id"), "kind": q.get("kind"), "text": q.get("text")} if q else None,
        "current_position": context.get("summary"),
    }
    body = {
        "model": config.MISTRAL_MODEL,
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.replace("TYPES", types)},
            {"role": "user", "content": json.dumps({"context": ctx, "transcript": text})},
        ],
    }
    if config._LOCAL_LLM and ":11434" in config.MISTRAL_BASE_URL:
        # Ollama native API: small context so the whole model fits on the GPU,
        # and keep it loaded between reports.
        root = config.MISTRAL_BASE_URL.rstrip("/").removesuffix("/v1")
        r = httpx.post(root + "/api/chat", timeout=config.LLM_TIMEOUT_S, json={
            "model": config.MISTRAL_MODEL, "messages": body["messages"], "format": "json",
            "stream": False, "keep_alive": "2h",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 600}})
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    headers = {"Authorization": f"Bearer {config.MISTRAL_API_KEY}"} if config.MISTRAL_API_KEY else {}
    r = httpx.post(config.MISTRAL_BASE_URL.rstrip("/") + "/chat/completions", json=body,
                   timeout=config.LLM_TIMEOUT_S, headers=headers)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def _clean(ex):
    """Make any extraction safe to use: right keys, known types, sane numbers."""
    out = empty()
    out["callsign"] = ex.get("callsign")
    out["lang"] = "fr" if ex.get("lang") == "fr" else "en"
    for c in ex.get("casualties") or []:
        out["casualties"].append({
            "count": int(c.get("count") or 1),
            "mechanism": c.get("mechanism"),
            "injuries": [str(i) for i in (c.get("injuries") or [])],
            "signs": {k: v for k, v in (c.get("signs") or {}).items() if v is not None},
            "treatments": [t for t in (c.get("treatments") or []) if isinstance(t, dict)],
            "priority_hint": c.get("priority_hint"),
        })
    for o in ex.get("observations") or []:
        t = normalise_type(o.get("landmark_type") or "") or normalise_type(o.get("landmark_name") or "")
        if not t:
            continue
        d = o.get("direction") or {}
        clock = d.get("clock") if isinstance(d, dict) else None
        try:
            clock = int(clock) if clock is not None else None
        except (TypeError, ValueError):
            clock = None
        if clock is not None and not 1 <= clock <= 12:
            clock = None
        out["observations"].append({
            "landmark_type": t, "landmark_name": o.get("landmark_name"),
            "direction": {"clock": clock} if clock else None,
            "relative": o.get("relative"), "distance_m": o.get("distance_m"),
            "visible": o.get("visible", True) is not False, "heard": bool(o.get("heard")),
        })
    out["hearing"] = [h for h in (ex.get("hearing") or [])
                      if isinstance(h, dict) and h.get("cls") in HEAR_CLASSES]
    out["surroundings"] = ex.get("surroundings") if ex.get("surroundings") in (
        "open", "built", "indoor") else None
    s = ex.get("sun")
    if isinstance(s, dict) and s.get("clock"):
        try:
            out["sun"] = {"clock": int(s["clock"])}
        except (TypeError, ValueError):
            pass
    out["answer_to_question"] = ex.get("answer_to_question")
    return out


def merge(rules, llm, text, context):
    """Rules first; the LLM only fills what the rules missed. Anything the LLM
    adds must be backed by words in the transcript (no invented landmarks)."""
    out = json.loads(json.dumps(rules))
    said_types = {t for t, _ in _find_landmarks(text)}
    have_types = {o["landmark_type"] for o in out["observations"]}
    have_clocks = {(o.get("direction") or {}).get("clock") for o in out["observations"]} - {None}
    for o in llm["observations"]:
        clock = (o.get("direction") or {}).get("clock")
        if o["landmark_type"] not in said_types:
            continue
        if o["landmark_type"] in have_types:
            # The rules saw it but missed the direction: take the LLM's.
            for r in out["observations"]:
                if (r["landmark_type"] == o["landmark_type"] and r["visible"] and not r.get("direction")
                        and not r.get("relative") and (clock or o.get("relative"))):
                    r["direction"] = o.get("direction")
                    r["relative"] = o.get("relative")
            continue
        if clock and clock in have_clocks:          # same direction = same thing
            continue
        out["observations"].append(o)

    if not out["casualties"] and llm["casualties"] and re.search(
            r"(casualt|wounded|injur|bless|victim|patient|bleed|saign|tourniquet|garrot)", text, re.I):
        out["casualties"] = llm["casualties"]
    elif out["casualties"] and llm["casualties"]:
        a, b = out["casualties"][0], llm["casualties"][0]
        # "I hear explosions" is a sound, not how the casualty was hurt: take the
        # LLM's mechanism only if a mechanism word is said outside sound sentences.
        cas_text = " ".join(c for c in re.split(r"[.;!?]", text) if not re.search(HEAR_VERB, c, re.I))
        if re.search(MECH_WORDS, cas_text, re.I):
            a["mechanism"] = a["mechanism"] or b.get("mechanism")
        a["priority_hint"] = a["priority_hint"] or b.get("priority_hint")
        for k, v in (b.get("signs") or {}).items():
            a["signs"].setdefault(k, v)
        have = {t.get("type") for t in a["treatments"]}
        a["treatments"] += [t for t in b.get("treatments") or [] if t.get("type") not in have]
        if not a["injuries"]:
            a["injuries"] = b.get("injuries") or []

    if not out["sun"] and llm["sun"] and re.search(r"\b(sun|soleil)\b", text, re.I):
        out["sun"] = llm["sun"]
    if not out["answer_to_question"] and context.get("last_question") and llm["answer_to_question"]:
        out["answer_to_question"] = llm["answer_to_question"]
    out["callsign"] = out["callsign"] or llm.get("callsign")
    return out


def extract(text, context=None):
    """Main entry. Returns (extraction, source): 'rules' or 'rules+llm'."""
    context = context or {}
    rules = _clean(rules_extract(text, context))
    if not config.LLM_ENABLED:
        return rules, "rules"
    # A short reply the rules already understood ("yes", "300 metres"): no need to wait for the LLM.
    if rules["answer_to_question"] and len(text.split()) <= 6:
        return rules, "rules"
    try:
        llm = _clean(mistral_extract(text, context))
        return merge(rules, llm, text, context), "rules+llm"
    except Exception as e:
        print("LLM failed, using rules only:", e)
        return rules, "rules"


# ====================================================== extraction -> constraints
REL_DEG = {"ahead": 0.0, "right": 90.0, "behind": 180.0, "left": 270.0}


def to_constraints(ex):
    """Observations + sun -> constraint dicts for localise.py."""
    out = []
    for o in ex["observations"]:
        base = {"type": o["landmark_type"], "name": o.get("landmark_name")}
        clock = (o.get("direction") or {}).get("clock")
        rel = o.get("relative")
        heard = o.get("heard")   # direction judged by ear: wider than by eye
        if not o.get("visible", True):
            out.append({"kind": "visible", **base, "value": False})
        elif clock:
            out.append({"kind": "bearing", **base, "beta": (clock * 30.0) % 360,
                        "sigma": config.SIGMA_HEARD if heard else config.SIGMA_CLOCK,
                        "distance_m": o.get("distance_m"), "heard": heard})
        elif rel in REL_DEG:
            out.append({"kind": "bearing", **base, "beta": REL_DEG[rel],
                        "sigma": max(config.SIGMA_RELATIVE, config.SIGMA_HEARD if heard else 0),
                        "distance_m": o.get("distance_m"), "heard": heard})
        elif rel == "here":
            out.append({"kind": "here", **base})
        else:
            c = {"kind": "visible", **base, "value": True}
            if o.get("distance_m"):
                c["radius"] = max(100.0, o["distance_m"] * 1.5)
            out.append(c)
    if ex.get("sun") and ex["sun"].get("clock"):
        out.append({"kind": "sun", "clock": int(ex["sun"]["clock"])})
    for h in ex.get("hearing") or []:
        out.append({"kind": "hear", "cls": h["cls"], "q": 1.0 if h["heard"] else 0.0,
                    "source": "voice", "w": 1.0})
    if ex.get("surroundings"):
        out.append({"kind": "setting", "source": "voice", "w": 1.0,
                    "p": SAID_SETTING[ex["surroundings"]]})
    return out


# What the operator says -> probabilities over the four settings (see spatial.py).
SAID_SETTING = {
    "indoor": {"indoor_small": 0.5, "indoor_large": 0.5, "outdoor_enclosed": 0.0, "outdoor_open": 0.0},
    "built": {"indoor_small": 0.0, "indoor_large": 0.0, "outdoor_enclosed": 0.9, "outdoor_open": 0.1},
    "open": {"indoor_small": 0.0, "indoor_large": 0.0, "outdoor_enclosed": 0.1, "outdoor_open": 0.9},
    "outdoor": {"indoor_small": 0.0, "indoor_large": 0.0, "outdoor_enclosed": 0.5, "outdoor_open": 0.5},
}
