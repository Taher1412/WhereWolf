"""Bring a walking casualty to the CCP, and plan the medic's route to one who can't walk.

Once a casualty who CAN walk is located (within GUIDE_START_R), Near:
  1. plans a walking route to the CCP away from the danger zones (route.py);
  2. speaks it as short legs, with landmarks instead of street signs:
     "Walk with the keep at your 2 o'clock, about 150 metres. The church should be on your left.";
  3. moves the casualty's pin along the route with no GPS (dead reckoning):
       - distance walked = steps counted by the phone x STEP_M, else walking speed x time;
       - the uncertainty grows with the distance walked (DRIFT_STEPS / DRIFT_TIME);
       - "reached" (button or voice) puts the pin back at the end of the leg and shrinks it;
       - a new spoken landmark report re-locates the walker around the expected spot ("track" prior);
  4. reroutes when a new danger zone appears on the way.
A casualty who can't walk (stretcher, trapped, unknown) gets a medic route CCP -> casualty instead.
Rehearsal (simulated soldier): the true walker follows the route a bit slower than assumed and
confirms each leg, SIM_TIME_SCALE times faster than real time.
"""
import math
import re
import time

import numpy as np

from . import config
from .route import _wrap, get_router, point_at

SIM_TIME_SCALE = 5.0     # rehearsal only: simulated walkers move 5x faster than real time
SIM_TRUE_SPEED = 0.85    # rehearsal: the real walker is 15 % slower than the speed we assume
LEAD_IN_M = 80.0         # rehearsal: the walker reaches the route line within this distance
ARRIVE_M = 15.0          # "you should be there" this close to the end of the route
MIN_R = 20.0             # never claim better than this while walking
CLOCK_FR = "heures"

COMMANDS = [   # voice commands while guided (checked before the normal report parser)
    ("arrived", r"\b(arrived|i'?m at the ccp|at the ccp|we'?re here|arriv[ée]e?s?|au poste|on y est)\b"),
    ("lost", r"\b(lost|i'?m lost|don'?t know where|perdu|perdus|je ne sais plus)\b"),
    ("repeat", r"\b(repeat|say again|again|r[ée]p[èe]te[sz]?|redis)\b"),
    ("stop", r"\b(stop guid\w*|cancel|arr[êe]te[sz]? le guidage|annule[rz]?)\b"),
    ("reached", r"\b(next|reached|done|ok next|got there|i'?m there|suivant|j'?y suis|c'?est fait|atteint)\b"),
]


def command(text):
    t = text.lower().strip()
    if len(t.split()) > 8:        # a long sentence is a report, not a command
        return None
    for name, pat in COMMANDS:
        if re.search(pat, t):
            return name
    return None


# ---------------------------------------------------------------- who goes where
def mobility(rep):
    from .readback import _mobility
    return _mobility(rep)


def can_guide(rep, ccp):
    """A walking casualty, located well enough, not at the CCP yet."""
    pos = rep.get("position") or {}
    if rep.get("guide") or rep.get("evacuated") or rep.get("at_ccp") or pos.get("lat") is None:
        return False
    if pos.get("state") == "ambiguous" or (pos.get("radius_m") or 1e9) > config.GUIDE_START_R:
        return False
    if mobility(rep) not in config.WALK_SPEED:
        return False
    return _dist(pos, ccp) > 50


def _dist(a, b):
    kx = 111320 * math.cos(math.radians(a["lat"]))
    return math.hypot((a["lon"] - b["lon"]) * kx, (a["lat"] - b["lat"]) * 110540)


