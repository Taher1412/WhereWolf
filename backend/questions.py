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
ENABLE_GROUND_QUESTIONS = True  # "under trees?", "what's under your feet?", "water in sight?"

# Features worth asking about by name ("Can you see the town hall?").
NAMED_TYPES = {"castle", "keep", "church", "townhall", "station", "hospital", "stadium",
               "water_tower"}


def entropy_bits(p):
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def _key(q):
    return (q["kind"], q.get("type"), q.get("feature"), q.get("ref_i"), q.get("pair"))


# ----------------------------------------------------------------- phrasing
def phrase(q, lang="en", short=False):
    """Short, speakable text for a question. short: a stressed speaker gets the fewest
    words possible (one item, yes / no)."""
    k = q["kind"]
    if short:
        s = _short(q, lang)
        if s:
            return s
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
        if k == "compass":
            return (f"Si vous avez une boussole : quel azimut pour {spoken(q['ref']['type'], 'fr')} ? "
                    "En degrés ou en millièmes.")
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
        if k == "wound_where":
            return "Où est la blessure ? Dites la partie du corps, par exemple jambe gauche."
        if k == "ground":
            return GROUND_Q["fr"][q["type"]]
        if k == "hear_dir":
            return "D'où vient le bruit de circulation ? Donnez une direction en heures, ou dites aucun."
        if k == "which_see":
            a = q["labels"]
            return f"Lesquels voyez-vous : {', '.join(a[:-1])} ou {a[-1]} ? Dites tout ce que vous voyez, ou aucun."
        if k == "feature_dir":
            return f"Où est {q['label']} par rapport à vous ? Une direction en heures, ou dites que vous ne le voyez pas."
    else:
        if k == "visible_type":
            return f"Can you see a {spoken(q['type'])} from where you are? Yes or no."
        if k == "visible_feature":
            return f"Can you see {q['label']}? Yes or no."
        if k == "dist_band":
            return f"Roughly how far is the {spoken(q['ref']['type'])}, in metres?"
        if k == "sun":
            return "Where is the sun? Give me a clock direction."
        if k == "compass":
            return (f"If you have a compass: what is the bearing to the {spoken(q['ref']['type'])}? "
                    "Degrees or mils.")
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
        if k == "wound_where":
            return "Where is the wound? Name the body part, for example left leg."
        if k == "ground":
            return GROUND_Q["en"][q["type"]]
        if k == "hear_dir":
            return "Where do you hear road traffic from? Give a clock direction, or say none."
        if k == "which_see":
            a = q["labels"]
            return f"Which of these can you see: {', '.join(a[:-1])}, or {a[-1]}? Say all you see, or none."
        if k == "feature_dir":
            return f"Where is {q['label']} from you? Give a clock direction, or say you can't see it."
    return ""


# Only sounds a person can answer about on demand (no "can you hear a bell?").
HEAR_Q = {
    "en": {"rail": "In the last few minutes, have you heard a train? Yes or no.",
           "traffic": "Can you hear heavy road traffic right now? Yes or no."},
    "fr": {"rail": "Ces dernières minutes, avez-vous entendu un train ? Oui ou non.",
           "traffic": "Entendez-vous une forte circulation routière en ce moment ? Oui ou non."},
}


# Woods and parks (backend/forest.py): things you can answer without seeing far.
GROUND_Q = {
    "en": {"cover": "Are you under trees, or in the open?",
           "surface": "What is under your feet: tarmac, a dirt or gravel path, or no path?",
           "water": "Can you see water from where you are, a lake, pond or stream? Yes or no."},
    "fr": {"cover": "Êtes-vous sous les arbres, ou à découvert ?",
           "surface": "Qu'y a-t-il sous vos pieds : du goudron, un chemin de terre ou de gravier, ou pas de chemin ?",
           "water": "Voyez-vous de l'eau, un lac, un étang ou un ruisseau ? Oui ou non."},
}


def _feature_label(f, lang="en"):
    """'the Lac des Minimes' / 'a water tower' for an option in a spoken question."""
    if f.get("name"):
        return ("" if lang == "fr" else "the ") + f["name"]
    return ("un(e) " if lang == "fr" else "a ") + spoken(f["type"], lang)


