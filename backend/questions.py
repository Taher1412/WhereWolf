"""Ask the one question that helps most.

1. Build candidate questions from what we already know.
2. For each one, predict the answer at every likely (cell, heading).
3. Score = expected drop in entropy of the position map after hearing the answer.
4. Ask the best one, unless the position is already good enough.

Each question also knows how to turn a spoken answer into a constraint for
localise.py (see `answer_to_constraint`).
"""
import math
import re

import numpy as np

from . import config
from .landmarks import QUESTION_TYPES, get_db, spoken

ENABLE_SPACE_QUESTIONS = True   # "inside / street / open?", "heard a train?" (eval switches it)

# Features worth asking about by name ("Can you see the town hall?").
NAMED_TYPES = {"castle", "keep", "church", "townhall", "station", "hospital", "stadium",
               "water_tower"}


def entropy_bits(p):
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def _key(q):
    return (q["kind"], q.get("type"), q.get("feature"), q.get("ref_i"), q.get("pair"))


# ----------------------------------------------------------------- phrasing
def phrase(q, lang="en"):
    """Short, speakable text for a question."""
    k = q["kind"]
    if lang == "fr":
        if k == "visible_type":
            return f"Voyez-vous : {spoken(q['type'], 'fr')} ? Oui ou non."
        if k == "visible_feature":
            return f"Voyez-vous : {q['label']} ? Oui ou non."
        if k == "dist_band":
            return (f"À quelle distance environ : {spoken(q['ref']['type'], 'fr')} ? "
                    "En mètres.")
        if k == "sun":
            return "Où est le soleil ? Donnez une direction en heures."
        if k == "left_right":
            return (f"Face à : {spoken(q['a']['type'], 'fr')}, "
                    f"{spoken(q['b']['type'], 'fr')} est à gauche ou à droite ?")
        if k == "describe":
            return "Quels repères voyez-vous ? Donnez les directions en heures."
        if k == "setting3":
            return "Êtes-vous dans un bâtiment, dans une rue entre des bâtiments, ou à découvert ?"
        if k == "room_size":
            return "La pièce est-elle petite, comme un bureau, ou grande, comme une salle ou un hall ?"
        if k == "hear_type":
            return HEAR_Q["fr"][q["type"]]
    else:
        if k == "visible_type":
            return f"Can you see a {spoken(q['type'])} from where you are? Yes or no."
        if k == "visible_feature":
            return f"Can you see {q['label']}? Yes or no."
        if k == "dist_band":
            return f"Roughly how far is the {spoken(q['ref']['type'])}, in metres?"
        if k == "sun":
            return "Where is the sun? Give me a clock direction."
        if k == "left_right":
            return (f"Facing the {spoken(q['a']['type'])}, is the {spoken(q['b']['type'])} "
                    "on your left or your right?")
        if k == "describe":
            return "What landmarks can you see? Give me clock directions."
        if k == "setting3":
            return "Are you inside a building, in a street between buildings, or in the open?"
        if k == "room_size":
            return "Is the room small, like an office, or large, like a hall?"
        if k == "hear_type":
            return HEAR_Q["en"][q["type"]]
    return ""


# Only sounds a person can answer about on demand (no "can you hear a bell?").
HEAR_Q = {
    "en": {"rail": "In the last few minutes, have you heard a train? Yes or no.",
           "traffic": "Can you hear heavy road traffic right now? Yes or no."},
    "fr": {"rail": "Ces dernières minutes, avez-vous entendu un train ? Oui ou non.",
           "traffic": "Entendez-vous une forte circulation routière en ce moment ? Oui ou non."},
}


def _soundscape(eng):
    from .soundscape import get_soundscape
    sc = get_soundscape(eng)
    return sc if sc.ok else None


def _setting_known(constraints):
    """P(indoor) from what we already have (None if nothing)."""
    ps = [c["p"] for c in constraints if c["kind"] == "setting"]
    if not ps:
        return None
    return max(p["indoor_small"] + p["indoor_large"] for p in ps)


