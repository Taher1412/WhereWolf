"""In-memory store of casualty reports, and the pipeline for one utterance:

text -> extract -> constraints / answer -> localise -> next question
     -> read-back + packet -> (main.py broadcasts the new state)
"""
import math
import threading
import time
from datetime import datetime, timezone

from . import casualty, condition, config, danger, guide, questions, readback
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
        elif k in ("reflector", "echoes"):   # the latest echo measurement only
            out = [x for x in out if x["kind"] not in ("reflector", "echoes")] + [c]
        elif k == "ambient":                  # the most precise level (calibrated beats not), else latest
            same = [x for x in out if x["kind"] == "ambient"]
            if not same or c["sigma"] <= min(x["sigma"] for x in same):
                out = [x for x in out if x["kind"] != "ambient"] + [c]
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
            "ambient": {k: v for k, v in (an.get("ambient") or {}).items() if k != "offset"} or None,
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
            "dangers": [], "danger_near": [], "guide": None,
        }
        return self.reports[rid]

    def get_or_create(self, rid):
        if rid and rid in self.reports:
            return self.reports[rid]
        return self.new_report()

    # ------------------------------------------------------------ pipeline
    def process(self, rid, text, gps=None, source="voice", lang_hint=None, truth=None,
                compass=None, last_fix=None, aims=None, voice=None):
        """Handle one utterance from the field. Returns the updated report."""
        with LOCK:
            rep = self.get_or_create(rid)
            if truth:
                rep["truth"] = truth
            g = rep.get("guide")
            moving = bool(g and g["state"] in ("active", "lost"))
            cmd = guide.command(text) if moving else None
            if cmd:   # "next", "I'm lost", "arrived"... while walking to the CCP
                rep["transcripts"].append({"ms": now_ms(), "text": text, "source": "guide", "via": source})
                said = guide.apply(rep, cmd, self.ccp, self.zones(), now_ms())
                rep["readback"] = said or rep["readback"]
                self._log_changes(rep, "voice", text)
                rep["updated_ms"] = now_ms()
                self.version += 1
                return rep
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
            for c in ex["casualties"]:
                if c.get("injury_ago_min") is not None:          # "hit 10 minutes ago"
                    c["injury_ago_ms"] = now_ms() - int(c["injury_ago_min"]) * 60000
            for i, c in enumerate(ex["casualties"]):
                if i < len(rep["casualties"]):
                    rep["casualties"][i] = casualty.merge(rep["casualties"][i], c)
                else:
                    rep["casualties"].append(c)

            # New landmarks / sun.
            new_cons = to_constraints(ex)
            if moving and new_cons:
                # A walker describing new landmarks: what they saw at the start no longer
                # applies. Locate again around where the dead reckoning puts them.
                rep["constraints"] = [guide.track_prior(g)]
                rep["_refix"] = True
            for c in new_cons:
                if c["kind"] == "sun":   # only one sun direction
                    rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "sun"]
                if c["kind"] in ("hear", "setting", "reflector"):
                    rep["constraints"] = merge_acoustic(rep["constraints"], [c])
                elif c["kind"] == "ground":   # the latest word on the ground wins
                    rep["constraints"] = [x for x in rep["constraints"]
                                          if not (x["kind"] == "ground" and x["what"] == c["what"])] + [c]
                else:
                    rep["constraints"].append(c)

            # Answer to the pending question.
            if q:
                ans = ex.get("answer_to_question") or {}
                medical = q["kind"] in questions.MEDICAL_KINDS and q["kind"] != "wound_where"
                val = questions.parse_medical(q, text) if medical else questions.parse_answer(q, text, ans.get("value"))
                if medical and val is not None and rep["casualties"]:
                    questions.apply_medical(rep["casualties"][0], q, val)
                if val is not None:
                    q["answer"] = val
                    con = None if medical else questions.answer_to_constraint(q, val)
                    if con:
                        if con["kind"] == "sun":   # may already be there from extraction
                            rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "sun"]
                        if con["kind"] in ("hear", "setting"):
                            rep["constraints"] = merge_acoustic(rep["constraints"], [con])
                        elif con["kind"] == "ground":
                            rep["constraints"] = [x for x in rep["constraints"] if not (
                                x["kind"] == "ground" and x["what"] == con["what"])] + [con]
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

            # How stressed the speaker sounds (voice of this report + its words).
            self._update_stress(rep, voice, text)
            rep["_voice_quick"] = bool(voice)

            # Phone aimed at the top of each landmark, in the order they are named.
            self._apply_aims(rep, new_cons, aims)

            # Phone compass (where the speaker's 12 o'clock points) and the last GPS fix
            # before jamming: one of each, the latest wins.
            if compass and isinstance(compass.get("deg"), (int, float)):
                rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "compass"]
                rep["constraints"].append({"kind": "compass", "deg": float(compass["deg"]) % 360,
                                           "sigma": max(config.SIGMA_COMPASS, float(compass.get("acc") or 0))})
            if last_fix and last_fix.get("lat") is not None:
                rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "last_fix"]
                rep["constraints"].append({"kind": "last_fix", "lat": last_fix["lat"], "lon": last_fix["lon"],
                                           "acc": last_fix.get("acc"), "age_s": last_fix.get("age_s", 0)})
            # Threats named in the report ("drone overhead", "sniper at my 2 o'clock").
            for d in danger.from_text(text):
                danger.add(rep["dangers"], {**d, "source": "voice", "conf": 0.9, "ms": now_ms()})

            if gps and gps.get("lat") is not None:
                rep["constraints"] = [x for x in rep["constraints"] if x["kind"] != "gps"]
                rep["constraints"].append({"kind": "gps", "lat": gps["lat"], "lon": gps["lon"],
                                           "acc": gps.get("acc")})

            self._relocate(rep, ask=rep["question"] is None)
            self._log_changes(rep, "voice", text)
            rep["updated_ms"] = now_ms()
            self.version += 1
            return rep

    def process_audio(self, rid, an):
        """Handle one acoustic analysis (Listen clip or the audio of a voice report)."""
        from .acoustic import to_constraints as audio_constraints
        from .surround import calibrate
        with LOCK:
            rep = self.get_or_create(rid)
            calibrate(an, rep)              # voice clip: remember the phone's level offset
            vf = an.pop("voice_features", None)
            if vf and not rep.get("_voice_quick"):   # no quick measure for this report: use this clip
                self._update_stress(rep, vf)
            rep["_voice_quick"] = False
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
            for d in danger.from_audio(an.get("alerts", []), now_ms()):
                danger.add(rep["dangers"], d)
            # A Listen clip does not answer a question: keep asking the pending one.
            self._relocate(rep, ask=rep["question"] is None)
            self._log_changes(rep, "audio", an.get("kind") or "clip")
            rep["updated_ms"] = now_ms()
            self.version += 1
            return rep

    def _update_stress(self, rep, voice, text=None):
        """Speaker stress from the voice (backend/stress.py) and the words of the report.
        The voice of a report without its own clip keeps the last measured one."""
        from . import stress
        if voice:
            rep.setdefault("voices", []).append(voice)
        voices = rep.get("voices") or []
        last_text = text if text is not None else (rep["transcripts"][-1]["text"] if rep["transcripts"] else "")
        est = stress.estimate(voices[-1] if voices else None, stress.text_features(last_text),
                              voices[0] if len(voices) > 1 else None)
        if est["level"] != "unknown":
            rep["stress"] = est

    def _apply_aims(self, rep, new_cons, aims):
        """Taps from the field page (tilt = elevation angle, turn between taps = angle
        between landmarks) -> constraints, matched to the landmarks of this report in the
        order they were said. Taps with no landmark named yet wait for the next report."""
        aims = [a for a in (aims or []) if isinstance(a, dict) and isinstance(a.get("el"), (int, float))]             or rep.pop("pending_aims", None) or []
        if not aims:
            return
        seen = [c for c in new_cons if c["kind"] in ("bearing", "visible", "here")
                and c.get("value", True) and not c.get("heard")]
        if not seen:
            rep["pending_aims"] = aims
            return
        n = min(len(aims), len(seen))
        for i in range(n):
            lm = {"type": seen[i]["type"], "name": seen[i].get("name")}
            el = float(aims[i]["el"])
            if 0.0 < el < 80.0:
                rep["constraints"].append({"kind": "elevation", **lm, "deg": el, "sigma": config.SIGMA_TILT})
            if i > 0:
                a0 = {"type": seen[0]["type"], "name": seen[0].get("name")}
                deg = ((float(aims[i]["az"]) - float(aims[0]["az"])) + 180) % 360 - 180
                rep["constraints"].append({"kind": "angle_between", "a": a0, "b": lm, "deg": deg,
                                           "sigma": config.SIGMA_SWEEP})
        rep["aim_note"] = n

    def tick(self):
        """Every 2 s (main.py): move the walkers being guided. True if the map changed."""
        with LOCK:
            walking = [r for r in self.reports.values() if r.get("guide") and r["guide"]["state"] == "active"]
            if not walking:
                return False
            zs, now = self.zones(), now_ms()
            for r in walking:
                v = r["guide"]["say_v"]
                guide.tick(r, self.ccp, zs, now)
                if r["guide"]["say_v"] != v:          # new instruction: also refresh the packet
                    r["readback"] = r["guide"]["instruction"] or r["readback"]
                    r["packet"] = readback.packet(r)
            self.version += 1
            return True

    def guide_action(self, rid, action, steps=None):
        """Buttons on the phone or the map: start, reached, lost, repeat, arrived, stop, steps."""
        with LOCK:
            rep = self.reports.get(rid)
            if not rep:
                return None
            said = guide.apply(rep, action, self.ccp, self.zones(), now_ms(), steps=steps)
            if said:
                rep["readback"] = said
                rep["packet"] = readback.packet(rep)
            if action != "steps":
                self._log_changes(rep, "guide", action)
            self.version += 1
            return rep

    def zones(self):
        return danger.zones(self.reports.values(), now_ms())["zones"]

    def _relocate(self, rep, ask=True):
        eng = get_engine()
        when = datetime.now(timezone.utc)
        g = rep.get("guide")
        moving = bool(g and g["state"] in ("active", "lost"))
        refix = rep.pop("_refix", False)
        if moving and not refix:
            pass      # the pin follows the walker (guide.py); old landmarks are behind them
        elif rep["constraints"]:
            res = eng.run(rep["constraints"], when=when)
            rep["position"] = {k: res[k] for k in ("lat", "lon", "radius_m", "main_mass",
                                                   "blobs", "hyps", "heading_deg", "heading_conf")}
            rep["position"]["state"] = readback.position_state(rep["position"])
            rep["heat"] = res["heat"]
        else:
            res = {"blobs": [], "radius_m": None, "main_mass": 0}
            rep["position"], rep["heat"] = None, None

        ask = ask and not moving and not rep.get("at_ccp")
        if ask:
            level = (rep.get("stress") or {}).get("level", "unknown")
            med = questions.medical_question(rep["casualties"], rep["asked"])
            if med and med["kind"] == "wound_where":
                med.update(goal="health", goal_text="Goal: where the wound is, to know what is at risk")
            last = rep["asked"][-1]["kind"] if rep["asked"] else None
            loc = None
            if not (med and med.get("life")):
                loc, why = questions.choose(rep["constraints"], rep["asked"], res, eng, when, stress=level)
            # Life threats first; otherwise take turns: a location question, then a health one.
            if med and (med.get("life") or loc is None or last not in questions.MEDICAL_KINDS):
                q = med if (med.get("life") or loc is None or last is not None) else loc
            else:
                q = loc or med
            if q:
                q["id"] = f"q{len(rep['asked']) + 1}"
                q["stress"] = level
                short = level == "high"
                q["text"] = (questions.med_phrase(q, rep["lang"] or "en", short) if q["kind"] in questions.MED_TEXT
                             else questions.phrase(q, rep["lang"] or "en", short=short))
                rep["asked"].append(q)
                rep["question"] = q
        if rep["position"]:
            rep["position"]["state"] = readback.position_state(rep["position"])
        rep["summary"] = casualty.summary(rep["casualties"])
        # Threats other units reported where this one stands (spoken in the read-back).
        rep["danger_near"] = danger.near(rep, danger.zones(self.reports.values(), now_ms())["zones"])
        rep["readback"] = readback.make(rep)
        # A walking casualty, located: plan the route to the CCP and say the first leg.
        if moving and refix:
            guide.reanchor(rep, self.ccp, self.zones(), now_ms())
            rep["readback"] = rep["guide"]["instruction"]
        elif moving:
            guide.pin_dangers(rep)            # new threats stay where the walker is now
            rep["readback"] = readback.make(rep) + " " + (rep["guide"].get("instruction") or "")
        elif guide.can_guide(rep, self.ccp):
            g = guide.start(rep, self.ccp, self.zones(), now_ms())
            if g:
                rep["question"] = None
                rep["readback"] = readback.make(rep) + " " + g["instruction"]
        rep["packet"] = readback.packet(rep)

    # ------------------------------------------------------------ what changed
    def _snapshot(self, rep):
        """The things the coordinator watches, per casualty, to spot what a new report changed."""
        from . import body, response
        tw = body.twin(rep)
        cas = []
        for c in tw["casualties"]:
            s = c["signs"]
            cas.append({
                "priority": c["priority"],
                "conscious": s.get("conscious"), "breathing": s.get("breathing"),
                "massive bleeding": s.get("massive_bleeding"),
                "injuries": [i["text"] for i in c["injuries"]] + c["unmapped"],
                "tourniquets": [f"{t['segment'].replace('_', ' ')} {t['time'] or ''}".strip() for t in c["tourniquets"]],
                "mobility": c["mobility"]["label"],
                "posture": c["posture"]["label"] + ("" if c["posture"]["source"] == "said" else
                                                    f" ({round(c['posture']['confidence'] * 100)}%)"),
                "posture_key": c["posture"]["posture"],
            })
        team = None
        if rep["casualties"]:
            r = response.build(rep, self.distance_to_ccp(rep))
            team = r["team"]["total"] if r.get("team") else None
        p = rep.get("position")
        return {"cas": cas, "team": team, "radius": round(p["radius_m"]) if p and p.get("radius_m") else None,
                "areas": len([b for b in p["blobs"] if b["mass"] >= 0.12]) if p else 0}

    def _log_changes(self, rep, via, what):
        """Compare with the last snapshot and keep a short, readable list of changes."""
        try:
            new = self._snapshot(rep)
        except Exception as e:   # never break the pipeline for the change log
            print("change log:", e)
            return
        old = rep.get("_snap")
        rep["_snap"] = new
        items = []
        yn = {True: "yes", False: "no", None: "?"}
        if old is None:
            items.append("first report")
        else:
            for i, c in enumerate(new["cas"]):
                tag = f"#{i + 1} " if len(new["cas"]) > 1 else ""
                o = old["cas"][i] if i < len(old["cas"]) else None
                if o is None:
                    items.append(f"{tag}new casualty")
                    continue
                for k in ("priority", "mobility"):
                    if c[k] != o[k]:
                        items.append(f"{tag}{k}: {o[k]} → {c[k]}")
                if c["posture_key"] != o["posture_key"]:
                    items.append(f"{tag}posture: {o['posture']} → {c['posture']}")
                elif c["posture"] != o["posture"] and "%" not in c["posture"]:
                    items.append(f"{tag}posture confirmed: {c['posture']}")
                for k in ("conscious", "breathing", "massive bleeding"):
                    if c[k] != o[k]:
                        items.append(f"{tag}{k}: {yn[o[k]]} → {yn[c[k]]}")
                for x in c["injuries"]:
                    if x not in o["injuries"]:
                        items.append(f"{tag}new injury: {x}")
                for x in c["tourniquets"]:
                    if x not in o["tourniquets"]:
                        items.append(f"{tag}tourniquet: {x}")
            if new["team"] != old["team"] and new["team"] is not None:
                items.append(f"send: {old['team'] if old['team'] is not None else '–'} → {new['team']} people")
            if new["radius"] != old["radius"] and new["radius"] is not None:
                items.append(f"position: ±{old['radius'] if old['radius'] is not None else '–'} → ±{new['radius']} m"
                             + (f" · {new['areas']} areas" if new["areas"] > 1 else ""))
        what = what if via == "audio" else (what[:60] + ("…" if len(what) > 60 else ""))
        rep.setdefault("changes", []).append({"ms": now_ms(), "via": via, "what": what,
                                              "items": items or ["no change"]})
        rep["changes"] = rep["changes"][-12:]

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
        from .condition import worst_left

        def key(r):
            d = self.distance_to_ccp(r)
            w = worst_left(r)
            return (r["summary"]["rank"], w if w is not None else 9e9, r["summary"]["tq_ms"] or 9e15,
                    d if d is not None else 9e9)
        return [r["id"] for r in sorted(live, key=key)]

    def public(self):
        """Everything the coordinator page needs, JSON-ready."""
        from .body import twin
        out = []
        zs = danger.zones(self.reports.values(), now_ms())
        for r in self.reports.values():
            mob = [c["mobility"] for c in twin(r)["casualties"]] if r["casualties"] else []
            out.append({
                "id": r["id"], "callsign": r["callsign"], "lang": r["lang"],
                "created_ms": r["created_ms"], "updated_ms": r["updated_ms"],
                "casualties": [{**c, "priority": casualty.priority(c), "mist": casualty.mist(c),
                                "mobility": mob[i] if i < len(mob) else None,
                                "condition": condition.assess(c, r, i)}
                               for i, c in enumerate(r["casualties"])],
                "summary": r["summary"], "position": r["position"], "heat": r["heat"],
                "question": _q_public(r["question"]),
                "asked": [_q_public(q) for q in r["asked"]],
                "stress": r.get("stress"),
                "transcripts": r["transcripts"][-8:], "readback": r["readback"],
                "packet": r["packet"], "evacuated": r["evacuated"], "truth": r["truth"],
                "distance_ccp": self.distance_to_ccp(r),
                "acoustic": r.get("acoustic", []), "alerts": r.get("alerts", [])[-5:],
                "evidence": _evidence_counts(r["constraints"]),
                "changes": r.get("changes", [])[-8:],
                "dangers": danger.active(r.get("dangers", []), now_ms()),
                "danger_near": r.get("danger_near", []),
                "guide": guide.public(r.get("guide")), "at_ccp": bool(r.get("at_ccp")),
                "dispatch": guide.dispatch(r, self.ccp, zs["zones"], now_ms()),
            })
        return {"type": "state", "version": self.version, "server_ms": now_ms(),
                "reports": out, "order": self.evac_order(), "ccp": self.ccp,
                "danger": zs,
                "tq_warn_min": config.TOURNIQUET_WARN_MIN,
                "target_radius_m": config.TARGET_RADIUS_M}


def _evidence_counts(cons):
    """How many constraints of each family went into the position (for the card)."""
    fam = {"bearing": "landmarks", "visible": "landmarks", "here": "landmarks",
           "feature_visible": "landmarks", "distance": "landmarks", "left_right": "landmarks",
           "sun": "sun", "gps": "gps", "hear": "sound", "setting": "space", "reflector": "space",
           "echoes": "echoes", "ambient": "noise level", "ground": "ground", "compass": "compass",
           "last_fix": "last GPS fix", "offset": "walked from", "elevation": "aimed (tilt)",
           "angle_between": "aimed (angle)", "track": "walked (dead reckoning)"}
    out = {}
    for c in cons:
        f = fam.get(c["kind"], "other")
        out[f] = out.get(f, 0) + 1
    return out


def _q_public(q):
    if not q:
        return None
    return {"id": q.get("id"), "kind": q["kind"], "text": q.get("text"),
            "answer": q.get("answer"), "gain_bits": q.get("gain_bits"), "goal": q.get("goal"),
            "goal_text": q.get("goal_text"), "expect": q.get("expect"), "load": q.get("load"),
            "stress": q.get("stress")}


STORE = Store()
