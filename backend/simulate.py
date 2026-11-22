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


def observe(lat, lon, heading, n=3, noise_deg=10.0, with_sun=True, when=None, seed=None, trees=True,
            picks_out=None):
    """Return (constraints, sentence) for an observer at a known spot.
    trees: buildings, terrain and trees hide landmarks (true 3D line of sight from viewshed.py
    when available, else the canopy model) and trees often hide the sun.
    picks_out: list filled with what was called out (for simulated aiming)."""
    rng = random.Random(seed)
    db = get_db()
    x, y = db.to_xy(lat, lon)
    fo = None
    if trees:
        from .forest import get_forest
        fo = get_forest()
        fo = fo if fo.ok else None
        cell = fo.cell_of(x, y) if fo else None
    vs = None
    if trees:
        from .viewshed import get_viewshed
        vs = get_viewshed()
        vs = vs if vs.ok else None
        if vs is not None and cell is None:
            from .localise import get_engine
            e = get_engine()
            cell = int(np.argmin((e.X - x) ** 2 + (e.Y - y) ** 2))
    picks, used_types = [], set()
    for t in CALLOUT_TYPES:
        idx = np.where(db.types == t)[0]
        if len(idx) == 0:
            continue
        d = np.hypot(db.x[idx] - x, db.y[idx] - y)
        R = config.VIS_RADIUS.get(t, config.VIS_RADIUS_DEFAULT)
        ok = idx[d <= R]
        if (fo is not None or vs is not None) and len(ok):   # in sight? (reality = the 3D model)
            b = np.degrees(np.arctan2(db.x[ok] - x, db.y[ok] - y)) % 360
            T = np.ones(len(ok))
            if fo is not None:
                T = fo.transmission(np.full(len(ok), cell), b, np.hypot(db.x[ok] - x, db.y[ok] - y),
                                    tall=t in config.TALL_TYPES)
            if vs is not None:
                S = vs.sight(np.array([cell]), ok)[0]
                S = (S - 0.04) / 0.96                      # reality: no model-error floor
                T = np.where(np.isnan(S), T, S)
            ok = ok[np.array([rng.random() < tt for tt in T], bool)]
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
    if picks_out is not None:
        picks_out.extend(picks)

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
        # Under trees the low November sun is often hidden (assumed: 60 % under full cover).
        hidden = fo is not None and rng.random() < 0.6 * float(fo.wood[cell])
        if elev > 2 and not hidden:
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
    if q["kind"] == "wound_where":
        return "Left leg, bleeding"
    if q["kind"] in ("which_see", "feature_dir"):     # what is truly in sight (3D line of sight)
        from .localise import get_engine
        eng = get_engine()
        x, y = get_db().to_xy(lat, lon)
        cell = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
        if q["kind"] == "which_see":
            seen = [lab for i, lab in zip(q["opts"], q["labels"]) if eng.see_feature(i)[cell] >= 0.5]
            return ("I can see " + " and ".join(seen)) if seen else "None of them"
        i = q["feature"]
        if eng.see_feature(i)[cell] < 0.5:
            return "I can't see it"
        b = math.degrees(math.atan2(get_db().x[i] - x, get_db().y[i] - y)) % 360
        return f"At my {clock_of(b - heading)} o'clock"
    if q["kind"] == "ground":
        from .forest import get_forest
        fo = get_forest()
        x, y = get_db().to_xy(lat, lon)
        a = fo.truth(fo.cell_of(x, y), q["type"])
        return {"trees": "Under trees", "open": "In the open", "paved": "Tarmac",
                "unpaved": "A dirt path", "none": "No path", "yes": "Yes, I can see water",
                "no": "No water"}[a]
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
    if k == "hear_dir":
        return "No traffic" if a == 12 else f"Traffic at my {a + 1} o'clock"
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
    """A fake voice report + chirp at the true spot. The RECORDING is synthetic but
    built from the real place (echoes from the real walls around, road noise at the
    level the noise map predicts there), and it is measured by the SAME code as a
    real clip (spatial.probe for the echoes, surround.measure_ambient for the level).
    The classifier part (kind of space, sound events) is still drawn from our own model.
    It tests the matching, not the microphone: real accuracy needs real recordings."""
    from .audioviz import spectrogram
    from .soundscape import get_soundscape
    from .spatial import describe, probe as run_probe, setting_probs
    from .surround import get_places, measure_ambient
    rng = rng or random.Random()
    sc, pl, db = get_soundscape(), get_places(), get_db()
    s, a = true_setting(lat, lon)
    x, y = db.to_xy(lat, lon)
    here = pl.at_point(x - pl.x0, y - pl.y0)
    level = (here["l_in"] if here["inside"] else here["l_out"]) + rng.gauss(0, 3)
    echoes = []
    if not here["inside"]:
        for e in here["echoes"]:
            if e["m"] <= 25 and not (e["m"] > 8 and rng.random() < 0.25):    # far walls: sometimes missed
                echoes.append((e["m"], 0.22 * min(1.0, 4.0 / e["m"]) * (0.6 + 0.1 * min(e["width"], 5))))
        for e in here["echoes2"]:
            if rng.random() < 0.5:
                echoes.append((e["m"], 0.06))
        if rng.random() < 0.3:                                             # a parked car, a tree
            echoes.append((rng.uniform(2.5, 15), 0.08))
    wave, rec48, tl, ping_at = synth_report(level, echoes, here["inside"], rng)
    pr = run_probe(rec48, config.PROBE["sr"], ping_at)          # real echo detection
    cut = (int((ping_at - 0.05) * 16000), int((ping_at + config.PROBE["dur"] + 0.6) * 16000))
    amb = measure_ambient(np.r_[wave[:cut[0]], wave[cut[1]:]], 16000, True)   # real level measurement
    # A classifier that is right ~60 % of the time on the kind of space, mostly confusing neighbours.
    near = {"indoor_small": "indoor_large", "indoor_large": "indoor_small",
            "outdoor_enclosed": "outdoor_open", "outdoor_open": "outdoor_enclosed"}
    scene_p = {k: 0.08 for k in config.SETTINGS}
    scene_p[s], scene_p[near[s]] = 0.6, 0.24
    p, clues, strength = setting_probs(None, None, pr)
    p = {k: p[k] * scene_p[k] for k in p}
    tot = sum(p.values())
    p = {k: round(v / tot, 3) for k, v in p.items()}
    events = []
    for g in ("rail", "traffic", "bells", "machinery", "nature"):
        if rng.random() < float(sc.p_heard(g, "audio")[a["cell"]]):
            events.append({"class": g, "score": 0.6, "labels": [["(simulated)", 0.6]], "under_speech": True})
    viz = {"spec": spectrogram(wave), "chirp": [round(ping_at, 2), round(ping_at + config.PROBE["dur"], 2)],
           "timeline": tl, "simulated": True}
    truth = f"simulated at the true spot: {s.replace('_', ' ')}, {len(echoes)} echoes, {level:.0f} dB(A)"
    return {"_viz": viz, "kind": "voice", "audio_quality": "voice", "quality_notes": ["SIMULATED from map truth"],
            "events": events, "context": [], "alerts": [], "features": {}, "level_dbfs": -30,
            "speech_fraction": 0.5, "source": "simulated", "ambient": amb,
            "space": {"p": p, "clues": [truth] + clues, "strength": strength, **describe(p), "probe": pr,
                      "_p_for_grid": p, "_strength_for_grid": max(strength, 0.1)}}


