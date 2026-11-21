"""In-memory store of casualty reports, and the pipeline for one utterance:

text -> extract -> constraints / answer -> localise -> next question
     -> read-back + packet -> (main.py broadcasts the new state)
"""
import math
import threading
import time
from datetime import datetime, timezone

from . import casualty, config, questions, readback
from .extract import extract, to_constraints
from .landmarks import get_db
from .localise import get_engine

LOCK = threading.Lock()


def now_ms():
    return int(time.time() * 1000)


def merge_acoustic(existing, new):
    """Add acoustic constraints without counting the same thing twice:
    - hear: one per sound group; the operator's own answer beats the machine,
      among machine clips keep the strongest (several clips hear the same trains)
    - setting: one from audio (the most informative clip) + one from the operator
    - reflector: the latest echo distance only
    """
    out = list(existing)
    for c in new:
        k = c["kind"]
        if k == "hear":
            same = [x for x in out if x["kind"] == "hear" and x["cls"] == c["cls"]]
            if c["source"] == "voice":
                out = [x for x in out if x not in same] + [c]
            elif any(x["source"] == "voice" for x in same):
                continue
            elif not same or c["q"] > max(x["q"] for x in same):
                out = [x for x in out if x not in same] + [c]
        elif k == "setting":
            same = [x for x in out if x["kind"] == "setting" and x["source"] == c["source"]]
            if c["source"] == "voice" or not same or _strength(c) >= _strength(same[0]):
                out = [x for x in out if x not in same] + [c]
        elif k == "reflector":
            out = [x for x in out if x["kind"] != "reflector"] + [c]
        else:
            out.append(c)
    return out


def _strength(c):
    p = list(c["p"].values())
    return max(p) - min(p)


def acoustic_public(an):
    """What the coordinator sees of one audio analysis (no private keys)."""
    sp = {k: v for k, v in (an.get("space") or {}).items() if not k.startswith("_")}
    pr = sp.get("probe") or {}
    if pr:
        sp["probe"] = {k: pr.get(k) for k in ("ok", "why", "rt60_s", "drr_db", "c50_db", "nearest_wall_m",
                                              "wall_reliable", "floor_or_ceiling_m", "reflections")}
    return {"ms": now_ms(), "kind": an.get("kind"), "quality": an.get("audio_quality"),
            "notes": an.get("quality_notes"), "speech_fraction": an.get("speech_fraction"),
            "events": an.get("events", [])[:5], "context": an.get("context", [])[:3],
            "alerts": an.get("alerts", []), "features": an.get("features"), "space": sp,
            "source": an.get("source", "audio")}


