"""FastAPI app: pages, REST API and the coordinator websocket.

Run from the project root:   python run.py
  /field  -> phone page (push-to-talk, spoken read-back)
  /map    -> coordinator page (live map, evacuation list)
"""
import asyncio
import json
import random
from datetime import datetime, timezone

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

app = FastAPI(title="Pothenot")
app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")

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
    llm = f"{config.MISTRAL_MODEL} @ {config.MISTRAL_BASE_URL}" if config.LLM_ENABLED else "OFF (rule parser)"
    print(f"Pothenot ready: {len(get_db().feats)} landmark points, LLM: {llm}")
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
    print(f"Acoustic: {sc.n_buildings if sc.ok else 0} buildings, {model}")


# ------------------------------------------------------------------ pages
@app.get("/")
def root():
    return RedirectResponse("/map")


@app.get("/favicon.ico")
def favicon():
    from fastapi import Response
    return Response(status_code=204)


@app.get("/field")
def field_page():
    return FileResponse(config.FRONTEND_DIR / "field.html")


@app.get("/map")
def map_page():
    return FileResponse(config.FRONTEND_DIR / "map.html")


# ------------------------------------------------------------------ API
class ReportIn(BaseModel):
    report_id: str | None = None
    text: str
    gps: dict | None = None
    source: str = "voice"
    lang: str | None = None


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
    }


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


@app.post("/api/report")
async def post_report(body: ReportIn):
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "empty report"}, status_code=400)
    rep = await asyncio.to_thread(STORE.process, body.report_id, text, body.gps,
                                  body.source, body.lang)
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


@app.get("/api/state")
def get_state():
    return STORE.public()


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
    await broadcast()
    return {"ok": True}


# ------------------------------------------------------------------ rehearsal
class SimIn(BaseModel):
    lat: float
    lon: float
    heading: float | None = None
    casualty: bool = True


CASUALTY_LINES = [
    "One casualty, blast, left leg bleeding, tourniquet on at {t}, conscious and breathing.",
    "One casualty, gunshot to the chest, breathing problem, unconscious.",
    "One casualty, fell, right arm injured, conscious, walking wounded, routine.",
    "Two casualties, blast, shrapnel to the arms, tourniquet right arm at {t}, both conscious.",
]


@app.post("/api/simulate")
async def simulate(body: SimIn):
    """Pretend a soldier stands here: build the sentence they would say and send it."""
    heading = body.heading if body.heading is not None else random.uniform(0, 360)
    when = datetime.now(timezone.utc)
    _, sentence = observe(body.lat, body.lon, heading, n=3, when=when)
    text = sentence
    if body.casualty:
        t = datetime.now().strftime("%H:%M")
        text = random.choice(CASUALTY_LINES).format(t=t) + " " + sentence
    truth = {"lat": body.lat, "lon": body.lon, "heading": heading}
    rep = await asyncio.to_thread(STORE.process, None, text, None, "simulated", "en", truth)
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
