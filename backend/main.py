"""FastAPI app: pages, REST API and the coordinator websocket.

Run from the project root:   python run.py
  /field  -> phone page (push-to-talk, spoken read-back)
  /map    -> coordinator page (live map, evacuation list)
"""
import asyncio
import io
import json
import os
import random
from datetime import datetime, timezone

import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .landmarks import get_db
from .localise import get_engine
from .simulate import observe, truthful_answer
from .state import LOCK, STORE
from .stt import transcribe

import mimetypes  # noqa: E402
mimetypes.add_type("application/javascript", ".mjs")     # Windows maps these to text/plain
mimetypes.add_type("application/wasm", ".wasm")
app = FastAPI(title="Near")
# A frontend hosted elsewhere (Lovable preview, a tunnel) can call the API.
# CORS_ORIGINS="https://a.example,https://b.example" to restrict; "*" by default (demo).
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")
# Offline map tiles drawn from our own OSM / IGN data (scripts/render_tiles.py): no internet needed.
(config.DATA_DIR / "tiles").mkdir(parents=True, exist_ok=True)
app.mount("/tiles", StaticFiles(directory=config.DATA_DIR / "tiles"), name="tiles")
# The phone-sized sound model (scripts/train_small.py, export_small.py), cached by the phone.
(config.DATA_DIR / "models" / "near-small").mkdir(parents=True, exist_ok=True)
app.mount("/models/near-small", StaticFiles(directory=config.DATA_DIR / "models" / "near-small"), name="small")

CLIENTS = set()


async def broadcast():
    msg = json.dumps(STORE.public())
    dead = []
    for ws in list(CLIENTS):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)


@app.on_event("startup")
async def warm_up():
    # Load landmarks and build the grid now, not on the first report.
    await asyncio.to_thread(get_engine)
    from .route import get_router
    await asyncio.to_thread(get_router)     # walking network for routes to the CCP
    asyncio.get_event_loop().create_task(guide_loop())
    llm = f"{config.MISTRAL_MODEL} @ {config.MISTRAL_BASE_URL}" if config.LLM_ENABLED else "OFF (rule parser)"
    print(f"Near ready: {len(get_db().feats)} landmark points, LLM: {llm}")
    if config.LLM_ENABLED:
        # Load the model now (a local one takes a few seconds the first time).
        from .extract import extract
        asyncio.get_event_loop().run_in_executor(None, extract, "warm up", {})
    # Building / noise-source layers and the sound classifier.
    asyncio.get_event_loop().run_in_executor(None, _warm_acoustic)


def _warm_acoustic():
    from .soundscape import get_soundscape
    sc = get_soundscape()
    try:
        from . import acoustic
        acoustic._load()
        a = acoustic._load_ast()
        model = "YAMNet + AST loaded" + (f" (AST on {a['dev']})" if a else " (AST off: YAMNet only)")
    except Exception as e:
        model = f"sound classifier unavailable ({e})"
    from .surround import get_places
    get_places()      # echo + road-noise maps of every spot (cached in data/twin)
    from .landmarks import QUESTION_TYPES
    from .localise import get_engine
    from .viewshed import get_viewshed
    get_viewshed()    # 3D line of sight to every landmark (LiDAR, cached in data/twin)
    for t in QUESTION_TYPES:   # what can be seen from where, trees included (questions need it)
        get_engine().visibility(t)
    print(f"Acoustic: {sc.n_buildings if sc.ok else 0} buildings, {model}")


# ------------------------------------------------------------------ pages
@app.get("/")
def root():
    return RedirectResponse("/map")


@app.get("/favicon.ico")
def favicon():
    from fastapi import Response
    return Response(status_code=204)