def _adaptive(constraints, result, eng, max_feats=400):
    """Questions made for THIS situation: which real features tell the likely spots apart,
    and where a named landmark that should be in sight from the leading spot is."""
    hyps = result.get("hyps") or []
    if not hyps:
        return []
    from .viewshed import get_viewshed
    vs = get_viewshed(eng)
    if not vs.ok:
        return []
    db = eng.db
    said = {(c.get("type"), c.get("name")) for c in constraints if c.get("type")}
    asked_feats = {c.get("feature") for c in constraints if c["kind"] == "feature_visible"}
    # cells around each likely spot (3 x 3 around the peak)
    spots = []
    for h in hyps[:3]:
        x, y = db.to_xy(h["lat"], h["lon"])
        c = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
        r, col = divmod(c, eng.nx)
        cells = [rr * eng.nx + cc for rr in range(max(0, r - 1), min(eng.ny, r + 2))
                 for cc in range(max(0, col - 1), min(eng.nx, col + 2))]
        spots.append((np.array(cells), h["mass"]))
    # candidate features: with a top (viewshed), near any likely spot
    cand = vs.cands
    hx = np.array([db.to_xy(h["lat"], h["lon"])[0] for h in hyps[:3]])
    hy = np.array([db.to_xy(h["lat"], h["lon"])[1] for h in hyps[:3]])
    near = np.min(np.hypot(db.x[cand][:, None] - hx[None, :], db.y[cand][:, None] - hy[None, :]), axis=1) < 1500
    cand = cand[near][:max_feats]
    rows = []
    for i in cand:
        f = db.feature(int(i))
        if (f["type"], f.get("name")) in said or (f["type"], None) in said or int(i) in asked_feats                 or f["type"] in ("school",):
            continue
        T = vs.T[vs.col[i]]
        p = np.array([float(T[cells].mean()) / 255.0 for cells, _ in spots])
        w = np.array([m for _, m in spots])
        spread = float(np.sqrt(np.average((p - np.average(p, weights=w)) ** 2, weights=w)))
        rows.append((spread, float(p[0]), int(i), f))
    out = []
    # which_see: the 3 features that differ most between the likely spots (distinct labels)
    if len(spots) >= 2:
        pick, labels = [], set()
        for spread, _, i, f in sorted(rows, key=lambda r: -r[0]):
            lab = _feature_label(f)
            if spread < 0.12 or lab in labels:
                continue
            pick.append(i)
            labels.add(lab)
            if len(pick) == 3:
                break
        if len(pick) >= 2:
            fs = [db.feature(i) for i in pick]
            out.append({"kind": "which_see", "opts": pick, "labels": [_feature_label(f) for f in fs],
                        "pair": tuple(pick)})
    # feature_dir: a NAMED landmark likely in sight from the leading spot
    best = [r for r in rows if r[3].get("name") and r[1] >= 0.5]
    for _, _, i, f in sorted(best, key=lambda r: -r[1])[:2]:
        out.append({"kind": "feature_dir", "feature": i, "type": f["type"], "name": f["name"],
                    "label": _feature_label(f)})
    return out


def _parse_which(q, t):
    """'I can see the lake and the church but not the railway' -> bitmask of options seen."""
    if re.search(r"\b(none|neither|nothing|no one|aucun|aucune|rien|ni l'un)\b", t) or re.fullmatch(r"\W*(no|non)\W*", t):
        return 0
    mask, any_hit = 0, False
    for j, lab in enumerate(q["labels"]):
        words = [w for w in re.findall(r"[a-zà-ÿ]+", lab.lower()) if len(w) >= 4 and w not in
                 ("the", "dans", "with", "near", "saint", "sainte", "eglise", "église", "church")]
        keys = words or re.findall(r"[a-zà-ÿ]+", lab.lower())[-1:]
        hit = None
        for kw in keys:
            # word start + first 5 letters: "chapel" finds "Chapelle", "salve" finds "Salves"
            m = re.search(rf"\b{re.escape(kw[:5])}", t)
            if m:
                hit = m
                break
        if not hit and "church" in lab.lower() and re.search(r"\b(church|[ée]glise)\b", t):
            hit = re.search(r"\b(church|[ée]glise)\b", t)
        if hit:
            any_hit = True
            before = t[max(0, hit.start() - 25):hit.start()]
            if not re.search(r"(\b(not|no|pas|sans|ni)\b|n't\b|can'?t see)", before):
                mask |= 1 << j
    return mask if any_hit else None


