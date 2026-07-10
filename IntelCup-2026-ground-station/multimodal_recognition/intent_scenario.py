from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common import TemporalStabilizer, open_camera_capture
from gaze_three_point import (
    draw_eye_laser,
    estimate_head_pose,
    classify_head_direction,
    rotate_frame,
)
from gesture_three import LABELS, classify_by_landmarks, draw_landmarks
from model_assets import FACE_MODEL_URL, GESTURE_MODEL_URL, ensure_model


SCENARIOS = {
    "Open_Palm": {
        "title": "起飞",
        "display": "TAKEOFF",
        "gesture": "张开手掌",
        "gesture_display": "OPEN PALM",
        "options": [
            ("预热", "INFO_ACTION", "起飞前预热"),
            ("低空巡逻", "TAKEOFF", "低空巡逻"),
            ("定制航点", "TAKEOFF", "定制航点"),
        ],
    },
    "Closed_Fist": {
        "title": "自检",
        "display": "SELF_CHECK",
        "gesture": "握拳",
        "gesture_display": "FIST",
        "options": [
            ("姿态自检", "INFO_ACTION", "姿态自检"),
            ("参数自检", "INFO_ACTION", "参数自检"),
            ("摄像头状态", "INFO_ACTION", "摄像头状态检查"),
        ],
    },
    "Thumb_Up": {
        "title": "返航",
        "display": "RETURN_HOME",
        "gesture": "竖大拇指",
        "gesture_display": "THUMB UP",
        "options": [
            ("立即返航", "RTL", "立即返航"),
            ("10秒后返航", "INFO_ACTION", "10秒后返航"),
            ("日志输出", "INFO_ACTION", "日志输出"),
        ],
    },
}