# ---------------------------------------------------------------- start
def start(rep, ccp, zones, now_ms, force=False):
    """Plan the route and the first instruction. Returns the guide state, or None."""
    R = get_router()
    pos = rep.get("position") or {}
    if not R.ok or pos.get("lat") is None:
        return None
    r = R.route((pos["lat"], pos["lon"]), (ccp["lat"], ccp["lon"]), zones, now_ms)
    if r is None:
        return None
    mob = mobility(rep) or "walks"
    speed = config.WALK_SPEED.get(mob, config.WALK_SPEED["assisted"])
    g = {"state": "active", "started_ms": now_ms, "speed": speed, "mobility": mob, "forced": force,
         "route": r, "legs": R.legs(r), "s": 0.0, "s_anchor": 0.0, "anchor_ms": now_ms,
         "r_anchor": max(MIN_R, float(pos.get("radius_m") or 50)), "mode": "time",
         "steps": None, "steps_anchor": None, "leg": 0, "trail": [[pos["lat"], pos["lon"]]],
         "say_v": 1, "reroutes": 0, "zsig": _zsig(zones), "events": [], "arrive_said": False,
         "start": {k: pos.get(k) for k in ("lat", "lon", "radius_m")}}
    pin_dangers(rep)                       # threats stay where they were reported
    if rep.get("truth"):                   # rehearsal: remember how far the truth is from the estimate
        x0, y0 = R.db.to_xy(pos["lat"], pos["lon"])
        xt, yt = R.db.to_xy(rep["truth"]["lat"], rep["truth"]["lon"])
        g["sim"] = {"dx": float(xt - x0), "dy": float(yt - y0), "leg_done": -1}
    rep["guide"] = g
    g["instruction"] = header(rep, g) + " " + leg_text(rep, g, 0)
    _event(g, now_ms, "start", f"route {r['length_m']} m" + (f", +{r['detour_m']} m to avoid danger" if r.get("detour_m") else ""))
    return g


def pin_dangers(rep):
    """Danger events keep the position where they were reported, even if the unit moves."""
    pos = rep.get("position") or {}
    if pos.get("lat") is None:
        return
    snap = {k: pos.get(k) for k in ("lat", "lon", "radius_m", "heading_deg", "heading_conf")}
    for d in rep.get("dangers", []):
        d.setdefault("at", dict(snap))


def track_prior(g):
    """A walker re-reporting landmarks is near where the dead reckoning puts them."""
    e = g.get("est") or g["start"]
    return {"kind": "track", "lat": e["lat"], "lon": e["lon"], "acc": max(40.0, float(e.get("radius_m") or 80))}


# ---------------------------------------------------------------- moving
def tick(rep, ccp, zones, now_ms):
    """Move the estimate along the route. True when something the map shows changed."""
    g = rep.get("guide")
    if not g or g["state"] != "active":
        return False
    scale = SIM_TIME_SCALE if rep.get("truth") else 1.0
    if rep.get("truth") and "sim" in g:       # rehearsal: move the true walker first (it may confirm a leg)
        _sim_walker(rep, g, max(0.0, (now_ms - g["anchor_ms"]) / 1000.0) * scale, ccp, zones, now_ms)
        if g["state"] != "active":
            return True
    dt = max(0.0, (now_ms - g["anchor_ms"]) / 1000.0) * scale
    if g["mode"] == "steps" and g["steps"] is not None:
        walked = config.STEP_M * (g["steps"] - g["steps_anchor"])
        drift = config.DRIFT_STEPS
    else:
        walked = g["speed"] * dt
        drift = config.DRIFT_TIME
    L = g["route"]["length_m"]
    radius = g["r_anchor"] + drift * walked
    if g["mode"] == "steps":
        g["s"] = min(L, g["s_anchor"] + walked)
    else:
        # Clock only: we don't know they reached the turn, so the pin waits at the end of
        # the leg (its circle keeps growing) until they say "reached" / tap the button.
        end = g["legs"][g["leg"]]["s1"]
        g["s"] = min(L, end, g["s_anchor"] + walked)
        late = g["s_anchor"] + walked - end
        if late > 30 and g.get("prompted") != g["leg"] and g["leg"] < len(g["legs"]) - 1:
            g["prompted"] = g["leg"]
            say(g, g["instruction"] + (" Dites « suivant » au prochain virage." if rep.get("lang") == "fr"
                                       else " Say 'next' when you reach the turn."))

    lat, lon, _ = point_at(g["route"], g["s"])
    g["est"] = {"lat": lat, "lon": lon, "radius_m": radius}
    if not g["trail"] or _dist({"lat": lat, "lon": lon}, {"lat": g["trail"][-1][0], "lon": g["trail"][-1][1]}) > 10:
        g["trail"].append([lat, lon])
    _set_position(rep, g)

    # Next leg? (step counter only; with the clock alone we wait for "reached")
    k = _leg_at(g, g["s"])
    if g["mode"] == "steps" and k != g["leg"]:
        g["leg"] = k
        say(g, leg_text(rep, g, k))
    if g["s"] >= L - ARRIVE_M and not g["arrive_said"]:
        g["arrive_said"] = True
        say(g, "Le poste de secours devrait être juste devant vous. Dites « arrivé » quand vous voyez l'équipe."
            if rep.get("lang") == "fr" else "The CCP should be just ahead. Say 'arrived' when you see the medics.")

    # New danger on the way: look for a better route from here.
    sig = _zsig(zones)
    if sig != g["zsig"]:
        g["zsig"] = sig
        reroute(rep, ccp, zones, now_ms, why="danger")
    return True