@app.get("/sw.js")
def service_worker():
    """Offline cache for the field page (scope /: it must be served from the root)."""
    return FileResponse(config.FRONTEND_DIR / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@app.get("/field")
def field_page():
    return FileResponse(config.FRONTEND_DIR / "field.html")


@app.get("/pipeline")
def pipeline_page():
    return FileResponse(config.FRONTEND_DIR / "pipeline.html")


@app.get("/map")
def map_page():
    return FileResponse(config.FRONTEND_DIR / "map.html")


# ------------------------------------------------------------------ API
class ReportIn(BaseModel):
    report_id: str | None = None
    text: str
    gps: dict | None = None
    compass: dict | None = None    # {"deg": 245, "acc": 15}: phone compass at "my 12 o'clock"
    last_fix: dict | None = None   # {"lat", "lon", "acc", "age_s"}: last GPS fix before jamming
    aims: list | None = None       # [{"az", "el"}]: phone aimed at each landmark's top, in spoken order
    voice: dict | None = None      # quick voice features of this report (/api/voice_quick): stress
    source: str = "voice"
    lang: str | None = None


def _cond_short(rep):
    """Worst casualty's condition and the soonest threat, for the field phone."""
    from .condition import assess
    best = None
    for i, c in enumerate(rep.get("casualties") or []):
        a = assess(c, rep, i)
        if best is None or a["score"] < best["score"]:
            best = a
    if not best:
        return None
    return {"state": best["state"], "score": best["score"], "worse_in": best["worse_in"]}


def field_view(rep):
    """What the field phone needs back."""
    p = rep["position"]
    return {
        "report_id": rep["id"], "readback": rep["readback"], "lang": rep["lang"] or "en",
        "question": rep["question"]["text"] if rep["question"] else None,
        "radius_m": round(p["radius_m"]) if p and p.get("radius_m") else None,
        "state": p["state"] if p else "none", "summary": rep["summary"],
        "transcript": rep["transcripts"][-1] if rep["transcripts"] else None,
        "packet": rep["packet"],
        "acoustic": rep["acoustic"][-1] if rep.get("acoustic") else None,
        "stress": (rep.get("stress") or {}).get("level"),
        "condition": _cond_short(rep),
        "pulse": (rep.get("vitals") or [None])[-1],
        "goal": rep["question"].get("goal_text") if rep["question"] else None,
        "guide": _guide_phone(rep),
    }


def _guide_phone(rep):
    """Guidance for the phone: the instruction and progress, not the route geometry."""
    from .guide import public
    g = public(rep.get("guide"))
    if not g:
        return None
    return {k: g[k] for k in ("state", "instruction", "say_v", "leg", "legs", "leg_left_m", "left_m",
                              "length_m", "eta_s", "mode", "reroutes", "avoided")} | {
        "radius_m": round((g["est"] or {}).get("radius_m") or 0) or None}


@app.post("/api/voice_quick")
async def voice_quick(audio: UploadFile = File(...), ping_at: float = Form(None)):
    """Fast (~0.2 s): how the speaker's voice sounds in this push-to-talk clip (pitch, range,
    brightness, rate; backend/stress.py). The field page sends it with the report, so the
    question asked right away already fits the speaker's stress. The full sound analysis
    of the same clip follows on /api/audio."""
    from . import acoustic, stress
    data = await audio.read()

    def run():
        wave = acoustic.decode(data)
        if ping_at is not None:      # drop the end chirp and its echoes
            wave = wave[:max(0, int((ping_at - 0.05) * acoustic.SR))]
        return stress.voice_features(wave, acoustic.SR)
    try:
        vf = await asyncio.to_thread(run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"voice": vf}


@app.post("/api/audio")
async def post_audio(audio: UploadFile = File(...), report_id: str = Form(None),
                     kind: str = Form("ambient"), ping_at: float = Form(None)):
    """A Listen clip (operator quiet, optional chirp) or the raw audio of a voice report.
    Analysed locally: sound events + what kind of space the phone is in."""
    from . import acoustic
    data = await audio.read()
    try:
        an = await asyncio.to_thread(acoustic.analyse, data, ping_at,
                                     "voice" if kind == "voice" else "ambient")
    except acoustic.AcousticUnavailable as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    rep = await asyncio.to_thread(STORE.process_audio, report_id, an)
    await broadcast()
    return field_view(rep)


@app.post("/api/pulse")
async def post_pulse(audio: UploadFile = File(...), report_id: str = Form(None)):
    """10 s with the phone's microphone pressed on the casualty's chest -> heart rate
    (backend/heart.py). Updates the condition and the dashboard heart panel."""
    from . import acoustic, heart
    data = await audio.read()
    try:
        res = await asyncio.to_thread(lambda: heart.heart_rate(acoustic.decode(data, 16000), 16000))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    rep = await asyncio.to_thread(STORE.process_pulse, report_id, res, "chest audio")
    await broadcast()
    return {**field_view(rep), "pulse": res}


@app.post("/api/report/{rid}/simulate_pulse")
async def simulate_pulse(rid: str):
    """Rehearsal: a synthetic chest recording at a rate that fits the casualty's state,
    measured by the same code as a real one."""
    from . import condition, heart
    import random
    rep = STORE.reports.get(rid)
    if not rep or not rep["casualties"]:
        return JSONResponse({"error": "no casualty in this report"}, status_code=400)
    c = condition.assess(rep["casualties"][0], rep)
    base = {"stable": 84, "serious": 104, "critical": 124, "very critical": 138}[c["state"]]
    bpm = base + random.randint(-6, 6)
    res = await asyncio.to_thread(lambda: heart.heart_rate(heart.synth_pcg(bpm, noise=0.08, seed=random.randint(0, 999)), 16000))
    rep = await asyncio.to_thread(STORE.process_pulse, rid, res, "simulated chest audio")
    await broadcast()
    return {**field_view(rep), "pulse": res, "truth_bpm": bpm}


@app.post("/api/report/{rid}/simulate_listen")
async def simulate_listen(rid: str):
    """Rehearsal: a fake Listen clip at the simulated soldier's true spot."""
    from .simulate import simulate_audio
    rep = STORE.reports.get(rid)
    if not rep or not rep["truth"]:
        return JSONResponse({"error": "only for simulated reports"}, status_code=400)
    an = await asyncio.to_thread(simulate_audio, rep["truth"]["lat"], rep["truth"]["lon"])
    rep = await asyncio.to_thread(STORE.process_audio, rid, an)
    await broadcast()
    return field_view(rep)


class GuideIn(BaseModel):
    action: str                  # start | reached | lost | repeat | arrived | stop | steps
    steps: int | None = None     # phone step counter (with action "steps")


@app.get("/api/report/{rid}/guide")
def get_guide(rid: str):
    """The phone polls this while walking: current instruction and progress."""
    rep = STORE.reports.get(rid)
    if not rep:
        return JSONResponse({"error": "no such report"}, status_code=404)
    return field_view(rep)


@app.post("/api/report/{rid}/guide")
async def guide_action(rid: str, body: GuideIn):
    """Guidance to the CCP: buttons on the phone or the map, and the step counter."""
    if body.action not in ("start", "reached", "lost", "repeat", "arrived", "stop", "steps"):
        return JSONResponse({"error": "unknown action"}, status_code=400)
    rep = await asyncio.to_thread(STORE.guide_action, rid, body.action, body.steps)
    if rep is None:
        return JSONResponse({"error": "no such report"}, status_code=404)
    if body.action != "steps":
        await broadcast()
    return field_view(rep)


async def guide_loop():
    """Move the guided walkers on the map every 2 s."""
    while True:
        await asyncio.sleep(2)
        try:
            if await asyncio.to_thread(STORE.tick):
                await broadcast()
        except Exception as e:      # never kill the loop
            print("guide tick:", repr(e))


# ------------------------------------------------------------------ radio mode (no internet)
@app.post("/api/radio")
async def post_radio(audio: UploadFile = File(...), lang: str = Form(None)):
    """One transmission heard on the tactical radio (backend/radio.py): data tones, speech
    (local Whisper), background threats (Near-small) -> report -> reply to speak back."""
    from . import acoustic, radio
    data = await audio.read()
    try:
        wave = await asyncio.to_thread(acoustic.decode, data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    out = await asyncio.to_thread(radio.handle, STORE, wave, lang)
    await broadcast()
    if out["report_id"]:
        out["field"] = field_view(STORE.reports[out["report_id"]])
    return out


class PacketIn(BaseModel):
    hex: str                       # a measurement packet (backend/packet.py) as hex
    report_id: str | None = None


@app.post("/api/packet")
async def post_packet(body: PacketIn):
    """A measurement packet that came over a data link (radio data mode, mesh radio)."""
    from . import packet, radio
    try:
        p = packet.decode_report(bytes.fromhex(body.hex))
    except (ValueError, IndexError) as e:
        return JSONResponse({"error": f"bad packet: {e}"}, status_code=400)
    rep = await asyncio.to_thread(radio.apply_packet, STORE, body.report_id, p, p.get("callsign"))
    await broadcast()
    return {"packet": p, **field_view(rep)}


@app.get("/api/report/{rid}/route_tones.wav")
def route_tones(rid: str):
    """The current walking route as data tones, to play into the radio for a phone that
    guides offline (it decodes the tones with its microphone)."""
    from fastapi import Response
    from . import radio
    rep = STORE.reports.get(rid)
    if not rep or not rep.get("guide"):
        return JSONResponse({"error": "no route for this report"}, status_code=404)
    wave, raw, _ = radio.route_tones(rep)
    buf = io.BytesIO()
    sf.write(buf, wave, 16000, format="WAV")
    return Response(buf.getvalue(), media_type="audio/wav", headers={"X-Packet-Bytes": str(len(raw))})


class SayIn(BaseModel):
    text: str
    lang: str = "en"


@app.post("/api/tts")
async def post_tts(body: SayIn):
    """Offline speech (WAV) for a reply, so the map page can play it on the radio's output."""
    from fastapi import Response
    from .tts import speak_wav
    wav = await asyncio.to_thread(speak_wav, body.text, body.lang)
    if not wav:
        return JSONResponse({"error": "no offline voice on this laptop"}, status_code=503)
    return Response(wav, media_type="audio/wav")


@app.get("/api/cues")
def get_cues():
    """Named landmarks used in spoken route legs, by index (the phone keeps a copy offline)."""
    from .route import get_router
    return get_router().cues()


@app.post("/api/report")
async def post_report(body: ReportIn):
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "empty report"}, status_code=400)
    rep = await asyncio.to_thread(STORE.process, body.report_id, text, body.gps,
                                  body.source, body.lang, None, body.compass, body.last_fix, body.aims,
                                  body.voice)
    await broadcast()
    return field_view(rep)


