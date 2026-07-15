from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from models import DroneState


NCLINK_HEAD = b"\xff\xfc"
NCLINK_TAIL = b"\xa1\xa2"


@dataclass(frozen=True)
class NCLinkFrame:
    msg_id: int
    payload: bytes


class NCLinkParser:
    """Incrementally parse NamelessCotrun NCLink telemetry frames."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.invalid_frames = 0

    def feed(self, data: bytes) -> list[NCLinkFrame]:
        self._buffer.extend(data)
        frames: list[NCLinkFrame] = []
        while True:
            head_index = self._buffer.find(NCLINK_HEAD)
            if head_index < 0:
                if self._buffer.endswith(NCLINK_HEAD[:1]):
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self._buffer.clear()
                break
            if head_index > 0:
                del self._buffer[:head_index]
            if len(self._buffer) < 4:
                break

            payload_len = self._buffer[3]
            if payload_len > 120:
                del self._buffer[0]
                self.invalid_frames += 1
                continue

            total_len = 2 + 1 + 1 + payload_len + 1 + 2
            if len(self._buffer) < total_len:
                break
            candidate = bytes(self._buffer[:total_len])
            if candidate[-2:] != NCLINK_TAIL:
                del self._buffer[0]
                self.invalid_frames += 1
                continue

            checksum = 0
            for item in candidate[: 4 + payload_len]:
                checksum ^= item
            if checksum != candidate[4 + payload_len]:
                del self._buffer[0]
                self.invalid_frames += 1
                continue

            frames.append(NCLinkFrame(candidate[2], candidate[4 : 4 + payload_len]))
            del self._buffer[:total_len]
        return frames


class NCLinkStateDecoder:
    def __init__(self) -> None:
        self.state = DroneState(
            connected=False,
            telemetry_connected=False,
            flight_phase="等待飞控数传",
            warning="串口未连接",
        )
        self._last_xy: tuple[float, float] | None = None
        self._distance_travelled = 0.0

    def apply(self, frame: NCLinkFrame) -> bool:
        payload = frame.payload
        msg_id = frame.msg_id
        updated = False
        if msg_id == 0x01 and len(payload) >= 24:
            updated = self._decode_status(payload)
        elif msg_id == 0x06 and len(payload) >= 16:
            updated = self._decode_vertical_observation(payload)
        elif msg_id == 0x07 and len(payload) >= 12:
            updated = self._decode_fusion_u(payload)
        elif msg_id == 0x08 and len(payload) >= 24:
            updated = self._decode_fusion_ne(payload)
        elif msg_id == 0x17 and len(payload) >= 20:
            updated = self._decode_track(payload)
        elif msg_id == 0x18 and len(payload) >= 61:
            updated = self._decode_ahrs(payload)

        if updated:
            self.state.connected = True
            self.state.telemetry_connected = True
            self.state.warning = ""
            self.state.last_update = datetime.now()
            self._update_motion_bookkeeping()
        return updated

    def _decode_status(self, data: bytes) -> bool:
        roll = self._s16(data, 0) / 100.0
        pitch = self._s16(data, 2) / 100.0
        yaw = self._s16(data, 4) / 10.0
        vbat = self._s16(data, 20) / 100.0
        flight_mode = data[22]
        armed = data[23] != 0
        self.state.roll = roll
        self.state.pitch = pitch
        self.state.yaw = yaw
        self.state.battery_voltage = vbat
        self.state.battery_percent = self._voltage_to_percent(vbat)
        self.state.armed = armed
        self.state.flight_mode = "ARMED" if armed else "STANDBY"
        self.state.flight_phase = f"真实数传 · 飞控模式 {flight_mode}"
        return True

    def _decode_vertical_observation(self, data: bytes) -> bool:
        ground_distance = self._s32(data, 4) / 100.0
        self.state.rangefinder_distance = self._distance_to_meters(ground_distance)
        return True

    def _decode_fusion_u(self, data: bytes) -> bool:
        altitude = self._s32(data, 0) / 100.0
        vertical_speed = self._s32(data, 4) / 100.0
        self.state.altitude = self._distance_to_meters(altitude)
        self.state.vertical_speed = self._distance_to_meters(vertical_speed)
        return True

    def _decode_fusion_ne(self, data: bytes) -> bool:
        north = self._s32(data, 0) / 100.0
        east = self._s32(data, 4) / 100.0
        north_speed = self._s32(data, 8) / 100.0
        east_speed = self._s32(data, 12) / 100.0
        self.state.x = self._distance_to_meters(east)
        self.state.y = self._distance_to_meters(north)
        vn = self._distance_to_meters(north_speed)
        ve = self._distance_to_meters(east_speed)
        self.state.horizontal_speed = math.hypot(vn, ve)
        return True

    def _decode_track(self, data: bytes) -> bool:
        east, north, up = struct.unpack_from("<fff", data, 0)
        self.state.x = self._distance_to_meters(east)
        self.state.y = self._distance_to_meters(north)
        self.state.altitude = self._distance_to_meters(up)
        return True

    def _decode_ahrs(self, data: bytes) -> bool:
        east, north, up = struct.unpack_from("<fff", data, 0)
        east_speed, north_speed, vertical_speed = struct.unpack_from("<fff", data, 12)
        self.state.x = self._distance_to_meters(east)
        self.state.y = self._distance_to_meters(north)
        self.state.altitude = self._distance_to_meters(up)
        self.state.horizontal_speed = math.hypot(
            self._distance_to_meters(east_speed),
            self._distance_to_meters(north_speed),
        )
        self.state.vertical_speed = self._distance_to_meters(vertical_speed)
        ahrs_ok = data[56] != 0
        slam_ok = data[57] != 0
        self.state.optical_flow_quality = 90 if slam_ok else 45
        if not ahrs_ok:
            self.state.warning = "姿态解算未就绪"
        return True

    def _update_motion_bookkeeping(self) -> None:
        xy = (self.state.x, self.state.y)
        if self._last_xy is not None:
            step = math.hypot(xy[0] - self._last_xy[0], xy[1] - self._last_xy[1])
            if 0.02 <= step <= 5.0:
                self._distance_travelled += step
        self._last_xy = xy
        self.state.distance_travelled = self._distance_travelled

    @staticmethod
    def _s16(data: bytes, offset: int) -> int:
        return int.from_bytes(data[offset : offset + 2], "big", signed=True)

    @staticmethod
    def _s32(data: bytes, offset: int) -> int:
        return int.from_bytes(data[offset : offset + 4], "big", signed=True)

    @staticmethod
    def _distance_to_meters(value: float) -> float:
        if abs(value) > 20.0:
            return value / 100.0
        return value

    @staticmethod
    def _voltage_to_percent(voltage: float) -> float:
        if voltage <= 0:
            return 0.0
        return max(0.0, min(100.0, (voltage - 14.0) / (16.8 - 14.0) * 100.0))


class TelemetryThread(QThread):
    state_changed = pyqtSignal(object)
    status_changed = pyqtSignal(bool, str, dict)
    log_generated = pyqtSignal(str, str)

    def __init__(self, port: str, baudrate: int = 460800, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True
        if self.isRunning():
            self.wait(1800)

    def run(self) -> None:
        try:
            import serial
        except ImportError:
            self.status_changed.emit(
                False,
                "缺少 pyserial，无法打开飞控串口",
                {"port": self.port, "packets": 0, "invalid": 0},
            )
            self.log_generated.emit(
                "ERROR", "请先安装 pyserial：pip install pyserial"
            )
            return

        parser = NCLinkParser()
        decoder = NCLinkStateDecoder()
        packets = 0
        last_emit = 0.0
        last_valid = 0.0
        last_status = 0.0
        last_status_message = ""

        try:
            with serial.Serial(
                self.port,
                self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.05,
                write_timeout=0,
            ) as stream:
                self.log_generated.emit(
                    "INFO", f"飞控数传串口已打开：{self.port} @ {self.baudrate}"
                )
                self.status_changed.emit(
                    False,
                    f"串口已打开：{self.port}，等待 NCLink 数据",
                    {"port": self.port, "packets": packets, "invalid": 0},
                )
                while not self._stop_requested:
                    chunk = stream.read(512)
                    now = time.monotonic()
                    for frame in parser.feed(chunk):
                        packets += 1
                        if decoder.apply(frame):
                            last_valid = now
                            decoder.state.link_latency_ms = 0
                            if now - last_emit >= 0.05:
                                self.state_changed.emit(decoder.state)
                                last_emit = now
                    if now - last_status >= 1.0:
                        active = last_valid > 0 and now - last_valid <= 2.5
                        if active:
                            decoder.state.link_latency_ms = int(
                                min(999, max(0.0, now - last_valid) * 1000)
                            )
                            message = (
                                f"NCLink 在线：{self.port}，已解析 {packets} 包"
                            )
                        else:
                            message = (
                                f"串口已打开：{self.port}，等待 NCLink 数据"
                            )
                        if message != last_status_message:
                            self.status_changed.emit(
                                active,
                                message,
                                {
                                    "port": self.port,
                                    "packets": packets,
                                    "invalid": parser.invalid_frames,
                                },
                            )
                            last_status_message = message
                        last_status = now
        except Exception as exc:
            self.status_changed.emit(
                False,
                f"飞控串口打开失败：{exc}",
                {
                    "port": self.port,
                    "packets": packets,
                    "invalid": parser.invalid_frames,
                },
            )
            self.log_generated.emit("ERROR", f"飞控数传连接失败：{exc}")
        finally:
            self.status_changed.emit(
                False,
                "飞控数传已断开",
                {
                    "port": self.port,
                    "packets": packets,
                    "invalid": parser.invalid_frames,
                },
            )
