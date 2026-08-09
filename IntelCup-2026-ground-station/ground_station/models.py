from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


FIRE_CENTER_ROI_SCALE = 0.5


@dataclass
class DroneState:
    connected: bool = True
    camera_connected: bool = False
    telemetry_connected: bool = True
    ai_ready: bool = True
    armed: bool = False
    flight_mode: str = "STANDBY"
    flight_phase: str = "任务待命"
    x: float = 35.0
    y: float = 35.0
    altitude: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    roll_gyro: float = 0.0
    pitch_gyro: float = 0.0
    yaw_gyro: float = 0.0
    imu_temp: float = 0.0
    vertical_accel: float = 0.0
    ax: int = 0
    ay: int = 0
    az: int = 0
    gx: int = 0
    gy: int = 0
    gz: int = 0
    mx: int = 0
    my: int = 0
    mz: int = 0
    baro_altitude: float = 0.0
    ultrasonic_altitude: float = 0.0
    gps_longitude: float = 0.0
    gps_latitude: float = 0.0
    gps_altitude: float = 0.0
    gps_velocity_e: float = 0.0
    gps_velocity_n: float = 0.0
    gps_satellites: int = 0
    optical_flow_p: float = 0.0
    optical_flow_r: float = 0.0
    horizontal_speed: float = 0.0
    vertical_speed: float = 0.0
    battery_percent: float = 92.0
    battery_voltage: float = 16.4
    optical_flow_quality: int = 86
    rangefinder_distance: float = 0.0
    link_latency_ms: int = 26
    packet_loss_percent: float = 0.2
    current_waypoint: int = 0
    total_waypoints: int = 6
    mission_progress: float = 0.0
    elapsed_seconds: int = 0
    distance_travelled: float = 0.0
    warning: str = ""
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class CameraState:
    connected: bool = False
    source: str = "模拟画面"
    resolution: str = "1280 × 720"
    fps: float = 15.0
    frame_age_ms: int = 0
    reconnect_count: int = 0
    last_error: str = ""
    source_kind: str = "none"


@dataclass
class FireDetection:
    bbox: tuple[int, int, int, int]
    confidence: float
    area: float
    center_x: int
    center_y: int
    frame_width: int
    frame_height: int
    warm_ratio: float = 0.0
    core_ratio: float = 0.0
    kind: str = "k230_red_blob"
    consecutive_frames: int = 1
    required_frames: int = 20
    confirmed: bool = False


def bbox_inside_center_roi(
    bbox: tuple[int, int, int, int],
    frame_width: int,
    frame_height: int,
    roi_scale: float = FIRE_CENTER_ROI_SCALE,
) -> bool:
    """Return whether an entire image-space box is inside the centered ROI."""

    if frame_width <= 0 or frame_height <= 0:
        return False
    scale = max(0.0, min(1.0, float(roi_scale)))
    roi_width = frame_width * scale
    roi_height = frame_height * scale
    roi_left = (frame_width - roi_width) / 2.0
    roi_top = (frame_height - roi_height) / 2.0
    roi_right = roi_left + roi_width
    roi_bottom = roi_top + roi_height
    x, y, width, height = bbox
    return (
        width > 0
        and height > 0
        and x >= roi_left
        and y >= roi_top
        and x + width <= roi_right
        and y + height <= roi_bottom
    )


def fire_detection_inside_center_roi(
    detection: FireDetection,
    roi_scale: float = FIRE_CENTER_ROI_SCALE,
) -> bool:
    return bbox_inside_center_roi(
        detection.bbox,
        detection.frame_width,
        detection.frame_height,
        roi_scale,
    )


@dataclass
class FaceMatch:
    bbox: tuple[int, int, int, int]
    name: str
    confidence: float
    detection_confidence: float
    frame_width: int
    frame_height: int
    matched: bool = False


@dataclass
class OCRMatch:
    polygon: tuple[
        tuple[int, int],
        tuple[int, int],
        tuple[int, int],
        tuple[int, int],
    ]
    text: str
    confidence: float
    frame_width: int
    frame_height: int


@dataclass
class DetectionEvent:
    event_id: str = field(default_factory=lambda: uuid4().hex[:8].upper())
    target_type: str = "模拟火源"
    confidence: float = 0.92
    x: float = 0.0
    y: float = 0.0
    altitude: float = 0.0
    source: str = "视觉检测"
    review_state: str = "待确认"
    command_id: str = ""
    bbox: tuple[int, int, int, int] | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CommandIntent:
    action: str
    source: str
    label: str
    confidence: float = 1.0
    risk_level: str = "low"
    requires_confirmation: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    command_id: str = field(default_factory=lambda: uuid4().hex[:8].upper())
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SelectionState:
    target_id: str
    source: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None
    review_state: str = "待确认"
    command_id: str = field(default_factory=lambda: uuid4().hex[:8].upper())
    event_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