@app.post("/api/transcribe")
async def post_transcribe(audio: UploadFile = File(...), lang: str = Form(None)):
    data = await audio.read()
    try:
        text = await asyncio.to_thread(transcribe, data, audio.filename or "audio.webm", lang)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return {"text": text}


SCENES = {}   # report id -> (updated_ms, surroundings view): rebuilt only when the report changes


@app.get("/api/report/{rid}/surround")
async def get_surround(rid: str):
    """What the audio measured around the phone, how much each cue narrowed the map,
    and the real buildings at each likely area with measured vs expected (surround.py)."""
    from . import surround
    rep = STORE.reports.get(rid)
    if not rep:
        return JSONResponse({"error": "no such report"}, status_code=404)
    hit = SCENES.get(rid)
    if hit and hit[0] == rep["updated_ms"]:
        return hit[1]

    def make():
        with LOCK:
            return surround.build(rep, get_engine())
    out = await asyncio.to_thread(make)
    SCENES[rid] = (rep["updated_ms"], out)
    return out


@app.get("/api/report/{rid}/viz")
def get_viz(rid: str):
    """Spectrogram, classifier timeline and echogram of the report's latest clip."""
    rep = STORE.reports.get(rid)
    if not rep:
        return JSONResponse({"error": "no such report"}, status_code=404)
    return rep.get("_viz") or {}