def _sim_walker(rep, g, dt, ccp, zones, now_ms):
    """Rehearsal: the true walker follows the route, slower than assumed, and confirms each leg."""
    R = get_router()
    s_true = min(g["route"]["length_m"], g["sim"].get("s0", 0.0) + g["speed"] * SIM_TRUE_SPEED * dt)
    g["sim"]["s"] = s_true
    lat, lon, _ = point_at(g["route"], s_true)
    fade = max(0.0, 1 - s_true / LEAD_IN_M)            # the walker joins the route line
    x, y = R.db.to_xy(lat, lon)
    tl, tn = R.db.to_latlon(x + g["sim"]["dx"] * fade, y + g["sim"]["dy"] * fade)
    rep["truth"].update(lat=float(tl), lon=float(tn))
    end = s_true >= g["route"]["length_m"] - 1
    k = _leg_at(g, s_true)
    if k > g["sim"]["leg_done"] + 1 or (end and g["sim"]["leg_done"] < len(g["legs"]) - 1):
        done = len(g["legs"]) - 1 if end else k - 1
        g["sim"]["leg_done"] = done
        confirm(rep, g, done, now_ms, simulated=True)
    if end:
        apply(rep, "arrived", ccp, zones, now_ms)


def confirm(rep, g, leg, now_ms, simulated=False):
    """The walker says they reached the end of leg `leg`: the pin goes back there, uncertainty shrinks."""
    lg = g["legs"][min(leg, len(g["legs"]) - 1)]
    g["s"] = g["s_anchor"] = lg["s1"]
    g["anchor_ms"] = now_ms
    g["r_anchor"] = max(MIN_R, 0.4 * float((g.get("est") or {}).get("radius_m") or g["r_anchor"]))
    if g["steps"] is not None:
        g["steps_anchor"] = g["steps"]
    if "sim" in g and simulated:
        g["sim"]["s0"] = lg["s1"]
    nxt = min(leg + 1, len(g["legs"]) - 1)
    g["leg"] = nxt
    say(g, leg_text(rep, g, nxt) if leg + 1 < len(g["legs"]) else (
        "Vous devriez voir le poste de secours. Dites « arrivé » en arrivant." if rep.get("lang") == "fr"
        else "You should see the CCP now. Say 'arrived' when you get there."))
    _event(g, now_ms, "reached", f"leg {leg + 1}" + (" (simulated)" if simulated else ""))


