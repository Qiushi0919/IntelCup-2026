from __future__ import annotations

from dataclasses import dataclass
from math import hypot

import cv2
import numpy as np

from models import FireDetection


# Source: k230/apps/color_det/color_recog/color_recognition.py
# K230 uses L in [0, 100] and signed A/B in [-128, 127].
K230_RED_LAB = (32, 55, 26, 92, -3, 41)


@dataclass(frozen=True)
class K230RedBlobConfig:
    min_blob_area_ratio: float = 0.006
    max_blob_area_ratio: float = 0.45
    min_box_side: int = 18
    min_fill_ratio: float = 0.28
    morphology_size: int = 5


class K230RedBlobDetector:
    """OpenCV port of the K230 LAB red-color blob example.

    The original K230 color-recognition example calls ``find_blobs`` and does
    not load a kmodel. This implementation applies the same LAB threshold to
    AMB82 BGR frames and adds a pure-red compatibility mask for the simulated
    competition fire marker.
    """

    def __init__(self, config: K230RedBlobConfig | None = None) -> None:
        self.config = config or K230RedBlobConfig()

    def detect(self, frame: np.ndarray) -> list[FireDetection]:
        if frame is None or frame.size == 0:
            return []

        height, width = frame.shape[:2]
        frame_area = float(width * height)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        k230_mask = cv2.inRange(
            lab,
            self._lab_lower(K230_RED_LAB),
            self._lab_upper(K230_RED_LAB),
        )
        # The printed red marker used in the field can be brighter than the
        # K230 sample threshold. Keep it in the red hue bands, then rely on the
        # large-blob and 20-frame gates to reject transient noise.
        bright_red_low = cv2.inRange(
            hsv,
            np.array((0, 125, 95), dtype=np.uint8),
            np.array((12, 255, 255), dtype=np.uint8),
        )
        bright_red_high = cv2.inRange(
            hsv,
            np.array((168, 125, 95), dtype=np.uint8),
            np.array((180, 255, 255), dtype=np.uint8),
        )
        mask = cv2.bitwise_or(k230_mask, bright_red_low)
        mask = cv2.bitwise_or(mask, bright_red_high)

        kernel_size = max(3, self.config.morphology_size | 1)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        min_area = max(180.0, frame_area * self.config.min_blob_area_ratio)
        max_area = frame_area * self.config.max_blob_area_ratio
        detections: list[FireDetection] = []

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if not min_area <= area <= max_area:
                continue

            x, y, box_width, box_height = cv2.boundingRect(contour)
            if (
                box_width < self.config.min_box_side
                or box_height < self.config.min_box_side
            ):
                continue
            box_area = float(box_width * box_height)
            fill_ratio = area / max(1.0, box_area)
            if fill_ratio < self.config.min_fill_ratio:
                continue

            area_ratio = area / frame_area
            area_score = min(1.0, area_ratio / 0.035)
            density_score = min(1.0, fill_ratio / 0.78)
            confidence = float(
                np.clip(0.58 + 0.22 * area_score + 0.18 * density_score, 0.0, 0.98)
            )
            padding = max(4, round(max(box_width, box_height) * 0.05))
            left = max(0, x - padding)
            top = max(0, y - padding)
            right = min(width, x + box_width + padding)
            bottom = min(height, y + box_height + padding)
            detections.append(
                FireDetection(
                    bbox=(left, top, right - left, bottom - top),
                    confidence=confidence,
                    area=area,
                    center_x=x + box_width // 2,
                    center_y=y + box_height // 2,
                    frame_width=width,
                    frame_height=height,
                    warm_ratio=fill_ratio,
                    kind="k230_red_blob",
                )
            )

        detections.sort(key=lambda item: item.area, reverse=True)
        return detections

    @staticmethod
    def _lab_lower(threshold: tuple[int, int, int, int, int, int]) -> np.ndarray:
        l_min, _l_max, a_min, _a_max, b_min, _b_max = threshold
        return np.array(
            (round(l_min * 255 / 100), a_min + 128, b_min + 128),
            dtype=np.uint8,
        )

    @staticmethod
    def _lab_upper(threshold: tuple[int, int, int, int, int, int]) -> np.ndarray:
        _l_min, l_max, _a_min, a_max, _b_min, b_max = threshold
        return np.array(
            (round(l_max * 255 / 100), a_max + 128, b_max + 128),
            dtype=np.uint8,
        )