def _forest(eng):
    from .forest import get_forest
    fo = get_forest(eng)
    return fo if fo.ok else None


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

    # Compass bearing to a landmark already reported: removes the unknown facing direction
    # (2 named landmarks: median error 71 m with bearings vs 250 m with clock directions).
    have_abs = {c["type"] for c in constraints if c["kind"] == "abs_bearing"}
    for i, c in enumerate(constraints):
        if c["kind"] in ("bearing", "visible") and c.get("value", True) and c["type"] not in have_abs                 and not c.get("heard"):
            qs.append({"kind": "compass", "ref_i": i, "ref": c, "type": c["type"]})

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

    # Adaptive: built from the current likely spots (A / B / C) and the real named features.
    qs += _adaptive(constraints, result, eng)

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

    # The ground (woods, parks): the information gain decides if it is worth asking.
    if ENABLE_GROUND_QUESTIONS and _forest(eng):
        said = {c["what"] for c in constraints if c["kind"] == "ground"}
        for what in ("cover", "surface", "water"):
            if what not in said:
                qs.append({"kind": "ground", "type": what})
        # Under trees you hear roads you can't see: ask where the traffic is.
        if _soundscape(eng) and not any(c["kind"] == "bearing" and c.get("heard") and c["type"] == "main_road"
                                        for c in constraints):
            qs.append({"kind": "hear_dir", "type": "traffic"})

    return [q for q in qs if _key(q) not in asked_keys]


# ----------------------------------------- predicted answers: P(answer | cell, heading)
def answer_probs(q, eng, rows, when=None):
    """List of arrays, one per possible answer, each broadcastable to (n, H)."""
    k = q["kind"]
    from .localise import soft_inside
    if k == "visible_type":
        v = eng.visibility(q["type"])          # distance and trees in the way
        if v is None:
            return None
        yes = 0.05 + 0.9 * v[rows]
        return [yes[:, None], 1 - yes[:, None]]
    if k == "visible_feature":
        yes = 0.05 + 0.9 * eng.see_feature(q["feature"])[rows]
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
    if k == "compass":
        ref = q["ref"]
        L = eng.bearing_like({"type": ref["type"], "name": ref.get("name"), "beta": 0.0,
                              "sigma": config.SIGMA_BEARING, "distance_m": ref.get("distance_m"),
                              "heard": None})[rows]                       # (n, H): bearing = heading column
        per = eng.H // 16
        sec = [L[:, j * per:(j + 1) * per].sum(axis=1) + 1e-6 for j in range(16)]
        tot = sum(sec)
        has = 1 - P_NO_COMPASS
        return [(has * sj / tot)[:, None] for sj in sec] + [np.full((len(rows), 1), P_NO_COMPASS)]
    if k == "left_right":
        pr = eng.left_right_prob(q["a"], q["b"])[rows]
        return [pr[:, None], 1 - pr[:, None]]
    if k == "which_see":        # every subset of the options (said all you see)
        ps = [0.05 + 0.9 * eng.see_feature(i)[rows] for i in q["opts"]]
        out = []
        for mask in range(1 << len(ps)):
            v = np.ones_like(ps[0])
            for j, p in enumerate(ps):
                v = v * (p if mask >> j & 1 else 1 - p)
            out.append(v[:, None])
        return out
    if k == "feature_dir":      # 12 clock directions to that landmark, or "can't see it"
        i = q["feature"]
        see = 0.05 + 0.9 * eng.see_feature(i)[rows]
        bear = np.degrees(np.arctan2(eng.db.x[i] - eng.X[rows], eng.db.y[i] - eng.Y[rows])) % 360.0
        rel = (bear[:, None] - eng.headings[None, :]) % 360.0
        g = [np.exp(-0.5 * (((rel - c * 30.0) + 180) % 360 - 180) ** 2 / 20.0 ** 2) for c in range(1, 13)]
        tot = sum(g)
        return [see[:, None] * gk / tot for gk in g] + [np.broadcast_to(1 - see[:, None], rel.shape)]
    if k == "hear_dir":         # 12 clock directions to the nearest main road, or "none"
        sc = _soundscape(eng)
        d, idx = eng._nearest("main_road")
        if not sc or d is None:
            return None
        heard = sc.p_heard("traffic", "voice")[rows]
        j = idx[rows]                    # nearest main-road point of each cell
        bear = np.degrees(np.arctan2(eng.db.x[j] - eng.X[rows], eng.db.y[j] - eng.Y[rows])) % 360.0
        rel = (bear[:, None] - eng.headings[None, :]) % 360.0
        g = [np.exp(-0.5 * (((rel - k * 30.0) + 180) % 360 - 180) ** 2 / config.SIGMA_HEARD ** 2) for k in range(1, 13)]
        tot = sum(g)
        return [heard[:, None] * gk / tot for gk in g] + [np.broadcast_to(1 - heard[:, None], rel.shape)]
    if k == "ground":
        fo = _forest(eng)
        if not fo:
            return None
        P = fo.ground_probs(q["type"])
        return [P[a][rows][:, None] for a in fo.ANSWERS[q["type"]]]
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