def apply(rep, cmd, ccp, zones, now_ms, steps=None):
    """A command from the field (button or voice). Returns the text to say."""
    g = rep.get("guide")
    if cmd == "start":
        rep.pop("at_ccp", None)
        rep["guide"] = None
        g = start(rep, ccp, zones, now_ms, force=True)
        return g["instruction"] if g else _no_route(rep)
    if not g:
        return None
    fr = rep.get("lang") == "fr"
    if cmd == "steps" and steps is not None:
        if g["steps"] is None or steps < (g["steps"] or 0):   # first count, or the phone restarted it
            g["steps_anchor"] = steps - (g["s"] - g["s_anchor"]) / config.STEP_M
            g["mode"] = "steps"
        g["steps"] = steps
        return None
    if cmd == "reached":
        tick(rep, ccp, zones, now_ms)
        lg = g["legs"][g["leg"]]
        # Step counter just moved on to this leg? Then "reached" means the previous one.
        done = g["leg"] - 1 if (g["mode"] == "steps" and g["leg"] > 0
                                and g["s"] - lg["s0"] < 0.3 * lg["length_m"]) else g["leg"]
        confirm(rep, g, done, now_ms)
        tick(rep, ccp, zones, now_ms)
        return g["instruction"]
    if cmd == "repeat":
        return g["instruction"]
    if cmd == "lost":
        g["state"] = "lost"
        g["say_v"] += 1
        _event(g, now_ms, "lost", "")
        g["instruction"] = ("Arrêtez-vous. Dites-moi ce que vous voyez, avec les heures : par exemple « le donjon à mes 2 heures »."
                            if fr else "Stop where you are. Tell me what you see, with clock directions: for example 'the keep at my 2 o'clock'.")
        return g["instruction"]
    if cmd == "arrived":
        g["state"] = "arrived"
        g["arrived_ms"] = now_ms
        rep["at_ccp"] = True
        g["est"] = {"lat": ccp["lat"], "lon": ccp["lon"], "radius_m": 10.0}
        g["trail"].append([ccp["lat"], ccp["lon"]])
        _set_position(rep, g)
        g["say_v"] += 1
        _event(g, now_ms, "arrived", "")
        g["instruction"] = "Bien reçu, vous êtes au poste de secours." if fr else "Copy, you are at the CCP. The medics will take over."
        return g["instruction"]
    if cmd == "stop":
        g["state"] = "stopped"
        g["say_v"] += 1
        _event(g, now_ms, "stopped", "")
        g["instruction"] = "Guidage arrêté." if fr else "Guidance stopped."
        return g["instruction"]
    return None


def reanchor(rep, ccp, zones, now_ms):
    """New landmark fix while walking (or after 'I'm lost'): restart the route from there."""
    g = rep["guide"]
    pos = rep.get("position") or {}
    if pos.get("lat") is None:
        return
    g["state"] = "active"
    g["start"] = {k: pos.get(k) for k in ("lat", "lon", "radius_m")}
    g["r_anchor"] = max(MIN_R, float(pos.get("radius_m") or 50))
    g["trail"].append([pos["lat"], pos["lon"]])
    reroute(rep, ccp, zones, now_ms, why="fix", force=True)


