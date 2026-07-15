from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
import statistics
import sys
import time

import cv2

from common import TemporalStabilizer, open_camera_capture
from model_assets import FACE_MODEL_URL, ensure_model


POINTS = ("LEFT", "CENTER", "RIGHT")
POINT_NAMES = {"LEFT": "Left", "CENTER": "Center", "RIGHT": "Right"}
LEFT_IRIS = (468, 469, 470, 471, 472)
RIGHT_IRIS = (473, 474, 475, 476, 477)
LEFT_CORNERS = (33, 133)
RIGHT_CORNERS = (362, 263)
LEFT_LIDS = (159, 145)
RIGHT_LIDS = (386, 374)
GAZE_X_MAP = {"LEFT": 0.15, "CENTER": 0.50, "RIGHT": 0.85}


def rotate_frame(frame, angle: int):
    if angle == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def average_x(landmarks, indexes) -> float:
    return sum(landmarks[index].x for index in indexes) / len(indexes)


def average_point(landmarks, indexes) -> tuple[float, float]:
    x = sum(landmarks[index].x for index in indexes) / len(indexes)
    y = sum(landmarks[index].y for index in indexes) / len(indexes)
    return x, y


def eye_ratio(landmarks, iris_indexes, corner_indexes) -> float:
    iris_x = average_x(landmarks, iris_indexes)
    corner_x = [landmarks[index].x for index in corner_indexes]
    left, right = min(corner_x), max(corner_x)
    return (iris_x - left) / max(right - left, 1e-5)


def eye_open_ratio(landmarks, corners, lids) -> float:
    width = abs(landmarks[corners[0]].x - landmarks[corners[1]].x)
    height = abs(landmarks[lids[0]].y - landmarks[lids[1]].y)
    return height / max(width, 1e-5)


def extract_gaze_ratio(landmarks) -> tuple[float | None, str]:
    left_open = eye_open_ratio(landmarks, LEFT_CORNERS, LEFT_LIDS)
    right_open = eye_open_ratio(landmarks, RIGHT_CORNERS, RIGHT_LIDS)
    if min(left_open, right_open) < 0.10:
        return None, "open eyes"

    left_ratio = eye_ratio(landmarks, LEFT_IRIS, LEFT_CORNERS)
    right_ratio = eye_ratio(landmarks, RIGHT_IRIS, RIGHT_CORNERS)
    if not (0.02 <= left_ratio <= 0.98 and 0.02 <= right_ratio <= 0.98):
        return None, "unstable eyes"
    if abs(left_ratio - right_ratio) > 0.18:
        return None, "eyes mismatch"
    return (left_ratio + right_ratio) / 2, "valid"


def estimate_head_pose(landmarks) -> tuple[float, float]:
    """Return rough normalized yaw and pitch from face landmarks."""

    face_left = landmarks[234].x
    face_right = landmarks[454].x
    face_top = landmarks[10].y
    face_bottom = landmarks[152].y
    face_center_x = (face_left + face_right) / 2
    face_center_y = (face_top + face_bottom) / 2
    face_width = max(face_right - face_left, 1e-5)
    face_height = max(face_bottom - face_top, 1e-5)
    nose = landmarks[1]
    yaw = (nose.x - face_center_x) / face_width
    pitch = (nose.y - face_center_y) / face_height
    return yaw, pitch


def classify_head_direction(
    yaw: float,
    head_threshold: float,
) -> tuple[str, float]:
    if yaw <= -head_threshold:
        confidence = min(0.98, 0.68 + abs(yaw) * 1.8)
        return "LEFT", confidence
    if yaw >= head_threshold:
        confidence = min(0.98, 0.68 + abs(yaw) * 1.8)
        return "RIGHT", confidence
    center_confidence = max(0.55, 1.0 - abs(yaw) / max(head_threshold, 1e-5))
    return "CENTER", min(0.90, center_confidence)