# Health questions (backend/condition.py): asked in MARCH order, not counted in the location
# budget. "life" ones come before any location question.
MEDICAL_KINDS = {"wound_where", "med_bleed", "med_avpu", "med_breath", "med_mech", "med_shock", "med_time"}
MAX_MEDICAL = 6
MED_TEXT = {   # kind: (en buddy, en self, fr buddy, fr self, short en, short fr, goal)
    "med_bleed": ("Is the bleeding stopped? Yes or no.", "Has your bleeding stopped? Yes or no.",
                  "Le saignement est-il arrêté ? Oui ou non.", "Votre saignement est-il arrêté ? Oui ou non.",
                  "Bleeding stopped? Yes or no.", "Saignement arrêté ? Oui ou non.",
                  "Goal: is the bleeding still the life threat? It sets the time left"),
    "med_avpu": ("Is the casualty awake and answering you? Yes or no.", None,
                 "Le blessé est-il réveillé, il vous répond ? Oui ou non.", None,
                 "Awake and answering? Yes or no.", "Réveillé, il répond ? Oui ou non.",
                 "Goal: consciousness, for the airway and head injury risk"),
    "med_breath": ("Is the casualty breathing normally? Yes or no.", "Are you breathing normally? Yes or no.",
                   "Le blessé respire-t-il normalement ? Oui ou non.", "Respirez-vous normalement ? Oui ou non.",
                   "Breathing normally? Yes or no.", "Respire normalement ? Oui ou non.",
                   "Goal: breathing, the next life threat after bleeding"),
    "med_mech": ("How did it happen: explosion, gunshot, fall, vehicle, or other?", None,
                 "Comment est-ce arrivé : explosion, balle, chute, véhicule, ou autre ?", None,
                 "Explosion, gunshot, fall, or vehicle?", "Explosion, balle, chute, ou véhicule ?",
                 "Goal: how it happened, to know where hidden injuries may be"),
    "med_shock": ("Is the casualty's skin pale, cold or sweaty? Yes or no.", "Do you feel cold, sweaty or dizzy? Yes or no.",
                  "La peau du blessé est-elle pâle, froide ou moite ? Oui ou non.", "Avez-vous froid, des sueurs ou la tête qui tourne ? Oui ou non.",
                  "Pale, cold or sweaty? Yes or no.", "Pâle, froid ou moite ? Oui ou non.",
                  "Goal: signs of shock, how fast the condition is getting worse"),
    "med_time": ("How many minutes ago was the casualty hit?", "How many minutes ago were you hit?",
                 "Il y a combien de minutes le blessé a-t-il été touché ?", "Il y a combien de minutes avez-vous été touché ?",
                 "Hit how many minutes ago?", "Touché il y a combien de minutes ?",
                 "Goal: when it happened, so the clocks start at the right time"),
}


def medical_question(casualties, asked, life_only=False):
    """The next health question for the first casualty that needs one, MARCH order:
    bleeding control, consciousness, breathing (life threats), then where the wound is,
    how it happened, shock signs, when it happened. None when nothing useful is missing."""
    from .body import regions
    done = {a["kind"] for a in asked}
    if not casualties or sum(a["kind"] in MEDICAL_KINDS for a in asked) >= MAX_MEDICAL:
        return None
    c = casualties[0]
    s = c.get("signs") or {}
    me = bool(c.get("self_report"))
    wounds = [r for r in (regions(i) for i in c.get("injuries") or []) if r]
    bleeding = s.get("massive_bleeding") or any(r["kind"] in ("bleeding", "amputation", "gunshot", "shrapnel")
                                                for r in wounds)
    tq = any(t.get("type") == "tourniquet" for t in c.get("treatments") or [])
    serious = bleeding or tq or s.get("conscious") is False or c.get("mechanism") in ("blast", "gunshot")
    life = []
    if bleeding and not tq and s.get("bleeding_controlled") is None:
        life.append("med_bleed")
    if not me and s.get("avpu") is None and s.get("conscious") is None:
        life.append("med_avpu")
    if s.get("breathing") is None and (serious or not me):
        life.append("med_breath")
    rest = []
    named = [i for i in c.get("injuries") or [] if regions(i)] or [t for t in c.get("treatments") or [] if t.get("location")]
    if not named and c.get("injuries"):      # hurt, but where? It decides which threats apply
        life.append("wound_where")
    elif not named:
        rest.append("wound_where")
    if not c.get("mechanism"):
        rest.append("med_mech")
    if serious and s.get("shock_signs") is None:
        rest.append("med_shock")
    if c.get("injury_ago_min") is None and not any(t.get("time") for t in c.get("treatments") or []):
        rest.append("med_time")
    for k in life + ([] if life_only else rest):
        if k not in done:
            q = {"kind": k, "self": me, "life": k in life}
            if k in MED_TEXT:
                q.update(goal="health", goal_text=MED_TEXT[k][6])
            return q
    return None