def reroute(rep, ccp, zones, now_ms, why="danger", force=False):
    g = rep["guide"]
    R = get_router()
    e = g.get("est") if why != "fix" else None
    here = e or rep.get("position")
    new = R.route((here["lat"], here["lon"]), (ccp["lat"], ccp["lon"]), zones, now_ms)
    if new is None:
        return False
    fr = rep.get("lang") == "fr"
    if not force:
        # Is the rest of the current route now in danger, and is the new one better?
        left = _remaining_exposure(g, zones, now_ms)
        if left < 20 or sum(new["exposure"].values()) >= left:
            if left >= 20:
                types = sorted(_remaining_types(g, zones, now_ms))
                from .danger import spoken
                g["instruction"] = ((f"Attention : {spoken(types, 'fr')} signalé sur votre chemin, pas d'autre route plus sûre. "
                                     if fr else f"Warning: {spoken(types)} reported on your way, no safer route. ")
                                    + leg_text(rep, g, g["leg"]))
                g["say_v"] += 1
                _event(g, now_ms, "warning", ", ".join(types))
            return False
    g["prev_bearing"] = point_at(g["route"], g["s"])[2] if why != "fix" else None
    g["route"], g["legs"] = new, R.legs(new)
    g["s"] = g["s_anchor"] = 0.0
    g["anchor_ms"] = now_ms
    if e:
        g["r_anchor"] = max(MIN_R, float(e["radius_m"]))
    if g["steps"] is not None:
        g["steps_anchor"] = g["steps"]
    if "sim" in g:
        g["sim"].update(s0=0.0, leg_done=-1, dx=0.0, dy=0.0)
        if why == "fix" and rep.get("truth"):
            x0, y0 = R.db.to_xy(here["lat"], here["lon"])
            xt, yt = R.db.to_xy(rep["truth"]["lat"], rep["truth"]["lon"])
            g["sim"].update(dx=float(xt - x0), dy=float(yt - y0))
    g["leg"] = 0
    g["reroutes"] += 1
    g["arrive_said"] = False
    if why == "fix":
        lead = "Position mise à jour. " if fr else "Position updated. "
    else:
        lead = "Nouveau danger signalé sur votre chemin. Nouvelle route. " if fr else "New danger reported on your way. New route. "
    g["instruction"] = lead + header(rep, g, short=True) + " " + leg_text(rep, g, 0)
    g["say_v"] += 1
    _event(g, now_ms, "reroute", why + f": {new['length_m']} m")
    return True


def _remaining_types(g, zones, now_ms):
    R = get_router()
    _, inside = R.edge_risk(zones, now_ms)
    pts = _remaining_points(g)
    if not inside or pts is None:
        return set()
    _, ei = R.etree.query(pts)
    return {t for t, m in inside.items() if (m[ei] >= 0.5).any()}


def _remaining_exposure(g, zones, now_ms):
    R = get_router()
    _, inside = R.edge_risk(zones, now_ms)
    pts = _remaining_points(g)
    if not inside or pts is None:
        return 0.0
    _, ei = R.etree.query(pts)
    seg = np.r_[np.hypot(*np.diff(pts, axis=0).T), 0]
    return float(sum(seg[m[ei] >= 0.5].sum() for m in inside.values()))


def _remaining_points(g):
    r = g["route"]
    cum = np.array(r["cum"])
    i = int(np.searchsorted(cum, g["s"]))
    if i >= len(cum) - 1:
        return None
    return np.c_[r["x"][i:], r["y"][i:]]


def _set_position(rep, g):
    """The map pin follows the walker: one round area of the dead-reckoning radius."""
    e = g["est"]
    rad = float(e["radius_m"])
    rep["position"] = {"lat": e["lat"], "lon": e["lon"], "radius_m": rad, "main_mass": 1.0,
                       "blobs": [{"lat": e["lat"], "lon": e["lon"], "mass": 1.0, "sx": rad / 2, "sy": rad / 2,
                                  "angle": 0.0, "r80": rad, "peak_lat": e["lat"], "peak_lon": e["lon"]}],
                       "hyps": [], "heading_deg": point_at(g["route"], g["s"])[2],
                       "heading_conf": 6.0,        # walking: their 12 o'clock is the way they walk
                       "state": "confirmed" if rad <= config.TARGET_RADIUS_M else "rough", "source": "guided"}
    rep["heat"] = None


def say(g, text):
    """New instruction for the phone to speak (only when it really changed)."""
    if text and text != g.get("instruction"):
        g["instruction"] = text
        g["say_v"] += 1


def _leg_at(g, s):
    for k, lg in enumerate(g["legs"]):
        if s < lg["s1"] - 0.5:
            return k
    return len(g["legs"]) - 1


def _zsig(zones):
    return tuple(sorted((z["id"], round(z["radius_m"]), z.get("placed")) for z in zones))


def _event(g, ms, kind, text):
    g["events"] = (g["events"] + [{"ms": ms, "kind": kind, "text": text}])[-20:]


def _no_route(rep):
    return ("Pas de route trouvée vers le poste de secours." if rep.get("lang") == "fr"
            else "No walking route found to the CCP.")


# ---------------------------------------------------------------- what to say
COMPASS_EN = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
COMPASS_FR = ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"]