def fuse_head_and_gaze(
    head_label: str,
    head_confidence: float,
    gaze_label: str,
    gaze_confidence: float,
    head_priority: float,
) -> tuple[str, float, str]:
    if gaze_label == "UNKNOWN":
        return head_label, head_confidence, "HEAD"

    scores = {point: 0.0 for point in POINTS}
    if head_label in scores:
        scores[head_label] += head_confidence * head_priority
    if gaze_label in scores:
        scores[gaze_label] += gaze_confidence * (1.0 - head_priority)
    label = max(scores, key=scores.get)
    confidence = min(0.99, scores[label])
    source = "HEAD+GAZE"
    if head_label == "CENTER" and gaze_label != "CENTER":
        source = "GAZE"
    return label, confidence, source


class HeadMotionDetector:
    def __init__(
        self,
        window_seconds: float = 1.15,
        cooldown_seconds: float = 1.1,
    ) -> None:
        self.samples: deque[tuple[float, float, float]] = deque()
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.last_trigger_at = 0.0

    def update(self, yaw: float, pitch: float) -> str | None:
        now = time.monotonic()
        self.samples.append((now, yaw, pitch))
        while self.samples and now - self.samples[0][0] > self.window_seconds:
            self.samples.popleft()
        if now - self.last_trigger_at < self.cooldown_seconds:
            return None
        if len(self.samples) < 8:
            return None

        yaw_values = [item[1] for item in self.samples]
        pitch_values = [item[2] for item in self.samples]
        yaw_range = max(yaw_values) - min(yaw_values)
        pitch_range = max(pitch_values) - min(pitch_values)

        if (
            yaw_range > 0.18
            and max(yaw_values) > 0.07
            and min(yaw_values) < -0.07
        ):
            self.last_trigger_at = now
            return "CANCEL"
        if (
            pitch_range > 0.10
            and max(pitch_values) > 0.04
            and min(pitch_values) < -0.04
        ):
            self.last_trigger_at = now
            return "CONFIRM"
        return None


def point_to_pixel(
    frame,
    point: tuple[float, float],
) -> tuple[int, int]:
    height, width = frame.shape[:2]
    return (
        int(max(0, min(width - 1, point[0] * width))),
        int(max(0, min(height - 1, point[1] * height))),
    )


def interpolate_target_x(
    ratio: float,
    calibration: "ThreePointCalibration",
    width: int,
) -> int:
    if calibration.calibrated:
        pairs = sorted(
            (calibration.values[point], GAZE_X_MAP[point])
            for point in POINTS
        )
        if ratio <= pairs[0][0]:
            x_norm = pairs[0][1]
        elif ratio >= pairs[-1][0]:
            x_norm = pairs[-1][1]
        else:
            x_norm = pairs[1][1]
            for (left_ratio, left_x), (right_ratio, right_x) in zip(
                pairs,
                pairs[1:],
            ):
                if left_ratio <= ratio <= right_ratio:
                    span = max(right_ratio - left_ratio, 1e-5)
                    t = (ratio - left_ratio) / span
                    x_norm = left_x + (right_x - left_x) * t
                    break
    else:
        x_norm = 0.15 + max(0.0, min(1.0, ratio)) * 0.70
    return int(max(0, min(width - 1, x_norm * width)))


def label_target_x(label: str, width: int) -> int | None:
    if label not in GAZE_X_MAP:
        return None
    return int(max(0, min(width - 1, GAZE_X_MAP[label] * width)))


