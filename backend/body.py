"""Casualty digital twin from the voice report: a 3D body showing what the medic said.

Same idea as the image-to-3D project (SMPL-X body, wounds painted on body regions),
but every input comes from the push-to-talk audio:
  - posture      "lying on his back", "face down", "sitting", "recovery position"
  - injuries     the MIST injury phrases -> body segments, side, kind of wound
  - tourniquet   the stated location -> a band on the limb, with its time
  - signs        conscious / breathing / massive bleeding, as said
  - sound cues   casualty sounds the microphone heard (groaning, gasping, coughing):
                 shown as cues to confirm, never used for priority

Decision support only: it draws what was reported, it does not assess the casualty.
The mesh comes from scripts/build_body.py (local SMPL-X model, not in the repo).
"""
import re

import numpy as np

from . import casualty, config, mobility

SEGMENTS = ["head", "neck", "chest", "abdomen", "pelvis",
            "l_upper_arm", "l_forearm", "l_hand", "r_upper_arm", "r_forearm", "r_hand",
            "l_thigh", "l_lower_leg", "l_foot", "r_thigh", "r_lower_leg", "r_foot"]
# SMPL-X joint -> the segment it moves (joint 1 = left hip moves the left thigh, ...).
JOINT_SEG = {0: "pelvis", 1: "l_thigh", 2: "r_thigh", 3: "abdomen", 4: "l_lower_leg",
             5: "r_lower_leg", 6: "chest", 7: "l_foot", 8: "r_foot", 9: "chest", 10: "l_foot",
             11: "r_foot", 12: "neck", 13: "chest", 14: "chest", 15: "head", 16: "l_upper_arm",
             17: "r_upper_arm", 18: "l_forearm", 19: "r_forearm", 20: "l_hand", 21: "r_hand",
             22: "head", 23: "head", 24: "head",
             **{j: "l_hand" for j in range(25, 40)}, **{j: "r_hand" for j in range(40, 55)}}
POSTURES = ["supine", "prone", "sitting", "recovery", "standing"]
POSTURE_LABEL = {"supine": "lying on the back", "prone": "lying face down", "sitting": "sitting",
                 "recovery": "recovery position (on the side)", "standing": "standing / walking"}
JOINT = {"l_hip": 1, "r_hip": 2, "l_knee": 4, "r_knee": 5, "l_ankle": 7, "r_ankle": 8,
         "l_shoulder": 16, "r_shoulder": 17, "l_elbow": 18, "r_elbow": 19, "l_wrist": 20, "r_wrist": 21}

# ------------------------------------------------------------------ words -> body
# Most specific first: "lower leg" before "leg", "forearm" before "arm".
PARTS = [
    (r"upper arm|biceps|shoulder|[ée]paule", ["upper_arm"]),
    (r"forearm|elbow|avant[- ]bras|coude", ["forearm"]),
    (r"hand|wrist|finger|main|poignet|doigt", ["hand"]),
    (r"thigh|femur|cuisse|f[ée]mur", ["thigh"]),
    (r"lower leg|shin|calf|knee|tibia|mollet|genou", ["lower_leg"]),
    (r"foot|feet|ankle|toe|pied|cheville|orteil", ["foot"]),
    (r"\bleg|jambe", ["thigh", "lower_leg"]),
    (r"\barms?\b|\bbras\b", ["upper_arm", "forearm"]),
    (r"chest|thorax|rib|poitrine|c[oô]te|torse", ["chest"]),
    (r"abdomen|stomach|belly|abdo|ventre|flank|flanc", ["abdomen"]),
    (r"pelvis|hip|groin|buttock|bassin|hanche|aine|fesse", ["pelvis"]),
    (r"head|face|scalp|skull|eye|jaw|t[eê]te|visage|cr[aâ]ne|oeil|[oœ]il|m[aâ]choire", ["head"]),
    (r"neck|throat|\bcou\b|gorge", ["neck"]),
    (r"\bback\b|\bdos\b|spine|colonne", ["chest", "abdomen"]),   # back surface
]
KINDS = [("amputation", r"amputat|severed|arrach"), ("burn", r"burn|br[uû]l"),
         ("gunshot", r"gunshot|gsw|shot|bullet|balle"), ("shrapnel", r"shrapnel|fragment|[ée]clat"),
         ("fracture", r"fracture|broken|cass[ée]|deformed"),
         ("bleeding", r"bleed|blood|h[ée]morrag|saign|wound|laceration|plaie|cut\b")]
