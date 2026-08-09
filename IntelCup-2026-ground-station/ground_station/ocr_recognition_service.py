from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from models import OCRMatch


ASSET_DIR = Path(__file__).resolve().parent / "assets" / "ocr"
DETECTION_MODEL = ASSET_DIR / "text_detection_cn_ppocrv3_2023may.onnx"
RECOGNITION_MODEL = ASSET_DIR / "text_recognition_CRNN_CN_2021nov.onnx"
CHARSET_FILE = ASSET_DIR / "charset_3944_CN.txt"


class LocalOCRRecognizer:
    """OpenCV implementation aligned with the K230 two-stage OCR pipeline."""

    DETECTION_SIZE = (640, 640)
    RECOGNITION_SIZE = (100, 32)

    def __init__(
        self,
        minimum_detection_confidence: float = 0.55,
        max_regions: int = 4,
    ) -> None:
        required = [DETECTION_MODEL, RECOGNITION_MODEL, CHARSET_FILE]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("OCR 识别资源缺失：" + "、".join(missing))

        self.minimum_detection_confidence = minimum_detection_confidence
        self.max_regions = max(1, int(max_regions))
        self.charset = "".join(
            CHARSET_FILE.read_text(encoding="utf-8").splitlines()
        )
        if len(self.charset) != 3944:
            raise RuntimeError(
                f"OCR 字符表长度异常：应为 3944，实际为 {len(self.charset)}"
            )

        self.detector = cv2.dnn_TextDetectionModel_DB(
            cv2.dnn.readNet(str(DETECTION_MODEL))
        )
        self.detector.setBinaryThreshold(0.3)
        self.detector.setPolygonThreshold(0.5)
        self.detector.setUnclipRatio(1.8)
        self.detector.setMaxCandidates(24)
        self.detector.setInputSize(self.DETECTION_SIZE)
        self.detector.setInputMean((123.675, 116.28, 103.53))
        self.detector.setInputScale(
            1.0 / 255.0 / np.array([0.229, 0.224, 0.225])
        )
        self.recognizer = cv2.dnn.readNet(str(RECOGNITION_MODEL))
        self.target_vertices = np.array(
            [[0, 31], [0, 0], [99, 0], [99, 31]], dtype=np.float32
        )

    @staticmethod
    def _region_area(vertices: np.ndarray) -> float:
        return abs(float(cv2.contourArea(vertices.astype(np.float32))))

    def _recognize_region(
        self, image: np.ndarray, vertices: np.ndarray
    ) -> tuple[str, float]:
        transform = cv2.getPerspectiveTransform(vertices, self.target_vertices)
        crop = cv2.warpPerspective(
            image,
            transform,
            self.RECOGNITION_SIZE,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        blob = cv2.dnn.blobFromImage(
            crop,
            size=self.RECOGNITION_SIZE,
            mean=127.5,
            scalefactor=1.0 / 127.5,
        )
        self.recognizer.setInput(blob)
        output = self.recognizer.forward()[:, 0, :]

        shifted = output - output.max(axis=1, keepdims=True)
        probabilities = np.exp(shifted)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        indices = np.argmax(output, axis=1)

        characters: list[str] = []
        confidences: list[float] = []
        previous = -1
        for row, index in enumerate(indices):
            class_index = int(index)
            if class_index != 0 and class_index != previous:
                charset_index = class_index - 1
                if charset_index < len(self.charset):
                    characters.append(self.charset[charset_index])
                    confidences.append(float(probabilities[row, class_index]))
            previous = class_index

        text = "".join(characters).strip()
        confidence = float(np.mean(confidences)) if confidences else 0.0
        return text, confidence

    def recognize(self, frame: np.ndarray) -> list[OCRMatch]:
        if frame is None or frame.size == 0:
            return []

        frame_height, frame_width = frame.shape[:2]
        detection_width, detection_height = self.DETECTION_SIZE
        resized = cv2.resize(
            frame,
            self.DETECTION_SIZE,
            interpolation=cv2.INTER_AREA,
        )
        boxes, scores = self.detector.detect(resized)
        if boxes is None or len(boxes) == 0:
            return []

        candidates: list[tuple[np.ndarray, float, float]] = []
        for box, score in zip(boxes, scores):
            vertices = np.asarray(box, dtype=np.float32).reshape(4, 2)
            area = self._region_area(vertices)
            if float(score) < self.minimum_detection_confidence or area < 180.0:
                continue
            candidates.append((vertices, float(score), area))
        candidates.sort(key=lambda item: item[1] * item[2], reverse=True)

        scale_x = frame_width / detection_width
        scale_y = frame_height / detection_height
        matches: list[OCRMatch] = []
        for vertices, detection_score, _area in candidates[: self.max_regions]:
            text, recognition_score = self._recognize_region(resized, vertices)
            if not text:
                continue
            mapped: list[tuple[int, int]] = []
            for x, y in vertices:
                mapped.append(
                    (
                        max(0, min(frame_width - 1, int(round(x * scale_x)))),
                        max(0, min(frame_height - 1, int(round(y * scale_y)))),
                    )
                )
            matches.append(
                OCRMatch(
                    polygon=(mapped[0], mapped[1], mapped[2], mapped[3]),
                    text=text,
                    confidence=max(
                        0.0,
                        min(1.0, detection_score * recognition_score),
                    ),
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
            )

        matches.sort(
            key=lambda match: (
                min(point[1] for point in match.polygon),
                min(point[0] for point in match.polygon),
            )
        )
        return matches


class OCRRecognitionThread(QThread):
    results_ready = pyqtSignal(object)
    recognition_ready = pyqtSignal(object, object)
    status_changed = pyqtSignal(bool, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._enabled = False
        self._stop_requested = False

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)
            if not enabled:
                self._latest_frame = None
        if not enabled:
            self.results_ready.emit([])

    def submit_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            if self._enabled:
                self._latest_frame = frame.copy()

    def stop(self) -> None:
        self._stop_requested = True
        self.requestInterruption()
        self.wait(5000)

    def run(self) -> None:
        try:
            recognizer = LocalOCRRecognizer()
        except Exception as exc:
            self.status_changed.emit(False, str(exc))
            return

        self.status_changed.emit(True, "中文 PP-OCRv3 与 CRNN 模型已加载")
        while not self._stop_requested and not self.isInterruptionRequested():
            with self._lock:
                enabled = self._enabled
                frame = self._latest_frame
                self._latest_frame = None
            if not enabled:
                self.msleep(80)
                continue
            if frame is None:
                self.msleep(12)
                continue
            try:
                matches = recognizer.recognize(frame)
                self.results_ready.emit(matches)
                self.recognition_ready.emit(matches, frame)
            except Exception as exc:
                self.status_changed.emit(False, f"OCR 识别运行失败：{exc}")
                self.msleep(300)
