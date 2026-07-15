from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import urllib.request


MODEL_DIR = Path(__file__).resolve().parent / "models"
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
YUNET_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
OPENVINO_FACE_XML = "face-detection-retail-0005.xml"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_yunet_model(model_dir: Path | None = None) -> Path:
    target_dir = model_dir or MODEL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / YUNET_FILENAME
    if target.exists() and _sha256(target) == YUNET_SHA256:
        return target

    temporary = target.with_suffix(target.suffix + ".download")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(
        YUNET_URL,
        headers={"User-Agent": "IntelCup-Inspection-Demo/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        actual_hash = _sha256(temporary)
        if actual_hash != YUNET_SHA256:
            raise RuntimeError(
                f"YuNet model checksum mismatch: expected {YUNET_SHA256}, got {actual_hash}"
            )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def openvino_npu_face_model(model_dir: Path | None = None) -> Path:
    target_dir = model_dir or MODEL_DIR
    xml_path = target_dir / OPENVINO_FACE_XML
    bin_path = xml_path.with_suffix(".bin")
    if not xml_path.exists() or not bin_path.exists():
        raise FileNotFoundError(
            "NPU人脸模型不完整，请确认inspection_demo/models中同时存在"
            "face-detection-retail-0005.xml和.bin"
        )
    return xml_path