LIMB_PROXIMAL = {"thigh": ("hip", "knee", 0.3), "lower_leg": ("knee", "ankle", 0.25),
                 "upper_arm": ("shoulder", "elbow", 0.3), "forearm": ("elbow", "wrist", 0.25)}


def _side(text):
    t = text.lower()
    if re.search(r"\bboth\b|les deux|bilat", t):
        return "both"
    left = re.search(r"\bleft\b|gauche", t)
    right = re.search(r"\bright\b|droit", t)
    if left and not right:
        return "l"
    if right and not left:
        return "r"
    return None


def regions(text):
    """'left leg bleeding' -> (['l_thigh', 'l_lower_leg'], side, surface, kind)."""
    t = text.lower()
    found, rest = [], t
    for pat, parts in PARTS:
        if re.search(pat, rest):
            found.append((pat, parts))
            rest = re.sub(pat, " ", rest)
    if not found:
        return None
    side = _side(t)
    segs = []
    for pat, parts in found:
        for p in parts:
            if p in ("head", "neck", "chest", "abdomen", "pelvis"):
                segs.append(p)
            else:
                segs += [f"{s}_{p}" for s in (("l", "r") if side in (None, "both") else (side,))]
    surface = "back" if any(p.startswith(r"\bback") for p, _ in found) else None
    kind = next((k for k, pat in KINDS if re.search(pat, t)), "injury")
    return {"segments": list(dict.fromkeys(segs)), "side": side, "surface": surface, "kind": kind}


def posture(texts):
    """Last posture mentioned in the transcripts, or None."""
    pats = [("recovery", r"recovery position|on (his|her|their|the) side|lateral|\bpls\b|position lat[ée]rale|sur le c[oô]t[ée]"),
            ("prone", r"face down|prone|on (his|her|their) (stomach|front|belly)|[àa] plat ventre|sur le ventre"),
            ("supine", r"on (his|her|their) back|lying (down|flat)|supine|flat on|sur le dos|allong[ée]"),
            ("sitting", r"\bsitting|\bseated|sat (up|down)|propped|assis"),
            ("standing", r"\bstanding|walking|ambulatory|debout|marche")]
    best, pos = None, -1
    joined = " . ".join(texts).lower()
    for name, pat in pats:
        for m in re.finditer(pat, joined):
            if m.start() > pos:
                best, pos = name, m.start()
    return best


# ------------------------------------------------------------------ casualty sounds
SOUND_HINT = {
    "Groan": "groaning", "Whimper": "whimpering", "Crying, sobbing": "crying",
    "Screaming": "screaming", "Wail, moan": "moaning", "Grunt": "grunting",
    "Gasp": "gasping", "Wheeze": "wheezing", "Snoring": "snoring-like breathing",
    "Pant": "rapid breathing", "Breathing": "audible breathing", "Cough": "coughing",
    "Walk, footsteps": "footsteps", "Run": "running", "Shuffle": "shuffling steps",
}
MOVING = {"Walk, footsteps", "Run", "Shuffle"}
VOCAL = {"Groan", "Whimper", "Crying, sobbing", "Screaming", "Wail, moan", "Grunt"}
AIRWAY = {"Gasp", "Wheeze", "Snoring", "Pant"}


def sound_cues(found):
    """[(label, score)] -> cue lines. Cues to confirm by assessment, never a finding."""
    out = []
    for label, score in found:
        what = SOUND_HINT.get(label, label.lower())
        if label in MOVING:
            note = "someone moving nearby (may be the buddy, not the casualty)"
        elif label in VOCAL:
            note = "a vocalising casualty is usually responsive: confirm"
        elif label in AIRWAY:
            note = "noisy breathing sound: check the airway"
        else:
            note = "sound cue only"
        out.append({"label": what, "score": round(score, 2), "note": note})
    return out