REGIONS = ("LEFT", "CENTER", "RIGHT")
REGION_NAMES = {"LEFT": "左侧", "CENTER": "中间", "RIGHT": "右侧"}
GESTURE_REGIONS = {
    "LEFT": ("Closed_Fist", "握拳", "自检"),
    "CENTER": ("Open_Palm", "张开手掌", "起飞"),
    "RIGHT": ("Thumb_Up", "竖大拇指", "返航"),
}
GESTURE_REGION_BY_LABEL = {
    label: region for region, (label, _gesture, _title) in GESTURE_REGIONS.items()
}
GESTURE_NAMES = {
    "Open_Palm": "张开手掌",
    "Closed_Fist": "握拳",
    "Thumb_Up": "竖大拇指",
    "UNKNOWN": "未识别",
}
FONT_PATHS = (
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gesture-to-gaze multimodal intent scenario."
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument("--gesture-confidence", type=float, default=0.65)
    parser.add_argument("--gaze-confidence", type=float, default=0.62)
    parser.add_argument("--countdown", type=float, default=5.0)
    parser.add_argument("--head-threshold", type=float, default=0.14)
    parser.add_argument("--laser", action="store_true")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--preview-file", type=str, default="")
    parser.add_argument("--preview-interval", type=float, default=0.10)
    parser.add_argument("--gesture-model", type=str, default="")
    parser.add_argument("--face-model", type=str, default="")
    return parser.parse_args()


def put_text(
    frame,
    text: str,
    xy: tuple[int, int],
    scale: float = 0.72,
    color: tuple[int, int, int] = (235, 246, 255),
    thickness: int = 2,
) -> None:
    cv2.putText(
        frame,
        text,
        xy,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def put_cn(
    frame,
    text: str,
    xy: tuple[int, int],
    size: int = 26,
    color: tuple[int, int, int] = (235, 246, 255),
) -> None:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    draw.text(xy, text, font=load_font(size), fill=(color[2], color[1], color[0]))
    frame[:] = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def put_cn_overlay(
    frame,
    text: str,
    xy: tuple[int, int],
    size: int = 34,
    color: tuple[int, int, int] = (245, 250, 255),
    alpha: int = 210,
    bold: bool = False,
) -> None:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(size)
    x, y = xy
    shadow = (0, 0, 0, min(190, alpha))
    draw.text((x + 3, y + 3), text, font=font, fill=shadow)
    fill = (color[2], color[1], color[0], alpha)
    offsets = [(0, 0)]
    if bold:
        offsets += [(1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)]
    for dx, dy in offsets:
        draw.text((x + dx, y + dy), text, font=font, fill=fill)
    combined = Image.alpha_composite(image, overlay)
    frame[:] = cv2.cvtColor(np.array(combined.convert("RGB")), cv2.COLOR_RGB2BGR)


def draw_panel(frame, title: str, lines: list[str]) -> None:
    put_cn_overlay(frame, title, (34, 24), 44, (255, 246, 210), 230, True)
    y = 86
    for line in lines:
        put_cn_overlay(frame, line, (38, y), 30, (235, 248, 255), 205, True)
        y += 42


def draw_choice_regions(frame, scenario: dict, active_region: str, seconds: float) -> None:
    height, width = frame.shape[:2]
    options = scenario["options"]
    region_width = width // 3
    overlay = frame.copy()
    colors = {
        "LEFT": (70, 170, 230),
        "CENTER": (80, 220, 160),
        "RIGHT": (90, 140, 255),
    }
    progress = max(0.0, min(1.0, seconds / 5.0))
    remaining = max(0.0, 5.0 - seconds)
    for index, region in enumerate(REGIONS):
        left = index * region_width
        right = width if index == 2 else (index + 1) * region_width
        active = region == active_region
        fill = (18, 48, 72) if active else (7, 22, 36)
        border = colors[region] if active else (55, 86, 112)
        cv2.rectangle(overlay, (left + 8, 185), (right - 8, height - 76), fill, -1)
    cv2.addWeighted(overlay, 0.68, frame, 0.32, 0, frame)
    for index, region in enumerate(REGIONS):
        left = index * region_width
        right = width if index == 2 else (index + 1) * region_width
        active = region == active_region
        border = colors[region] if active else (55, 86, 112)
        top = 185
        bottom = height - 76
        cv2.rectangle(frame, (left + 8, top), (right - 8, bottom), border, 3)
        if active:
            bar_left = left + 18
            bar_right = right - 18
            bar_bottom = bottom - 16
            bar_top = bar_bottom - 12
            cv2.rectangle(frame, (bar_left, bar_top), (bar_right, bar_bottom), (30, 45, 56), -1)
            cv2.rectangle(
                frame,
                (bar_left, bar_top),
                (int(bar_left + (bar_right - bar_left) * progress), bar_bottom),
                border,
                -1,
            )
            center = (int((left + right) / 2), int((top + bottom) / 2 + 40))
            radius = 48
            cv2.circle(frame, center, radius, (40, 55, 65), 7, cv2.LINE_AA)
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                -90,
                0,
                int(progress * 360),
                border,
                8,
                cv2.LINE_AA,
            )
        name, _action, _label = options[index]
        put_cn_overlay(frame, REGION_NAMES[region], (left + 28, 202), 30, border, 220, True)
        put_cn_overlay(frame, name, (left + 28, 265), 42, (245, 250, 255), 230, True)
        if active:
            put_cn_overlay(
                frame,
                f"{remaining:.1f}",
                (int((left + right) / 2 - 42), int((top + bottom) / 2 + 6)),
                58,
                (255, 246, 160),
                230,
                True,
            )
            put_cn_overlay(
                frame,
                "秒后确认",
                (int((left + right) / 2 - 58), int((top + bottom) / 2 + 82)),
                27,
                (255, 246, 190),
                215,
                True,
            )
        else:
            put_cn_overlay(
                frame,
                "等待选择",
                (left + 28, bottom - 56),
                26,
                (180, 205, 225),
                165,
                True,
            )
    put_cn_overlay(
        frame,
        f"看左 / 中 / 右选择，保持 {seconds:.1f}/5.0 秒确认",
        (28, height - 52),
        30,
        (255, 240, 160),
        220,
        True,
    )


def draw_gesture_regions(frame, active_label: str, seconds: float, raw_text: str, confidence: float) -> None:
    height, width = frame.shape[:2]
    region_width = width // 3
    active_region = GESTURE_REGION_BY_LABEL.get(active_label, "")
    progress = max(0.0, min(1.0, seconds / 1.2))
    remaining = max(0.0, 1.2 - seconds)
    colors = {
        "LEFT": (70, 170, 230),
        "CENTER": (80, 220, 160),
        "RIGHT": (90, 140, 255),
    }
    overlay = frame.copy()
    for index, region in enumerate(REGIONS):
        left = index * region_width
        right = width if index == 2 else (index + 1) * region_width
        active = region == active_region
        fill = (18, 48, 72) if active else (7, 22, 36)
        cv2.rectangle(overlay, (left + 8, 170), (right - 8, height - 72), fill, -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)

    put_cn_overlay(frame, "第一步：用手势选择指令大类", (34, 24), 44, (255, 246, 210), 230, True)
    put_cn_overlay(
        frame,
        f"当前识别：{raw_text} {confidence:.0%}",
        (38, 82),
        30,
        (235, 248, 255),
        205,
        True,
    )
    for index, region in enumerate(REGIONS):
        left = index * region_width
        right = width if index == 2 else (index + 1) * region_width
        top = 170
        bottom = height - 72
        active = region == active_region
        border = colors[region] if active else (55, 86, 112)
        label, gesture, title = GESTURE_REGIONS[region]
        cv2.rectangle(frame, (left + 8, top), (right - 8, bottom), border, 3)
        put_cn_overlay(frame, REGION_NAMES[region], (left + 28, top + 22), 30, border, 220, True)
        put_cn_overlay(frame, gesture, (left + 28, top + 82), 39, (245, 250, 255), 230, True)
        put_cn_overlay(frame, f"→ {title}", (left + 28, top + 136), 42, (255, 246, 190), 230, True)
        if active:
            center = (int((left + right) / 2), int((top + bottom) / 2 + 58))
            radius = 48
            cv2.circle(frame, center, radius, (40, 55, 65), 7, cv2.LINE_AA)
            cv2.ellipse(
                frame,
                center,
                (radius, radius),
                -90,
                0,
                int(progress * 360),
                border,
                8,
                cv2.LINE_AA,
            )
            put_cn_overlay(
                frame,
                f"{remaining:.1f}",
                (center[0] - 42, center[1] - 35),
                58,
                (255, 246, 160),
                230,
                True,
            )
            put_cn_overlay(frame, "秒后选择", (center[0] - 62, center[1] + 42), 27, (255, 246, 190), 215, True)
        else:
            put_cn_overlay(frame, "等待手势", (left + 28, bottom - 54), 26, (180, 205, 225), 165, True)
    put_cn_overlay(
        frame,
        "保持对应手势，选择后直接进入视线三选一",
        (28, height - 52),
        30,
        (255, 240, 160),
        220,
        True,
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    args = parse_args()
    try:
        import mediapipe as mp
    except ImportError:
        print("Missing mediapipe. Please run install_multimodal_deps.bat first.", file=sys.stderr)
        return 2

    gesture_model = args.gesture_model or str(
        ensure_model("gesture_recognizer.task", GESTURE_MODEL_URL)
    )
    face_model = args.face_model or str(
        ensure_model("face_landmarker.task", FACE_MODEL_URL)
    )

    gesture_options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=gesture_model),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.70,
        min_hand_presence_confidence=0.70,
        min_tracking_confidence=0.70,
    )
    face_options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=face_model),
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

    mode = "GESTURE"
    scenario_key = ""
    scenario_started = 0.0
    latest_region = "CENTER"
    gaze_region_since = time.monotonic()
    smoothed_laser_target = None
    last_timestamp_ms = 0
    preview_path = Path(args.preview_file) if args.preview_file else None
    last_preview_at = 0.0
    gesture_stabilizer = TemporalStabilizer(
        window_size=12,
        required_ratio=0.75,
        hold_seconds=1.2,
    )
    gaze_stabilizer = TemporalStabilizer(
        window_size=14,
        required_ratio=0.72,
        hold_seconds=0.70,
        release_seconds=0.25,
    )

    with mp.tasks.vision.GestureRecognizer.create_from_options(
        gesture_options
    ) as gesture_recognizer, mp.tasks.vision.FaceLandmarker.create_from_options(
        face_options
    ) as face_landmarker:
        while True:
            ok, frame = capture.read()
            if not ok:
                continue
            frame = rotate_frame(frame, args.rotate)
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = max(last_timestamp_ms + 1, int(time.monotonic() * 1000))
            last_timestamp_ms = timestamp_ms

            if mode == "GESTURE":
                result = gesture_recognizer.recognize_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                    timestamp_ms,
                )
                raw_label, raw_confidence = "UNKNOWN", 0.0
                if result.hand_landmarks:
                    hand_landmarks = result.hand_landmarks[0]
                    draw_landmarks(frame, hand_landmarks)
                    raw_label, raw_confidence = classify_by_landmarks(hand_landmarks)
                if result.gestures and result.gestures[0]:
                    category = result.gestures[0][0]
                    if (
                        category.category_name in LABELS
                        and category.score >= args.gesture_confidence
                    ):
                        raw_label = category.category_name
                        raw_confidence = category.score
                    elif category.category_name in LABELS:
                        raw_confidence = max(raw_confidence, category.score)
                stable = gesture_stabilizer.update(raw_label, raw_confidence)
                if stable.triggered and stable.label in SCENARIOS:
                    scenario_key = stable.label
                    scenario_started = time.monotonic()
                    gaze_stabilizer = TemporalStabilizer(
                        window_size=14,
                        required_ratio=0.72,
                        hold_seconds=0.70,
                        release_seconds=0.25,
                    )
                    mode = "GAZE"
                    latest_region = "CENTER"
                    gaze_region_since = time.monotonic()
                    smoothed_laser_target = None
                    scenario = SCENARIOS[scenario_key]
                    print(
                        f"SCENARIO_STAGE: group={scenario['display']} "
                        f"label={scenario['title']} "
                        f"confidence={stable.confidence:.2f}",
                        flush=True,
                    )
                    print(
                        f"SCENARIO_STAGE: gaze_group={scenario['display']} "
                        f"label={scenario['title']}",
                        flush=True,
                    )
                raw_text = GESTURE_NAMES.get(raw_label, "未识别")
                draw_gesture_regions(
                    frame,
                    stable.label if stable.label in SCENARIOS else raw_label,
                    stable.stable_seconds if stable.label in SCENARIOS else 0.0,
                    raw_text,
                    raw_confidence,
                )

            elif mode == "COUNTDOWN":
                scenario = SCENARIOS[scenario_key]
                remaining = max(0.0, args.countdown - (time.monotonic() - scenario_started))
                if remaining <= 0.20:
                    mode = "GAZE"
                    gaze_region_since = time.monotonic()
                    smoothed_laser_target = None
                    print(
                        f"SCENARIO_STAGE: gaze_group={scenario['display']} "
                        f"label={scenario['title']}",
                        flush=True,
                    )
                    draw_choice_regions(frame, scenario, latest_region, 0.0)
                    draw_panel(
                        frame,
                        f"第三步：用视线选择「{scenario['title']}」选项",
                        [
                            "三个选项已出现",
                            "识别到脸后会显示眼神瞄准激光",
                            "看左 / 中 / 右并保持 5 秒确认",
                        ],
                    )
                else:
                    draw_panel(
                        frame,
                        f"第二步：已选择「{scenario['title']}」",
                        [
                            f"手势：{scenario['gesture']}",
                            f"视线选择将在 {remaining:.1f} 秒后开始",
                            "倒计时结束后看左 / 中 / 右选择",
                        ],
                    )
                    put_text(
                        frame,
                        f"{remaining:.1f}",
                        (frame.shape[1] // 2 - 70, frame.shape[0] // 2 + 45),
                        3.0,
                        (80, 220, 255),
                        5,
                    )

            else:
                scenario = SCENARIOS[scenario_key]
                result = face_landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                    timestamp_ms,
                )
                raw_label, confidence = "UNKNOWN", 0.0
                face_landmarks_for_laser = None
                relative_pitch = 0.0
                if result.face_landmarks:
                    face_landmarks = result.face_landmarks[0]
                    face_landmarks_for_laser = face_landmarks
                    yaw, relative_pitch = estimate_head_pose(face_landmarks)
                    raw_label, confidence = classify_head_direction(
                        yaw,
                        args.head_threshold,
                    )
                if confidence < args.gaze_confidence:
                    raw_label = "UNKNOWN"
                stable = gaze_stabilizer.update(raw_label, confidence)
                active_label = stable.label if stable.label in REGIONS else raw_label
                if active_label in REGIONS:
                    if active_label != latest_region:
                        latest_region = active_label
                        gaze_region_since = time.monotonic()
                    active_seconds = time.monotonic() - gaze_region_since
                else:
                    active_seconds = 0.0
                draw_choice_regions(
                    frame,
                    scenario,
                    latest_region,
                    active_seconds,
                )
                if args.laser and face_landmarks_for_laser is not None:
                    smoothed_laser_target = draw_eye_laser(
                        frame,
                        face_landmarks_for_laser,
                        latest_region,
                        relative_pitch,
                        smoothed_laser_target,
                        0.45,
                        0.18,
                        0.40,
                    )
                draw_panel(
                    frame,
                    f"第三步：用视线选择「{scenario['title']}」选项",
                    [
                        "看左 / 中 / 右任一区域",
                        f"当前视线：{REGION_NAMES.get(raw_label, '未锁定')} {confidence:.0%}",
                        f"当前区域：{REGION_NAMES.get(latest_region, '未锁定')} {active_seconds:.1f}/5.0 秒",
                    ],
                )
                if active_seconds >= 5.0 and latest_region in REGIONS:
                    index = REGIONS.index(latest_region)
                    option, action, label = scenario["options"][index]
                    print(
                        "SCENARIO_RESULT: "
                        f"group={scenario['display']} "
                        f"group_label={scenario['title']} "
                        f"region={latest_region} "
                        f"option={option} "
                        f"action={action} "
                        f"label={label} "
                        f"confidence={max(confidence, stable.confidence):.2f}",
                        flush=True,
                    )
                    mode = "GESTURE"
                    scenario_key = ""
                    latest_region = "CENTER"
                    gaze_region_since = time.monotonic()
                    smoothed_laser_target = None
                    gesture_stabilizer = TemporalStabilizer(
                        window_size=12,
                        required_ratio=0.75,
                        hold_seconds=1.2,
                    )

            now = time.monotonic()
            if preview_path and now - last_preview_at >= args.preview_interval:
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(preview_path), frame)
                last_preview_at = now

            if not args.no_window:
                cv2.imshow("手势+视线意图识别 - 按 Q 退出", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("r"):
                    mode = "GESTURE"
                    scenario_key = ""
                    latest_region = "CENTER"

    capture.release()
    if not args.no_window:
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