# ------------------------------------------------------- candidate questions
def candidates(constraints, asked, result, eng, when=None):
    db = get_db()
    qs = []
    said_types = {c.get("type") for c in constraints if c.get("type")}
    asked_keys = {_key(q) for q in asked}

    # Yes/no: can you see a {type}?
    for t in QUESTION_TYPES:
        if t not in said_types:
            qs.append({"kind": "visible_type", "type": t})

    # Yes/no about named features near the likely areas.
    near = set()
    for b in result["blobs"]:
        bx, by = db.to_xy(b["lat"], b["lon"])
        d = np.hypot(db.x - bx, db.y - by)
        for i in np.where((d < max(800.0, 2 * b["r2"])) & np.isin(db.types, list(NAMED_TYPES)))[0]:
            if db.feats[i]["name"]:
                near.add(int(i))
    for i in sorted(near)[:25]:
        f = db.feature(i)
        qs.append({"kind": "visible_feature", "feature": i, "type": f["type"],
                   "label": f["name"]})

    # How far is a landmark you already reported?
    for i, c in enumerate(constraints):
        if c["kind"] in ("bearing", "visible") and c.get("value", True):
            qs.append({"kind": "dist_band", "ref_i": i, "ref": c})

    # Sun as a compass, if not given yet and it is up.
    if not any(c["kind"] == "sun" for c in constraints):
        az, elev = eng.sun(when)
        if elev > 2:
            qs.append({"kind": "sun"})

    # Left/right between two reported landmarks, if one had no direction.
    seen = [c for c in constraints if c["kind"] in ("bearing", "visible") and c.get("value", True)]
    for i in range(len(seen)):
        for j in range(i + 1, len(seen)):
            a, b = seen[i], seen[j]
            if (a["kind"] != "bearing" or b["kind"] != "bearing") and a["type"] != b["type"]:
                qs.append({"kind": "left_right", "a": a, "b": b, "pair": (a["type"], b["type"])})

    # Space and sound (needs the building / noise-source layers).
    if ENABLE_SPACE_QUESTIONS and _soundscape(eng):
        voice_setting = any(c["kind"] == "setting" and c["source"] == "voice" for c in constraints)
        p_in = _setting_known(constraints)
        if not voice_setting:
            qs.append({"kind": "setting3"})
        if p_in is not None and p_in > 0.7:
            qs.append({"kind": "room_size"})
        heard_by_voice = {c["cls"] for c in constraints if c["kind"] == "hear" and c["source"] == "voice"}
        for cls in ("rail", "traffic"):
            if cls not in heard_by_voice:
                qs.append({"kind": "hear_type", "type": cls})

    return [q for q in qs if _key(q) not in asked_keys]


# ----------------------------------------- predicted answers: P(answer | cell, heading)
def answer_probs(q, eng, rows, when=None):
    """List of arrays, one per possible answer, each broadcastable to (n, H)."""
    k = q["kind"]
    from .localise import soft_inside
    if k == "visible_type":
        d, _ = eng._nearest(q["type"])
        if d is None:
            return None
        R = config.VIS_RADIUS.get(q["type"], config.VIS_RADIUS_DEFAULT)
        yes = 0.05 + 0.9 * soft_inside(d[rows], R)
        return [yes[:, None], 1 - yes[:, None]]
    if k == "visible_feature":
        f = get_db().feature(q["feature"])
        fx, fy = get_db().to_xy(f["lat"], f["lon"])
        d = np.hypot(eng.X[rows] - fx, eng.Y[rows] - fy)
        R = config.VIS_RADIUS.get(f["type"], config.VIS_RADIUS_DEFAULT)
        yes = 0.05 + 0.9 * soft_inside(d, R)
        return [yes[:, None], 1 - yes[:, None]]
    if k == "dist_band":
        bands = eng.dist_band_probs(q["ref"], rows=rows)
        return [0.95 * b + 0.05 / len(bands) for b in bands]
    if k == "sun":
        az, _ = eng.sun(when)
        rel = (az - eng.headings) % 360.0              # where the sun is, per heading
        out = []
        for clock in range(1, 13):
            diff = (rel - clock * 30.0 + 180) % 360 - 180
            out.append(np.exp(-0.5 * (diff / config.SIGMA_SUN) ** 2))
        tot = sum(out)
        return [(o / tot)[None, :] for o in out]
    if k == "left_right":
        pr = eng.left_right_prob(q["a"], q["b"])[rows]
        return [pr[:, None], 1 - pr[:, None]]
    if k in ("setting3", "room_size", "hear_type"):
        sc = _soundscape(eng)
        if not sc:
            return None
        if k == "hear_type":
            p = sc.p_heard(q["type"], "voice")[rows]
            return [p[:, None], 1 - p[:, None]]
        P = sc.P_setting[rows]
        if k == "setting3":      # inside / street / open, people sometimes get it wrong (5 %)
            a = np.vstack([P[:, 0] + P[:, 1], P[:, 2], P[:, 3]]).T * 0.95 + 0.05 / 3
            return [a[:, i:i + 1] for i in range(3)]
        small = P[:, 0] / np.maximum(P[:, 0] + P[:, 1], 1e-6) * 0.9 + 0.05
        return [small[:, None], 1 - small[:, None]]
    return None