def med_phrase(q, lang="en", short=False):
    t = MED_TEXT[q["kind"]]
    if short:
        return t[5] if lang == "fr" else t[4]
    if lang == "fr":
        return (q.get("self") and t[3]) or t[2]
    return (q.get("self") and t[1]) or t[0]


def parse_medical(q, text):
    """Answer to a health question -> value, or None if not understood."""
    t = (text or "").lower()
    k = q["kind"]
    if k == "med_mech":
        for name, pat in (("blast", r"(blast|explosion|ied|mine|grenade|shell|mortar|drone|obus|[ée]clat)"),
                          ("gunshot", r"(gunshot|shot|bullet|sniper|balle|tir)"), ("fall", r"(fall|fell|chute|tomb)"),
                          ("vehicle", r"(vehicle|car|truck|crash|accident|v[ée]hicule|voiture)"),
                          ("other", r"(other|autre|don'?t know|sais pas|stab|knife|couteau|burn|br[uû]l)")):
            if re.search(pat, t):
                return name
        return None
    if k == "med_time":
        m = re.search(r"\b(\d{1,3})\b", t)
        if m:
            return int(m.group(1))
        words = {"five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "half an hour": 30,
                 "an hour": 60, "cinq": 5, "dix": 10, "quinze": 15, "vingt": 20, "trente": 30, "une heure": 60}
        for w, n in words.items():
            if w in t:
                return n
        return None
    if re.search(NO, t):        # "no", "not breathing", "pas arrêté"
        return False
    if re.search(YES, t):
        return True
    return None


def medical_from_signs(q, cas):
    """A detailed answer may hold the answer without a yes / no ("he's pale and sweating",
    "blast, mortar round"): read it from what extraction put in the casualty."""
    s = cas.get("signs") or {}
    k = q["kind"]
    v = {"med_bleed": s.get("bleeding_controlled"), "med_breath": s.get("breathing"),
         "med_shock": s.get("shock_signs"), "med_mech": cas.get("mechanism"),
         "med_time": cas.get("injury_ago_min"),
         "med_avpu": (s.get("avpu") in ("A", "V")) if s.get("avpu") else s.get("conscious")}.get(k)
    return v


def apply_medical(cas, q, value):
    """Write a health answer into the casualty (signs / mechanism / injury time)."""
    import time as _t
    s = cas.setdefault("signs", {})
    k = q["kind"]
    if k == "med_bleed":
        s["bleeding_controlled"] = bool(value)
        if value is False:
            s["massive_bleeding"] = s.get("massive_bleeding") or None
    elif k == "med_avpu":
        s["conscious"] = bool(value)
        s["avpu"] = "A" if value else "U"
    elif k == "med_breath":
        s["breathing"] = bool(value)
    elif k == "med_shock":
        s["shock_signs"] = bool(value)
    elif k == "med_mech" and value != "other":
        cas["mechanism"] = value
    elif k == "med_time":
        cas["injury_ago_min"] = int(value)
        cas["injury_ago_ms"] = int(_t.time() * 1000) - int(value) * 60000


P_NO_COMPASS = 0.4    # chance the speaker has no compass at hand (the answer is then "none")

# What a question costs the person in the field (looking around, judging, counting):
# 1 = a glance and yes / no, 3 = scan everything and give clock directions.
LOAD = {"which_see": 1.5, "feature_dir": 2.0, "visible_type": 1.0, "visible_feature": 1.0, "hear_type": 1.0, "room_size": 1.0,
        "wound_where": 1.0, "med_bleed": 1.0, "med_avpu": 1.0, "med_breath": 1.0, "med_shock": 1.0,
        "med_mech": 1.5, "med_time": 1.5, "setting3": 1.5, "left_right": 2.0, "sun": 2.0, "compass": 2.0, "hear_dir": 2.0,
        "dist_band": 2.5, "describe": 3.0}
GROUND_LOAD = {"cover": 1.0, "water": 1.0, "surface": 1.5}
# How the speaker's stress (backend/stress.py) changes the asking: score / (1 + lam x
# (load - 1)) favours easy questions; max_load = hardest question allowed; max_q = budget.
STRESS_POLICY = {"unknown": {"lam": 0.15, "max_load": 3.0, "max_q": 6},
                 "low": {"lam": 0.10, "max_load": 3.0, "max_q": 6},
                 "elevated": {"lam": 0.35, "max_load": 2.5, "max_q": 5},
                 "high": {"lam": 0.60, "max_load": 2.0, "max_q": 4}}