BODY_JSON = {}   # posture -> JSON text of the posed mesh (built once)


@app.get("/api/body_mesh/{posture}")
def body_mesh(posture: str):
    """Posed SMPL-X body (from scripts/build_body.py) for the casualty twin."""
    from fastapi import Response
    from . import body
    if posture not in BODY_JSON:
        m = body.mesh_json(posture)
        if m is None:
            return JSONResponse({"error": "body mesh missing: run python -m scripts.build_body"},
                                status_code=404)
        BODY_JSON[posture] = json.dumps(m, separators=(",", ":"))
    return Response(BODY_JSON[posture], media_type="application/json",
                    headers={"Cache-Control": "max-age=3600"})


@app.get("/api/report/{rid}/body")
def report_body(rid: str):
    """Casualty twin: posture, injuries on body segments, tourniquets, signs, sound cues."""
    from . import body
    rep = STORE.reports.get(rid)
    if not rep:
        return JSONResponse({"error": "no such report"}, status_code=404)
    return body.twin(rep)


@app.get("/api/report/{rid}/response")
def report_response(rid: str):
    """Impact graph (report -> body -> structures -> MARCH -> kit), kit list, team size."""
    from . import response
    rep = STORE.reports.get(rid)
    if not rep:
        return JSONResponse({"error": "no such report"}, status_code=404)
    return response.build(rep, STORE.distance_to_ccp(rep))


@app.get("/api/state")
def get_state():
    return STORE.public()


@app.get("/api/config")
def get_config():
    """What the pages need to know: local (offline) speech-to-text or the browser's."""
    from .stt import local_available
    return {"stt": "local" if config.STT_PROVIDER == "local" and local_available() else "browser"}


@app.get("/api/probe")
def probe_params():
    """Chirp parameters, so the phone plays exactly what the server deconvolves."""
    return config.PROBE