class RedBlobConfirmationTracker:
    """Confirm the same large red blob after 20 uninterrupted frames."""

    def __init__(self, required_frames: int = 20) -> None:
        self.required_frames = max(1, required_frames)
        self._streak = 0
        self._last_bbox: tuple[int, int, int, int] | None = None
        self._already_emitted = False

    def update(self, detections: list[FireDetection]) -> FireDetection | None:
        if not detections:
            self.reset()
            return None

        candidate = detections[0]
        if self._last_bbox is not None and self._same_blob(
            self._last_bbox, candidate.bbox, candidate.frame_width, candidate.frame_height
        ):
            self._streak += 1
        else:
            self._streak = 1
            self._already_emitted = False

        self._last_bbox = candidate.bbox
        candidate.consecutive_frames = self._streak
        candidate.required_frames = self.required_frames
        candidate.confirmed = self._streak >= self.required_frames

        if candidate.confirmed and not self._already_emitted:
            self._already_emitted = True
            return candidate
        return None

    def reset(self) -> None:
        self._streak = 0
        self._last_bbox = None
        self._already_emitted = False

    @staticmethod
    def _same_blob(
        previous: tuple[int, int, int, int],
        current: tuple[int, int, int, int],
        frame_width: int,
        frame_height: int,
    ) -> bool:
        if RedBlobConfirmationTracker._iou(previous, current) >= 0.18:
            return True
        px, py, pw, ph = previous
        cx, cy, cw, ch = current
        previous_center = (px + pw / 2.0, py + ph / 2.0)
        current_center = (cx + cw / 2.0, cy + ch / 2.0)
        distance = hypot(
            previous_center[0] - current_center[0],
            previous_center[1] - current_center[1],
        )
        frame_diagonal = hypot(frame_width, frame_height)
        allowed_jump = max(frame_diagonal * 0.06, max(pw, ph, cw, ch) * 1.25)
        return distance <= allowed_jump

    @staticmethod
    def _iou(
        first: tuple[int, int, int, int], second: tuple[int, int, int, int]
    ) -> float:
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        left = max(ax, bx)
        top = max(ay, by)
        right = min(ax + aw, bx + bw)
        bottom = min(ay + ah, by + bh)
        intersection = max(0, right - left) * max(0, bottom - top)
        union = aw * ah + bw * bh - intersection
        return intersection / max(1.0, float(union))


def annotate_red_blob_detections(
    frame: np.ndarray, detections: list[FireDetection]
) -> np.ndarray:
    annotated = frame.copy()
    for detection in detections:
        x, y, width, height = detection.bbox
        color = (30, 30, 235) if detection.confirmed else (0, 190, 255)
        cv2.rectangle(annotated, (x, y), (x + width, y + height), color, 3)
        label = (
            "FIRE CONFIRMED"
            if detection.confirmed
            else f"RED BLOB {detection.consecutive_frames}/{detection.required_frames}"
        )
        cv2.putText(
            annotated,
            label,
            (x, max(24, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            color,
            2,
            cv2.LINE_AA,
        )
    return annotated


def create_red_blob_demo_frame(
    width: int = 1280, height: int = 720
) -> np.ndarray:
    """Create a diagnostic frame with one valid blob and small red noise."""

    frame = np.full((height, width, 3), (34, 39, 43), dtype=np.uint8)
    cv2.rectangle(
        frame,
        (round(width * 0.08), round(height * 0.16)),
        (round(width * 0.92), round(height * 0.88)),
        (48, 55, 60),
        -1,
    )
    center = (width // 2, height // 2)
    radius = max(45, round(min(width, height) * 0.12))
    cv2.circle(frame, center, radius, (0, 0, 230), -1, cv2.LINE_AA)
    for x_ratio, y_ratio in ((0.18, 0.25), (0.82, 0.72), (0.24, 0.78)):
        cv2.circle(
            frame,
            (round(width * x_ratio), round(height * y_ratio)),
            max(4, round(min(width, height) * 0.008)),
            (0, 0, 255),
            -1,
            cv2.LINE_AA,
        )
    return frame