# High stress: short yes / no or one clock direction, no distances, no "describe everything".
# Tested (scripts/eval_questions.py + variants): keeping 3 quick questions loses far less
# accuracy than cutting to 2 (median 617 m vs 791 m on spots that see a landmark).
OBJECTIVE = "blend"     # "entropy" (bits), "spread" (metres of error), or "blend" (both)
MIN_SCORE = 0.008


def _short(q, lang):
    k, fr = q["kind"], lang == "fr"
    if k == "visible_type":
        return f"{spoken(q['type'], 'fr' if fr else 'en').capitalize()} en vue ? Oui ou non." if fr else \
            f"See a {spoken(q['type'])}? Yes or no."
    if k == "visible_feature":
        return f"{q['label']} en vue ? Oui ou non." if fr else f"See {q['label']}? Yes or no."
    if k == "ground":
        return {"cover": ("Sous les arbres ? Oui ou non." if fr else "Under trees? Yes or no."),
                "water": ("De l'eau en vue ? Oui ou non." if fr else "See water? Yes or no."),
                "surface": ("Sol : goudron, terre, ou rien ?" if fr else "Ground: tarmac, dirt, or none?")}.get(q.get("type"))
    if k == "hear_type":
        return {"rail": ("Un train ? Oui ou non." if fr else "Heard a train? Yes or no."),
                "traffic": ("Des voitures ? Oui ou non." if fr else "Hear traffic? Yes or no.")}.get(q.get("type"))
    if k == "setting3":
        return "Dedans, rue, ou découvert ?" if fr else "Inside, street, or open?"
    if k == "wound_where":
        return "Blessure où ?" if fr else "Where is the wound?"
    if k == "sun":
        return "Soleil à quelle heure ?" if fr else "Sun at what o'clock?"
    if k == "compass":
        t = spoken(q["ref"]["type"], "fr" if fr else "en")
        return f"Azimut de {t} ?" if fr else f"Compass bearing to the {t}?"
    if k == "hear_dir":
        return "Circulation à quelle heure, ou aucune ?" if fr else "Traffic at what o'clock, or none?"
    if k == "left_right":
        a, b = spoken(q["a"]["type"], "fr" if fr else "en"), spoken(q["b"]["type"], "fr" if fr else "en")
        return f"{b.capitalize()} : à gauche ou à droite de {a} ?" if fr else f"{b.capitalize()}: left or right of the {a}?"
    return None


def load_of(q):
    return GROUND_LOAD.get(q.get("type"), 1.0) if q["kind"] == "ground" else LOAD.get(q["kind"], 1.5)


def _spread(w, X, Y):
    """RMS distance (m) of a cell distribution w to its mean: how far off a best guess is."""
    s = w.sum()
    if s <= 0:
        return 0.0
    w = w / s
    mx, my = float((w * X).sum()), float((w * Y).sum())
    return float(np.sqrt((w * ((X - mx) ** 2 + (Y - my) ** 2)).sum()))


def choose(constraints, asked, result, eng, when=None, stress="unknown"):
    """Return (question or None, reason). Each question gets a goal (what it is for) and
    the error it is expected to leave, and the choice adapts to the speaker's stress."""
    pol = STRESS_POLICY.get(stress, STRESS_POLICY["unknown"])
    under_trees = any(c["kind"] == "ground" and c["what"] == "cover" and c["value"] == "trees"
                      for c in constraints)
    if not any(c["kind"] in ("bearing", "visible", "here") for c in constraints) and not under_trees \
            and stress != "high":
        q = {"kind": "describe", "goal": "get landmarks to place you",
             "goal_text": "Goal: get landmarks with clock directions, nothing to place you yet"}
        return (q, "no landmarks yet") if _key(q) not in {_key(a) for a in asked} else (None, "")
    if len([a for a in asked if a["kind"] not in MEDICAL_KINDS]) >= pol["max_q"]:
        return None, "question budget used" + (" (stressed speaker: fewer questions)" if stress == "high" else "")
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
    X, Y = eng.X[rows], eng.Y[rows]
    pc0 = J.sum(axis=1)
    h0 = entropy_bits(pc0)
    s0 = _spread(pc0, X, Y)

    best, best_score, best_info = None, MIN_SCORE, None
    for q in candidates(constraints, asked, result, eng, when):
        load = load_of(q)
        if load > pol["max_load"]:
            continue
        try:
            probs = answer_probs(q, eng, rows, when)
        except Exception as e:
            print("question skipped:", q["kind"], e)
            continue
        if not probs:
            continue
        eh = es = 0.0
        outs = []
        for p in probs:
            pj = J * p                                  # broadcast to (n, H)
            pa = float(pj.sum())
            if pa <= 1e-12:
                outs.append((0.0, None))
                continue
            pcell = pj.sum(axis=1) / pa
            eh += pa * entropy_bits(pcell)
            es += pa * _spread(pcell, X, Y)
            outs.append((pa, pcell))
        g_bits = (h0 - eh) / max(h0, 1e-6)              # share of the uncertainty removed
        g_m = (s0 - es) / max(s0, 1e-6)                 # share of the expected error removed
        raw = {"entropy": g_bits, "spread": g_m}.get(OBJECTIVE, 0.5 * (g_bits + g_m))
        score = raw / (1.0 + pol["lam"] * (load - 1.0))
        if raw > MIN_SCORE and score > best_score:
            best, best_score = q, score
            best_info = (h0 - eh, es, outs)
    if not best:
        return None, "no useful question"
    gain_bits, es, outs = best_info
    best["gain_bits"] = round(gain_bits, 2)
    best["load"] = load_of(best)
    best["expect"] = {"now_m": int(round(s0)), "after_m": int(round(es))}
    best.update(_goal(best, outs, rows, result, eng, s0, es))
    return best, "best question"


