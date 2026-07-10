from __future__ import annotations

import math
import queue
import struct
import time
from dataclasses import dataclass
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from models import DroneState


NCLINK_HEAD = b"\xff\xfc"
FIRETRUCK_HEAD = b"\xfc\xff"
NCLINK_COMMAND_HEAD = b"\xfc\xff"
NCLINK_TAIL = b"\xa1\xa2"
FORCE_SDK_MODE18_FRAME = bytes.fromhex("FC FF 10 02 01 12 02 A1 A2")
SAFETY_HOLD_FRAME = bytes.fromhex("FC FF 10 02 04 00 15 A1 A2")
SAFETY_RTL_FRAME = bytes.fromhex("FC FF 10 02 03 00 12 A1 A2")
SAFETY_LAND_FRAME = bytes.fromhex("FC FF 10 02 02 00 13 A1 A2")
SAFETY_SHUTDOWN_FRAME = bytes.fromhex("FC FF 10 02 00 00 11 A1 A2")


def build_nclink_command_frame(msg_id: int, payload: bytes) -> bytes:
    frame = bytearray(NCLINK_COMMAND_HEAD)
    frame.append(msg_id & 0xFF)
    frame.append(len(payload) & 0xFF)
    frame.extend(payload)
    checksum = 0
    for item in frame:
        checksum ^= item
    frame.append(checksum)
    frame.extend(NCLINK_TAIL)
    return bytes(frame)


def build_waypoint_clear_frame() -> bytes:
    return build_nclink_command_frame(0x11, bytes([1, 0, 0, 0, 0, 0, 0, 0]))


def build_waypoint_write_frame(
    waypoint_id: int, x_cm: int, y_cm: int, z_cm: int
) -> bytes:
    payload = bytearray([0, waypoint_id & 0xFF])
    for value in (x_cm, y_cm, z_cm):
        payload.extend(int(value).to_bytes(2, "big", signed=True))
    return build_nclink_command_frame(0x11, bytes(payload))


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


@dataclass(frozen=True)
class FiretruckFrame:
    x_cm: float
    y_cm: float
    z_cm: float
    distance_cm: float
    fire_x: int
    fire_y: int
    update_flag: int


