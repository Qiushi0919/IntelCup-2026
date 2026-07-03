from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from fire_detector import FireDetector, annotate_fire_detections


APP_DIR = Path(__file__).resolve().parent
EXAMPLE_DIR = APP_DIR / "examples"
ORIGINAL_MAP = EXAMPLE_DIR / "competition_map_original.png"
SCENE_PATH = EXAMPLE_DIR / "fire_test_scene.png"
RESULT_PATH = EXAMPLE_DIR / "fire_detection_result.png"


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"无法读取图片：{path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    extension = path.suffix or ".png"
    ok, encoded = cv2.imencode(extension, image)
    if not ok:
        raise RuntimeError(f"无法编码图片：{path}")
    encoded.tofile(str(path))


def locate_original_fire_marks(
    image: np.ndarray,
) -> list[tuple[int, int, int, int, int, int]]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_mask = cv2.inRange(
        hsv,
        np.array((0, 180, 150), dtype=np.uint8),
        np.array((9, 255, 255), dtype=np.uint8),
    )
    red_mask |= cv2.inRange(
        hsv,
        np.array((171, 180, 150), dtype=np.uint8),
        np.array((180, 255, 255), dtype=np.uint8),
    )
    count, _, stats, centroids = cv2.connectedComponentsWithStats(red_mask)
    marks: list[tuple[int, int, int, int, int, int]] = []
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        if 300 <= area <= 5000 and width <= 100 and height <= 100:
            center_x, center_y = centroids[index]
            marks.append(
                (x, y, width, height, round(center_x), round(center_y))
            )
    marks.sort(key=lambda item: (item[5], item[4]))
    return marks


def create_test_scene() -> tuple[np.ndarray, list[tuple[int, int]]]:
    image = read_image(ORIGINAL_MAP)
    marks = locate_original_fire_marks(image)
    if len(marks) != 3:
        raise RuntimeError(f"预期找到 3 个原始星标，实际找到 {len(marks)} 个")

    clean_map = image.copy()
    centers: list[tuple[int, int]] = []
    for x, y, width, height, center_x, center_y in marks:
        margin = 10
        cv2.rectangle(
            clean_map,
            (max(0, x - margin), max(0, y - margin)),
            (
                min(clean_map.shape[1] - 1, x + width + margin),
                min(clean_map.shape[0] - 1, y + height + margin),
            ),
            (255, 255, 255),
            -1,
        )
        centers.append((center_x, center_y))

    radius = 23
    for center in centers:
        cv2.circle(
            clean_map,
            center,
            radius,
            (0, 0, 255),
            -1,
            cv2.LINE_AA,
        )
    return clean_map, centers


def main() -> int:
    EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    scene, centers = create_test_scene()
    write_image(SCENE_PATH, scene)

    detector = FireDetector()
    detections = detector.detect(scene)
    result = annotate_fire_detections(scene, detections)
    write_image(RESULT_PATH, result)

    marker_detections = [
        detection
        for detection in detections
        if detection.kind == "simulated_marker"
    ]
    print(f"original={ORIGINAL_MAP}")
    print(f"source={SCENE_PATH}")
    print(f"result={RESULT_PATH}")
    print(f"marker_centers={centers}")
    print(f"detections={len(marker_detections)}")
    for detection in marker_detections:
        print(
            "bbox={} confidence={:.3f} center=({}, {})".format(
                detection.bbox,
                detection.confidence,
                detection.center_x,
                detection.center_y,
            )
        )
    return 0 if len(marker_detections) == len(centers) else 1


if __name__ == "__main__":
    raise SystemExit(main())