ANSWER_NAMES = {"visible_type": ["yes", "no"], "visible_feature": ["yes", "no"], "hear_type": ["yes", "no"],
                "left_right": ["right", "left"], "room_size": ["small", "large"],
                "setting3": ["inside", "street", "open"]}


def _goal(q, outs, rows, result, eng, s0, es):
    """What the question is for, in one line: tell two areas apart, fix the heading, or
    narrow the main area. With the expected error before / after."""
    letters = "ABC"
    blobs = [b for b in (result.get("hyps") or result["blobs"])[:3] if b["mass"] >= 0.08]
    names = ANSWER_NAMES.get(q["kind"]) or (list(_forest_answers(q)) if q["kind"] == "ground" else None)
    # Which area does each answer point to?
    if len(blobs) >= 2:
        bx = np.array([eng.db.to_xy(b["lat"], b["lon"])[0] for b in blobs])
        by = np.array([eng.db.to_xy(b["lat"], b["lon"])[1] for b in blobs])
        d = np.hypot(eng.X[rows][:, None] - bx[None, :], eng.Y[rows][:, None] - by[None, :])
        lim = np.array([max(2.0 * b["r2"], 120.0) for b in blobs])
        member = np.where(d.min(axis=1) <= lim[d.argmin(axis=1)], d.argmin(axis=1), -1)
        share = []          # share[answer][area] after that answer
        for pa, pcell in outs:
            if pcell is None:
                share.append(None)
                continue
            share.append([float(pcell[member == k].sum()) for k in range(len(blobs))])
        # Two areas are told apart when the answers move the mass between them.
        prior = [b["mass"] for b in blobs]
        swing = max((max(abs(s[k] / max(sum(s), 1e-9) - prior[k] / sum(prior)) for k in range(len(blobs)))
                     for s in share if s), default=0.0)
        if swing >= 0.25:
            a, b = letters[0], letters[1]
            txt = f"Goal: tell area {a} ({blobs[0]['mass'] * 100:.0f}%) from area {b} ({blobs[1]['mass'] * 100:.0f}%)"
            if names and len(names) == len(share) and len(names) <= 3:
                lead = [f"{nm} → {letters[int(np.argmax(s))]}" for nm, s in zip(names, share) if s and max(s) > 0.4]
                if lead:
                    txt += " · " + ", ".join(lead)
            return {"goal": "split", "goal_text": txt + f" · error ~{s0:.0f} m → ~{es:.0f} m"}
    if q["kind"] == "compass":
        return {"goal": "heading", "goal_text": f"Goal: a compass bearing removes the unknown facing direction · error ~{s0:.0f} m → ~{es:.0f} m"}
    if q["kind"] == "sun":
        return {"goal": "heading", "goal_text": f"Goal: fix which way you face, so the landmark directions line up · error ~{s0:.0f} m → ~{es:.0f} m"}
    return {"goal": "narrow", "goal_text": f"Goal: narrow area A · error ~{s0:.0f} m → ~{es:.0f} m"}


