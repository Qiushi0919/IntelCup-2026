from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
from PyQt5.QtCore import QThread, pyqtSignal

from fire_detector import FireConfirmationTracker, FireDetector
from lens_correction import LensCorrector
from models import FireDetection


WORKSPACE = Path(__file__).resolve().parent.parent
CAMERA_MODULE_DIR = WORKSPACE / "pc_camera_viewer"
if str(CAMERA_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(CAMERA_MODULE_DIR))

from amb82_camera import AMB82Camera  # noqa: E402


class CameraThread(QThread):
    frame_ready = pyqtSignal(object, object)
    fire_confirmed = pyqtSignal(object)
    status_changed = pyqtSignal(bool, str, float, object)

    def __init__(
        self,
        url: str = "auto",
        parent=None,
        lens_correction_enabled: bool = True,
        lens_correction_strength: int = 50,
    ) -> None:
        super().__init__(parent)
        self.url = url
        self._stop_requested = False
        self.lens_corrector = LensCorrector(
            lens_correction_enabled,
            lens_correction_strength,
        )

    def run(self) -> None:
        self._stop_requested = False
        camera = AMB82Camera(
            self.url,
            timeout=4.0,
            reconnect_delay=1.0,
            poll_interval=0.5,
        )
        last_frame_time = 0.0
        last_detection_time = 0.0
        last_status_time = 0.0
        latest_detections: list[FireDetection] = []
        detector = FireDetector()
        tracker = FireConfirmationTracker()
        try:
            while not self._stop_requested:
                ok, frame = camera.read(timeout=0.25, wait_for_new=True, copy=True)
                now = time.monotonic()
                if ok and frame is not None and now - last_frame_time >= 0.055:
                    frame = self.lens_corrector.apply(frame)
                    if now - last_detection_time >= 0.16:
                        latest_detections = self._detect_scaled(frame, detector)
                        confirmed = tracker.update(latest_detections, now)
                        if confirmed:
                            self.fire_confirmed.emit(confirmed)
                        last_detection_time = now
                    self.frame_ready.emit(frame, latest_detections)
                    last_frame_time = now
                if now - last_status_time >= 0.5:
                    if camera.connected:
                        mode = "RTSP 720p" if camera.source_kind == "rtsp" else "快照回退"
                        correction = (
                            f"去畸变 {self.lens_corrector.strength}%"
                            if self.lens_corrector.enabled
                            else "原始镜头"
                        )
                        message = f"{mode} · {correction} · {camera.url}"
                    else:
                        message = camera.last_error or "正在搜索 AMB82-Mini"
                    diagnostics = {
                        "source_kind": camera.source_kind,
                        "frame_age_ms": camera.frame_age_ms,
                        "reconnect_count": camera.reconnect_count,
                        "last_error": camera.last_error,
                    }
                    self.status_changed.emit(
                        camera.connected,
                        message,
                        camera.fps,
                        diagnostics,
                    )
                    last_status_time = now
                self.msleep(20)
        finally:
            camera.release()
            self.status_changed.emit(
                False,
                "相机服务已停止",
                0.0,
                {
                    "source_kind": "stopped",
                    "frame_age_ms": -1,
                    "reconnect_count": camera.reconnect_count,
                    "last_error": camera.last_error,
                },
            )

    def stop(self) -> None:
        self._stop_requested = True
        self.requestInterruption()
        self.wait(5000)

    def set_lens_correction(self, enabled: bool, strength: int) -> None:
        self.lens_corrector.configure(enabled, strength)

    @staticmethod
    def _detect_scaled(
        frame, detector: FireDetector
    ) -> list[FireDetection]:
        height, width = frame.shape[:2]
        if width <= 640:
            return detector.detect(frame)

        scale = 640.0 / width
        detect_width = 640
        detect_height = max(1, round(height * scale))
        resized = cv2.resize(
            frame,
            (detect_width, detect_height),
            interpolation=cv2.INTER_AREA,
        )
        detections = detector.detect(resized)
        inverse = 1.0 / scale
        return [
            FireDetection(
                bbox=(
                    round(item.bbox[0] * inverse),
                    round(item.bbox[1] * inverse),
                    round(item.bbox[2] * inverse),
                    round(item.bbox[3] * inverse),
                ),
                confidence=item.confidence,
                area=item.area * inverse * inverse,
                center_x=round(item.center_x * inverse),
                center_y=round(item.center_y * inverse),
                frame_width=width,
                frame_height=height,
                warm_ratio=item.warm_ratio,
                core_ratio=item.core_ratio,
                kind=item.kind,
            )
            for item in detections
        ]