# ------------------------------------------------------------------ mesh
_mesh = None


def mesh():
    """The posed meshes, or None if scripts/build_body.py was not run."""
    global _mesh
    if _mesh is None:
        path = config.DATA_DIR / "body" / "body.npz"
        if not path.exists():
            _mesh = False
        else:
            z = np.load(path)
            _mesh = {k: z[k] for k in z.files}
    return _mesh or None


def mesh_json(p):
    m = mesh()
    if not m or f"verts_{p}" not in m:
        return None
    return {"posture": p, "segments": SEGMENTS, "joints": JOINT,
            "verts": np.round(m[f"verts_{p}"], 4).ravel().tolist(),
            "faces": m["faces"].ravel().tolist(), "seg": m["seg"].tolist(),
            "front": m["front"].tolist(),
            "joint_xyz": np.round(m[f"joints_{p}"], 4).tolist()}


# ------------------------------------------------------------------ twin
def twin(rep):
    """Everything the viewer needs for each casualty of a report."""
    texts = [t["text"] for t in rep.get("transcripts", [])]
    pst = posture(texts)
    cues = sound_cues(rep.get("casualty_audio") or [])
    out = []
    for i, c in enumerate(rep.get("casualties") or []):
        injuries = []
        for phrase in c.get("injuries") or []:
            r = regions(phrase)
            if r:
                injuries.append({"text": phrase, **r})
        if (c.get("signs") or {}).get("massive_bleeding"):
            # On the bleeding wound(s); if none is named as bleeding, on the limb wounds.
            bleeding = [x for x in injuries if x["kind"] in ("bleeding", "amputation")] or \
                [x for x in injuries if any(s[2:] in LIMB_PROXIMAL for s in x["segments"])]
            for inj in bleeding:
                inj["massive"] = True
        tqs = []
        for t in c.get("treatments") or []:
            if t.get("type") != "tourniquet":
                continue
            r = regions(t.get("location") or "") if t.get("location") else None
            limb_segs = [s for s in (r["segments"] if r else []) if s[2:] in LIMB_PROXIMAL]
            if not limb_segs:   # no location said: the injured limb, if there is one
                limb_segs = [s for inj in injuries for s in inj["segments"] if s[2:] in LIMB_PROXIMAL]
            if not limb_segs:
                continue
            # A tourniquet goes high on the limb: thigh / upper arm when the whole limb was named.
            seg = next((s for s in limb_segs if s[2:] in ("thigh", "upper_arm")), limb_segs[0])
            a, b, at = LIMB_PROXIMAL[seg[2:]]
            tqs.append({"segment": seg, "from": f"{seg[0]}_{a}", "to": f"{seg[0]}_{b}", "at": at,
                        "time": t.get("time"), "tq_ms": casualty.tourniquet_epoch_ms(t.get("time")),
                        "said": t.get("location"), "side_said": bool(r and r["side"] in ("l", "r"))})
        out.append({
            "index": i, "count": c.get("count", 1), "priority": casualty.priority(c),
            "mechanism": c.get("mechanism"), "signs": c.get("signs") or {},
            "injuries": injuries, "tourniquets": tqs,
            "unmapped": [p for p in c.get("injuries") or [] if not regions(p)],
            "treatments": [t["type"] for t in c.get("treatments") or [] if t.get("type") != "tourniquet"],
        })
        out[-1]["mobility"] = mobility.assess(rep, out[-1], pst)
    return {"report_id": rep["id"], "posture": pst or "supine", "posture_said": bool(pst),
            "posture_label": POSTURE_LABEL[pst or "supine"], "sound_cues": cues,
            "casualties": out, "mesh_ok": mesh() is not None,
            "tq_warn_min": config.TOURNIQUET_WARN_MIN}
