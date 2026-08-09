from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from k230_color_detector import (
    K230RedBlobDetector,
    RedBlobConfirmationTracker,
    annotate_red_blob_detections,
    create_red_blob_demo_frame,
)


APP_DIR = Path(__file__).resolve().parent
EXAMPLE_DIR = APP_DIR / "examples"
SCENE_PATH = EXAMPLE_DIR / "k230_red_blob_input.png"
RESULT_PATH = EXAMPLE_DIR / "k230_red_blob_result.png"


def write_image(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise RuntimeError(f"无法编码图片：{path}")
    encoded.tofile(str(path))


def main() -> int:
    EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    scene = create_red_blob_demo_frame()
    detector = K230RedBlobDetector()
    tracker = RedBlobConfirmationTracker(required_frames=20)
    detections = []
    confirmed = None
    for _ in range(20):
        detections = detector.detect(scene)
        confirmed = tracker.update(detections) or confirmed

    result_detections = [confirmed] if confirmed is not None else detections
    result = annotate_red_blob_detections(scene, result_detections)
    write_image(SCENE_PATH, scene)
    write_image(RESULT_PATH, result)
    print(f"source={SCENE_PATH}")
    print(f"result={RESULT_PATH}")
    print(f"detections={len(result_detections)}")
    print(f"confirmed={confirmed is not None}")
    return 0 if confirmed is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
