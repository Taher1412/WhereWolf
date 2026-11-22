"""Offline text-to-speech for replies sent back over the radio.

The browser's speechSynthesis always plays on the default speaker, but the radio is usually
plugged into another audio output. So the laptop makes a WAV here (offline) and the map page
plays it on the output the operator picked (setSinkId).
Windows: the built-in SAPI voices (no internet). Elsewhere: espeak-ng if installed.
"""
import os
import shutil
import subprocess
import tempfile


def speak_wav(text: str, lang: str = "en") -> bytes | None:
    text = (text or "").replace('"', "'").replace("\n", " ").strip()
    if not text:
        return None
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "say.wav")
        if os.name == "nt":
            culture = "fr-FR" if lang == "fr" else "en-"
            ps = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like '{culture}*' }} | Select-Object -First 1; "
                  "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Rate = 0; "
                  f"$s.SetOutputToWaveFile('{out}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], input=text.encode("utf-8"),
                               capture_output=True, timeout=60)
        elif shutil.which("espeak-ng"):
            r = subprocess.run(["espeak-ng", "-v", "fr" if lang == "fr" else "en", "-w", out, text],
                               capture_output=True, timeout=60)
        else:
            return None
        if r.returncode != 0 or not os.path.exists(out):
            return None
        return open(out, "rb").read()