class Store:
    def __init__(self):
        self.reports = {}
        self.counter = 0
        self.ccp = dict(config.CCP)
        self.version = 0

    # ------------------------------------------------------------ reports
    def new_report(self):
        self.counter += 1
        rid = f"C{self.counter}"
        self.reports[rid] = {
            "id": rid, "created_ms": now_ms(), "updated_ms": now_ms(), "callsign": None,
            "lang": None, "casualties": [], "constraints": [], "asked": [], "question": None,
            "transcripts": [], "position": None, "heat": None, "readback": "",
            "summary": casualty.summary([]), "packet": None, "evacuated": False, "truth": None,
            "acoustic": [], "alerts": [], "casualty_audio": [],
        }
        return self.reports[rid]

    def get_or_create(self, rid):
        if rid and rid in self.reports:
            return self.reports[rid]
        return self.new_report()

    # ------------------------------------------------------------ pipeline
    def process(self, rid, text, gps=None, source="voice", lang_hint=None, truth=None):
        """Handle one utterance from the field. Returns the updated report."""
        with LOCK:
            rep = self.get_or_create(rid)
            if truth:
                rep["truth"] = truth
            q = rep["question"]
            ctx = {"last_question": q, "summary": self._short_summary(rep)}
            ex, src = extract(text, ctx)

            # Language: set by the first real report, not by a "yes".
            if rep["lang"] is None or len(text.split()) >= 5:
                rep["lang"] = ex["lang"] if len(text.split()) >= 3 else (lang_hint or rep["lang"] or "en")
            rep["lang"] = rep["lang"] or lang_hint or "en"
            if ex.get("callsign"):
                rep["callsign"] = ex["callsign"]
            rep["transcripts"].append({"ms": now_ms(), "text": text, "source": src,
                                       "via": source})

            # Casualty info: merge into what we have.
            for i, c in enumerate(ex["casualties"]):
                if i < len(rep["casualties"]):
                    rep["casualties"][i] = casualty.merge(rep["casualties"][i], c)
                else:
                    rep["casualties"].append(c)

            # New landmarks / sun.
            new_cons = to_constraints(ex)
            for c in new_cons:
                if c["kind"] == "sun":   # only one sun direction
                    rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "sun"]
                if c["kind"] in ("hear", "setting", "reflector"):
                    rep["constraints"] = merge_acoustic(rep["constraints"], [c])
                else:
                    rep["constraints"].append(c)

            # Answer to the pending question.
            if q:
                ans = ex.get("answer_to_question") or {}
                val = questions.parse_answer(q, text, ans.get("value"))
                if val is not None:
                    q["answer"] = val
                    con = questions.answer_to_constraint(q, val)
                    if con:
                        if con["kind"] == "sun":   # may already be there from extraction
                            rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "sun"]
                        if con["kind"] in ("hear", "setting"):
                            rep["constraints"] = merge_acoustic(rep["constraints"], [con])
                        else:
                            rep["constraints"].append(con)
                    rep["question"] = None
                elif new_cons:
                    q["answer"] = "skipped"
                    rep["question"] = None
                else:
                    # Not understood: ask again once, then move on to another question.
                    q["tries"] = q.get("tries", 0) + 1
                    if q["tries"] >= 2:
                        q["answer"] = "not understood"
                        rep["question"] = None

            if gps and gps.get("lat") is not None:
                rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "gps"]
                rep["constraints"].append({"kind": "gps", "lat": gps["lat"], "lon": gps["lon"],
                                           "acc": gps.get("acc")})

            self._relocate(rep, ask=rep["question"] is None)
            rep["updated_ms"] = now_ms()
            self.version += 1
            return rep

    def process_audio(self, rid, an):
        """Handle one acoustic analysis (Listen clip or the audio of a voice report)."""
        from .acoustic import to_constraints as audio_constraints
        with LOCK:
            rep = self.get_or_create(rid)
            new = audio_constraints(an)
            rep["constraints"] = merge_acoustic(rep["constraints"], new)
            viz = an.pop("_viz", None)
            if "casualty_sounds" in an:   # latest clip only: an old groan is no longer news
                rep["casualty_audio"] = an["casualty_sounds"]
            pub = acoustic_public(an)
            if viz:   # pictures for the pipeline page (kept out of the websocket state)
                pr = (an.get("space") or {}).get("probe") or {}
                rep["_viz"] = {**viz, "ms": pub["ms"], "kind": pub["kind"], "quality": pub["quality"],
                               "echogram": pr.get("echogram"), "wall_m": pr.get("nearest_wall_m"),
                               "wall_reliable": pr.get("wall_reliable"),
                               "floor_m": pr.get("floor_or_ceiling_m")}
            pub["used"] = [c["kind"] + (":" + c["cls"] if c.get("cls") else "") for c in new]
            rep["acoustic"] = (rep["acoustic"] + [pub])[-6:]
            for a in an.get("alerts", []):
                rep["alerts"].append({"ms": now_ms(), **a})
            # A Listen clip does not answer a question: keep asking the pending one.
            self._relocate(rep, ask=rep["question"] is None)
            rep["updated_ms"] = now_ms()
            self.version += 1
            return rep

    def _relocate(self, rep, ask=True):
        eng = get_engine()
        when = datetime.now(timezone.utc)
        if rep["constraints"]:
            res = eng.run(rep["constraints"], when=when)
            rep["position"] = {k: res[k] for k in ("lat", "lon", "radius_m", "main_mass",
                                                   "blobs", "heading_deg")}
            rep["position"]["state"] = readback.position_state(rep["position"])
            rep["heat"] = res["heat"]
        else:
            res = {"blobs": [], "radius_m": None, "main_mass": 0}
            rep["position"], rep["heat"] = None, None

        if ask:
            q, why = questions.choose(rep["constraints"], rep["asked"], res, eng, when)
            if q:
                q["id"] = f"q{len(rep['asked']) + 1}"
                q["text"] = questions.phrase(q, rep["lang"] or "en")
                rep["asked"].append(q)
                rep["question"] = q
        if rep["position"]:
            rep["position"]["state"] = readback.position_state(rep["position"])
        rep["summary"] = casualty.summary(rep["casualties"])
        rep["readback"] = readback.make(rep)
        rep["packet"] = readback.packet(rep)

    def _short_summary(self, rep):
        p = rep.get("position")
        if not p:
            return None
        return {"lat": round(p["lat"], 5), "lon": round(p["lon"], 5),
                "radius_m": round(p["radius_m"]), "areas": len(p["blobs"])}

    # ------------------------------------------------------------ views
    def distance_to_ccp(self, rep):
        p = rep.get("position")
        if not p or p.get("lat") is None:
            return None
        db = get_db()
        x1, y1 = db.to_xy(p["lat"], p["lon"])
        x2, y2 = db.to_xy(self.ccp["lat"], self.ccp["lon"])
        return float(math.hypot(x1 - x2, y1 - y2))

    def evac_order(self):
        live = [r for r in self.reports.values() if not r["evacuated"] and r["summary"]["count"]]
        def key(r):
            d = self.distance_to_ccp(r)
            return (r["summary"]["rank"], r["summary"]["tq_ms"] or 9e15, d if d is not None else 9e9)
        return [r["id"] for r in sorted(live, key=key)]

    def public(self):
        """Everything the coordinator page needs, JSON-ready."""
        from .body import twin
        out = []
        for r in self.reports.values():
            mob = [c["mobility"] for c in twin(r)["casualties"]] if r["casualties"] else []
            out.append({
                "id": r["id"], "callsign": r["callsign"], "lang": r["lang"],
                "created_ms": r["created_ms"], "updated_ms": r["updated_ms"],
                "casualties": [{**c, "priority": casualty.priority(c), "mist": casualty.mist(c),
                                "mobility": mob[i] if i < len(mob) else None}
                               for i, c in enumerate(r["casualties"])],
                "summary": r["summary"], "position": r["position"], "heat": r["heat"],
                "question": _q_public(r["question"]),
                "asked": [_q_public(q) for q in r["asked"]],
                "transcripts": r["transcripts"][-8:], "readback": r["readback"],
                "packet": r["packet"], "evacuated": r["evacuated"], "truth": r["truth"],
                "distance_ccp": self.distance_to_ccp(r),
                "acoustic": r.get("acoustic", []), "alerts": r.get("alerts", [])[-5:],
                "evidence": _evidence_counts(r["constraints"]),
            })
        return {"type": "state", "version": self.version, "server_ms": now_ms(),
                "reports": out, "order": self.evac_order(), "ccp": self.ccp,
                "tq_warn_min": config.TOURNIQUET_WARN_MIN,
                "target_radius_m": config.TARGET_RADIUS_M}


def _evidence_counts(cons):
    """How many constraints of each family went into the position (for the card)."""
    fam = {"bearing": "landmarks", "visible": "landmarks", "here": "landmarks",
           "feature_visible": "landmarks", "distance": "landmarks", "left_right": "landmarks",
           "sun": "sun", "gps": "gps", "hear": "sound", "setting": "space", "reflector": "space"}
    out = {}
    for c in cons:
        f = fam.get(c["kind"], "other")
        out[f] = out.get(f, 0) + 1
    return out


def _q_public(q):
    if not q:
        return None
    return {"id": q.get("id"), "kind": q["kind"], "text": q.get("text"),
            "answer": q.get("answer"), "gain_bits": q.get("gain_bits")}


STORE = Store()