def _forest_answers(q):
    from .forest import Forest
    return Forest.ANSWERS.get(q.get("type"), ())


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
    if k == "which_see":
        return _parse_which(q, t)
    if k == "feature_dir":
        if re.search(r"(can'?t see|cannot see|don'?t see|not see|no\b|ne (le|la) vois pas|vois pas|pas visible)", t):
            return "none"
        m = re.search(r"\b(1[0-2]|[1-9])\b", t)
        if m:
            return int(m.group(1))
        for w, n in CLOCK_WORDS.items():
            if re.search(rf"\b{w}\b", t):
                return n
        return None
    if k == "hear_dir":
        if re.search(r"\b(none|nothing|no traffic|can'?t hear|don'?t hear|aucun|rien|pas de circulation|n'entends)\b", t)                 or re.fullmatch(r"\s*no\.?\s*", t):
            return "none"
        m = re.search(r"\b(1[0-2]|[1-9])\b", t)
        if m:
            return int(m.group(1))
        for w, n in CLOCK_WORDS.items():
            if re.search(rf"\b{w}\b", t):
                return n
        return None
    if k == "ground":
        from .extract import GROUND_SAID
        w = q["type"]
        if w == "water":
            if re.search(NO, t):
                return "no"
            if re.search(YES, t) or re.search(r"\b(lake|pond|stream|water|lac|étang|ruisseau|eau)\b", t):
                return "yes"
            return None
        for what, value, pat in GROUND_SAID:
            if what == w and re.search(pat, t, re.I):
                return value
        if w == "cover" and re.fullmatch(r"\W*(yes|yeah|oui|ouais)\W*", t):
            return "trees"
        if w == "cover" and re.fullmatch(r"\W*(no|nope|non)\W*", t):
            return "open"
        short = {"cover": [("trees", r"\b(trees?|woods?|forest|arbres?|bois|for[êe]t)\b"),
                           ("open", r"\b(open|lawn|grass|field|clearing|street|découvert|pelouse|rue)\b")],
                 "surface": [("none", r"\b(no path|none|nothing|grass|leaves|mud|pas de chemin|rien|herbe|feuilles)\b"),
                             ("paved", r"\b(tarmac|asphalt|paved|road|concrete|goudron|bitume|route|béton)\b"),
                             ("unpaved", r"\b(dirt|gravel|sand|earth|track|trail|path|terre|gravier|sable|chemin|sentier)\b")]}
        for value, pat in short.get(w, []):
            if re.search(pat, t):
                return value
        return None
    if k == "wound_where":
        # The body part itself is picked up by extraction (same casualty card).
        from .body import regions
        return "said" if regions(text or "") else None
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
    if k == "compass":
        if re.search(r"(no compass|don'?t have|pas de boussole|sans boussole)", t):
            return "none"
        from .extract import _compass_bearing
        b = _compass_bearing(t)
        if b is None:
            m = re.search(r"\b(\d{1,4})\b", t)
            if m:
                n = int(m.group(1))
                b = n * 360.0 / 6400.0 if n > 360 else float(n % 360)
        return b
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
    if k == "which_see":       # one yes / no per option, together
        return {"kind": "multi", "items": [{"kind": "feature_visible", "feature": i, "value": bool(value >> j & 1)}
                                           for j, i in enumerate(q["opts"])]}
    if k == "feature_dir":
        if value == "none":
            return {"kind": "feature_visible", "feature": q["feature"], "value": False}
        return {"kind": "bearing", "type": q["type"], "name": q["name"], "beta": int(value) * 30.0 % 360,
                "sigma": config.SIGMA_CLOCK, "distance_m": None}
    if k == "ground":
        return {"kind": "ground", "what": q["type"], "value": value, "source": "voice"}
    if k == "hear_dir":
        if value == "none":
            return {"kind": "hear", "cls": "traffic", "q": 0.0, "source": "voice", "w": 1.0}
        return {"kind": "bearing", "type": "main_road", "name": None, "beta": int(value) * 30.0 % 360,
                "sigma": config.SIGMA_HEARD, "distance_m": None, "heard": True}
    if k == "visible_type":
        return {"kind": "visible", "type": q["type"], "value": bool(value)}
    if k == "visible_feature":
        return {"kind": "feature_visible", "feature": q["feature"], "value": bool(value)}
    if k == "dist_band":
        return {"kind": "distance", "ref": q["ref"], "distance_m": float(value)}
    if k == "sun":
        return {"kind": "sun", "clock": int(value)}
    if k == "compass":
        if value in ("none", "unknown") or value is None:
            return None
        return {"kind": "abs_bearing", "type": q["ref"]["type"], "name": q["ref"].get("name"),
                "deg": (float(value) + config.MAG_DECLINATION) % 360, "said_deg": float(value),
                "sigma": config.SIGMA_BEARING, "distance_m": q["ref"].get("distance_m"), "heard": None}
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
