"""Speech-to-text behind one function: transcribe(audio) -> text.

Default is the browser (Chrome Web Speech API), so the server only gets text.
This module is the fallback for browsers without it: the page records audio
and posts it here. Set STT_PROVIDER=mistral (Voxtral) or openai (Whisper).
"""
import httpx

from . import config


def transcribe(audio: bytes, filename="audio.webm", lang=None) -> str:
    provider = config.STT_PROVIDER
    if provider == "openai" and config.OPENAI_API_KEY:
        url = "https://api.openai.com/v1/audio/transcriptions"
        key, model = config.OPENAI_API_KEY, "whisper-1"
    elif config.MISTRAL_API_KEY:
        url = "https://api.mistral.ai/v1/audio/transcriptions"
        key, model = config.MISTRAL_API_KEY, "voxtral-mini-latest"
    else:
        raise RuntimeError("No speech-to-text key set (MISTRAL_API_KEY or OPENAI_API_KEY). "
                           "Use Chrome's built-in speech recognition or type the report.")
    data = {"model": model}
    if lang:
        data["language"] = lang
    r = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, data=data,
                   files={"file": (filename, audio)}, timeout=60)
    r.raise_for_status()
    return r.json().get("text", "").strip()