def draw_eye_laser(
    frame,
    landmarks,
    label: str,
    relative_pitch: float,
    smoothed_target: tuple[float, float] | None,
    strength: float,
    base_offset: float,
    vertical_scale: float,
) -> tuple[float, float] | None:
    height, width = frame.shape[:2]
    target_x = label_target_x(label, width)
    if target_x is None:
        return smoothed_target

    left_eye = point_to_pixel(frame, average_point(landmarks, LEFT_IRIS))
    right_eye = point_to_pixel(frame, average_point(landmarks, RIGHT_IRIS))
    eye_mid_y = (left_eye[1] + right_eye[1]) / 2
    vertical_offset = height * (base_offset + relative_pitch * vertical_scale)
    raw_target = (
        target_x,
        int(max(height * 0.10, min(height * 0.90, eye_mid_y + vertical_offset))),
    )

    if smoothed_target is None:
        target = (float(raw_target[0]), float(raw_target[1]))
    else:
        alpha = max(0.05, min(0.95, strength))
        target = (
            smoothed_target[0] * (1 - alpha) + raw_target[0] * alpha,
            smoothed_target[1] * (1 - alpha) + raw_target[1] * alpha,
        )

    target_px = (int(target[0]), int(target[1]))
    overlay = frame.copy()
    beam_color = (20, 20, 255)
    glow_color = (55, 85, 255)
    for eye in (left_eye, right_eye):
        cv2.line(overlay, eye, target_px, glow_color, 14, cv2.LINE_AA)
        cv2.line(overlay, eye, target_px, beam_color, 4, cv2.LINE_AA)
        cv2.circle(overlay, eye, 9, (40, 40, 255), -1, cv2.LINE_AA)
        cv2.circle(overlay, eye, 15, (70, 90, 255), 2, cv2.LINE_AA)
    cv2.circle(overlay, target_px, 16, glow_color, 3, cv2.LINE_AA)
    cv2.circle(overlay, target_px, 5, beam_color, -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.58, frame, 0.42, 0, frame)
    return target