def choose(constraints, asked, result, eng, when=None):
    """Return (question or None, reason)."""
    if not any(c["kind"] in ("bearing", "visible", "here") for c in constraints):
        q = {"kind": "describe"}
        return (q, "no landmarks yet") if _key(q) not in {_key(a) for a in asked} else (None, "")
    if len(asked) >= config.MAX_QUESTIONS:
        return None, "question budget used"
    blobs = result["blobs"]
    confident = (blobs and result["radius_m"] <= config.TARGET_RADIUS_M
                 and result["main_mass"] >= 0.6)
    if confident:
        return None, "position confirmed"

    # Only look at the cells that matter (speed).
    post = result["post"]
    order = np.argsort(post)[::-1]
    cum = np.cumsum(post[order])
    n = min(int(np.searchsorted(cum, 0.995)) + 1, 5000)
    rows = order[:n]
    J = result["joint"][rows]
    J = J / J.sum()
    h0 = entropy_bits(J.sum(axis=1))

    best, best_gain = None, config.MIN_GAIN_BITS
    for q in candidates(constraints, asked, result, eng, when):
        try:
            probs = answer_probs(q, eng, rows, when)
        except Exception as e:
            print("question skipped:", q["kind"], e)
            continue
        if not probs:
            continue
        eh = 0.0
        for p in probs:
            pj = J * p                                  # broadcast to (n, H)
            pa = float(pj.sum())
            if pa <= 1e-12:
                continue
            eh += pa * entropy_bits(pj.sum(axis=1) / pa)
        gain = h0 - eh
        # Small bonus for questions that are easy to answer on the ground.
        if q["kind"] in ("visible_type", "visible_feature", "setting3"):
            gain *= 1.05
        if gain > best_gain:
            best, best_gain = q, gain
    if best:
        best["gain_bits"] = round(best_gain, 2)
    return best, ("best question" if best else "no useful question")


# ------------------------------------------------------- answers -> constraints
YES = (r"\b(yes|yeah|yep|affirmative|correct|i do|i can|i see|i hear|i heard|i have|"
       r"oui|ouais|affirmatif|je vois|j'entends|entendu)\b")
NO = (r"(\bno\b|\bnope\b|negative|can'?t|cannot|can not|don'?t see|do not see|haven'?t|have not|"
      r"didn'?t|did not|\bnon\b|négatif|negatif|vois pas|voit pas|pas de|pas entendu|n'entends|"
      r"aucun|nothing|rien)")
INDOOR_A = r"(inside|indoors|in a building|in the building|in a room|intérieur|interieur|dedans|dans un bâtiment|dans le bâtiment)"
STREET_A = r"(street|between buildings|between houses|courtyard|alley|\brue\b|entre des|entre les|\bcour\b|ruelle)"
OPEN_A = r"(\bopen\b|field|park|woods?|forest|clearing|grass|découvert|decouvert|dégagé|degage|\bparc\b|\bbois\b|champ|pelouse|forêt)"
DONT_KNOW = r"(don'?t know|not sure|unknown|je ne sais pas|sais pas|aucune idée)"
CLOCK_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
               "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "une": 1, "un": 1,
               "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8,
               "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "midi": 12}


