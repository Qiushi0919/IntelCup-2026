from __future__ import annotations

import argparse
import math
import sys
import time

import cv2

from common import TemporalStabilizer
from model_assets import GESTURE_MODEL_URL, ensure_model


LABELS = {
    "Open_Palm": "Open Palm",
    "Closed_Fist": "Fist",
    "Thumb_Up": "Thumb Up",
    "UNKNOWN": "Unknown",
}
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


def draw_landmarks(frame, landmarks) -> None:
    height, width = frame.shape[:2]
    points = [
        (round(item.x * width), round(item.y * height))
        for item in landmarks
    ]
    for start, end in HAND_CONNECTIONS:
        cv2.line(
            frame,
            points[start],
            points[end],
            (80, 150, 255),
            2,
            cv2.LINE_AA,
        )
    for point in points:
        cv2.circle(frame, point, 4, (70, 220, 150), -1, cv2.LINE_AA)


def distance(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def classify_by_landmarks(landmarks) -> tuple[str, float]:
    """Geometry fallback for the three gestures used in this project."""

    wrist = landmarks[0]
    palm_size = max(distance(wrist, landmarks[9]), 1e-5)

    finger_tips = (8, 12, 16, 20)
    finger_pips = (6, 10, 14, 18)
    extended_fingers = 0
    folded_fingers = 0
    for tip_index, pip_index in zip(finger_tips, finger_pips):
        tip_distance = distance(wrist, landmarks[tip_index])
        pip_distance = distance(wrist, landmarks[pip_index])
        if tip_distance > pip_distance * 1.16:
            extended_fingers += 1
        if tip_distance < pip_distance * 1.05:
            folded_fingers += 1

    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]
    thumb_extended = distance(wrist, thumb_tip) > distance(wrist, thumb_ip) * 1.12
    thumb_away = distance(thumb_tip, index_mcp) > palm_size * 0.52
    palm_span = distance(landmarks[8], landmarks[20]) / palm_size

    if extended_fingers >= 3 and thumb_away and palm_span > 1.05:
        confidence = min(0.94, 0.72 + 0.06 * extended_fingers)
        return "Open_Palm", confidence

    if folded_fingers >= 3 and not thumb_away:
        confidence = min(0.93, 0.70 + 0.06 * folded_fingers)
        return "Closed_Fist", confidence

    thumb_to_finger_distance = min(
        distance(thumb_tip, landmarks[index])
        for index in (8, 12, 16, 20)
    )
    if thumb_extended and folded_fingers >= 3 and thumb_to_finger_distance > palm_size * 0.58:
        confidence = min(0.92, 0.70 + 0.06 * folded_fingers)
        return "Thumb_Up", confidence

    return "UNKNOWN", 0.0


def rotate_frame(frame, angle: int):
    if angle == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone three-gesture recognizer."
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--hold", type=float, default=0.55)
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.65,
        help="Minimum confidence required before a gesture can trigger.",
    )
    parser.add_argument(
        "--rotate",
        type=int,
        choices=(0, 90, 180, 270),
        default=0,
        help="Rotate the camera image clockwise before recognition.",
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
        ensure_model("gesture_recognizer.task", GESTURE_MODEL_URL)
    )
    options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.70,
        min_hand_presence_confidence=0.70,
        min_tracking_confidence=0.70,
    )

    capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not capture.isOpened():
        print(f"Cannot open camera {args.camera}", file=sys.stderr)
        return 3

    stabilizer = TemporalStabilizer(
        window_size=12,
        required_ratio=0.75,
        hold_seconds=args.hold,
    )
    last_trigger = "No confirmed gesture yet"
    last_trigger_at = 0.0
    trigger_visible_seconds = 3.0
    last_timestamp_ms = 0

    with mp.tasks.vision.GestureRecognizer.create_from_options(
        options
    ) as recognizer:
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
            result = recognizer.recognize_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                timestamp_ms,
            )

            raw_label, raw_confidence = "UNKNOWN", 0.0
            if result.hand_landmarks:
                hand_landmarks = result.hand_landmarks[0]
                draw_landmarks(frame, hand_landmarks)
                raw_label, raw_confidence = classify_by_landmarks(
                    hand_landmarks
                )
            if result.gestures and result.gestures[0]:
                category = result.gestures[0][0]
                if (
                    category.category_name in LABELS
                    and category.score >= args.min_confidence
                ):
                    raw_label = category.category_name
                    raw_confidence = category.score
                elif category.category_name in LABELS:
                    raw_confidence = max(raw_confidence, category.score)

            stable = stabilizer.update(raw_label, raw_confidence)
            if stable.triggered:
                last_trigger = (
                    f"TRIGGER: {LABELS[stable.label]} "
                    f"({stable.confidence:.0%})"
                )
                last_trigger_at = time.monotonic()
                print(last_trigger, flush=True)

            if time.monotonic() - last_trigger_at > trigger_visible_seconds:
                trigger_text = "No confirmed gesture yet"
                trigger_color = (170, 195, 215)
            else:
                trigger_text = last_trigger
                trigger_color = (80, 210, 255)

            stable_text = LABELS[stable.label]
            if stable.label != "UNKNOWN":
                stable_text += f"  {stable.stable_seconds:.1f}s"

            cv2.rectangle(frame, (18, 18), (650, 150), (8, 24, 38), -1)
            cv2.putText(
                frame,
                "GESTURE: OPEN PALM / FIST / THUMB UP",
                (34, 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.68,
                (225, 242, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"Raw: {LABELS[raw_label]}  {raw_confidence:.0%}",
                (34, 86),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (105, 204, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"Stable: {stable_text}",
                (34, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (91, 231, 175),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                trigger_text,
                (24, frame.shape[0] - 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.64,
                trigger_color,
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Three Gesture Recognition - Q to quit", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

    capture.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