class ThreePointCalibration:
    def __init__(
        self,
        sample_count: int = 36,
        path: Path | None = None,
    ) -> None:
        self.sample_count = sample_count
        self.path = path
        self.values: dict[str, float] = {}
        self.current_index = 0
        self.collecting = False
        self.samples: list[float] = []

    @property
    def current_point(self) -> str:
        return POINTS[min(self.current_index, len(POINTS) - 1)]

    @property
    def calibrated(self) -> bool:
        return all(point in self.values for point in POINTS)

    def start_collection(self) -> None:
        if self.calibrated:
            return
        self.samples = []
        self.collecting = True

    def add(self, value: float) -> bool:
        if not self.collecting:
            return False
        self.samples.append(value)
        if len(self.samples) < self.sample_count:
            return False
        ordered = sorted(self.samples)
        trim = max(2, len(ordered) // 8)
        robust = ordered[trim:-trim]
        self.values[self.current_point] = statistics.median(robust)
        self.collecting = False
        self.current_index += 1
        if self.calibrated:
            self.save()
        return True

    def classify(self, value: float) -> tuple[str, float]:
        if not self.calibrated:
            return "UNKNOWN", 0.0
        label = min(
            POINTS,
            key=lambda point: abs(value - self.values[point]),
        )
        ordered = sorted(self.values.values())
        separation = max(
            min(
                abs(ordered[1] - ordered[0]),
                abs(ordered[2] - ordered[1]),
            ),
            0.02,
        )
        distance = abs(value - self.values[label])
        confidence = max(0.0, min(0.99, 1.0 - distance / separation))
        return label, confidence

    def reset(self) -> None:
        self.values = {}
        self.current_index = 0
        self.collecting = False
        self.samples = []

    def save(self) -> None:
        if self.path and self.calibrated:
            self.path.write_text(
                json.dumps(self.values, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load(self) -> bool:
        if not self.path or not self.path.exists():
            return False
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not all(point in data for point in POINTS):
            return False
        self.values = {point: float(data[point]) for point in POINTS}
        self.current_index = len(POINTS)
        return True


def draw_target(frame, point: str, collecting: bool) -> None:
    width, height = frame.shape[1], frame.shape[0]
    center = (int(width * GAZE_X_MAP[point]), int(height * 0.50))
    color = (45, 65, 255) if collecting else (65, 190, 255)
    cv2.circle(frame, center, 22, color, -1, cv2.LINE_AA)
    cv2.circle(frame, center, 34, (235, 245, 255), 2, cv2.LINE_AA)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrated left/center/right gaze recognizer."
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--samples", type=int, default=36)
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.62,
        help="Minimum confidence required before a gaze direction can trigger.",
    )
    parser.add_argument(
        "--head-threshold",
        type=float,
        default=0.075,
        help="Head yaw threshold for LEFT/RIGHT direction.",
    )
    parser.add_argument(
        "--head-priority",
        type=float,
        default=0.72,
        help="Fusion weight of head direction versus eye gaze.",
    )
    parser.add_argument(
        "--rotate",
        type=int,
        choices=(0, 90, 180, 270),
        default=0,
        help="Rotate the camera image clockwise before recognition.",
    )
    parser.add_argument(
        "--laser",
        action="store_true",
        help="Draw red eye-laser beams following the final head/gaze result.",
    )
    parser.add_argument(
        "--laser-strength",
        type=float,
        default=0.35,
        help="Laser target smoothing strength, 0.05-0.95.",
    )
    parser.add_argument(
        "--laser-base-offset",
        type=float,
        default=0.08,
        help="Neutral laser vertical offset from eye height.",
    )
    parser.add_argument(
        "--laser-vertical-scale",
        type=float,
        default=1.15,
        help="How strongly the laser follows relative head up/down motion.",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path(__file__).with_name("gaze_calibration.json"),
    )
    parser.add_argument("--model", type=str, default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import mediapipe as mp
    except ImportError:
        print(
            "Missing mediapipe. Please run install_multimodal_deps.bat first.",
            file=sys.stderr,
        )
        return 2

    model_path = args.model or str(
        ensure_model("face_landmarker.task", FACE_MODEL_URL)
    )
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.70,
        min_face_presence_confidence=0.70,
        min_tracking_confidence=0.70,
    )

    capture, camera_index, backend_name = open_camera_capture(
        args.camera, args.width, args.height
    )
    if capture is None:
        print(
            "未检测到可用摄像头。请重新插拔 USB 摄像头，确认 Windows 相机应用能打开，"
            "并关闭其它占用摄像头的软件。",
            file=sys.stderr,
        )
        return 3
    print(f"CAMERA_OPENED index={camera_index} backend={backend_name}", flush=True)

    calibration = ThreePointCalibration(args.samples, args.calibration)
    calibration.load()
    stabilizer = TemporalStabilizer(
        window_size=14,
        required_ratio=0.72,
        hold_seconds=0.45,
        release_seconds=0.25,
    )
    latest_message = "Press R to recalibrate; Q to quit"
    last_timestamp_ms = 0
    laser_target: tuple[float, float] | None = None
    motion_detector = HeadMotionDetector()
    head_label, head_confidence = "UNKNOWN", 0.0
    yaw, pitch = 0.0, 0.0
    neutral_pitch: float | None = None
    relative_pitch = 0.0
    motion_label = ""

    with mp.tasks.vision.FaceLandmarker.create_from_options(
        options
    ) as face_landmarker:
        while True:
            ok, frame = capture.read()
            if not ok:
                continue
            frame = rotate_frame(frame, args.rotate)
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = max(
                last_timestamp_ms + 1,
                int(time.monotonic() * 1000),
            )
            last_timestamp_ms = timestamp_ms
            result = face_landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                timestamp_ms,
            )
            ratio, quality = None, "no face"
            raw_label, confidence = "UNKNOWN", 0.0
            source = "NONE"
            stable = None

            if result.face_landmarks:
                face_landmarks = result.face_landmarks[0]
                yaw, pitch = estimate_head_pose(face_landmarks)
                if neutral_pitch is None:
                    neutral_pitch = pitch
                    latest_message = "Neutral head pitch captured"
                elif abs(yaw) < args.head_threshold * 0.55:
                    neutral_pitch = neutral_pitch * 0.985 + pitch * 0.015
                relative_pitch = pitch - neutral_pitch
                head_label, head_confidence = classify_head_direction(
                    yaw,
                    args.head_threshold,
                )
                motion = motion_detector.update(yaw, pitch)
                if motion:
                    motion_label = motion
                    latest_message = (
                        "HEAD MOTION: nod confirm"
                        if motion == "CONFIRM"
                        else "HEAD MOTION: shake cancel"
                    )
                    print(motion_label, flush=True)
                ratio, quality = extract_gaze_ratio(
                    face_landmarks
                )
            else:
                laser_target = None
                head_label, head_confidence = "UNKNOWN", 0.0
                yaw, pitch = 0.0, 0.0
                relative_pitch = 0.0
                motion_label = ""

            if not calibration.calibrated:
                draw_target(
                    frame,
                    calibration.current_point,
                    calibration.collecting,
                )
                if calibration.collecting and ratio is not None:
                    if calibration.add(ratio):
                        previous = POINTS[calibration.current_index - 1]
                        latest_message = (
                            f"{POINT_NAMES[previous]} point collected"
                        )
            elif ratio is not None:
                gaze_label, gaze_confidence = calibration.classify(ratio)
                if gaze_confidence < args.min_confidence:
                    gaze_label = "UNKNOWN"
                raw_label, confidence, source = fuse_head_and_gaze(
                    head_label,
                    head_confidence,
                    gaze_label,
                    gaze_confidence,
                    args.head_priority,
                )
                if confidence < args.min_confidence:
                    raw_label = "UNKNOWN"
                stable = stabilizer.update(raw_label, confidence)
                if stable.triggered:
                    latest_message = (
                        f"{source}: {stable.label} "
                        f"({stable.confidence:.0%})"
                    )
                    print(latest_message, flush=True)
            else:
                if head_label in POINTS:
                    raw_label = head_label
                    confidence = head_confidence
                    source = "HEAD"
                stable = stabilizer.update(raw_label, confidence)
                if stable.triggered:
                    latest_message = (
                        f"{source}: {stable.label} "
                        f"({stable.confidence:.0%})"
                    )
                    print(latest_message, flush=True)

            if args.laser and result.face_landmarks:
                if raw_label in POINTS:
                    laser_label = raw_label
                elif stable and stable.label in POINTS:
                    laser_label = stable.label
                else:
                    laser_label = head_label
                laser_target = draw_eye_laser(
                    frame,
                    face_landmarks,
                    laser_label,
                    relative_pitch,
                    laser_target,
                    args.laser_strength,
                    args.laser_base_offset,
                    args.laser_vertical_scale,
                )

            cv2.rectangle(frame, (18, 18), (760, 194), (8, 24, 38), -1)
            cv2.putText(
                frame,
                "HEAD + GAZE: LEFT / CENTER / RIGHT",
                (34, 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.68,
                (225, 242, 255),
                2,
                cv2.LINE_AA,
            )
            if not calibration.calibrated:
                point = calibration.current_point
                progress = len(calibration.samples)
                instruction = (
                    f"Look at {point}, press SPACE "
                    f"({progress}/{calibration.sample_count})"
                )
                cv2.putText(
                    frame,
                    instruction,
                    (34, 86),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.66,
                    (80, 210, 255),
                    2,
                    cv2.LINE_AA,
                )
            else:
                stable_label = stable.label if stable else "UNKNOWN"
                raw_text = (
                    f"Raw: {raw_label} {confidence:.0%} [{source}]  "
                    f"Stable: {stable_label}"
                )
                cv2.putText(
                    frame,
                    raw_text,
                    (34, 86),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.66,
                    (91, 231, 175),
                    2,
                    cv2.LINE_AA,
                )
            cv2.putText(
                frame,
                f"Head: {head_label} {head_confidence:.0%}  "
                f"Pitch: {pitch:+.2f}/{relative_pitch:+.2f}  Eye: {quality}",
                (34, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (170, 195, 215),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                latest_message,
                (34, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 198, 100),
                2,
                cv2.LINE_AA,
            )
            if motion_label:
                cv2.putText(
                    frame,
                    f"Motion: {motion_label}",
                    (34, 180),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.60,
                    (80, 210, 255),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow("Head + Gaze Recognition - Q to quit", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                calibration.reset()
                latest_message = "Calibration reset"
            if key == ord("c"):
                neutral_pitch = pitch if result.face_landmarks else None
                laser_target = None
                latest_message = "Neutral head pitch reset"
            if key == ord(" ") and not calibration.calibrated:
                calibration.start_collection()
                latest_message = (
                    f"Collecting {POINT_NAMES[calibration.current_point]} "
                    "point, keep your head still"
                )

    capture.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
