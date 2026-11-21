"""Compare YAMNet, AST and their ensemble on real labelled sounds, and test the
RT60 (reverberation) estimator on real sounds played through rooms.

  python -m scripts.eval_audio            (downloads ~30 MB of ESC-50 clips once)

Data: ESC-50 (Piczak 2015, CC BY-NC 3.0), 5-second clips in 50 classes.
We use the classes that map to our sound groups, plus classes that should NOT
trigger any location evidence (dog, rain, wind...).
"""
import csv
import io
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from scipy import signal

from backend import acoustic, config, spatial

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "eval" / "esc50"
URL = "https://raw.githubusercontent.com/karolpiczak/ESC-50/master"
PER_CLASS = 5

EXPECT = {   # ESC-50 class -> our group (None = must not trigger a location group)
    "train": "rail", "church_bells": "bells", "car_horn": "traffic", "engine": "traffic",
    "hand_saw": "machinery", "chirping_birds": "nature", "crickets": "nature",
    "siren": "siren", "airplane": "aircraft", "helicopter": "aircraft",
    "dog": None, "rain": None, "wind": None, "sea_waves": None, "clock_tick": None,
    "keyboard_typing": None, "door_wood_knock": None,
}
GROUPS = acoustic.GEO_GROUPS + acoustic.CONTEXT_GROUPS


def fetch():
    DIR.mkdir(parents=True, exist_ok=True)
    meta = DIR / "esc50.csv"
    if not meta.exists():
        meta.write_bytes(httpx.get(f"{URL}/meta/esc50.csv", timeout=60).content)
    rows = list(csv.DictReader(io.StringIO(meta.read_text())))
    clips = []
    for cat in EXPECT:
        for r in [r for r in rows if r["category"] == cat][:PER_CLASS]:
            p = DIR / r["filename"]
            if not p.exists():
                p.write_bytes(httpx.get(f"{URL}/audio/{r['filename']}", timeout=60).content)
            clips.append((cat, p))
    return clips


def group_scores(wave):
    """{group: (yamnet, ast)} like analyse() does, without speech removal."""
    m = acoustic._load()
    S = acoustic.scores(wave)
    A = acoustic.ast_scores(wave)
    a = acoustic._load_ast()
    out = {}
    for g in GROUPS:
        ids = m["groups"][g]
        v = np.sort(S[:, ids].max(axis=1))[::-1] if ids else np.zeros(1)
        y = float(v[:2].mean())
        s_ast = float(A[a["groups"][g]].max()) if A is not None and a["groups"][g] else 0.0
        out[g] = (y, s_ast)
    scene = {}
    for n in acoustic.SCENE_LABELS:
        li = m["labels"].index(n)
        scene[n] = (float(np.median(S[:, li])), float(A[a["idx"][n]]) if A is not None else 0.0)
    return out, scene


def combine(y, s, which):
    w = config.AST_WEIGHT
    return {"yamnet": y, "ast": s, "ensemble": (1 - w) * y + w * s}[which]


def part1(clips):
    print("\n== Part 1: sound groups on real recordings (ESC-50, %d clips) ==" % len(clips))
    res = []
    t0 = time.time()
    for cat, p in clips:
        w = acoustic.decode(p.read_bytes())
        gs, _ = group_scores(w)
        res.append((cat, gs))
    print(f"(scored in {time.time() - t0:.1f} s)")
    for which in ("yamnet", "ast", "ensemble"):
        for thr in (0.15, 0.3):
            tp = fp = fn = 0
            top_ok = n_pos = false_alarm = n_neg = 0
            for cat, gs in res:
                exp = EXPECT[cat]
                sc = {g: combine(*gs[g], which) for g in GROUPS}
                det = {g for g, v in sc.items() if v >= thr}
                if exp:
                    n_pos += 1
                    tp += exp in det
                    fn += exp not in det
                    fp += len(det - {exp})
                    top_ok += max(sc, key=sc.get) == exp
                else:
                    n_neg += 1
                    geo = det & set(acoustic.GEO_GROUPS)
                    fp += len(det)
                    false_alarm += bool(geo)
            prec = tp / max(tp + fp, 1)
            rec = tp / max(tp + fn, 1)
            f1 = 2 * prec * rec / max(prec + rec, 1e-9)
            print(f"  {which:9s} thr {thr:.2f}: recall {rec:4.0%}  precision {prec:4.0%}  F1 {f1:.2f}  "
                  f"top group right {top_ok}/{n_pos}  false location alarms on negatives {false_alarm}/{n_neg}")
    print("  per class (yamnet / ast score of the expected group):")
    for cat in EXPECT:
        exp = EXPECT[cat]
        if not exp:
            continue
        ys = [gs[exp][0] for c, gs in res if c == cat]
        a_ = [gs[exp][1] for c, gs in res if c == cat]
        print(f"    {cat:15s} -> {exp:9s} yamnet {np.mean(ys):.2f}  ast {np.mean(a_):.2f}")


def room_ir(sr, rt, seed):
    rng = np.random.default_rng(seed)
    n = int(sr * max(rt * 1.5, 0.3))
    t = np.arange(n) / sr
    h = rng.standard_normal(n) * np.exp(-6.91 * t / rt) * 0.08 * (1 - np.exp(-t / 0.015))
    h[0] = 1.0
    return h


def part2(clips):
    print("\n== Part 2: reverberation (RT60) estimated from real sounds in known rooms ==")
    srcs = [p for cat, p in clips if cat in ("dog", "door_wood_knock", "car_horn", "church_bells",
                                             "clock_tick", "keyboard_typing")]
    sr = acoustic.SR
    print(f"  {'room RT60':>9s} | {'estimate median':>15s} {'median error':>12s} {'no estimate':>11s} | "
          f"scene 'inside' share: yamnet / ast / ensemble")
    for rt in (0.0, 0.3, 0.6, 1.2, 2.4):
        est, inside = [], {"yamnet": [], "ast": [], "ensemble": []}
        for i, p in enumerate(srcs):
            w = acoustic.decode(p.read_bytes())
            x = w if rt == 0 else signal.fftconvolve(w, room_ir(sr, rt, i))[: w.size + int(rt * sr)]
            x = x / (np.abs(x).max() + 1e-9) * 0.5
            r, _ = spatial.blind_rt60(x, sr)
            est.append(r)
            _, scene = group_scores(x.astype(np.float32))
            for which in inside:
                ins = max(combine(*scene["Inside, small room"], which), combine(*scene["Inside, large room or hall"], which))
                out = max(combine(*scene["Outside, urban or manmade"], which), combine(*scene["Outside, rural or natural"], which))
                inside[which].append(ins > out)
        got = [e for e in est if e]
        med = np.median(got) if got else float("nan")
        err = np.median([abs(e - rt) / rt for e in got]) if got and rt else float("nan")
        share = " / ".join(f"{np.mean(v):.0%}" for v in inside.values())
        print(f"  {rt:8.1f}s | {med:14.2f}s {err:11.0%} {len(est) - len(got):6d}/{len(est):<4d} | {share}")


def main():
    clips = fetch()
    if acoustic._load_ast() is None:
        sys.exit("AST not available: download it first (see README)")
    part1(clips)
    part2(clips)


if __name__ == "__main__":
    main()
