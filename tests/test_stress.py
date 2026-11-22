"""Speaker stress from the voice and words, and how it adapts the questions."""
import numpy as np

from backend import questions as Q
from backend.stress import estimate, pitch_track, text_features, voice_features

SR = 16000


def talk(f0, swing, rate, bright, dur=8.0, noise=0.003, seed=0):
    """Voice-like test signal: harmonics with a pitch contour, syllables, words and pauses."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    st = swing * np.sin(2 * np.pi * 0.7 * t + rng.uniform(0, 6)) + 0.5 * swing * np.sin(2 * np.pi * 1.9 * t)
    ph = 2 * np.pi * np.cumsum(f0 * 2 ** (st / 12)) / SR
    src = sum((1.0 / k ** (2.2 - bright)) * np.sin(k * ph) for k in range(1, 30))
    syl = np.clip(np.sin(2 * np.pi * rate / 2 * t), 0, None) ** 0.8
    words = (np.sin(2 * np.pi * t / 2.9) > -0.2).astype(float)
    y = src * syl * words
    return (0.2 * y / np.abs(y).max() + noise * rng.standard_normal(t.size)).astype(np.float32)


def test_pitch_tracker():
    t = np.arange(SR) / SR
    f0 = pitch_track((0.3 * np.sin(2 * np.pi * 150 * t) + 0.1 * np.sin(2 * np.pi * 300 * t)).astype(np.float32))
    assert abs(np.median(f0[f0 > 0]) - 150) < 4


def test_stressed_voice_scores_higher():
    calm = estimate(voice_features(talk(115, 1.0, 4.0, 0.0)), text_features("one casualty, left leg"))
    high_voice_calm = estimate(voice_features(talk(210, 1.0, 4.2, 0.1)), text_features("one casualty, left leg"))
    stressed = estimate(voice_features(talk(185, 3.5, 6.5, 0.8)), text_features("one casualty, left leg"))
    assert calm["level"] == "low" and high_voice_calm["level"] == "low"
    assert stressed["score"] > calm["score"] + 0.2


def test_loud_background_trusts_the_voice_less():
    quiet = voice_features(talk(185, 3.5, 6.5, 0.8, noise=0.001))
    noisy = voice_features(talk(185, 3.5, 6.5, 0.8, noise=0.02))
    wq = [c["w"] for c in estimate(quiet)["cues"] if c["cue"] == "pitch raised"][0]
    wn = [c["w"] for c in estimate(noisy)["cues"] if c["cue"] == "pitch raised"][0]
    assert wn < wq


def test_urgent_words():
    assert estimate(None, text_features("Hurry! He's dying, help help, please!"))["level"] == "high"
    assert estimate(None, text_features("One casualty, left leg wound, tourniquet on"))["level"] == "low"


def test_high_stress_asks_fewer_simpler_shorter():
    from backend.state import Store
    s = Store()
    r = s.new_report()
    r = s.process(r["id"], "Hurry! Hurry! He is dying, please! I see the castle keep at my 11 o'clock "
                           "and a church at my 2 o'clock")
    assert r["stress"]["level"] == "high"
    q = r["question"]
    assert q is None or (Q.load_of(q) <= 2.0 and len(q["text"].split()) <= 7)
    assert Q.STRESS_POLICY["high"]["max_load"] < Q.STRESS_POLICY["low"]["max_load"]


def test_questions_carry_a_goal():
    from backend.state import Store
    s = Store()
    r = s.new_report()
    r = s.process(r["id"], "I see the castle keep at my 11 o'clock and a church at my 2 o'clock")
    q = r["question"]
    assert q and q.get("goal_text", "").startswith("Goal:") and q["expect"]["after_m"] <= q["expect"]["now_m"]


def test_goal_tells_two_areas_apart():
    """When the answers move the mass between two areas, the goal says which answer points where."""
    from backend.localise import get_engine
    eng = get_engine()
    a, b = 1000, eng.N - 1000
    rows = np.array([a, b])
    la, lo_a = eng.db.to_latlon(eng.X[a], eng.Y[a])
    lb, lo_b = eng.db.to_latlon(eng.X[b], eng.Y[b])
    result = {"blobs": [{"lat": la, "lon": lo_a, "mass": 0.55, "r2": 50.0},
                        {"lat": lb, "lon": lo_b, "mass": 0.45, "r2": 50.0}]}
    outs = [(0.55, np.array([0.95, 0.05])), (0.45, np.array([0.05, 0.95]))]
    g = Q._goal({"kind": "visible_type", "type": "church"}, outs, rows, result, eng, 900.0, 100.0)
    assert g["goal"] == "split" and "area A" in g["goal_text"] and "yes → A" in g["goal_text"] and "no → B" in g["goal_text"]
