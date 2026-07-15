from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
import time

import numpy as np

from .detectors import (
    FireRuleDetector,
    InspectionDetection,
    RapidOcrDetector,
    YuNetFaceDetector,
)


@dataclass(frozen=True)
class InspectionResult:
    faces: tuple[InspectionDetection, ...] = ()
    texts: tuple[InspectionDetection, ...] = ()
    fires: tuple[InspectionDetection, ...] = ()
    fire_event: InspectionDetection | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    ocr_busy: bool = False
    ocr_error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "faces": [item.to_dict() for item in self.faces],
            "texts": [item.to_dict() for item in self.texts],
            "fires": [item.to_dict() for item in self.fires],
            "fire_event": self.fire_event.to_dict() if self.fire_event else None,
            "timings_ms": {key: round(value, 2) for key, value in self.timings_ms.items()},
            "ocr_busy": self.ocr_busy,
            "ocr_error": self.ocr_error,
        }


class InspectionEngine:
    """Runs fast detectors inline and slow OCR on a latest-frame worker."""

    def __init__(
        self,
        face_detector: YuNetFaceDetector,
        face_interval: float = 0.18,
        fire_interval: float = 0.16,
        ocr_interval: float = 3.0,
        enable_face: bool = True,
        enable_ocr: bool = True,
        enable_fire: bool = True,
    ) -> None:
        self.face_detector = face_detector
        self.ocr_detector = RapidOcrDetector()
        self.fire_detector = FireRuleDetector()
        self.face_interval = face_interval
        self.fire_interval = fire_interval
        self.ocr_interval = ocr_interval
        self.enabled = {
            "face": enable_face,
            "text": enable_ocr,
            "fire": enable_fire,
        }
        self._faces: tuple[InspectionDetection, ...] = ()
        self._texts: tuple[InspectionDetection, ...] = ()
        self._fires: tuple[InspectionDetection, ...] = ()
        self._fire_event: InspectionDetection | None = None
        self._timings = {"face": 0.0, "ocr": 0.0, "fire": 0.0}
        self._ocr_error = ""
        self._next_face = 0.0
        self._next_fire = 0.0
        self._next_ocr = 0.0
        self._force_ocr = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="inspection-ocr")
        self._ocr_future: Future | None = None
        self._ocr_future_generation: int | None = None
        self._ocr_generation = 0

    def toggle(self, kind: str) -> bool:
        self.enabled[kind] = not self.enabled[kind]
        if kind == "text":
            self._ocr_generation += 1
            self._force_ocr = False
            self._ocr_error = ""
            self._next_ocr = 0.0
        if not self.enabled[kind]:
            if kind == "face":
                self._faces = ()
            elif kind == "text":
                self._texts = ()
            elif kind == "fire":
                self._fires = ()
        return self.enabled[kind]

    def request_ocr(self) -> None:
        self._force_ocr = True

    def _run_ocr(self, frame: np.ndarray):
        started = time.perf_counter()
        detections = self.ocr_detector.detect(frame)
        return tuple(detections), (time.perf_counter() - started) * 1000.0

    def _poll_ocr(self) -> None:
        if self._ocr_future is None or not self._ocr_future.done():
            return
        future = self._ocr_future
        generation = self._ocr_future_generation
        self._ocr_future = None
        self._ocr_future_generation = None
        try:
            detections, duration = future.result()
            if generation == self._ocr_generation and self.enabled["text"]:
                self._texts = detections
                self._timings["ocr"] = duration
                self._ocr_error = ""
        except Exception as exc:  # the preview must stay alive if OCR fails
            if generation == self._ocr_generation and self.enabled["text"]:
                self._ocr_error = f"{type(exc).__name__}: {exc}"
        if generation == self._ocr_generation and self.enabled["text"]:
            self._next_ocr = time.monotonic() + self.ocr_interval

    def process(self, frame: np.ndarray, now: float | None = None) -> InspectionResult:
        timestamp = time.monotonic() if now is None else now
        self._fire_event = None
        self._poll_ocr()

        if self.enabled["face"] and timestamp >= self._next_face:
            started = time.perf_counter()
            self._faces = tuple(self.face_detector.detect(frame))
            self._timings["face"] = (time.perf_counter() - started) * 1000.0
            self._next_face = timestamp + self.face_interval

        if self.enabled["fire"] and timestamp >= self._next_fire:
            started = time.perf_counter()
            detections, event = self.fire_detector.detect(frame, timestamp)
            self._fires = tuple(detections)
            self._fire_event = event
            self._timings["fire"] = (time.perf_counter() - started) * 1000.0
            self._next_fire = timestamp + self.fire_interval

        should_start_ocr = (
            self.enabled["text"]
            and self._ocr_future is None
            and (timestamp >= self._next_ocr or self._force_ocr)
        )
        if should_start_ocr:
            self._ocr_future = self._executor.submit(self._run_ocr, frame.copy())
            self._ocr_future_generation = self._ocr_generation
            self._force_ocr = False
        return self.current_result()

    def wait_for_ocr(self, timeout: float = 90.0) -> InspectionResult:
        if self._ocr_future is not None:
            future = self._ocr_future
            generation = self._ocr_future_generation
            try:
                detections, duration = future.result(timeout=timeout)
            except FutureTimeoutError as exc:
                if generation == self._ocr_generation and self.enabled["text"]:
                    self._ocr_error = f"{type(exc).__name__}: OCR仍在后台运行"
                return self.current_result()
            except Exception as exc:
                if generation == self._ocr_generation and self.enabled["text"]:
                    self._ocr_error = f"{type(exc).__name__}: {exc}"
            else:
                if generation == self._ocr_generation and self.enabled["text"]:
                    self._texts = detections
                    self._timings["ocr"] = duration
                    self._ocr_error = ""
                    self._next_ocr = time.monotonic() + self.ocr_interval
            if future.done():
                self._ocr_future = None
                self._ocr_future_generation = None
        return self.current_result()

    def current_result(self) -> InspectionResult:
        return InspectionResult(
            faces=self._faces,
            texts=self._texts,
            fires=self._fires,
            fire_event=self._fire_event,
            timings_ms=dict(self._timings),
            ocr_busy=self._ocr_future is not None,
            ocr_error=self._ocr_error,
        )

    def close(self) -> None:
        if self._ocr_future is not None:
            self._ocr_future.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)