def _clock(rel):
    k = int(round((rel % 360) / 30.0)) % 12
    return 12 if k == 0 else k


def _metres(d, fr=False):
    d = 10 * round(d / 10) if d < 100 else 50 * round(d / 50)
    return f"{max(10, d)} mètres" if fr else f"{max(10, d)} metres"


def _minutes(sec, fr=False):
    m = max(1, round(sec / 60))
    return f"{m} minute{'s' if m > 1 else ''}"


def header(rep, g, short=False):
    fr = rep.get("lang") == "fr"
    r = g["route"]
    eta = r["length_m"] / g["speed"]
    from .danger import spoken
    avoid = [t for t in r.get("avoided", {})]
    if fr:
        s = f"Guidage vers le poste de secours : {_metres(r['length_m'], True)}, environ {_minutes(eta, True)}"
        s += f", en évitant : {spoken(avoid, 'fr')}." if avoid else "."
    else:
        s = f"Guiding you to the CCP: {_metres(r['length_m'])}, about {_minutes(eta)}"
        s += f", avoiding the {spoken(avoid)} area." if avoid else "."
    if short:
        return s
    if g.get("forced") and g["r_anchor"] > config.GUIDE_START_R:   # coordinator started it early
        rr = 50 * round(g["r_anchor"] / 50)
        s += (f" Position encore approximative, à {rr} mètres près : vérifiez chaque virage, dites « perdu » si rien ne correspond."
              if fr else f" Your position is still rough, within {rr} metres: check each turn, say 'lost' if nothing matches.")
    return ("Vous pouvez marcher. " if fr else "You can walk. ") + s