def synth_report(level_dba, echoes, inside, rng, dur=6.0, ping_at=3.4):
    """Synthetic phone clip: 3 s of voice-like sound at the reference level, road noise
    at `level_dba`, then the chirp with its echoes (or a ringing room indoors).
    Returns (wave 16 kHz, recording 48 kHz, timeline, ping_at)."""
    from scipy import signal
    from .audioviz import timeline
    from .spatial import make_sweep
    from .surround import VOICE_REF_DBA, frame_levels
    sr = config.PROBE["sr"]
    nr = np.random.default_rng(rng.randrange(1 << 30))
    n = int(dur * sr)
    t = np.arange(n) / sr
    off = 96.0                                         # dB(A) <-> dBFS for this fake phone

    def at_level(x, dba, active=False):
        lv = frame_levels(x[::3], sr // 3)
        cur = np.percentile(lv[lv > lv.max() - 25], 70) if active else 10 * np.log10(np.mean(10 ** (lv / 10)))
        return x * 10 ** ((dba - off - cur) / 20)

    # Road noise: low-mid band, slow swells (cars passing).
    road = signal.sosfilt(signal.butter(2, [60, 1500], btype="band", fs=sr, output="sos"), nr.normal(0, 1, n))
    road *= 1 + 0.35 * np.sin(2 * np.pi * t / 3.1 + rng.random() * 6)
    road = at_level(road, level_dba)
    # Voice: speech-shaped noise in syllables (~4 per second), words of ~0.6 s.
    v = signal.sosfilt(signal.butter(2, [180, 3500], btype="band", fs=sr, output="sos"), nr.normal(0, 1, n))
    syll = np.clip(np.sin(2 * np.pi * 4.2 * t), 0, None) ** 0.7
    words = (np.sin(2 * np.pi * 0.8 * t + 0.4) > -0.3).astype(float)
    env = syll * words * (t > 0.3) * (t < 3.0)
    voice = at_level(v * env, VOICE_REF_DBA, active=True)
    # Chirp: direct sound + ground + echoes, or a reverberant room (DRR < 0).
    x, _ = make_sweep(sr)
    ir = np.zeros(int(0.7 * sr))
    ir[0] = 1.0
    ir[int(2 * 1.2 / config.SPEED_OF_SOUND * sr)] += 0.25
    if inside:
        k = np.arange(ir.size)
        ir += nr.normal(0, 1, ir.size) * np.exp(-6.9 * k / (0.55 * sr)) * 0.06 * (k > int(0.003 * sr))
    for d, g in echoes:
        ir[int(2 * d / config.SPEED_OF_SOUND * sr)] += g
    chirp = np.zeros(n)
    y = signal.fftconvolve(x * 0.5, ir)[: n - int(ping_at * sr)]
    chirp[int(ping_at * sr): int(ping_at * sr) + y.size] = y
    rec = road + voice + chirp + nr.normal(0, 10 ** ((30 - off) / 20), n)    # mic self-noise ~30 dB(A)
    # 48 -> 16 kHz: low-pass then keep every 3rd sample (resample_poly can trip over a
    # half-imported jax while the server is still loading the AST model).
    wave = signal.sosfiltfilt(signal.butter(8, 7000, fs=sr, output="sos"), rec)[::3].astype(np.float32)
    # Timeline at YAMNet's rhythm: speech while the voice is on, traffic underneath.
    win, hop = int(0.975 * 16000), int(0.48 * 16000)
    e16 = env[::3]
    sp = [float(e16[a:a + win].mean() > 0.15) for a in range(0, wave.size - win + 1, hop)]
    tr = [min(1.0, max(0.0, (level_dba - 50) / 25)) for _ in sp]
    tl = timeline({"speech": np.array(sp), "traffic": np.array(tr)}, [v_ < 0.5 for v_ in sp], 0.48,
                  ["speech", "traffic"])
    return wave, rec, tl, ping_at


def aim_constraints(lat, lon, picks, rng, sigma_tilt=1.5, sigma_sweep=2.0):
    """What the field page's Aim & tap would add for the landmarks called out: the tilt to
    each top (true elevation + noise) and the turn from the first to each other one."""
    from .viewshed import get_viewshed
    from .localise import get_engine
    vs, eng = get_viewshed(), get_engine()
    if not vs.ok or not picks:
        return []
    x, y = get_db().to_xy(lat, lon)
    cell = int(np.argmin((eng.X - x) ** 2 + (eng.Y - y) ** 2))
    out = []
    for k, p in enumerate(picks):
        lm = {"type": p["type"], "name": None}
        el = float(vs.elevation(np.array([cell]), np.array([p["i"]]))[0, 0])
        if np.isfinite(el):
            out.append({"kind": "elevation", **lm, "deg": el + rng.gauss(0, sigma_tilt), "sigma": config.SIGMA_TILT})
        if k > 0:
            deg = ((p["bearing"] - picks[0]["bearing"] + rng.gauss(0, sigma_sweep)) + 180) % 360 - 180
            out.append({"kind": "angle_between", "a": {"type": picks[0]["type"], "name": None}, "b": lm,
                        "deg": deg, "sigma": config.SIGMA_SWEEP})
    return out
