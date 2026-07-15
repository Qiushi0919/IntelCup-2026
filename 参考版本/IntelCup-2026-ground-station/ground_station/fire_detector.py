from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from models import FireDetection


@dataclass(frozen=True)
class FireDetectorConfig:
    min_confidence: float = 0.58
    min_area_ratio: float = 0.00004
    max_area_ratio: float = 0.20
    morphology_size: int = 5
    detect_simulated_markers: bool = True


class FireDetector:
    """Classical color/brightness detector for visible open flames.

    This is intentionally lightweight enough for the AMB82 snapshot stream.
    It is suitable for a competition prototype and controlled scenes, but it
    is not a replacement for a trained detector in complex environments.
    """

    def __init__(self, config: FireDetectorConfig | None = None) -> None:
        self.config = config or FireDetectorConfig()

    def detect(self, frame: np.ndarray) -> list[FireDetection]:
        if frame is None or frame.size == 0:
            return []

        height, width = frame.shape[:2]
        frame_area = float(width * height)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        blue, green, red = cv2.split(blurred)

        orange_yellow = cv2.inRange(
            hsv,
            np.array((0, 105, 135), dtype=np.uint8),
            np.array((42, 255, 255), dtype=np.uint8),
        )
        deep_red = cv2.inRange(
            hsv,
            np.array((170, 105, 120), dtype=np.uint8),
            np.array((180, 255, 255), dtype=np.uint8),
        )
        warm_hsv = cv2.bitwise_or(orange_yellow, deep_red)

        channel_rule = (
            (red.astype(np.int16) > 135)
            & (red.astype(np.int16) - blue.astype(np.int16) > 45)
            & (green.astype(np.int16) - blue.astype(np.int16) > 22)
            & (red.astype(np.float32) >= green.astype(np.float32) * 0.90)
        )
        channel_mask = (channel_rule.astype(np.uint8) * 255)
        candidate_mask = cv2.bitwise_and(warm_hsv, channel_mask)

        bright_core_rule = (
            (red.astype(np.int16) > 205)
            & (green.astype(np.int16) > 145)
            & (blue.astype(np.int16) < 180)
            & (hsv[:, :, 2] > 215)
        )
        core_mask = bright_core_rule.astype(np.uint8) * 255

        kernel_size = max(3, self.config.morphology_size | 1)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        candidate_mask = cv2.morphologyEx(
            candidate_mask, cv2.MORPH_OPEN, kernel, iterations=1
        )
        candidate_mask = cv2.morphologyEx(
            candidate_mask, cv2.MORPH_CLOSE, kernel, iterations=2
        )

        contours, _ = cv2.findContours(
            candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        detections: list[FireDetection] = []
        min_area = max(24.0, frame_area * self.config.min_area_ratio)
        max_area = frame_area * self.config.max_area_ratio

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue

            x, y, box_width, box_height = cv2.boundingRect(contour)
            if box_width < 5 or box_height < 5:
                continue

            box_area = float(box_width * box_height)
            warm_pixels = cv2.countNonZero(
                candidate_mask[y : y + box_height, x : x + box_width]
            )
            core_pixels = cv2.countNonZero(
                core_mask[y : y + box_height, x : x + box_width]
            )
            warm_ratio = warm_pixels / max(1.0, box_area)
            core_ratio = core_pixels / max(1.0, box_area)
            if warm_ratio < 0.10 or core_ratio < 0.006:
                continue

            aspect_ratio = box_height / max(1.0, box_width)
            shape_score = max(0.0, 1.0 - abs(aspect_ratio - 1.25) / 2.0)
            area_score = min(1.0, area / max(1.0, frame_area * 0.0015))
            density_score = min(1.0, warm_ratio / 0.55)
            core_score = min(1.0, core_ratio / 0.18)
            confidence = (
                0.30
                + 0.22 * density_score
                + 0.22 * core_score
                + 0.14 * shape_score
                + 0.12 * area_score
            )
            confidence = float(np.clip(confidence, 0.0, 0.99))
            if confidence < self.config.min_confidence:
                continue

            padding_x = max(4, int(box_width * 0.18))
            padding_y = max(4, int(box_height * 0.18))
            left = max(0, x - padding_x)
            top = max(0, y - padding_y)
            right = min(width, x + box_width + padding_x)
            bottom = min(height, y + box_height + padding_y)

            detections.append(
                FireDetection(
                    bbox=(left, top, right - left, bottom - top),
                    confidence=confidence,
                    area=area,
                    center_x=x + box_width // 2,
                    center_y=y + box_height // 2,
                    frame_width=width,
                    frame_height=height,
                    warm_ratio=warm_ratio,
                    core_ratio=core_ratio,
                )
            )

        detections.sort(key=lambda item: item.confidence, reverse=True)
        if self.config.detect_simulated_markers:
            detections.extend(self._detect_simulated_markers(hsv, width, height))
            detections.sort(key=lambda item: item.confidence, reverse=True)
        return detections

    def _detect_simulated_markers(
        self, hsv: np.ndarray, width: int, height: int
    ) -> list[FireDetection]:
        frame_area = float(width * height)
        red_low = cv2.inRange(
            hsv,
            np.array((0, 175, 145), dtype=np.uint8),
            np.array((9, 255, 255), dtype=np.uint8),
        )
        red_high = cv2.inRange(
            hsv,
            np.array((171, 175, 145), dtype=np.uint8),
            np.array((180, 255, 255), dtype=np.uint8),
        )
        marker_mask = cv2.bitwise_or(red_low, red_high)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        marker_mask = cv2.morphologyEx(
            marker_mask, cv2.MORPH_OPEN, kernel, iterations=1
        )
        marker_mask = cv2.morphologyEx(
            marker_mask, cv2.MORPH_CLOSE, kernel, iterations=1
        )
        contours, _ = cv2.findContours(
            marker_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        results: list[FireDetection] = []
        min_area = max(30.0, frame_area * 0.00002)
        max_area = frame_area * 0.004
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            circularity = 4.0 * np.pi * area / (perimeter * perimeter)
            (center_x, center_y), radius = cv2.minEnclosingCircle(contour)
            enclosing_fill = area / max(1.0, np.pi * radius * radius)
            x, y, box_width, box_height = cv2.boundingRect(contour)
            aspect = box_width / max(1.0, box_height)
            if (
                circularity < 0.68
                or enclosing_fill < 0.55
                or not 0.55 <= aspect <= 1.80
            ):
                continue

            shape_score = min(
                1.0,
                0.60 * circularity / 0.90
                + 0.40 * enclosing_fill / 0.85,
            )
            confidence = float(np.clip(0.72 + 0.25 * shape_score, 0.0, 0.98))
            padding = max(4, round(radius * 0.30))
            left = max(0, x - padding)
            top = max(0, y - padding)
            right = min(width, x + box_width + padding)
            bottom = min(height, y + box_height + padding)
            results.append(
                FireDetection(
                    bbox=(left, top, right - left, bottom - top),
                    confidence=confidence,
                    area=area,
                    center_x=round(center_x),
                    center_y=round(center_y),
                    frame_width=width,
                    frame_height=height,
                    kind="simulated_marker",
                )
            )
        return results


class FireConfirmationTracker:
    """Confirms a candidate only after several consecutive positive frames."""

    def __init__(
        self,
        required_frames: int = 3,
        confidence_threshold: float = 0.68,
        cooldown_seconds: float = 8.0,
    ) -> None:
        self.required_frames = required_frames
        self.confidence_threshold = confidence_threshold
        self.cooldown_seconds = cooldown_seconds
        self._streak = 0
        self._last_emitted_at = float("-inf")

    def update(
        self, detections: list[FireDetection], now: float | None = None
    ) -> FireDetection | None:
        timestamp = time.monotonic() if now is None else now
        top = detections[0] if detections else None
        if top and top.confidence >= self.confidence_threshold:
            self._streak += 1
        else:
            self._streak = max(0, self._streak - 1)
            return None

        if (
            self._streak >= self.required_frames
            and timestamp - self._last_emitted_at >= self.cooldown_seconds
        ):
            self._last_emitted_at = timestamp
            self._streak = 0
            return top
        return None


def annotate_fire_detections(
    frame: np.ndarray, detections: list[FireDetection]
) -> np.ndarray:
    annotated = frame.copy()
    for detection in detections:
        x, y, width, height = detection.bbox
        color = (45, 70, 255)
        cv2.rectangle(annotated, (x, y), (x + width, y + height), color, 3)
        prefix = "SIM FIRE" if detection.kind == "simulated_marker" else "FIRE"
        label = f"{prefix} {detection.confidence:.0%}"
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.82, 2
        )
        label_top = max(0, y - text_height - baseline - 10)
        cv2.rectangle(
            annotated,
            (x, label_top),
            (x + text_width + 16, y),
            (35, 45, 185),
            -1,
        )
        cv2.putText(
            annotated,
            label,
            (x + 8, y - 7),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.82,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.circle(
            annotated,
            (detection.center_x, detection.center_y),
            5,
            (70, 255, 255),
            -1,
        )
    return annotated
