from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import cv2

from .detectors import FireRuleDetector, RapidOcrDetector, YuNetFaceDetector
from .model_assets import ensure_yunet_model
from .sources import OpenCVFrameSource


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = PROJECT.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline smoke test for inspection demo.")
    parser.add_argument("--camera", action="store_true", help="Also read one USB camera frame.")
    args = parser.parse_args()

    model = ensure_yunet_model()
    face_detector = YuNetFaceDetector(model)
    fire_detector = FireRuleDetector()
    ocr_detector = RapidOcrDetector()

    fire_image = cv2.imread(
        str(PROJECT / "ground_station" / "examples" / "fire_test_scene.png")
    )
    if fire_image is None:
        raise RuntimeError("Missing fire_test_scene.png")
    fires, _ = fire_detector.detect(fire_image)
    confidences = [round(item.confidence, 3) for item in fires]
    print(f"FIRE_TEST detections={len(fires)} confidences={confidences}")
    if len(fires) < 3:
        raise AssertionError("Expected at least 3 simulated fire markers")

    ocr_image = cv2.imread(str(PROJECT / "docs" / "images" / "ground-station-runtime.png"))
    if ocr_image is None:
        raise RuntimeError("Missing ground-station-runtime.png")
    texts = ocr_detector.detect(ocr_image)
    print(f"OCR_TEST detections={len(texts)} sample={[item.text for item in texts[:5]]}")
    if not texts:
        raise AssertionError("Expected Chinese/English OCR results")
    joined_text = " ".join(item.text for item in texts)
    if re.search(r"[\u4e00-\u9fff]", joined_text) is None:
        raise AssertionError("Expected at least one Chinese OCR result")
    if re.search(r"[A-Za-z]", joined_text) is None:
        raise AssertionError("Expected at least one English OCR result")

    local_face_image = REPO / "work" / "multimodal_preview.jpg"
    if local_face_image.exists():
        image = cv2.imread(str(local_face_image))
        faces = face_detector.detect(image) if image is not None else []
        print(f"FACE_TEST detections={len(faces)}")
        if not faces:
            raise AssertionError("Expected at least one face in local preview")
    else:
        blank = fire_image[:480, :640].copy()
        blank.fill(0)
        blank_faces = face_detector.detect(blank)
        if blank_faces:
            raise AssertionError("Face model produced a false positive on a blank image")
        print("FACE_MODEL_TEST loaded=true blank_detections=0")

    if args.camera:
        source = OpenCVFrameSource(0, width=640, height=480)
        try:
            source.open()
            ok, frame = source.read()
            if not ok or frame is None:
                raise AssertionError("USB camera opened but returned no frame")
            print(f"CAMERA_TEST source={source.description} shape={frame.shape}")
        finally:
            source.release()

    print("SELF_TEST_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SELF_TEST_FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
