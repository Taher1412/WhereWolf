"""Fake observer: stand at (lat, lon) facing `heading`, describe what you see.

Used by tests (does localise.py find us again?) and by the coordinator's
"simulate report here" button, to rehearse without walking outside.
"""
import math
import random

import numpy as np

from . import config
from .landmarks import get_db, spoken
from .sun import sun_position

# Things a soldier would actually call out, best first.
CALLOUT_TYPES = ["keep", "castle", "water_tower", "church", "tower", "station", "townhall",
                 "hospital", "stadium"]


def clock_of(rel_deg):
    """Relative bearing (deg, 0 = ahead) -> clock hour 1..12."""
    k = int(round((rel_deg % 360) / 30.0)) % 12
    return 12 if k == 0 else k


def observe(lat, lon, heading, n=3, noise_deg=10.0, with_sun=True, when=None, seed=None):
    """Return (constraints, sentence) for an observer at a known spot."""
    rng = random.Random(seed)
    db = get_db()
    x, y = db.to_xy(lat, lon)
    picks, used_types = [], set()
    for t in CALLOUT_TYPES:
        idx = np.where(db.types == t)[0]
        if len(idx) == 0:
            continue
        d = np.hypot(db.x[idx] - x, db.y[idx] - y)
        R = config.VIS_RADIUS.get(t, config.VIS_RADIUS_DEFAULT)
        ok = idx[d <= R]
        if len(ok) == 0 or t in used_types:
            continue
        j = ok[np.argmin(np.hypot(db.x[ok] - x, db.y[ok] - y))]
        if t == "castle" and "keep" in used_types:
            continue  # same thing, don't say it twice
        bearing = math.degrees(math.atan2(db.x[j] - x, db.y[j] - y)) % 360
        # Avoid two callouts in the same direction.
        if any(abs(((bearing - p["bearing"]) + 180) % 360 - 180) < 25 for p in picks):
            continue
        picks.append({"type": t, "i": int(j), "bearing": bearing,
                      "dist": float(np.hypot(db.x[j] - x, db.y[j] - y))})
        used_types.add(t)
        if len(picks) >= n:
            break

    constraints, parts = [], []
    for p in picks:
        rel = p["bearing"] - heading + rng.gauss(0, noise_deg)
        k = clock_of(rel)
        constraints.append({"kind": "bearing", "type": p["type"], "name": None,
                            "beta": k * 30.0 % 360, "sigma": config.SIGMA_CLOCK})
        art = "the" if p["type"] in ("keep", "castle") else "a"
        parts.append(f"{art} {spoken(p['type'])} at my {k} o'clock")

    sentence = "I see " + ", ".join(parts) if parts else "I can't see any clear landmark"
    if with_sun:
        az, elev = sun_position(lat, lon, when)
        if elev > 2:
            k = clock_of(az - heading + rng.gauss(0, noise_deg))
            constraints.append({"kind": "sun", "clock": k})
            sentence += f", sun at my {k} o'clock"
    return constraints, sentence + "."


def truthful_answer(q, lat, lon, heading, when=None):
    """What a speaker standing at the true spot would say to question q (text)."""
    from .localise import get_engine
    from .questions import answer_probs
    eng = get_engine()
    db = get_db()
    if q["kind"] == "describe":
        return observe(lat, lon, heading, n=3, with_sun=False, when=when)[1]
    if q["kind"] in ("setting3", "room_size", "hear_type"):
        return _space_answer(q, lat, lon)
    x, y = db.to_xy(lat, lon)
    cell = np.array([int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))])
    h = int(round(heading / 5.0)) % eng.H
    probs = answer_probs(q, eng, cell, when)
    if not probs:
        return "I don't know"
    vals = [float(np.broadcast_to(p, (1, eng.H))[0, h]) for p in probs]
    a = int(np.argmax(vals))
    k = q["kind"]
    if k in ("visible_type", "visible_feature"):
        return "Yes, I can see it" if a == 0 else "No, I can't see it"
    if k == "left_right":
        return "On my right" if a == 0 else "On my left"
    if k == "sun":
        return f"Sun at my {a + 1} o'clock"
    if k == "dist_band":
        # True distance to the landmark they meant, misjudged by ~30 % like a real person.
        d = float(np.broadcast_to(eng.ref_distance(q["ref"], cell), (1, eng.H))[0, h])
        est = d * math.exp(random.gauss(0, 0.3))
        return f"About {int(round(est / 50.0) * 50) or 50} metres"
    return "I don't know"


