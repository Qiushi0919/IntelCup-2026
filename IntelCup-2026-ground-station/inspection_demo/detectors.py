from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time

import cv2
import numpy as np


GROUND_STATION_DIR = Path(__file__).resolve().parents[1] / "ground_station"
if str(GROUND_STATION_DIR) not in sys.path:
    sys.path.insert(0, str(GROUND_STATION_DIR))

from fire_detector import FireConfirmationTracker, FireDetector  # noqa: E402


@dataclass(frozen=True)
class InspectionDetection:
    kind: str
    bbox: tuple[int, int, int, int]
    confidence: float
    label: str
    text: str = ""
    polygon: tuple[tuple[int, int], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "bbox": list(self.bbox),
            "confidence": round(self.confidence, 4),
            "label": self.label,
            "text": self.text,
            "polygon": [list(point) for point in self.polygon],
        }


class YuNetFaceDetector:
    def __init__(
        self,
        model_path: Path,
        score_threshold: float = 0.72,
        max_input_width: int = 640,
    ) -> None:
        self.max_input_width = max_input_width
        self.detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            (320, 320),
            score_threshold,
            0.30,
            5000,
        )

    def detect(self, frame: np.ndarray) -> list[InspectionDetection]:
        height, width = frame.shape[:2]
        scale = min(1.0, self.max_input_width / max(1, width))
        if scale < 1.0:
            work = cv2.resize(
                frame,
                (round(width * scale), round(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            work = frame
        work_height, work_width = work.shape[:2]
        self.detector.setInputSize((work_width, work_height))
        _, faces = self.detector.detect(work)
        if faces is None:
            return []

        inverse = 1.0 / scale
        results: list[InspectionDetection] = []
        for face in faces:
            x, y, box_width, box_height = face[:4]
            left = max(0, round(x * inverse))
            top = max(0, round(y * inverse))
            right = min(width, round((x + box_width) * inverse))
            bottom = min(height, round((y + box_height) * inverse))
            if right <= left or bottom <= top:
                continue
            results.append(
                InspectionDetection(
                    kind="face",
                    bbox=(left, top, right - left, bottom - top),
                    confidence=float(face[-1]),
                    label="FACE",
                )
            )
        return results


class OpenVinoNpuFaceDetector:
    """Static-shape SSD face detector compiled for Intel AI Boost."""

    def __init__(
        self,
        model_path: Path,
        score_threshold: float = 0.68,
        device: str = "NPU",
    ) -> None:
        import openvino as ov

        self.score_threshold = score_threshold
        self.device = device
        self.core = ov.Core()
        if device not in self.core.available_devices:
            raise RuntimeError(
                f"OpenVINO未发现{device}，当前设备：{self.core.available_devices}"
            )
        cache_dir = model_path.parent / ".npu_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        model = self.core.read_model(str(model_path))
        self.compiled_model = self.core.compile_model(
            model,
            device,
            {"CACHE_DIR": str(cache_dir)},
        )
        self.input_port = self.compiled_model.input(0)
        self.output_port = self.compiled_model.output(0)
        input_shape = tuple(int(value) for value in self.input_port.shape)
        if input_shape != (1, 3, 300, 300):
            raise RuntimeError(f"不支持的人脸模型输入形状：{input_shape}")

    def detect(self, frame: np.ndarray) -> list[InspectionDetection]:
        height, width = frame.shape[:2]
        resized = cv2.resize(frame, (300, 300), interpolation=cv2.INTER_LINEAR)
        tensor = np.transpose(resized, (2, 0, 1))[None, ...].astype(
            np.float32,
            copy=False,
        )
        output = self.compiled_model([tensor])[self.output_port]
        detections: list[InspectionDetection] = []
        for row in output.reshape(-1, 7):
            image_id, _label, confidence, x_min, y_min, x_max, y_max = row
            if image_id < 0:
                break
            confidence = float(confidence)
            if confidence < self.score_threshold:
                continue
            left = max(0, min(width - 1, round(float(x_min) * width)))
            top = max(0, min(height - 1, round(float(y_min) * height)))
            right = max(0, min(width, round(float(x_max) * width)))
            bottom = max(0, min(height, round(float(y_max) * height)))
            if right <= left or bottom <= top:
                continue
            detections.append(
                InspectionDetection(
                    kind="face",
                    bbox=(left, top, right - left, bottom - top),
                    confidence=confidence,
                    label="FACE/NPU",
                )
            )
        return detections


class RapidOcrDetector:
    def __init__(self, min_score: float = 0.52, max_input_side: int = 640) -> None:
        self.min_score = min_score
        self.max_input_side = max_input_side
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from rapidocr import RapidOCR

            self._engine = RapidOCR(
                params={
                    "EngineConfig.onnxruntime.intra_op_num_threads": 4,
                    "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                    "Global.log_level": "warning",
                }
            )
        return self._engine

    @staticmethod
    def _extract_output(result) -> tuple[object, object, object]:
        boxes = getattr(result, "boxes", None)
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        if boxes is not None and texts is not None:
            return boxes, texts, scores
        if isinstance(result, (tuple, list)) and result:
            rows = result[0] if len(result) == 2 and isinstance(result[0], list) else result
            parsed_boxes, parsed_texts, parsed_scores = [], [], []
            for row in rows or []:
                if len(row) < 3:
                    continue
                parsed_boxes.append(row[0])
                parsed_texts.append(row[1])
                parsed_scores.append(row[2])
            return parsed_boxes, parsed_texts, parsed_scores
        return [], [], []

    def detect(self, frame: np.ndarray) -> list[InspectionDetection]:
        height, width = frame.shape[:2]
        longest = max(height, width)
        scale = min(1.0, self.max_input_side / max(1, longest))
        if scale < 1.0:
            work = cv2.resize(
                frame,
                (round(width * scale), round(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            work = frame
        result = self._get_engine()(work)
        boxes, texts, scores = self._extract_output(result)
        inverse = 1.0 / scale
        detections: list[InspectionDetection] = []
        scores = scores if scores is not None else [1.0] * len(texts)
        for box, text, score in zip(boxes, texts, scores):
            clean_text = str(text).strip()
            confidence = float(score)
            if not clean_text or confidence < self.min_score:
                continue
            points = np.asarray(box, dtype=np.float32).reshape(-1, 2)
            mapped = tuple(
                (round(float(point[0]) * inverse), round(float(point[1]) * inverse))
                for point in points
            )
            xs = [point[0] for point in mapped]
            ys = [point[1] for point in mapped]
            left, top = max(0, min(xs)), max(0, min(ys))
            right, bottom = min(width, max(xs)), min(height, max(ys))
            detections.append(
                InspectionDetection(
                    kind="text",
                    bbox=(left, top, max(1, right - left), max(1, bottom - top)),
                    confidence=confidence,
                    label="TEXT",
                    text=clean_text,
                    polygon=mapped,
                )
            )
        return detections


class FireRuleDetector:
    def __init__(self, max_input_width: int = 640) -> None:
        self.max_input_width = max_input_width
        self.detector = FireDetector()
        self.tracker = FireConfirmationTracker(
            required_frames=3,
            confidence_threshold=0.68,
            cooldown_seconds=8.0,
        )

    def detect(
        self, frame: np.ndarray, now: float | None = None
    ) -> tuple[list[InspectionDetection], InspectionDetection | None]:
        height, width = frame.shape[:2]
        scale = min(1.0, self.max_input_width / max(1, width))
        if scale < 1.0:
            work = cv2.resize(
                frame,
                (round(width * scale), round(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            work = frame
        native = self.detector.detect(work)
        confirmed_native = self.tracker.update(native, now or time.monotonic())
        inverse = 1.0 / scale

        def convert(item) -> InspectionDetection:
            x, y, box_width, box_height = item.bbox
            bbox = (
                max(0, round(x * inverse)),
                max(0, round(y * inverse)),
                max(1, round(box_width * inverse)),
                max(1, round(box_height * inverse)),
            )
            return InspectionDetection(
                kind="fire",
                bbox=bbox,
                confidence=float(item.confidence),
                label="SIM FIRE" if item.kind == "simulated_marker" else "FIRE",
            )

        converted = [convert(item) for item in native]
        event = convert(confirmed_native) if confirmed_native is not None else None
        return converted, event
