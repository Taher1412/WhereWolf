"""Download every model Near needs, ONCE, while there is internet. After that the laptop
runs fully offline (speech-to-text, sound classes, drones, threats).

    python -m scripts.fetch_models            # Whisper turbo (GPU) + small (CPU), sound models
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHISPER = ROOT / "data" / "models" / "whisper"


def main():
    from faster_whisper import WhisperModel
    for name in ("large-v3-turbo", "small"):
        print("Whisper", name, "...")
        WhisperModel(name, device="cpu", compute_type="int8", download_root=str(WHISPER))
    from huggingface_hub import snapshot_download
    for repo in ("preszzz/drone-audio-detection-05-17-trial-0", "MIT/ast-finetuned-audioset-10-10-0.4593",
                 "mispeech/ced-tiny"):
        print(repo, "...")
        snapshot_download(repo)
    from huggingface_hub import hf_hub_download
    hf_hub_download("topel/ConvNeXt-Tiny-AT", "class_labels_indices.csv")   # CED's AudioSet label names
    print("done: the laptop can now run offline")


if __name__ == "__main__":
    main()
