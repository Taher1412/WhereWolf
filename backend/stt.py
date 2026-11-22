"""Speech-to-text behind one function: transcribe(audio) -> text.

Default: **local Whisper** (faster-whisper, large-v3-turbo on the GPU, small on CPU), so
nothing leaves the laptop and it works with no internet: the war setting. The model is
downloaded once by `python -m scripts.fetch_models` into data/models/whisper.
Other providers, only with internet: STT_PROVIDER=browser (Chrome speech recognition, done
on Google's servers), mistral (Voxtral) or openai (Whisper API).
"""
import os
import threading

import httpx

from . import config

# Words of this domain: steers Whisper towards them on noisy radio audio.
PROMPT = ("Casualty report. Tourniquet, conscious, breathing, bleeding, shrapnel, blast, gunshot. "
          "The keep at my 2 o'clock, church, water tower, bearing 240 degrees, 4200 mils. "
          "CCP, medic, drone, sniper, over. Blessé, garrot, à mes 2 heures, clocher, château d'eau.")

_model = None
_lock = threading.Lock()


def local_available():
    return (config.WHISPER_DIR / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo").exists() or \
        (config.WHISPER_DIR / "models--Systran--faster-whisper-small").exists()


def _load():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            try:
                import torch
                cuda = torch.cuda.is_available()
                if cuda and hasattr(os, "add_dll_directory"):   # cuBLAS / cuDNN shipped with torch
                    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
            except Exception:
                cuda = False
            if cuda:
                _model = WhisperModel(config.WHISPER_MODEL, device="cuda", compute_type="float16",
                                      download_root=str(config.WHISPER_DIR), local_files_only=True)
            else:
                _model = WhisperModel(config.WHISPER_CPU_MODEL, device="cpu", compute_type="int8",
                                      download_root=str(config.WHISPER_DIR), local_files_only=True)
            print(f"speech-to-text: local Whisper ({'GPU ' + config.WHISPER_MODEL if cuda else 'CPU ' + config.WHISPER_CPU_MODEL})")
    return _model


def transcribe_wave(wave, lang=None) -> str:
    """16 kHz mono float32 -> text, locally."""
    m = _load()
    # Voice-activity filter tuned on radio audio (radiosim.py): 0.25 keeps the quiet first
    # words after the radio's gain kicks in, and still returns nothing on pure hiss.
    segs, _ = m.transcribe(wave, language=(lang or None) and lang[:2], vad_filter=True,
                           vad_parameters=dict(threshold=0.25, min_silence_duration_ms=600, speech_pad_ms=400),
                           condition_on_previous_text=False, initial_prompt=PROMPT,
                           no_speech_threshold=0.5, beam_size=5)
    text = " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.6)
    return text.strip()


def transcribe(audio: bytes, filename="audio.webm", lang=None) -> str:
    provider = config.STT_PROVIDER
    if provider in ("local", "browser") and local_available():
        from .acoustic import decode
        return transcribe_wave(decode(audio), lang)
    if provider == "openai" and config.OPENAI_API_KEY:
        url = "https://api.openai.com/v1/audio/transcriptions"
        key, model = config.OPENAI_API_KEY, "whisper-1"
    elif config.MISTRAL_API_KEY:
        url = "https://api.mistral.ai/v1/audio/transcriptions"
        key, model = config.MISTRAL_API_KEY, "voxtral-mini-latest"
    else:
        raise RuntimeError("No speech-to-text available: run python -m scripts.fetch_models once "
                           "(local Whisper), or type the report.")
    data = {"model": model}
    if lang:
        data["language"] = lang
    r = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, data=data,
                   files={"file": (filename, audio)}, timeout=60)
    r.raise_for_status()
    return r.json().get("text", "").strip()
