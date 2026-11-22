"""Body parts graph: every body part as a node, red when the report says it is affected,
orange when nothing was said about it (no data, NOT "fine").

Tree: body -> 7 regions (head, neck, torso, left / right arm, left / right leg) -> parts.
Words are matched most specific first ("lower leg" before "leg", "back of the neck" before
"neck" and "back"). A part is red when it was named; a region is red when one of its parts
is, or when only the region was named ("leg wound": the leg is red, its parts stay orange
because we don't know where on the leg). An injury with no body part ("very hurt") turns
only the root red. Side not said -> both sides, flagged.
"""
import re

from .body import _side

REGIONS = [("head", "Head", None), ("neck", "Neck", None), ("torso", "Torso", None),
           ("l_arm", "Left arm", "l"), ("r_arm", "Right arm", "r"),
           ("l_leg", "Left leg", "l"), ("r_leg", "Right leg", "r")]

# (part, label, region kind, pattern). Region kind "arm" / "leg" means one per side.
PARTS = [
    ("nape", "Back of neck", "neck", r"back of (the |his |her )?neck|nape|nuque|cervical|cervicale"),
    ("upper_back", "Upper back", "torso", r"upper back|shoulder blade|haut du dos|omoplate"),
    ("lower_back", "Lower back", "torso", r"lower back|bas du dos|lumbar|lombaire|spine|colonne|vert[eè]bre"),
    ("upper_arm", "Upper arm", "arm", r"upper arm|biceps|triceps|humerus|hum[ée]rus|haut du bras"),
    ("lower_leg", "Lower leg", "leg", r"lower leg|shin|calf|tibia|mollet|bas de la jambe"),
    ("forearm", "Forearm", "arm", r"forearm|avant[- ]bras"),
    ("scalp", "Scalp / skull", "head", r"scalp|skull|cr[aâ]ne|cuir chevelu"),
    ("face", "Face", "head", r"face|cheek|nose|forehead|visage|joue|nez|front\b"),
    ("eyes", "Eyes", "head", r"\beyes?\b|\boeil\b|\bœil\b|\byeux\b"),
    ("ears", "Ears", "head", r"\bears?\b|eardrum|oreilles?|tympan"),
    ("jaw", "Jaw / mouth", "head", r"jaw|mouth|teeth|tooth|m[aâ]choire|bouche|dents?\b"),
    ("throat", "Throat", "neck", r"throat|trachea|airway|gorge|trach[ée]e"),
    ("ribs", "Ribs", "torso", r"\bribs?\b|c[oô]tes?\b"),
    ("chest", "Chest", "torso", r"chest|thorax|sternum|poitrine|torse|thoracique"),
    ("abdomen", "Abdomen", "torso", r"abdomen|stomach|belly|abdo|ventre|flank|flanc"),
    ("groin", "Groin", "torso", r"groin|\baine\b|entrejambe"),
    ("buttocks", "Buttocks", "torso", r"buttock|fesse"),
    ("pelvis", "Pelvis", "torso", r"pelvis|bassin"),
    ("shoulder", "Shoulder", "arm", r"shoulder|[ée]paule"),
    ("elbow", "Elbow", "arm", r"elbow|coude"),
    ("wrist", "Wrist", "arm", r"wrist|poignet"),
    ("hand", "Hand", "arm", r"\bhands?\b|finger|thumb|palm|\bmains?\b|doigt|pouce|paume"),
    ("hip", "Hip", "leg", r"\bhips?\b|hanche"),
    ("thigh", "Thigh", "leg", r"thigh|femur|f[ée]mur|cuisse"),
    ("knee", "Knee", "leg", r"knee|genou"),
    ("ankle", "Ankle", "leg", r"ankle|cheville"),
    ("foot", "Foot", "leg", r"\bfoot\b|\bfeet\b|\btoes?\b|heel|\bpieds?\b|orteil|talon"),
]
# Only the region said ("head wound", "leg", "arm", "back").
REGION_WORDS = [("head", r"\bhead\b|t[eê]te"), ("neck", r"\bneck\b|\bcou\b"),
                ("torso", r"\bback\b|\bdos\b|torso|trunk|tronc"),
                ("arm", r"\barms?\b|\bbras\b"), ("leg", r"\blegs?\b|jambes?")]
ORDER = {"head": ["scalp", "face", "eyes", "ears", "jaw"], "neck": ["throat", "nape"],
         "torso": ["chest", "ribs", "upper_back", "lower_back", "abdomen", "pelvis", "groin", "buttocks"],
         "arm": ["shoulder", "upper_arm", "elbow", "forearm", "wrist", "hand"],
         "leg": ["hip", "thigh", "knee", "lower_leg", "ankle", "foot"]}
LABEL = {p: lab for p, lab, _, _ in PARTS}


def _region_ids(kind, side):
    if kind in ("arm", "leg"):
        sides = ("l", "r") if side not in ("l", "r") else (side,)
        return [f"{s}_{kind}" for s in sides]
    return [kind]


def match(text):
    """'left knee and shin' -> ([node ids], side_unknown). Region ids when only the region was said."""
    t = text.lower()
    side = _side(t)
    rest, hits, kinds = t, [], set()
    for part, _, kind, pat in PARTS:
        if re.search(pat, rest):
            rest = re.sub(pat, " ", rest)
            kinds.add(kind)
            for reg in _region_ids(kind, side):
                hits.append(f"{reg[0]}_{part}" if kind in ("arm", "leg") else part)
    for kind, pat in REGION_WORDS:
        if kind not in kinds and re.search(pat, rest):
            if kind == "torso" and re.search(r"\bback\b|\bdos\b", rest):   # "back": both back parts
                hits += ["upper_back", "lower_back"]
            else:
                hits += _region_ids(kind, side)
    unknown_side = side not in ("l", "r") and any(h[:2] in ("l_", "r_") for h in hits)
    return list(dict.fromkeys(hits)), unknown_side


def parts_graph(cas):
    """Nodes for one casualty (a report casualty dict: injuries, treatments)."""
    nodes = {"body": {"id": "body", "label": "Body", "parent": None, "said": [], "direct": False}}
    for rid, label, _ in REGIONS:
        nodes[rid] = {"id": rid, "label": label, "parent": "body", "said": [], "direct": False}
        kind = rid[2:] if rid[:2] in ("l_", "r_") else rid
        for p in ORDER[kind]:
            pid = f"{rid[0]}_{p}" if kind in ("arm", "leg") else p
            nodes[pid] = {"id": pid, "label": LABEL[p], "parent": rid, "said": [], "direct": False}

    def mark(text, why):
        ids, unknown = match(text)
        if not ids:
            nodes["body"]["said"].append(f"{why}: “{text}” (no body part named)")
            nodes["body"]["direct"] = True
            return
        for i in ids:
            if i in nodes:
                nodes[i]["direct"] = True
                nodes[i]["said"].append(f"{why}: “{text}”" + (" · side not said" if unknown and i[:2] in ("l_", "r_") else ""))

    for phrase in cas.get("injuries") or []:
        mark(phrase, "wound")
    for t in cas.get("treatments") or []:
        if t.get("location"):
            mark(t["location"], t.get("type") or "treatment")
    # A part / region is affected when it or anything under it was named.
    for n in list(nodes.values()):
        if n["direct"]:
            p = n
            while p:
                p["affected"] = True
                p = nodes.get(p["parent"]) if p["parent"] else None
    out = []
    for n in nodes.values():
        out.append({"id": n["id"], "label": n["label"], "parent": n["parent"],
                    "status": "affected" if n.get("affected") else "nodata",
                    "direct": n["direct"], "said": n["said"]})
    return out
