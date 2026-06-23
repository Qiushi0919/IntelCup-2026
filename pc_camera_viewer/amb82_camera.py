from __future__ import annotations

import ipaddress
import os
import socket
import threading
import time
import urllib.parse
import urllib.request
from collections import deque
from typing import Optional

import cv2
import numpy as np


class AMB82Camera:
    """Read AMB82 RTSP video, with legacy JPEG snapshots as fallback."""

    def __init__(
        self,
        url: str = "auto",
        timeout: float = 8.0,
        reconnect_delay: float = 1.0,
        poll_interval: float = 0.5,
        auto_start: bool = True,
        **_ignored,
    ) -> None:
        self.auto_discover = url.lower() == "auto"
        self.url = "" if self.auto_discover else self._normalize_url(url)
        self.timeout = timeout
        self.poll_interval = max(0.1, poll_interval)
        self.reconnect_delay = max(0.5, reconnect_delay)

        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame: Optional[np.ndarray] = None
        self._sequence = 0
        self._last_read_sequence = 0
        self._last_success = 0.0
        self._last_error = ""
        self._frame_times: deque[float] = deque(maxlen=45)

        if auto_start:
            self.start()

    def start(self) -> "AMB82Camera":
        if self._thread and self._thread.is_alive():
            return self
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._reader_loop,
            name="AMB82VideoReader",
            daemon=True,
        )
        self._thread.start()
        return self

    def read(
        self,
        timeout: float = 2.0,
        wait_for_new: bool = True,
        copy: bool = True,
    ) -> tuple[bool, Optional[np.ndarray]]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._stop_event.is_set():
                has_frame = self._frame is not None
                is_new = self._sequence > self._last_read_sequence
                if has_frame and (is_new or not wait_for_new):
                    frame = self._frame.copy() if copy else self._frame
                    self._last_read_sequence = self._sequence
                    return True, frame
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
        return False, None

    def read_latest(
        self, copy: bool = True
    ) -> tuple[bool, Optional[np.ndarray]]:
        with self._condition:
            if self._frame is None:
                return False, None
            return True, self._frame.copy() if copy else self._frame

    def isOpened(self) -> bool:
        return self.connected and self._frame is not None

    @property
    def connected(self) -> bool:
        freshness = 2.5 if self.source_kind == "rtsp" else self.timeout + 1.0
        return (
            self._last_success > 0
            and time.monotonic() - self._last_success <= freshness
        )

    @property
    def source_kind(self) -> str:
        return "rtsp" if self.url.lower().startswith("rtsp://") else "snapshot"

    @property
    def fps(self) -> float:
        with self._condition:
            if len(self._frame_times) < 2:
                return 0.0
            elapsed = self._frame_times[-1] - self._frame_times[0]
            return (len(self._frame_times) - 1) / elapsed if elapsed > 0 else 0.0

    @property
    def last_error(self) -> str:
        return self._last_error

    def release(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    close = release

    def __enter__(self) -> "AMB82Camera":
        return self.start()

    def __exit__(self, *_args) -> None:
        self.release()

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if not self.url:
                    self.url = self._discover_camera_url()
                if self.source_kind == "rtsp":
                    self._read_rtsp_session()
                else:
                    self._read_snapshot_once()
                    self._stop_event.wait(self.poll_interval)
            except Exception as error:
                self._last_error = f"{type(error).__name__}: {error}"
                if self.auto_discover:
                    self.url = ""
                self._stop_event.wait(self.reconnect_delay)

    def _publish(self, frame: np.ndarray) -> None:
        now = time.perf_counter()
        with self._condition:
            self._frame = frame
            self._sequence += 1
            self._last_success = time.monotonic()
            self._frame_times.append(now)
            self._last_error = ""
            self._condition.notify_all()

    def _read_rtsp_session(self) -> None:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|stimeout;5000000|max_delay;300000"
        )
        capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            capture.release()
            raise ConnectionError(f"cannot open RTSP stream: {self.url}")

        failures = 0
        try:
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= 12:
                        raise ConnectionError("RTSP stream interrupted")
                    time.sleep(0.03)
                    continue
                failures = 0
                self._publish(frame)
        finally:
            capture.release()

    def _read_snapshot_once(self) -> None:
        separator = "&" if urllib.parse.urlsplit(self.url).query else "?"
        request_url = f"{self.url}{separator}_={time.time_ns()}"
        request = urllib.request.Request(
            request_url,
            headers={
                "User-Agent": "AMB82-Snapshot-Python",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Connection": "close",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            content_length = int(response.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 2 * 1024 * 1024:
                raise ValueError(f"invalid JPEG length: {content_length}")
            jpeg = response.read(content_length)
        if len(jpeg) != content_length:
            raise ValueError(f"incomplete JPEG: {len(jpeg)}/{content_length}")
        encoded = np.frombuffer(jpeg, dtype=np.uint8)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("JPEG decode failed")
        self._publish(frame)

    def _discover_camera_url(self) -> str:
        hosts = self._candidate_hosts()
        for host in hosts:
            snapshot = f"http://{host}/snapshot.jpg"
            if self._is_snapshot_camera(snapshot):
                if self._port_open(host, 554, timeout=0.35):
                    return f"rtsp://{host}:554"
                return snapshot
        raise ConnectionError("AMB82 camera not found on local networks")

    @staticmethod
    def _normalize_url(url: str) -> str:
        value = url.strip()
        if value.lower().startswith(("rtsp://", "http://", "https://")):
            return value
        return f"rtsp://{value}:554"

    @staticmethod
    def _candidate_hosts() -> list[str]:
        hosts: list[str] = []
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = ipaddress.ip_address(item[4][0])
            if (
                address.is_private
                and not address.is_loopback
                and address not in ipaddress.ip_network("198.18.0.0/15")
            ):
                host = (
                    f"{address.packed[0]}.{address.packed[1]}."
                    f"{address.packed[2]}.2"
                )
                if host not in hosts and address.packed[3] != 2:
                    hosts.append(host)
        for host in ("172.25.135.2", "10.75.128.2"):
            if host not in hosts:
                hosts.append(host)
        return hosts

    @staticmethod
    def _port_open(host: str, port: int, timeout: float) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _is_snapshot_camera(url: str) -> bool:
        try:
            request = urllib.request.Request(
                f"{url}?discover={time.time_ns()}",
                headers={
                    "User-Agent": "AMB82-Discovery",
                    "Connection": "close",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=1.5) as response:
                content_type = response.headers.get("Content-Type", "")
                content_length = int(response.headers.get("Content-Length", "0"))
                if "image/jpeg" not in content_type or content_length <= 0:
                    return False
                jpeg = response.read(content_length)
            return len(jpeg) == content_length and jpeg.startswith(b"\xff\xd8")
        except Exception:
            return False


Camera = AMB82Camera
