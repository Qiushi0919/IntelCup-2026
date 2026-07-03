from __future__ import annotations

import threading

import cv2
import numpy as np


class LensCorrector:
    """Cached radial undistortion for the AMB82 wide-angle camera."""

    def __init__(self, enabled: bool = True, strength: int = 50) -> None:
        self._lock = threading.Lock()
        self._enabled = enabled
        self._strength = max(0, min(65, int(strength)))
        self._map_key: tuple[int, int, int] | None = None
        self._map_x = None
        self._map_y = None

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def strength(self) -> int:
        with self._lock:
            return self._strength

    def configure(self, enabled: bool, strength: int) -> None:
        strength = max(0, min(65, int(strength)))
        with self._lock:
            changed = (
                self._enabled != bool(enabled)
                or self._strength != strength
            )
            self._enabled = bool(enabled)
            self._strength = strength
            if changed:
                self._map_key = None
                self._map_x = None
                self._map_y = None

    def apply(self, frame):
        with self._lock:
            enabled = self._enabled
            strength = self._strength

        if not enabled or strength <= 0 or frame is None:
            return frame

        height, width = frame.shape[:2]
        key = (width, height, strength)
        with self._lock:
            if self._map_key != key:
                self._build_maps(width, height, strength)
            map_x = self._map_x
            map_y = self._map_y

        return cv2.remap(
            frame,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )

    def _build_maps(self, width: int, height: int, strength: int) -> None:
        amount = strength / 100.0
        focal = 0.78 * max(width, height)
        camera_matrix = np.array(
            [
                [focal, 0.0, width / 2.0],
                [0.0, focal, height / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )
        distortion = np.array(
            [-amount, amount * 0.18, 0.0, 0.0, 0.0],
            dtype=np.float32,
        )
        new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
            camera_matrix,
            distortion,
            (width, height),
            0.0,
            (width, height),
        )
        self._map_x, self._map_y = cv2.initUndistortRectifyMap(
            camera_matrix,
            distortion,
            None,
            new_camera_matrix,
            (width, height),
            cv2.CV_32FC1,
        )
        self._map_key = (width, height, strength)