class CCPIn(BaseModel):
    lat: float
    lon: float


@app.post("/api/ccp")
async def set_ccp(body: CCPIn):
    with LOCK:
        STORE.ccp.update(lat=body.lat, lon=body.lon)
        STORE.version += 1
    await broadcast()
    return STORE.ccp


@app.post("/api/report/{rid}/evacuated")
async def evacuated(rid: str):
    with LOCK:
        if rid in STORE.reports:
            STORE.reports[rid]["evacuated"] = not STORE.reports[rid]["evacuated"]
            STORE.version += 1
    await broadcast()
    return {"ok": True}


@app.post("/api/reset")
async def reset():
    with LOCK:
        STORE.reports.clear()
        STORE.counter = 0
        STORE.version += 1
        SCENES.clear()
    await broadcast()
    return {"ok": True}


# ------------------------------------------------------------------ rehearsal
class SimIn(BaseModel):
    lat: float
    lon: float
    heading: float | None = None
    casualty: bool = True
    danger: bool = True
    walking: bool | None = None    # rehearsal: True = a casualty who can walk, False = stretcher case


CASUALTY_LINES = [
    "One casualty, blast, left leg bleeding, tourniquet on at {t}, conscious and breathing.",
    "One casualty, gunshot to the chest, breathing problem, unconscious.",
    "One casualty, fell, right arm injured, conscious, walking wounded, routine.",
    "Two casualties, blast, shrapnel to the arms, tourniquet right arm at {t}, both conscious.",
]

# Rehearsal threats (half the simulated reports carry one), to show the danger layer.
DANGER_LINES = ["Drone overhead.", "Taking fire from my {k} o'clock.", "Sniper at my {k} o'clock.",
                "Mortar rounds landing nearby.", "Mines on the track.", "We hear a drone."]


@app.post("/api/simulate")
async def simulate(body: SimIn):
    """Pretend a soldier stands here: build the sentence they would say and send it."""
    heading = body.heading if body.heading is not None else random.uniform(0, 360)
    when = datetime.now(timezone.utc)
    _, sentence = observe(body.lat, body.lon, heading, n=3, when=when)
    text = sentence
    if body.casualty:
        t = datetime.now().strftime("%H:%M")
        lines = CASUALTY_LINES if body.walking is None else [CASUALTY_LINES[i] for i in ((2, 3) if body.walking else (0, 1))]
        text = random.choice(lines).format(t=t) + " " + sentence
    if body.danger and random.random() < 0.5:
        text += " " + random.choice(DANGER_LINES).format(k=random.randint(1, 12))
    truth = {"lat": body.lat, "lon": body.lon, "heading": heading}
    rep = await asyncio.to_thread(STORE.process, None, text, None, "simulated", "en", truth)
    # The voice report carries its own audio (voice + chirp at the end): simulate it too.
    from .simulate import simulate_audio
    try:
        an = await asyncio.to_thread(simulate_audio, body.lat, body.lon)
        rep = await asyncio.to_thread(STORE.process_audio, rep["id"], an)
    except Exception as e:      # the report itself is in: never lose it over the fake clip
        print("simulated audio failed:", repr(e))
    await broadcast()
    return field_view(rep)


@app.post("/api/report/{rid}/auto_answer")
async def auto_answer(rid: str):
    """Rehearsal: answer the pending question as the simulated soldier would."""
    rep = STORE.reports.get(rid)
    if not rep or not rep["truth"] or not rep["question"]:
        return JSONResponse({"error": "nothing to answer"}, status_code=400)
    t = rep["truth"]
    text = await asyncio.to_thread(truthful_answer, rep["question"], t["lat"], t["lon"],
                                   t["heading"], datetime.now(timezone.utc))
    rep = await asyncio.to_thread(STORE.process, rid, text, None, "simulated")
    await broadcast()
    return field_view(rep)


@app.get("/api/landmarks")
def landmarks(types: str = "keep,castle,church,station,townhall,water_tower,tower,hospital"):
    """Point landmarks for the map layer (not the sampled lines)."""
    want = set(types.split(","))
    return [f for f in get_db().feats if f["type"] in want]


# ------------------------------------------------------------------ websocket
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    CLIENTS.add(websocket)
    await websocket.send_text(json.dumps(STORE.public()))
    try:
        while True:
            await websocket.receive_text()   # we only push; ignore pings
    except WebSocketDisconnect:
        CLIENTS.discard(websocket)
