from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import time

import cv2

from .detectors import YuNetFaceDetector
from .engine import InspectionEngine
from .model_assets import ensure_yunet_model
from .renderer import InspectionRenderer, save_image
from .sources import OpenCVFrameSource


HERE = Path(__file__).resolve().parent
CAPTURE_DIR = HERE / "captures"
WINDOW_TITLE = "IntelCup Flight Inspection Demo"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="USB/RTSP camera demo for face, Chinese-English text and fire inspection."
    )
    parser.add_argument(
        "--source",
        default="0",
        help="USB camera index, image/video path, or RTSP URL (default: 0).",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--camera-fps", type=int, default=30)
    parser.add_argument("--no-face", action="store_true")
    parser.add_argument("--no-ocr", action="store_true")
    parser.add_argument("--no-fire", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=0.0)
    parser.add_argument("--save-output", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser


def _timestamped_capture(prefix: str = "inspection") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return CAPTURE_DIR / f"{prefix}_{stamp}.jpg"


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    model_path = ensure_yunet_model()
    face_detector = YuNetFaceDetector(model_path)
    engine = InspectionEngine(
        face_detector,
        enable_face=not args.no_face,
        enable_ocr=not args.no_ocr,
        enable_fire=not args.no_fire,
    )
    renderer = InspectionRenderer()
    source = OpenCVFrameSource(
        args.source,
        width=args.width,
        height=args.height,
        fps=args.camera_fps,
    )
    events: deque[str] = deque(maxlen=8)
    last_ocr_texts: tuple[str, ...] = ()
    last_canvas = None
    last_result = None
    frame_count = 0
    started = time.monotonic()
    previous_frame_at = started
    display_fps = 0.0
    consecutive_failures = 0

    try:
        source.open()
        print(f"SOURCE_OPENED {source.description}", flush=True)
        print("DETECTORS_READY face=YuNet ocr=RapidOCR fire=rule+3frame", flush=True)
        if not args.headless:
            cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_TITLE, 1280, 720)

        while True:
            ok, frame = source.read()
            if not ok or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= 30:
                    raise RuntimeError("视频源连续读取失败")
                time.sleep(0.03)
                continue
            consecutive_failures = 0
            now = time.monotonic()
            delta = max(1e-6, now - previous_frame_at)
            instant_fps = 1.0 / delta
            display_fps = (
                instant_fps
                if display_fps <= 0
                else display_fps * 0.90 + instant_fps * 0.10
            )
            previous_frame_at = now

            result = engine.process(frame, now)
            frame_count += 1
            if result.fire_event is not None:
                message = f"{datetime.now():%H:%M:%S} 火源确认 {result.fire_event.confidence:.0%}"
                events.appendleft(message)
                event_canvas = renderer.render(
                    frame,
                    result,
                    source.description,
                    display_fps,
                    engine.enabled,
                    list(events),
                    show_text_boxes=source.is_static_image,
                )
                capture_path = _timestamped_capture("fire")
                save_image(capture_path, event_canvas)
                print(
                    f"FIRE_CONFIRMED confidence={result.fire_event.confidence:.3f} "
                    f"capture={capture_path}",
                    flush=True,
                )

            current_texts = tuple(item.text for item in result.texts)
            if current_texts and current_texts != last_ocr_texts:
                events.appendleft(f"{datetime.now():%H:%M:%S} 文字：{' / '.join(current_texts[:2])}")
                last_ocr_texts = current_texts

            canvas = renderer.render(
                frame,
                result,
                source.description,
                display_fps,
                engine.enabled,
                list(events),
                show_text_boxes=source.is_static_image,
            )
            last_canvas, last_result = canvas, result

            elapsed = now - started
            reached_limit = (
                (args.max_frames > 0 and frame_count >= args.max_frames)
                or (args.max_seconds > 0 and elapsed >= args.max_seconds)
            )
            if args.headless and reached_limit:
                last_result = engine.wait_for_ocr()
                last_canvas = renderer.render(
                    frame,
                    last_result,
                    source.description,
                    display_fps,
                    engine.enabled,
                    list(events),
                    show_text_boxes=source.is_static_image,
                )
                break

            if not args.headless:
                cv2.imshow(WINDOW_TITLE, canvas)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
                if key == ord("1"):
                    engine.toggle("face")
                elif key == ord("2"):
                    engine.toggle("text")
                elif key == ord("3"):
                    engine.toggle("fire")
                elif key in (ord("o"), ord("O")):
                    engine.request_ocr()
                elif key in (ord("s"), ord("S")):
                    path = _timestamped_capture()
                    save_image(path, canvas)
                    events.appendleft(f"{datetime.now():%H:%M:%S} 已截图 {path.name}")
                    print(f"CAPTURE_SAVED {path}", flush=True)
                if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    break
            elif reached_limit:
                break
    finally:
        source.release()
        if engine.current_result().ocr_busy:
            print("OCR_STOPPING 正在等待本次文字扫描安全结束…", flush=True)
        engine.close()
        cv2.destroyAllWindows()

    if last_result is None or last_canvas is None:
        raise RuntimeError("没有生成有效识别结果")
    summary = {
        "source": source.description,
        "frames": frame_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "result": last_result.to_dict(),
    }
    if args.save_output:
        save_image(args.save_output, last_canvas)
        summary["saved_output"] = str(args.save_output.resolve())
    if args.json_output:
        _write_json(args.json_output, summary)
    # Keep the machine-readable console line safe on legacy Windows code pages.
    # The optional JSON file above still preserves the original Chinese text.
    print("INSPECTION_SUMMARY " + json.dumps(summary, ensure_ascii=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
