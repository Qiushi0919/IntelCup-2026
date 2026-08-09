from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2

from models import CameraState, DroneState


@dataclass
class FlightSample:
    timestamp: datetime
    elapsed_s: float
    state: DroneState
    camera: CameraState
    route_sequence: list[str]
    route_track: list[tuple[float, float]]
    planned_waypoints: dict[str, tuple[float, float, float]]
    system_logs: list[tuple[str, str, str]]


@dataclass
class RecognitionRecord:
    timestamp: datetime
    target_type: str
    label: str
    confidence: float
    x: float
    y: float
    altitude: float
    image_filename: str


@dataclass
class FlightRecord:
    started_at: datetime
    ended_at: datetime | None = None
    samples: list[FlightSample] = field(default_factory=list)
    image_files: list[tuple[datetime, str]] = field(default_factory=list)
    route_sequence: list[str] = field(default_factory=list)
    planned_waypoints: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    route_track: list[tuple[float, float]] = field(default_factory=list)
    system_logs: list[tuple[str, str, str]] = field(default_factory=list)
    recognition_records: list[RecognitionRecord] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        end = self.ended_at or datetime.now()
        return max(0.0, (end - self.started_at).total_seconds())


class FlightLogRecorder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.active: FlightRecord | None = None
        self.last_completed: FlightRecord | None = None
        self._last_armed: bool | None = None
        self._last_sample_time = 0.0
        self._last_image_time = 0.0
        self._latest_frame = None
        self._system_logs: list[tuple[str, str, str]] = []

    def update_latest_frame(self, frame) -> None:
        if frame is not None:
            self._latest_frame = frame.copy()

    def append_system_log(self, level: str, message: str) -> None:
        item = (datetime.now().strftime("%H:%M:%S"), level, message)
        self._system_logs.append(item)
        self._system_logs = self._system_logs[-200:]

    def record_recognition(
        self,
        target_type: str,
        label: str,
        confidence: float,
        state: DroneState,
        bbox: tuple[int, int, int, int] | None = None,
        frame_width: int = 0,
        frame_height: int = 0,
        overlay_label: str = "TARGET",
        recognition_frame=None,
    ) -> bool:
        """Save one annotated recognition frame into the active flight record."""

        source_frame = recognition_frame if recognition_frame is not None else self._latest_frame
        if self.active is None or source_frame is None:
            return False
        frame = source_frame.copy()
        image_height, image_width = frame.shape[:2]
        if bbox is not None and image_width > 0 and image_height > 0:
            source_width = frame_width if frame_width > 0 else image_width
            source_height = frame_height if frame_height > 0 else image_height
            scale_x = image_width / source_width
            scale_y = image_height / source_height
            x, y, width, height = bbox
            x1 = max(0, min(image_width - 1, round(x * scale_x)))
            y1 = max(0, min(image_height - 1, round(y * scale_y)))
            x2 = max(x1 + 1, min(image_width - 1, round((x + width) * scale_x)))
            y2 = max(y1 + 1, min(image_height - 1, round((y + height) * scale_y)))
            color = {
                "人脸识别": (80, 220, 80),
                "火源识别": (40, 40, 240),
            }.get(target_type, (255, 180, 40))
            thickness = max(2, round(min(image_width, image_height) / 300))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            caption = f"{overlay_label} {confidence:.0%}"
            font_scale = max(0.55, min(image_width, image_height) / 900)
            (text_width, text_height), baseline = cv2.getTextSize(
                caption,
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                thickness,
            )
            text_top = max(0, y1 - text_height - baseline - 8)
            cv2.rectangle(
                frame,
                (x1, text_top),
                (min(image_width - 1, x1 + text_width + 10), y1),
                (12, 22, 30),
                -1,
            )
            cv2.putText(
                frame,
                caption,
                (x1 + 5, max(text_height + 2, y1 - baseline - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                color,
                thickness,
                cv2.LINE_AA,
            )

        now = datetime.now()
        flight_dir = self._flight_asset_dir(self.active)
        flight_dir.mkdir(parents=True, exist_ok=True)
        index = len(self.active.recognition_records) + 1
        filename = f"recognition_{index:02d}_{now.strftime('%H%M%S_%f')}.jpg"
        path = flight_dir / filename
        if not cv2.imwrite(str(path), frame):
            return False
        self.active.recognition_records.append(
            RecognitionRecord(
                timestamp=now,
                target_type=target_type,
                label=label,
                confidence=max(0.0, min(1.0, float(confidence))),
                x=state.x,
                y=state.y,
                altitude=state.altitude,
                image_filename=filename,
            )
        )
        return True

    def observe_state(
        self,
        state: DroneState,
        camera: CameraState,
        route_sequence: list[str],
        route_track: list[tuple[float, float]],
        planned_waypoints: dict[str, tuple[float, float, float]],
    ) -> tuple[str, FlightRecord | None]:
        event = ""
        completed: FlightRecord | None = None
        armed = bool(state.armed)
        if self._last_armed is None:
            self._last_armed = armed
        elif not self._last_armed and armed:
            self._start_record(route_sequence, planned_waypoints, route_track)
            event = "started"
        elif self._last_armed and not armed and self.active is not None:
            self._sample(
                state,
                camera,
                route_sequence,
                route_track,
                planned_waypoints,
                force=True,
            )
            self.active.ended_at = datetime.now()
            self.active.route_sequence = list(route_sequence)
            self.active.route_track = list(route_track)
            self.active.system_logs = list(self._system_logs)
            self.last_completed = self.active
            completed = self.active
            self.active = None
            event = "completed"
        self._last_armed = armed

        if self.active is not None:
            self._sample(
                state,
                camera,
                route_sequence,
                route_track,
                planned_waypoints,
            )
        return event, completed

    def _start_record(
        self,
        route_sequence: list[str],
        planned_waypoints: dict[str, tuple[float, float, float]],
        route_track: list[tuple[float, float]],
    ) -> None:
        self.active = FlightRecord(
            started_at=datetime.now(),
            route_sequence=list(route_sequence),
            planned_waypoints=dict(planned_waypoints),
            route_track=list(route_track),
            system_logs=list(self._system_logs),
        )
        self._last_sample_time = 0.0
        self._last_image_time = 0.0

    def _sample(
        self,
        state: DroneState,
        camera: CameraState,
        route_sequence: list[str],
        route_track: list[tuple[float, float]],
        planned_waypoints: dict[str, tuple[float, float, float]],
        force: bool = False,
    ) -> None:
        if self.active is None:
            return
        now = datetime.now()
        elapsed = (now - self.active.started_at).total_seconds()
        if not force and elapsed - self._last_sample_time < 1.0:
            return
        self._last_sample_time = elapsed
        self.active.route_sequence = list(route_sequence)
        self.active.route_track = list(route_track)
        self.active.planned_waypoints = dict(planned_waypoints)
        self.active.system_logs = list(self._system_logs)
        self.active.samples.append(
            FlightSample(
                timestamp=now,
                elapsed_s=elapsed,
                state=self._copy_state(state),
                camera=self._copy_camera(camera),
                route_sequence=list(route_sequence),
                route_track=list(route_track),
                planned_waypoints=dict(planned_waypoints),
                system_logs=list(self._system_logs[-40:]),
            )
        )
        self.active.samples = self.active.samples[-1200:]

        if (
            self._latest_frame is not None
            and (force or elapsed - self._last_image_time >= 8.0)
            and len(self.active.image_files) < 8
        ):
            self._last_image_time = elapsed
            flight_dir = self._flight_asset_dir(self.active)
            flight_dir.mkdir(parents=True, exist_ok=True)
            filename = f"camera_{len(self.active.image_files) + 1:02d}_{int(elapsed):04d}s.jpg"
            path = flight_dir / filename
            cv2.imwrite(str(path), self._latest_frame)
            self.active.image_files.append((now, filename))

    def export_markdown(self, map_image_path: Path | None = None) -> Path:
        record = self.last_completed or self.active
        if record is None:
            raise RuntimeError("还没有可导出的飞行记录。请先完成一次解锁到上锁的飞行。")
        if record.ended_at is None:
            record.ended_at = datetime.now()
        flight_dir = self._flight_asset_dir(record)
        flight_dir.mkdir(parents=True, exist_ok=True)
        if map_image_path is not None and map_image_path.exists():
            target = flight_dir / "route_map.png"
            target.write_bytes(map_image_path.read_bytes())

        markdown = self._build_markdown(record, include_map=map_image_path is not None)
        output_path = flight_dir / "flight_log.md"
        output_path.write_text(markdown, encoding="utf-8")
        self.last_completed = record
        return output_path

    def _build_markdown(self, record: FlightRecord, include_map: bool) -> str:
        samples = record.samples
        final_state = samples[-1].state if samples else None
        route_text = "".join(record.route_sequence) if record.route_sequence else "未记录"
        lines: list[str] = [
            "# 无人机飞行日志",
            "",
            f"- 起飞/解锁时间：{record.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 锁定/结束时间：{record.ended_at.strftime('%Y-%m-%d %H:%M:%S') if record.ended_at else '记录中'}",
            f"- 记录时长：{record.duration_s:.1f} 秒",
            f"- 规划航线：{route_text}",
            f"- 采样点数：{len(samples)}",
            f"- 图传采样：{len(record.image_files)} 张",
            f"- 视觉识别记录：{len(record.recognition_records)} 条",
            "",
        ]
        if final_state is not None:
            lines += [
                "## 最终状态",
                "",
                f"- 飞控模式：{final_state.flight_mode}",
                f"- 飞行阶段：{final_state.flight_phase}",
                f"- 位置：X {final_state.x:.1f} cm，Y {final_state.y:.1f} cm，高度 {final_state.altitude:.2f} m",
                f"- 姿态：Roll {final_state.roll:.1f}°，Pitch {final_state.pitch:.1f}°，Yaw {final_state.yaw:.1f}°",
                f"- 电压：{final_state.battery_voltage:.2f} V",
                f"- 链路：延迟 {final_state.link_latency_ms} ms，丢包 {final_state.packet_loss_percent:.1f}%",
                "",
            ]
        lines += [
            "## 航点与航线",
            "",
            "| 序号 | 区域 | X(cm) | Y(cm) | Z(cm) |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
        for index, region in enumerate(record.route_sequence, start=1):
            waypoint = record.planned_waypoints.get(region)
            if waypoint is None:
                lines.append(f"| P{index} | {region} | - | - | - |")
            else:
                x, y, z = waypoint
                lines.append(f"| P{index} | {region} | {x:.0f} | {y:.0f} | {z:.0f} |")
        if not record.route_sequence:
            lines.append("| - | 未记录 | - | - | - |")
        lines.append("")
        if include_map:
            lines += ["![航线规划与实际航迹](route_map.png)", ""]

        lines += [
            "## 采样数据",
            "",
            "| 时间 | t(s) | 解锁 | 模式 | X(cm) | Y(cm) | 高度(m) | Roll | Pitch | Yaw | 电压(V) | 图传 |",
            "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for sample in self._thin_samples(samples, limit=80):
            s = sample.state
            c = sample.camera
            lines.append(
                "| "
                f"{sample.timestamp.strftime('%H:%M:%S')} | {sample.elapsed_s:.1f} | "
                f"{'是' if s.armed else '否'} | {s.flight_mode} | "
                f"{s.x:.1f} | {s.y:.1f} | {s.altitude:.2f} | "
                f"{s.roll:.1f} | {s.pitch:.1f} | {s.yaw:.1f} | {s.battery_voltage:.2f} | "
                f"{'在线' if c.connected else '离线'} {c.fps:.1f} FPS |"
            )
        lines.append("")

        if record.route_track:
            lines += [
                "## 实际航迹点",
                "",
                "以下为地图窗口记录到的轨迹点，单位 cm，最多展示前 160 个点。",
                "",
                "```text",
            ]
            for index, (x, y) in enumerate(record.route_track[:160], start=1):
                lines.append(f"{index:03d}: x={x:.1f}, y={y:.1f}")
            lines += ["```", ""]

        if record.image_files:
            lines += ["## 图传画面采样", ""]
            for timestamp, filename in record.image_files:
                lines += [
                    f"### {timestamp.strftime('%H:%M:%S')}",
                    "",
                    f"![图传采样]({filename})",
                    "",
                ]

        if record.recognition_records:
            lines += ["## 视觉识别结果", ""]
            for recognition in record.recognition_records:
                lines += [
                    f"### {recognition.timestamp.strftime('%H:%M:%S')} · "
                    f"{recognition.target_type} · {recognition.label}",
                    "",
                    f"- 识别置信度：{recognition.confidence:.1%}",
                    f"- 无人机位置：X {recognition.x:.1f} cm，"
                    f"Y {recognition.y:.1f} cm，高度 {recognition.altitude:.2f} m",
                    "",
                    f"![{recognition.target_type}识别结果]({recognition.image_filename})",
                    "",
                ]

        lines += [
            "## 设备状态与系统日志",
            "",
            "| 时间 | 级别 | 事件 |",
            "| --- | --- | --- |",
        ]
        for time_text, level, message in record.system_logs[-80:]:
            safe_message = message.replace("|", "/")
            lines.append(f"| {time_text} | {level} | {safe_message} |")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _thin_samples(samples: list[FlightSample], limit: int) -> list[FlightSample]:
        if len(samples) <= limit:
            return samples
        step = max(1, math.ceil(len(samples) / limit))
        return samples[::step]

    def _flight_asset_dir(self, record: FlightRecord) -> Path:
        name = "flight_" + record.started_at.strftime("%Y%m%d_%H%M%S")
        return self.output_dir / name

    @staticmethod
    def _copy_state(state: DroneState) -> DroneState:
        return DroneState(**state.__dict__)

    @staticmethod
    def _copy_camera(camera: CameraState) -> CameraState:
        return CameraState(**camera.__dict__)
