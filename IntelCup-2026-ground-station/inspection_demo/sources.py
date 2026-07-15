from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


class FrameSource(Protocol):
    description: str

    def open(self) -> None: ...

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...


class OpenCVFrameSource:
    """USB camera today; file or RTSP source later without changing detectors."""

    def __init__(
        self,
        source: str | int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        loop: bool = True,
    ) -> None:
        self.requested_source = source
        self.width = width
        self.height = height
        self.requested_fps = fps
        self.loop = loop
        self.capture: cv2.VideoCapture | None = None
        self.image: np.ndarray | None = None
        self._pending_frame: np.ndarray | None = None
        self.description = str(source)

    @property
    def is_static_image(self) -> bool:
        return self.image is not None

    @staticmethod
    def _normalize_source(source: str | int) -> str | int:
        if isinstance(source, int):
            return source
        value = source.strip()
        if value.lower().startswith("camera:"):
            value = value.split(":", 1)[1]
        if value.lstrip("-").isdigit():
            return int(value)
        return value

    def open(self) -> None:
        source = self._normalize_source(self.requested_source)
        if isinstance(source, str):
            candidate = Path(source).expanduser()
            if candidate.suffix.lower() in IMAGE_SUFFIXES and candidate.exists():
                self.image = cv2.imdecode(
                    np.fromfile(str(candidate), dtype=np.uint8), cv2.IMREAD_COLOR
                )
                if self.image is None:
                    raise RuntimeError(f"无法读取图片：{candidate}")
                self.description = f"图片 · {candidate.name}"
                return

        if isinstance(source, int):
            self._open_camera(source)
        else:
            self._open_stream(str(source))

    def _configure_capture(self, capture: cv2.VideoCapture) -> None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.requested_fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _open_camera(self, requested_index: int) -> None:
        backends = (
            (cv2.CAP_DSHOW, "DSHOW"),
            (cv2.CAP_MSMF, "MSMF"),
            (0, "DEFAULT"),
        )
        indexes = [requested_index]
        indexes.extend(index for index in range(8) if index not in indexes)
        for index in indexes:
            for backend, backend_name in backends:
                capture = (
                    cv2.VideoCapture(index, backend)
                    if backend
                    else cv2.VideoCapture(index)
                )
                self._configure_capture(capture)
                ok, first_frame = capture.read() if capture.isOpened() else (False, None)
                if ok and first_frame is not None:
                    self.capture = capture
                    self._pending_frame = first_frame
                    self.description = f"USB 摄像头 {index} · {backend_name}"
                    return
                capture.release()
        raise RuntimeError("未找到可用 USB 摄像头（已扫描 0-7 号设备）")

    def _open_stream(self, source: str) -> None:
        if source.lower().startswith("rtsp://"):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"
            )
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        self._configure_capture(capture)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"无法打开视频源：{source}")
        self.capture = capture
        kind = "RTSP 图传" if source.lower().startswith("rtsp://") else "视频文件"
        self.description = f"{kind} · {source}"

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self.image is not None:
            return True, self.image.copy()
        if self._pending_frame is not None:
            frame = self._pending_frame
            self._pending_frame = None
            return True, frame
        if self.capture is None:
            return False, None
        ok, frame = self.capture.read()
        if ok and frame is not None:
            return True, frame
        source = self._normalize_source(self.requested_source)
        if self.loop and isinstance(source, str) and not source.lower().startswith("rtsp://"):
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return self.capture.read()
        return False, None

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self._pending_frame = None

    def __enter__(self) -> "OpenCVFrameSource":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