def _orient(rep, bearing, fr):
    """How to face the first leg without a compass: own heading, a landmark they see, or the sun."""
    pos = rep.get("position") or {}
    if (pos.get("heading_conf") or 0) >= 5 and pos.get("source") != "guided":
        k = _clock(bearing - pos["heading_deg"])
        if k == 12:
            return "Continuez tout droit" if fr else "Keep facing the same way"
        return f"Tournez vers vos {k} {CLOCK_FR}" if fr else f"Turn to your {k} o'clock"
    R = get_router()
    for c in rep.get("constraints", []):
        if c.get("kind") != "bearing" or c.get("heard"):
            continue
        idx = R.db.candidates(c["type"], c.get("name"))
        if not len(idx):
            continue
        x0, y0 = R.db.to_xy(pos["lat"], pos["lon"])
        d = np.hypot(R.db.x[idx] - x0, R.db.y[idx] - y0)
        i = int(idx[int(np.argmin(d))])
        if d.min() > 2500:
            continue
        f = R.db.feats[i]
        brg = math.degrees(math.atan2(R.db.x[i] - x0, R.db.y[i] - y0)) % 360
        k = _clock(brg - bearing)
        what = f.get("name") or (c.get("name") or c["type"].replace("_", " "))
        return (f"Marchez avec {what} à vos {k} {CLOCK_FR}" if fr else f"Walk with the {what} at your {k} o'clock")
    try:
        from .localise import get_engine
        az, el = get_engine().sun()
        if el > 5:
            k = _clock(az - bearing)
            return f"Marchez avec le soleil à vos {k} {CLOCK_FR}" if fr else f"Walk with the sun at your {k} o'clock"
    except Exception:
        pass
    w = (COMPASS_FR if fr else COMPASS_EN)[int(((bearing + 22.5) % 360) // 45)]
    return f"Partez vers le {w}" if fr else f"Head {w}"


def _turn(t, fr):
    a = abs(t)
    side = ("à droite" if t > 0 else "à gauche") if fr else ("right" if t > 0 else "left")
    if a < 25:
        return "Continuez tout droit" if fr else "Continue straight on"
    if a < 60:
        return f"Prenez légèrement {side}" if fr else f"Bear {side}"
    if a < 150:
        return f"Tournez {side}" if fr else f"Turn {side}"
    return "Faites demi-tour" if fr else "Turn back"


def leg_text(rep, g, k):
    fr = rep.get("lang") == "fr"
    lg = g["legs"][k]
    along = (f" par {lg['name']}" if fr else f" along {lg['name']}") if lg.get("name") else ""
    if k == 0 and g.get("prev_bearing") is not None:     # rerouted while walking
        s = f"{_turn(_wrap(lg['bearing'] - g['prev_bearing']), fr)}, " + (
            f"puis environ {_metres(lg['length_m'], True)}{along}." if fr else f"then about {_metres(lg['length_m'])}{along}.")
    elif k == 0:
        s = f"{_orient(rep, lg['bearing'], fr)}, " + (f"environ {_metres(lg['length_m'], True)}{along}."
                                                       if fr else f"about {_metres(lg['length_m'])}{along}.")
    else:
        s = f"{_turn(lg['turn'], fr)}, " + (f"puis environ {_metres(lg['length_m'], True)}{along}."
                                             if fr else f"then about {_metres(lg['length_m'])}{along}.")
    cue = lg.get("cue")
    prev = g["legs"][k - 1].get("cue") if k > 0 else None
    if cue and not (prev and prev["name"] == cue["name"] and prev["side"] == cue["side"]):
        if fr:
            side = {"left": "sur votre gauche", "right": "sur votre droite", "ahead": "devant vous"}[cue["side"]]
            s += f" Repère : {cue['name']}, {side}."
        else:
            side = {"left": "on your left", "right": "on your right", "ahead": "ahead of you"}[cue["side"]]
            s += f" You should see {cue['name']} {side}."
    if k == len(g["legs"]) - 1:
        s += " Ensuite, le poste de secours." if fr else " Then you reach the CCP."
    return s


# ---------------------------------------------------------------- medic route
def dispatch(rep, ccp, zones, now_ms):
    """A casualty who can't walk: the safest route for the team going out to them."""
    pos = rep.get("position") or {}
    if rep.get("evacuated") or rep.get("at_ccp") or rep.get("guide") and rep["guide"]["state"] in ("active", "lost"):
        return None
    if pos.get("lat") is None or pos.get("state") == "ambiguous" or (pos.get("radius_m") or 1e9) > config.DISPATCH_MAX_R:
        return None
    if not rep.get("casualties") or mobility(rep) in config.WALK_SPEED:
        return None
    R = get_router()
    if not R.ok:
        return None
    r = R.route((ccp["lat"], ccp["lon"]), (pos["lat"], pos["lon"]), zones, now_ms)
    if r is None:
        return None
    return {"lat": r["lat"], "lon": r["lon"], "length_m": r["length_m"], "detour_m": r.get("detour_m", 0),
            "avoided": r.get("avoided", {}), "exposure": r["exposure"],
            "eta_out_s": round(r["length_m"] / config.MEDIC_SPEED),
            "eta_back_s": round(r["length_m"] / config.LITTER_SPEED)}


def public(g):
    """What the map and the phone need (no internal counters)."""
    if not g:
        return None
    r = g["route"]
    left = max(0.0, r["length_m"] - g["s"])
    lg = g["legs"][g["leg"]] if g["legs"] else None
    return {"state": g["state"], "instruction": g.get("instruction"), "say_v": g["say_v"],
            "leg": g["leg"] + 1, "legs": len(g["legs"]), "mode": g["mode"],
            "leg_left_m": round(max(0.0, lg["s1"] - g["s"])) if lg else None,
            "length_m": r["length_m"], "done_m": round(g["s"]), "left_m": round(left),
            "eta_s": round(left / g["speed"]) if g["state"] == "active" else 0,
            "detour_m": r.get("detour_m", 0), "avoided": r.get("avoided", {}), "exposure": r["exposure"],
            "lat": r["lat"], "lon": r["lon"], "trail": g["trail"][-200:],
            "est": g.get("est"), "reroutes": g["reroutes"], "events": g["events"][-6:],
            "speed": g["speed"], "started_ms": g["started_ms"]}
