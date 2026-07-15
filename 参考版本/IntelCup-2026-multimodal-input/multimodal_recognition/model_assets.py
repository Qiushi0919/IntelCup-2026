from __future__ import annotations

from pathlib import Path
import urllib.request


MODEL_DIR = Path(__file__).resolve().parent / "models"
GESTURE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/1/"
    "gesture_recognizer.task"
)
FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/"
    "face_landmarker.task"
)


def ensure_model(filename: str, url: str) -> Path:
    MODEL_DIR.mkdir(exist_ok=True)
    path = MODEL_DIR / filename
    if path.exists() and path.stat().st_size > 1024:
        return path
    print(f"首次运行，正在下载模型：{filename}", flush=True)
    temporary = path.with_suffix(path.suffix + ".download")
    try:
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path
