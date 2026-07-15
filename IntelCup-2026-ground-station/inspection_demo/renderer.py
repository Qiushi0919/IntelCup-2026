from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .engine import InspectionResult


FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def _font(size: int, bold: bool = False):
    candidates = (
        (Path("C:/Windows/Fonts/msyhbd.ttc"),) + FONT_CANDIDATES
        if bold
        else FONT_CANDIDATES
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    shortened = text
    while shortened and draw.textlength(shortened + "…", font=font) > max_width:
        shortened = shortened[:-1]
    return shortened + "…"


class InspectionRenderer:
    VIDEO_SIZE = (920, 560)
    PANEL_WIDTH = 360

    def __init__(self) -> None:
        self.title_font = _font(24, bold=True)
        self.section_font = _font(18, bold=True)
        self.body_font = _font(16)
        self.small_font = _font(14)

    @staticmethod
    def _draw_detections(
        frame: np.ndarray,
        result: InspectionResult,
        show_text_boxes: bool,
    ) -> np.ndarray:
        annotated = frame.copy()
        if show_text_boxes:
            for index, detection in enumerate(result.texts, start=1):
                if detection.polygon:
                    points = np.asarray(detection.polygon, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(annotated, [points], True, (80, 220, 120), 2, cv2.LINE_AA)
                x, y, _, _ = detection.bbox
                cv2.putText(
                    annotated,
                    f"TEXT-{index} {detection.confidence:.0%}",
                    (x, max(20, y - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (80, 220, 120),
                    2,
                    cv2.LINE_AA,
                )
        for detection in result.faces:
            x, y, width, height = detection.bbox
            cv2.rectangle(annotated, (x, y), (x + width, y + height), (255, 210, 60), 2)
            cv2.putText(
                annotated,
                f"FACE {detection.confidence:.0%}",
                (x, max(20, y - 7)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (255, 210, 60),
                2,
                cv2.LINE_AA,
            )
        for detection in result.fires:
            x, y, width, height = detection.bbox
            cv2.rectangle(annotated, (x, y), (x + width, y + height), (20, 80, 255), 3)
            cv2.putText(
                annotated,
                f"{detection.label} {detection.confidence:.0%}",
                (x, max(24, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (20, 80, 255),
                2,
                cv2.LINE_AA,
            )
        return annotated

    def render(
        self,
        frame: np.ndarray,
        result: InspectionResult,
        source_label: str,
        fps: float,
        enabled: dict[str, bool],
        events: list[str],
        show_text_boxes: bool = False,
    ) -> np.ndarray:
        annotated = self._draw_detections(frame, result, show_text_boxes)
        video_width, video_height = self.VIDEO_SIZE
        height, width = annotated.shape[:2]
        scale = min(video_width / width, video_height / height)
        resized = cv2.resize(
            annotated,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        canvas = np.full(
            (video_height, video_width + self.PANEL_WIDTH, 3),
            (20, 24, 31),
            dtype=np.uint8,
        )
        offset_x = (video_width - resized.shape[1]) // 2
        offset_y = (video_height - resized.shape[0]) // 2
        canvas[
            offset_y : offset_y + resized.shape[0],
            offset_x : offset_x + resized.shape[1],
        ] = resized

        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        draw = ImageDraw.Draw(image)
        panel_x = video_width + 20
        panel_right = video_width + self.PANEL_WIDTH - 18
        text_width = panel_right - panel_x

        draw.text((panel_x, 16), "飞行巡检识别 Demo", font=self.title_font, fill=(240, 245, 252))
        draw.text(
            (panel_x, 52),
            _fit_text(draw, source_label, self.small_font, text_width),
            font=self.small_font,
            fill=(150, 165, 185),
        )
        draw.text((panel_x, 76), f"画面 {fps:4.1f} FPS", font=self.body_font, fill=(190, 205, 220))

        rows = (
            ("人脸", len(result.faces), enabled["face"], (255, 215, 80)),
            ("文字", len(result.texts), enabled["text"], (90, 225, 130)),
            ("火源", len(result.fires), enabled["fire"], (255, 100, 65)),
        )
        y = 112
        for label, count, active, color in rows:
            fill = color if active else (95, 105, 120)
            draw.rounded_rectangle((panel_x, y, panel_right, y + 36), radius=8, fill=(38, 45, 57))
            draw.ellipse((panel_x + 10, y + 12, panel_x + 22, y + 24), fill=fill)
            state = f"{label}  {count}" if active else f"{label}  OFF"
            draw.text((panel_x + 32, y + 7), state, font=self.body_font, fill=(236, 240, 246))
            y += 44

        draw.text((panel_x, y + 3), "最近识别文字", font=self.section_font, fill=(236, 240, 246))
        y += 34
        if result.ocr_busy:
            draw.text((panel_x, y), "OCR 正在后台扫描…", font=self.small_font, fill=(100, 190, 255))
            y += 24
        if result.ocr_error:
            message = _fit_text(draw, "OCR错误：" + result.ocr_error, self.small_font, text_width)
            draw.text((panel_x, y), message, font=self.small_font, fill=(255, 115, 100))
            y += 24
        text_items = [item.text for item in result.texts]
        for item in text_items[:6]:
            line = _fit_text(draw, "• " + item, self.small_font, text_width)
            draw.text((panel_x, y), line, font=self.small_font, fill=(205, 218, 232))
            y += 23
        if not text_items and not result.ocr_busy and not result.ocr_error:
            draw.text((panel_x, y), "暂未识别到中英文", font=self.small_font, fill=(135, 150, 170))
            y += 23

        y = max(y + 10, 374)
        draw.text((panel_x, y), "最近事件", font=self.section_font, fill=(236, 240, 246))
        y += 30
        for event in events[:3]:
            line = _fit_text(draw, "• " + event, self.small_font, text_width)
            draw.text((panel_x, y), line, font=self.small_font, fill=(205, 218, 232))
            y += 23
        if not events:
            draw.text((panel_x, y), "等待巡检事件", font=self.small_font, fill=(135, 150, 170))

        timing = result.timings_ms
        footer = (
            f"人脸 {timing.get('face', 0):.0f}ms · 火源 {timing.get('fire', 0):.0f}ms · "
            f"OCR {timing.get('ocr', 0):.0f}ms"
        )
        draw.text((panel_x, 500), footer, font=self.small_font, fill=(120, 138, 158))
        draw.text(
            (panel_x, 526),
            "1人脸  2文字  3火源  O立即OCR  S截图  Q退出",
            font=self.small_font,
            fill=(170, 185, 202),
        )

        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower() or ".jpg"
    ok, encoded = cv2.imencode(suffix, image)
    if not ok:
        raise RuntimeError(f"无法编码截图：{path}")
    encoded.tofile(str(path))
