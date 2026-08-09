from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from models import FaceMatch


ASSET_DIR = Path(__file__).resolve().parent / "assets" / "face_recognition"
DETECTION_MODEL = ASSET_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNITION_MODEL = ASSET_DIR / "face_recognition_sface_2021dec.onnx"
REFERENCE_IMAGES = {
    "Lucy": ASSET_DIR / "lucy.png",
    "Mark": ASSET_DIR / "mark.jpg",
}


class LocalFaceRecognizer:
    """Real-time Windows implementation of the K230 face pipeline."""

    def __init__(
        self,
        recognition_threshold: float = 0.62,
        minimum_margin: float = 0.06,
    ) -> None:
        required = [DETECTION_MODEL, RECOGNITION_MODEL, *REFERENCE_IMAGES.values()]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("人脸识别资源缺失：" + "、".join(missing))

        self.recognition_threshold = recognition_threshold
        self.minimum_margin = minimum_margin
        self.detector = cv2.FaceDetectorYN_create(
            str(DETECTION_MODEL),
            "",
            (320, 320),
            0.72,
            0.3,
            5000,
        )
        self.recognizer = cv2.FaceRecognizerSF_create(
            str(RECOGNITION_MODEL), ""
        )
        self.reference_features = self._load_reference_features()

    def _detect(self, frame: np.ndarray) -> np.ndarray | None:
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _status, faces = self.detector.detect(frame)
        return faces

    def _feature(self, frame: np.ndarray, face: np.ndarray) -> np.ndarray:
        aligned = self.recognizer.alignCrop(frame, face)
        return self.recognizer.feature(aligned)

    def _load_reference_features(self) -> dict[str, np.ndarray]:
        references: dict[str, np.ndarray] = {}
        for name, path in REFERENCE_IMAGES.items():
            image = cv2.imread(str(path))
            if image is None:
                raise RuntimeError(f"无法读取注册图片：{path}")
            faces = self._detect(image)
            if faces is None or len(faces) == 0:
                raise RuntimeError(f"注册图片中未检测到人脸：{path.name}")
            face = max(faces, key=lambda item: float(item[2] * item[3]))
            references[name] = self._feature(image, face)
        return references

    def recognize(self, frame: np.ndarray) -> list[FaceMatch]:
        faces = self._detect(frame)
        if faces is None or len(faces) == 0:
            return []

        height, width = frame.shape[:2]
        ordered_faces = sorted(
            faces,
            key=lambda item: float(item[-1] * item[2] * item[3]),
            reverse=True,
        )[:4]
        matches: list[FaceMatch] = []
        for face in ordered_faces:
            feature = self._feature(frame, face)
            scores = sorted(
                (
                    (
                        name,
                        float(
                            self.recognizer.match(
                                feature,
                                reference,
                                cv2.FaceRecognizerSF_FR_COSINE,
                            )
                        ),
                    )
                    for name, reference in self.reference_features.items()
                ),
                key=lambda item: item[1],
                reverse=True,
            )
            best_name, best_score = scores[0]
            runner_up = scores[1][1] if len(scores) > 1 else -1.0
            is_match = (
                best_score >= self.recognition_threshold
                and best_score - runner_up >= self.minimum_margin
            )
            x, y, box_width, box_height = [int(round(value)) for value in face[:4]]
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            box_width = max(1, min(width - x, box_width))
            box_height = max(1, min(height - y, box_height))
            matches.append(
                FaceMatch(
                    bbox=(x, y, box_width, box_height),
                    name=best_name if is_match else "陌生人",
                    confidence=max(0.0, min(1.0, best_score)),
                    detection_confidence=max(0.0, min(1.0, float(face[-1]))),
                    frame_width=width,
                    frame_height=height,
                    matched=is_match,
                )
            )
        return matches


class FaceRecognitionThread(QThread):
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
            recognizer = LocalFaceRecognizer()
        except Exception as exc:
            self.status_changed.emit(False, str(exc))
            return

        self.status_changed.emit(True, "Lucy、Mark 人脸库已加载")
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
                self.status_changed.emit(False, f"人脸识别运行失败：{exc}")
                self.msleep(300)