# ------------------------------------------------------------ space and sound
def true_setting(lat, lon):
    """The setting at the exact spot, from the 5 m building raster."""
    from .soundscape import get_soundscape
    a = get_soundscape().at(lat, lon)
    if a["inside"]:
        P = a["P_setting"]
        return ("indoor_large" if P["indoor_large"] > 0.3 else "indoor_small"), a
    if a["facade_m"] < config.ENCLOSED_FACADE_M:
        return "outdoor_enclosed", a
    if a["facade_m"] > config.OPEN_FACADE_M:
        return "outdoor_open", a
    return random.choice(["outdoor_enclosed", "outdoor_open"]), a


def _space_answer(q, lat, lon):
    from .soundscape import get_soundscape
    sc = get_soundscape()
    if not sc.ok:
        return "I don't know"
    s, a = true_setting(lat, lon)
    if q["kind"] == "setting3":
        return {"indoor_small": "Inside a building", "indoor_large": "Inside a building",
                "outdoor_enclosed": "In a street between buildings", "outdoor_open": "In the open"}[s]
    if q["kind"] == "room_size":
        return "A large hall" if s == "indoor_large" else "A small room"
    # hear_type: hearing a train depends on timing, so draw it from the model.
    p = float(sc.p_heard(q["type"], "voice")[a["cell"]])
    return "Yes, I hear it" if random.random() < p else "No, nothing"


def simulate_audio(lat, lon, rng=None):
    """A fake Listen clip (with chirp) at the true spot, drawn from our own sound
    model. It tests the matching logic, NOT the microphone or the classifier:
    real accuracy needs real recordings."""
    from .soundscape import get_soundscape
    rng = rng or random.Random()
    sc = get_soundscape()
    s, a = true_setting(lat, lon)
    # A classifier that is right ~60 % of the time, mostly confusing neighbours.
    near = {"indoor_small": "indoor_large", "indoor_large": "indoor_small",
            "outdoor_enclosed": "outdoor_open", "outdoor_open": "outdoor_enclosed"}
    p = {k: 0.08 for k in config.SETTINGS}
    p[s], p[near[s]] = 0.6, 0.24
    probe = {"ok": True, "wall_reliable": False, "nearest_wall_m": None}
    if not a["inside"] and a["facade_m"] <= 25 and rng.random() < 0.7:
        probe.update(wall_reliable=True, nearest_wall_m=round(max(a["facade_m"], 1.5) * math.exp(rng.gauss(0, 0.15)), 1))
    events = []
    for g in ("rail", "traffic", "bells", "machinery", "nature"):
        if rng.random() < float(sc.p_heard(g, "audio")[a["cell"]]):
            events.append({"class": g, "score": 0.6, "labels": [["(simulated)", 0.6]]})
    from .audioviz import spectrogram, synth_clip
    from .spatial import describe, probe as run_probe
    wall = probe["nearest_wall_m"] if probe["wall_reliable"] else None
    wave, rec48, tl = synth_clip([e["class"] for e in events], wall, rng)
    pr = run_probe(rec48, config.PROBE["sr"], 0.3)        # real echo code on the fake recording
    probe["echogram"] = pr.get("echogram")
    viz = {"spec": spectrogram(wave), "chirp": [0.3, 0.3 + config.PROBE["dur"]],
           "timeline": tl, "simulated": True}
    return {"_viz": viz, "kind": "simulated", "audio_quality": "good", "quality_notes": ["SIMULATED from map truth"],
            "events": events, "context": [], "alerts": [], "features": {}, "level_dbfs": -30,
            "speech_fraction": 0.0, "source": "simulated",
            "space": {"p": p, "clues": [f"simulated: true setting {s}, facade {a['facade_m']:.0f} m"],
                      "strength": 0.3, **describe(p), "probe": probe,
                      "_p_for_grid": p, "_strength_for_grid": 0.3}}