class FiretruckCoordinateParser:
    """Parse UART2 FC FF E1 coordinate frames sent by NCLink_Send_To_Firetruck."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.invalid_frames = 0

    def feed(self, data: bytes) -> list[FiretruckFrame]:
        self._buffer.extend(data)
        frames: list[FiretruckFrame] = []
        while True:
            head_index = self._buffer.find(FIRETRUCK_HEAD)
            if head_index < 0:
                if self._buffer.endswith(FIRETRUCK_HEAD[:1]):
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self._buffer.clear()
                break
            if head_index > 0:
                del self._buffer[:head_index]
            if len(self._buffer) < 4:
                break

            msg_id = self._buffer[2]
            payload_len = self._buffer[3]
            if msg_id != 0xE1 or payload_len > 80:
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

            payload = candidate[4 : 4 + payload_len]
            frame = self._decode_payload(payload)
            if frame is not None:
                frames.append(frame)
            else:
                self.invalid_frames += 1
            del self._buffer[:total_len]
        return frames

    @staticmethod
    def _decode_payload(payload: bytes) -> FiretruckFrame | None:
        if len(payload) < 21:
            return None
        x_cm, y_cm, z_cm, distance_cm = struct.unpack_from("<ffff", payload, 0)
        if not math.isfinite(x_cm) or not math.isfinite(y_cm):
            return None
        fire_x = int.from_bytes(payload[16:18], "big", signed=True)
        fire_y = int.from_bytes(payload[18:20], "big", signed=True)
        update_flag = payload[20]
        return FiretruckFrame(
            x_cm=x_cm,
            y_cm=y_cm,
            z_cm=z_cm,
            distance_cm=distance_cm,
            fire_x=fire_x,
            fire_y=fire_y,
            update_flag=update_flag,
        )


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
        self._has_fusion_xy = False

    def apply(self, frame: NCLinkFrame) -> bool:
        payload = frame.payload
        msg_id = frame.msg_id
        updated = False
        if msg_id == 0x01 and len(payload) >= 24:
            updated = self._decode_status(payload)
        elif msg_id == 0x02 and len(payload) >= 18:
            updated = self._decode_imu_raw(payload)
        elif msg_id == 0x04 and len(payload) >= 16:
            updated = self._decode_gps_position(payload)
        elif msg_id == 0x05 and len(payload) >= 16:
            updated = self._decode_gps_velocity(payload)
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
        yaw = self._s16(data, 4) / 100.0
        roll_gyro = self._s32(data, 6) / 100.0
        pitch_gyro = self._s32(data, 10) / 100.0
        yaw_gyro = self._s32(data, 14) / 100.0
        imu_temp = self._s16(data, 18) / 100.0
        vbat = self._s16(data, 20) / 100.0
        flight_mode = data[22]
        armed = data[23] != 0
        self.state.roll = roll
        self.state.pitch = pitch
        self.state.yaw = yaw
        self.state.roll_gyro = roll_gyro
        self.state.pitch_gyro = pitch_gyro
        self.state.yaw_gyro = yaw_gyro
        self.state.imu_temp = imu_temp
        self.state.battery_voltage = vbat
        self.state.battery_percent = self._voltage_to_percent(vbat)
        self.state.armed = armed
        self.state.flight_mode = self._flight_mode_name(flight_mode)
        self.state.flight_phase = f"真实数传 · 飞控模式 {flight_mode}"
        return True

    def _decode_imu_raw(self, data: bytes) -> bool:
        self.state.ax = self._s16(data, 0)
        self.state.ay = self._s16(data, 2)
        self.state.az = self._s16(data, 4)
        self.state.gx = self._s16(data, 6)
        self.state.gy = self._s16(data, 8)
        self.state.gz = self._s16(data, 10)
        self.state.mx = self._s16(data, 12)
        self.state.my = self._s16(data, 14)
        self.state.mz = self._s16(data, 16)
        return True

    def _decode_gps_position(self, data: bytes) -> bool:
        self.state.gps_longitude = self._s32(data, 0) * 0.0000001
        self.state.gps_latitude = self._s32(data, 4) * 0.0000001
        self.state.gps_altitude = self._s32(data, 8) * 0.001
        self.state.gps_satellites = data[15]
        return True

    def _decode_gps_velocity(self, data: bytes) -> bool:
        north_obs = self._s32(data, 0) * 0.01
        east_obs = self._s32(data, 4) * 0.01
        self.state.gps_velocity_n = self._s32(data, 8) * 0.01
        self.state.gps_velocity_e = self._s32(data, 12) * 0.01
        if not self._has_fusion_xy and (north_obs != 0.0 or east_obs != 0.0):
            self.state.x = east_obs
            self.state.y = north_obs
        return True

    def _decode_vertical_observation(self, data: bytes) -> bool:
        baro_altitude = self._s32(data, 0) / 100.0
        ultrasonic_altitude = self._s32(data, 4) / 100.0
        opt_vel_p = self._s32(data, 8) / 100.0
        opt_vel_r = self._s32(data, 12) / 100.0
        self.state.baro_altitude = self._distance_to_meters(baro_altitude)
        self.state.ultrasonic_altitude = self._distance_to_meters(ultrasonic_altitude)
        self.state.rangefinder_distance = self.state.ultrasonic_altitude
        self.state.optical_flow_p = opt_vel_p
        self.state.optical_flow_r = opt_vel_r
        return True

    def _decode_fusion_u(self, data: bytes) -> bool:
        altitude = self._s32(data, 0) / 100.0
        vertical_speed = self._s32(data, 4) / 100.0
        vertical_accel = self._s32(data, 8) / 100.0
        self.state.altitude = self._distance_to_meters(altitude)
        self.state.vertical_speed = self._distance_to_meters(vertical_speed)
        self.state.vertical_accel = self._distance_to_meters(vertical_accel)
        return True

    def _decode_fusion_ne(self, data: bytes) -> bool:
        north = self._s32(data, 0) * 0.01
        east = self._s32(data, 4) * 0.01
        north_speed = self._s32(data, 8) * 0.01
        east_speed = self._s32(data, 12) * 0.01
        if north != 0.0 or east != 0.0:
            self.state.x = east
            self.state.y = north
            self._has_fusion_xy = True
        if north_speed != 0.0 or east_speed != 0.0:
            self.state.horizontal_speed = math.hypot(north_speed, east_speed)
        return True

    def _decode_track(self, data: bytes) -> bool:
        east_cm, north_cm, up_cm = struct.unpack_from("<fff", data, 0)
        if math.isfinite(east_cm) and math.isfinite(north_cm):
            self.state.x = east_cm
            self.state.y = north_cm
        if math.isfinite(up_cm):
            self.state.altitude = self._cm_to_meters(up_cm)
        return True

    def _decode_ahrs(self, data: bytes) -> bool:
        east_cm, north_cm, up_cm = struct.unpack_from("<fff", data, 0)
        east_speed_cm_s, north_speed_cm_s, vertical_speed_cm_s = struct.unpack_from("<fff", data, 12)
        if math.isfinite(east_cm) and math.isfinite(north_cm) and (east_cm != 0.0 or north_cm != 0.0):
            self.state.x = east_cm
            self.state.y = north_cm
        if math.isfinite(up_cm):
            self.state.altitude = self._cm_to_meters(up_cm)
        if math.isfinite(east_speed_cm_s) and math.isfinite(north_speed_cm_s):
            self.state.horizontal_speed = math.hypot(
                self._cm_to_meters(east_speed_cm_s),
                self._cm_to_meters(north_speed_cm_s),
            )
        if math.isfinite(vertical_speed_cm_s):
            self.state.vertical_speed = self._cm_to_meters(vertical_speed_cm_s)
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
            if 0.2 <= step <= 120.0:
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
    def _cm_to_meters(value: float) -> float:
        return value / 100.0

    @staticmethod
    def _voltage_to_percent(voltage: float) -> float:
        if voltage <= 0:
            return 0.0
        return max(0.0, min(100.0, (voltage - 14.0) / (16.8 - 14.0) * 100.0))

    @staticmethod
    def _flight_mode_name(mode: int) -> str:
        if mode == 1:
            return "姿态"
        if mode == 2:
            return "定高"
        return f"模式 {mode}"


class TelemetryThread(QThread):
    state_changed = pyqtSignal(object)
    status_changed = pyqtSignal(bool, str, dict)
    log_generated = pyqtSignal(str, str)

    def __init__(self, port: str, baudrate: int = 460800, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self._stop_requested = False
        self._send_queue: queue.Queue[bytes] = queue.Queue()

    def stop(self) -> None:
        self._stop_requested = True
        if self.isRunning():
            self.wait(1800)

    def send_bytes(self, data: bytes) -> None:
        if not data:
            return
        self._send_queue.put(bytes(data))

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
                write_timeout=0.15,
            ) as stream:
                stream.dtr = False
                stream.rts = False
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
                    while True:
                        try:
                            outbound = self._send_queue.get_nowait()
                        except queue.Empty:
                            break
                        stream.write(outbound)
                        stream.flush()
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


class CoordinateThread(QThread):
    coordinate_changed = pyqtSignal(object)
    status_changed = pyqtSignal(bool, str, dict)
    log_generated = pyqtSignal(str, str)

    def __init__(self, port: str, baudrate: int = 115200, parent=None) -> None:
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
                "缺少 pyserial，无法打开 UART2 坐标口",
                {"port": self.port, "packets": 0, "invalid": 0},
            )
            self.log_generated.emit(
                "ERROR", "请先安装 pyserial：pip install pyserial"
            )
            return

        parser = FiretruckCoordinateParser()
        packets = 0
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
                stream.dtr = False
                stream.rts = False
                self.log_generated.emit(
                    "INFO", f"UART2 坐标串口已打开：{self.port} @ {self.baudrate}"
                )
                self.status_changed.emit(
                    False,
                    f"坐标口已打开：{self.port}，等待 FC FF E1 数据",
                    {"port": self.port, "packets": packets, "invalid": 0},
                )
                while not self._stop_requested:
                    chunk = stream.read(512)
                    now = time.monotonic()
                    for frame in parser.feed(chunk):
                        packets += 1
                        last_valid = now
                        self.coordinate_changed.emit(frame)

                    if now - last_status >= 1.0:
                        active = last_valid > 0 and now - last_valid <= 2.5
                        if active:
                            message = f"UART2 坐标在线：{self.port}，已解析 {packets} 包"
                        else:
                            message = f"坐标口已打开：{self.port}，等待 FC FF E1 数据"
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
                f"UART2 坐标口打开失败：{exc}",
                {
                    "port": self.port,
                    "packets": packets,
                    "invalid": parser.invalid_frames,
                },
            )
            self.log_generated.emit("ERROR", f"UART2 坐标口连接失败：{exc}")
        finally:
            self.status_changed.emit(
                False,
                "UART2 坐标口已断开",
                {
                    "port": self.port,
                    "packets": packets,
                    "invalid": parser.invalid_frames,
                },
            )