def parse_answer(q, text, value=None):
    """Read the answer to question q from free text (or from a value the LLM
    already extracted). Returns a normalised value, 'unknown', or None."""
    t = (text or "").lower()
    k = q["kind"]
    v = value if value is not None else None
    if isinstance(v, str):
        t = v.lower() + " " + t
    if re.search(DONT_KNOW, t):
        return "unknown"
    if k == "setting3":
        if re.search(INDOOR_A, t):
            return "indoor"
        if re.search(STREET_A, t):
            return "built"
        if re.search(OPEN_A, t):
            return "open"
        if re.search(r"\b(outside|outdoors|dehors|extérieur|exterieur)\b", t):
            return "outdoor"
        return None
    if k == "room_size":
        if re.search(r"\b(small|little|tiny|office|bedroom|corridor|petite?|bureau|chambre|couloir)\b", t):
            return "small"
        if re.search(r"\b(big|large|huge|hall|church|hangar|warehouse|gym|station|grande?|salle|église|entrepôt|gymnase|gare)\b", t):
            return "large"
        return None
    if k in ("visible_type", "visible_feature", "hear_type"):
        if isinstance(v, bool):
            return v
        if re.search(NO, t):        # check "can't" before "can"
            return False
        if re.search(YES, t):
            return True
        return None
    if k == "left_right":
        if re.search(r"\b(left|gauche)\b", t):
            return "left"
        if re.search(r"\b(right|droite)\b", t):
            return "right"
        return None
    if k == "sun":
        if isinstance(v, (int, float)) and 1 <= v <= 12:
            return int(v)
        m = re.search(r"\b(1[0-2]|[1-9])\b", t)
        if m:
            return int(m.group(1))
        for w, n in CLOCK_WORDS.items():
            if re.search(rf"\b{w}\b", t):
                return n
        if re.search(r"(overcast|cloudy|no sun|can'?t see|nuageux|couvert|pas de soleil)", t):
            return "unknown"
        return None
    if k == "dist_band":
        # Returns a distance in metres.
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|kilo)", t)
        if m:
            return float(m.group(1).replace(",", ".")) * 1000
        nums = [int(n) for n in re.findall(r"\b(\d{2,4})\b", t)]
        if nums:
            n = nums[0] if len(nums) == 1 else sum(nums[:2]) / 2   # "200 to 300" -> 250
            if re.search(r"(under|less|moins de|within)", t):
                n *= 0.7
            elif re.search(r"(more than|over|beyond|plus de)", t):
                n *= 1.4
            return float(n)
        if re.search(r"(very close|right next|tout près|juste à côté)", t):
            return 60.0
        if re.search(r"(close|near|proche|pas loin)", t):
            return 150.0
        if re.search(r"(very far|très loin)", t):
            return 1500.0
        if re.search(r"(far|loin)", t):
            return 800.0
        return None
    return None


def answer_to_constraint(q, value):
    k = q["kind"]
    if value in (None, "unknown"):
        return None
    if k == "visible_type":
        return {"kind": "visible", "type": q["type"], "value": bool(value)}
    if k == "visible_feature":
        return {"kind": "feature_visible", "feature": q["feature"], "value": bool(value)}
    if k == "dist_band":
        return {"kind": "distance", "ref": q["ref"], "distance_m": float(value)}
    if k == "sun":
        return {"kind": "sun", "clock": int(value)}
    if k == "left_right":
        return {"kind": "left_right", "a": q["a"], "b": q["b"], "value": value}
    if k == "hear_type":
        return {"kind": "hear", "cls": q["type"], "q": 1.0 if value else 0.0, "source": "voice", "w": 1.0}
    if k == "setting3":
        from .extract import SAID_SETTING
        return {"kind": "setting", "source": "voice", "w": 1.0, "p": SAID_SETTING[value]}
    if k == "room_size":
        p = {"indoor_small": 0.9, "indoor_large": 0.1} if value == "small" else \
            {"indoor_small": 0.1, "indoor_large": 0.9}
        return {"kind": "setting", "source": "voice", "w": 1.0,
                "p": {**p, "outdoor_enclosed": 0.0, "outdoor_open": 0.0}}
    return None
