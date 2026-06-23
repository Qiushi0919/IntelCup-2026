from __future__ import annotations

import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from PyQt5.QtCore import QProcess, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from models import (
    CameraState,
    CommandIntent,
    DetectionEvent,
    DroneState,
    FireDetection,
)


def card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


class VideoCanvas(QWidget):
    target_clicked = pyqtSignal(str, object)
    target_missed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._frame: QImage | None = None
        self._pixmap: QPixmap | None = None
        self._state = DroneState()
        self._camera = CameraState()
        self._synthetic_time = 0.0
        self._demo_mode = False
        self._detections: list[FireDetection] = []
        self._detections_hold_until = 0.0
        self._confirmed_until = 0.0
        self._frame_size = (1280, 720)
        self._display_scale = 1.0
        self._display_detection_boxes: list[
            tuple[str, QRectF, FireDetection]
        ] = []
        self._view_offset = QPointF()
        self._selected_target_id = ""
        self._hover_target_id = ""
        self._interaction_message = ""
        self._interaction_message_until = 0.0
        self._detection_timer = QTimer(self)
        self._detection_timer.setInterval(200)
        self._detection_timer.timeout.connect(self._expire_detections)
        self._detection_timer.start()
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    def set_display_scale(self, large: bool) -> None:
        self._display_scale = 2.56 if large else 1.0
        self.update()

    def set_frame(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        self._frame_size = (width, height)
        self._frame = QImage(
            rgb.data, width, height, channels * width, QImage.Format_RGB888
        ).copy()
        self._pixmap = QPixmap.fromImage(self._frame)
        self.update()

    def set_demo_mode(self, enabled: bool) -> None:
        self._demo_mode = enabled
        self.update()

    def clear_selection(self) -> None:
        self._selected_target_id = ""
        self._hover_target_id = ""
        self.update()

    def select_target(self, target_id: str) -> None:
        self._selected_target_id = target_id
        self.update()

    def get_detection(self, target_id: str) -> FireDetection | None:
        try:
            index = int(target_id.rsplit("-", 1)[1]) - 1
        except (IndexError, ValueError):
            return None
        if 0 <= index < len(self._detections):
            return self._detections[index]
        return None

    def set_detections(self, detections: list[FireDetection]) -> None:
        now = time.monotonic()
        if detections:
            self._detections = detections
            self._detections_hold_until = max(
                self._detections_hold_until, now + 1.6
            )
        elif now >= self._detections_hold_until:
            self._detections = []
        self.update()

    def confirm_detection(
        self, detection: FireDetection, hold_seconds: float = 6.0
    ) -> None:
        now = time.monotonic()
        self._detections = [detection]
        self._detections_hold_until = now + hold_seconds
        self._confirmed_until = now + hold_seconds
        self.update()

    def _expire_detections(self) -> None:
        now = time.monotonic()
        if self._detections and now >= self._detections_hold_until:
            self._detections = []
            self._confirmed_until = 0.0
            self.update()

    def set_state(self, state: DroneState) -> None:
        self._state = state
        self._synthetic_time += 0.08
        self.update()

    def set_camera_state(self, state: CameraState) -> None:
        self._camera = state
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outer_rect = self.rect()
        painter.fillRect(outer_rect, QColor("#030910"))

        view_width = min(outer_rect.width(), int(outer_rect.height() * 16 / 9))
        view_height = min(outer_rect.height(), int(view_width * 9 / 16))
        view_width = int(view_height * 16 / 9)
        view_left = (outer_rect.width() - view_width) // 2
        view_top = (outer_rect.height() - view_height) // 2
        rect = QRect(0, 0, view_width, view_height)
        self._view_offset = QPointF(view_left, view_top)
        self._display_detection_boxes = []

        painter.save()
        painter.translate(view_left, view_top)
        content_rect = QRectF(rect)
        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                int(rect.width()),
                int(rect.height()),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = (rect.width() - scaled.width()) / 2
            y = (rect.height() - scaled.height()) / 2
            target = QRectF(x, y, scaled.width(), scaled.height())
            content_rect = target
            painter.drawPixmap(target, scaled, QRectF(scaled.rect()))
        else:
            self._draw_synthetic_scene(painter, rect)
        self._draw_overlay(painter, rect, content_rect)
        painter.restore()

        painter.setPen(QPen(QColor(70, 128, 157, 55), 1))
        painter.drawRoundedRect(
            QRectF(view_left, view_top, view_width, view_height).adjusted(1, 1, -2, -2),
            12,
            12,
        )

    def _draw_synthetic_scene(self, painter: QPainter, rect) -> None:
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor("#173953"))
        gradient.setColorAt(0.48, QColor("#1f5265"))
        gradient.setColorAt(0.49, QColor("#394f47"))
        gradient.setColorAt(1.0, QColor("#17271f"))
        painter.fillRect(rect, gradient)

        horizon = int(rect.height() * 0.49)
        painter.setPen(QPen(QColor(150, 215, 225, 45), 1))
        for offset in range(-8, 9):
            x = rect.center().x() + offset * 72
            painter.drawLine(rect.center().x(), horizon, x, rect.bottom())
        for i in range(1, 9):
            y = horizon + int((rect.height() - horizon) * (i / 9) ** 1.8)
            painter.drawLine(rect.left(), y, rect.right(), y)

        painter.setBrush(QColor(27, 34, 36, 180))
        painter.setPen(QPen(QColor("#5f7f7b"), 2))
        blocks = [
            QRectF(rect.width() * 0.12, horizon - 92, 145, 80),
            QRectF(rect.width() * 0.57, horizon - 76, 125, 65),
            QRectF(rect.width() * 0.75, horizon + 64, 130, 88),
        ]
        for block in blocks:
            painter.drawRoundedRect(block, 6, 6)

    def _draw_overlay(
        self, painter: QPainter, rect: QRect, content_rect: QRectF
    ) -> None:
        scale = self._display_scale
        painter.setPen(QPen(QColor(225, 245, 255, 135), 1))
        cx, cy = rect.center().x(), rect.center().y()
        arm = int(18 * scale)
        gap = int(5 * scale)
        painter.drawLine(cx - arm, cy, cx - gap, cy)
        painter.drawLine(cx + gap, cy, cx + arm, cy)
        painter.drawLine(cx, cy - arm, cx, cy - gap)
        painter.drawLine(cx, cy + gap, cx, cy + arm)

        margin = int(16 * scale)
        painter.setFont(QFont("Microsoft YaHei UI", round(10 * scale), QFont.Bold))
        painter.setPen(QColor("#d8f4ff"))
        source = self._camera.source
        if self._demo_mode:
            status = "DEMO"
            source = "离线识别示例 · 非实时图传"
        elif self._camera.connected:
            status = "ONLINE"
        else:
            status = "NO SIGNAL"
            source = "未连接图传"
        painter.drawText(margin, int(26 * scale), f"{status}  |  {source}")
        painter.setFont(QFont("Microsoft YaHei UI", round(9 * scale)))
        painter.setPen(QColor("#91b7ca"))
        painter.drawText(
            margin,
            int(47 * scale),
            f"{self._camera.resolution}  {self._camera.fps:.1f} FPS   "
            f"高度 {self._state.altitude:.2f} m",
        )

        if self._pixmap is not None and not self._pixmap.isNull():
            self._draw_fire_detections(painter, content_rect)

        if self._demo_mode:
            banner_width = min(rect.width() * 0.46, 310 * scale)
            banner_height = 28 * scale
            banner = QRectF(
                rect.right() - banner_width - margin,
                margin,
                banner_width,
                banner_height,
            )
            painter.fillRect(banner, QColor(128, 74, 13, 225))
            painter.setPen(QColor("#ffe0a3"))
            painter.setFont(
                QFont("Microsoft YaHei UI", round(9 * scale), QFont.Bold)
            )
            painter.drawText(
                banner.adjusted(8 * scale, 0, -8 * scale, 0),
                Qt.AlignVCenter | Qt.AlignRight,
                "离线 DEMO · 结果仅用于演示",
            )

        if (
            self._interaction_message
            and time.monotonic() < self._interaction_message_until
        ):
            message_rect = QRectF(
                margin,
                rect.bottom() - 42 * scale,
                min(rect.width() - margin * 2, 360 * scale),
                30 * scale,
            )
            painter.fillRect(message_rect, QColor(10, 27, 43, 225))
            painter.setPen(QColor("#dbeeff"))
            painter.setFont(QFont("Microsoft YaHei UI", round(9 * scale)))
            painter.drawText(
                message_rect.adjusted(9 * scale, 0, -9 * scale, 0),
                Qt.AlignVCenter,
                self._interaction_message,
            )

        painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -2, -2), 12, 12)

    def _draw_fire_detections(self, painter: QPainter, rect: QRectF) -> None:
        if not self._detections:
            return

        frame_width, frame_height = self._frame_size
        if frame_width <= 0 or frame_height <= 0:
            return
        scale_x = rect.width() / frame_width
        scale_y = rect.height() / frame_height
        ui_scale = self._display_scale
        confirmed = time.monotonic() < self._confirmed_until

        for index, detection in enumerate(self._detections[:5], start=1):
            target_id = f"FIRE-{index:02d}"
            x, y, width, height = detection.bbox
            raw_box = QRectF(
                rect.left() + x * scale_x,
                rect.top() + y * scale_y,
                width * scale_x,
                height * scale_y,
            )
            minimum_size = (48.0 if confirmed else 34.0) * min(ui_scale, 1.5)
            box_width = max(raw_box.width(), minimum_size)
            box_height = max(raw_box.height(), minimum_size)
            box = QRectF(
                raw_box.center().x() - box_width / 2,
                raw_box.center().y() - box_height / 2,
                box_width,
                box_height,
            )
            box = box.intersected(rect)
            self._display_detection_boxes.append(
                (
                    target_id,
                    box.translated(self._view_offset),
                    detection,
                )
            )
            label_height = max(25.0, 25.0 * ui_scale)
            selected = target_id == self._selected_target_id
            hovered = target_id == self._hover_target_id
            box_color = (
                QColor("#53d7ff")
                if selected
                else QColor("#ffbd52")
                if hovered
                else QColor("#ff303d" if confirmed else "#ff5454")
            )
            painter.setBrush(Qt.NoBrush)
            painter.setPen(
                QPen(
                    box_color,
                    max(
                        4 if confirmed or selected else 2,
                        round((3 if confirmed or selected else 2) * ui_scale),
                    ),
                )
            )
            painter.drawRect(box)
            if confirmed:
                painter.setPen(
                    QPen(
                        QColor(255, 57, 68, 185),
                        max(2, round(2 * ui_scale)),
                    )
                )
                painter.drawEllipse(box.adjusted(-7, -7, 7, 7))

            label = (
                f"{target_id} · 已确认  {detection.confidence:.0%}"
                if confirmed
                else f"{target_id} · 火源  {detection.confidence:.0%}"
            )
            label_width = max(
                box.width(),
                (132.0 if confirmed else 96.0) * min(ui_scale, 1.5),
            )
            label_left = min(
                max(rect.left(), box.left()),
                max(rect.left(), rect.right() - label_width),
            )
            label_top = max(rect.top(), box.top() - label_height)
            painter.fillRect(
                QRectF(
                    label_left,
                    label_top,
                    label_width,
                    label_height,
                ),
                QColor(
                    25,
                    112,
                    145,
                    235,
                )
                if selected
                else QColor(196, 28, 42, 235 if confirmed else 220),
            )
            painter.setPen(Qt.white)
            painter.setFont(
                QFont("Microsoft YaHei UI", round(9 * ui_scale), QFont.Bold)
            )
            painter.drawText(
                QRectF(
                    label_left + 7 * ui_scale,
                    label_top,
                    max(1.0, label_width - 10 * ui_scale),
                    label_height,
                ),
                Qt.AlignVCenter,
                label,
            )

    def mouseDoubleClickEvent(self, event) -> None:
        for target_id, box, detection in reversed(
            self._display_detection_boxes
        ):
            if box.contains(event.pos()):
                self._selected_target_id = target_id
                self._interaction_message = (
                    f"已选择 {target_id}，请在下方候选卡确认或取消"
                )
                self._interaction_message_until = time.monotonic() + 3.0
                self.target_clicked.emit(target_id, detection)
                self.update()
                event.accept()
                return
        self._interaction_message = "未命中检测框，请双击红色目标框"
        self._interaction_message_until = time.monotonic() + 2.5
        self.target_missed.emit(self._interaction_message)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        hovered = ""
        for target_id, box, _detection in reversed(
            self._display_detection_boxes
        ):
            if box.contains(event.pos()):
                hovered = target_id
                break
        if hovered != self._hover_target_id:
            self._hover_target_id = hovered
            self.update()
        event.accept()

    def leaveEvent(self, event) -> None:
        if self._hover_target_id:
            self._hover_target_id = ""
            self.update()
        super().leaveEvent(event)


class VideoPanel(QFrame):
    snapshot_requested = pyqtSignal()
    connect_camera_requested = pyqtSignal()
    demo_requested = pyqtSignal()
    target_selected = pyqtSignal(str, object)
    target_missed = pyqtSignal(str)
    lens_correction_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        toolbar = QHBoxLayout()
        title = QLabel("无人机实时画面")
        title.setObjectName("sectionTitle")
        self.mode_label = QLabel("模拟视觉链")
        self.mode_label.setObjectName("chipInfo")
        toolbar.addWidget(title)
        toolbar.addWidget(self.mode_label)
        toolbar.addStretch()

        connect_button = QPushButton("连接 AMB82")
        connect_button.clicked.connect(self.connect_camera_requested)
        demo_button = QPushButton("识别示例")
        demo_button.clicked.connect(self.demo_requested)
        self.lens_button = QPushButton("去畸变 ON")
        self.lens_button.setCheckable(True)
        self.lens_button.setChecked(True)
        self.lens_button.toggled.connect(self._on_lens_toggled)
        snapshot_button = QPushButton("截图")
        snapshot_button.clicked.connect(self.snapshot_requested)
        toolbar.addWidget(connect_button)
        toolbar.addWidget(demo_button)
        toolbar.addWidget(self.lens_button)
        toolbar.addWidget(snapshot_button)
        layout.addLayout(toolbar)

        self.canvas = VideoCanvas()
        self.canvas.target_clicked.connect(self.target_selected)
        self.canvas.target_missed.connect(self.target_missed)
        layout.addWidget(self.canvas, 1)

        footer = QHBoxLayout()
        self.camera_status = QLabel("● 模拟画面")
        self.camera_status.setObjectName("chipGood")
        self.hint = QLabel("双击检测框可将目标加入候选任务")
        self.hint.setObjectName("muted")
        footer.addWidget(self.camera_status)
        footer.addStretch()
        footer.addWidget(self.hint)
        layout.addLayout(footer)

    def _on_lens_toggled(self, enabled: bool) -> None:
        self.lens_button.setText("去畸变 ON" if enabled else "去畸变 OFF")
        self.lens_correction_toggled.emit(enabled)

    def set_lens_correction(self, enabled: bool) -> None:
        self.lens_button.blockSignals(True)
        self.lens_button.setChecked(enabled)
        self.lens_button.setText("去畸变 ON" if enabled else "去畸变 OFF")
        self.lens_button.blockSignals(False)

    def set_state(self, state: DroneState) -> None:
        self.canvas.set_state(state)

    def set_camera_state(self, state: CameraState) -> None:
        self.canvas.set_camera_state(state)
        if state.connected:
            age_text = (
                f" · 帧龄 {state.frame_age_ms} ms"
                if state.frame_age_ms >= 0
                else ""
            )
            self.camera_status.setText(
                f"● AMB82 在线  {state.fps:.1f} FPS{age_text}"
            )
            self.camera_status.setObjectName("chipGood")
            self.mode_label.setText("火源识别 ON")
        else:
            error = f" · {state.last_error}" if state.last_error else ""
            self.camera_status.setText(
                f"● 图传离线 · 重连 {state.reconnect_count} 次{error}"
            )
            self.camera_status.setObjectName(
                "chipWarn" if state.last_error else "chipInfo"
            )
            self.mode_label.setText("等待真实图传")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_demo_mode(self, detection_count: int) -> None:
        self.canvas.set_demo_mode(True)
        self.mode_label.setText("火源识别示例")
        self.camera_status.setText(
            f"● 离线 DEMO · {detection_count} 个候选 · 非实时图传"
        )
        self.camera_status.setObjectName(
            "chipGood" if detection_count else "chipWarn"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_live_mode(self) -> None:
        self.canvas.set_demo_mode(False)


class MetricBox(QFrame):
    def __init__(self, name: str, value: str, unit: str = "") -> None:
        super().__init__()
        self.setObjectName("metricBox")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(2)
        self.name = QLabel(name)
        self.name.setObjectName("metricName")
        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        self.unit = QLabel(unit)
        self.unit.setObjectName("muted")
        row = QHBoxLayout()
        row.addWidget(self.value)
        row.addWidget(self.unit)
        row.addStretch()
        layout.addWidget(self.name)
        layout.addLayout(row)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class StatusPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._large_display = False
        self._compact = False
        self._has_warning = False
        layout = QVBoxLayout(self)
        self._layout = layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(11)

        header = QHBoxLayout()
        title = QLabel("无人机状态")
        title.setObjectName("sectionTitle")
        self.mode = QLabel("STANDBY")
        self.mode.setObjectName("chipInfo")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.mode)
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.altitude = MetricBox("高度", "0.00", "m")
        self.speed = MetricBox("水平速度", "0.00", "m/s")
        self.position = MetricBox("本地坐标", "4.0, 4.0", "m")
        self.attitude = MetricBox("姿态 R/P", "0.0 / 0.0", "°")
        self._secondary_metrics = [self.position, self.attitude]
        grid.addWidget(self.altitude, 0, 0)
        grid.addWidget(self.speed, 0, 1)
        grid.addWidget(self.position, 1, 0)
        grid.addWidget(self.attitude, 1, 1)
        layout.addLayout(grid)

        battery_row = QHBoxLayout()
        battery_label = QLabel("电池")
        battery_label.setObjectName("muted")
        self.battery_text = QLabel("92%")
        battery_row.addWidget(battery_label)
        battery_row.addStretch()
        battery_row.addWidget(self.battery_text)
        layout.addLayout(battery_row)
        self.battery = QProgressBar()
        self.battery.setRange(0, 100)
        self.battery.setValue(92)
        self.battery.setTextVisible(True)
        self.battery.setFormat("92%")
        layout.addWidget(self.battery)

        detail = QGridLayout()
        detail.setHorizontalSpacing(16)
        detail.setVerticalSpacing(7)
        self.phase = QLabel("任务待命")
        self.flow = QLabel("86")
        self.latency = QLabel("26 ms")
        self.waypoint = QLabel("0 / 10")
        rows = [
            ("任务阶段", self.phase),
            ("光流质量", self.flow),
            ("链路延迟", self.latency),
            ("当前航点", self.waypoint),
        ]
        self._detail_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for index, (label, widget) in enumerate(rows):
            name = QLabel(label)
            name.setObjectName("muted")
            detail.addWidget(name, index, 0)
            detail.addWidget(widget, index, 1, Qt.AlignRight)
            self._detail_rows[label] = (name, widget)
        layout.addLayout(detail)

        self.warning = QLabel("系统状态正常")
        self.warning.setObjectName("chipGood")
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self._layout.setContentsMargins(
            12 if compact else 14,
            10 if compact else 14,
            12 if compact else 14,
            10 if compact else 14,
        )
        self._layout.setSpacing(7 if compact else 11)
        for widget in self._secondary_metrics:
            widget.setVisible(not compact)
        hidden_detail_rows = {"光流质量", "当前航点"}
        if compact and self._large_display:
            hidden_detail_rows.update({"任务阶段", "链路延迟"})
        for key, row_widgets in self._detail_rows.items():
            for widget in row_widgets:
                widget.setVisible(not (compact and key in hidden_detail_rows))
        compact_height = 390 if self._large_display else 255
        self.warning.setVisible(
            not (compact and self._large_display and not self._has_warning)
        )
        self.setMinimumHeight(compact_height if compact else 0)
        self.setMaximumHeight(compact_height if compact else 16777215)
        self.updateGeometry()

    def set_display_scale(self, large: bool) -> None:
        self._large_display = large
        self.set_compact(self._compact)

    def set_state(self, state: DroneState) -> None:
        self.mode.setText(state.flight_mode)
        self.altitude.set_value(f"{state.altitude:.2f}")
        self.speed.set_value(f"{state.horizontal_speed:.2f}")
        self.position.set_value(f"{state.x:.1f}, {state.y:.1f}")
        self.attitude.set_value(f"{state.roll:.1f} / {state.pitch:.1f}")
        self.battery.setValue(int(state.battery_percent))
        self.battery.setFormat(f"{state.battery_percent:.0f}%")
        self.battery_text.setText(
            f"{state.battery_percent:.0f}%  ·  {state.battery_voltage:.1f} V"
        )
        self.phase.setText(state.flight_phase)
        self.flow.setText(str(state.optical_flow_quality))
        self.latency.setText(f"{state.link_latency_ms} ms")
        self.waypoint.setText(
            f"{state.current_waypoint} / {state.total_waypoints}"
        )
        if state.warning:
            self._has_warning = True
            self.warning.setText("⚠ " + state.warning)
            self.warning.setObjectName("chipWarn")
        else:
            self._has_warning = False
            armed = "已解锁" if state.armed else "已上锁"
            self.warning.setText(f"● 系统正常 · {armed}")
            self.warning.setObjectName("chipGood")
        self.warning.setVisible(
            not (self._compact and self._large_display and not self._has_warning)
        )
        self.warning.style().unpolish(self.warning)
        self.warning.style().polish(self.warning)


class MissionMap(QWidget):
    def __init__(self, waypoints: list[tuple[float, float]], parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._waypoints = waypoints
        self._state = DroneState()
        self._track: list[tuple[float, float]] = [(4.0, 4.0)]

    def set_state(self, state: DroneState) -> None:
        self._state = state
        point = (state.x, state.y)
        if math.hypot(
            point[0] - self._track[-1][0], point[1] - self._track[-1][1]
        ) > 0.25:
            self._track.append(point)
            self._track = self._track[-600:]
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.fillRect(rect, QColor("#091726"))
        painter.setPen(QPen(QColor("#1c354b"), 1))
        for i in range(0, 49, 4):
            x = rect.left() + rect.width() * i / 48
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())
        for i in range(0, 41, 4):
            y = rect.bottom() - rect.height() * i / 40
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        def point(x: float, y: float) -> QPointF:
            return QPointF(
                rect.left() + rect.width() * x / 48,
                rect.bottom() - rect.height() * y / 40,
            )

        painter.setBrush(QColor("#162334"))
        painter.setPen(QPen(QColor("#4d6174"), 1))
        obstacles = [
            (7, 23, 10, 9),
            (23, 23, 8, 9),
            (37, 23, 7, 9),
            (7, 9, 7, 9),
            (20, 9, 10, 9),
            (37, 4, 7, 14),
        ]
        for x, y, w, h in obstacles:
            top_left = point(x, y + h)
            bottom_right = point(x + w, y)
            painter.drawRoundedRect(
                QRectF(top_left, bottom_right).normalized(), 4, 4
            )

        painter.setPen(QPen(QColor("#5e839d"), 1, Qt.DashLine))
        route = QPainterPath()
        first = point(*self._waypoints[0])
        route.moveTo(first)
        for wp in self._waypoints[1:]:
            route.lineTo(point(*wp))
        painter.drawPath(route)

        if len(self._track) > 1:
            painter.setPen(QPen(QColor("#26c6da"), 2))
            track = QPainterPath()
            track.moveTo(point(*self._track[0]))
            for item in self._track[1:]:
                track.lineTo(point(*item))
            painter.drawPath(track)

        for index, wp in enumerate(self._waypoints):
            p = point(*wp)
            painter.setBrush(QColor("#3e85bd"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(p, 4, 4)
            if index in (0, len(self._waypoints) - 1):
                painter.setPen(QColor("#86aac3"))
                painter.drawText(p + QPointF(6, -6), str(index + 1))

        drone = point(self._state.x, self._state.y)
        painter.setBrush(QColor("#5ff0be"))
        painter.setPen(QPen(QColor("#d8fff1"), 2))
        painter.drawEllipse(drone, 7, 7)
        painter.setPen(QColor("#d8fff1"))
        painter.drawText(drone + QPointF(10, -8), "UAV")

        fire = point(26, 20)
        painter.setBrush(QColor("#ff5656"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(fire, 6, 6)

        painter.setPen(QColor("#6f879c"))
        painter.drawText(rect.adjusted(8, 6, -8, -6), Qt.AlignTop, "48 m × 40 m 任务场地")


class MapPanel(QFrame):
    def __init__(self, waypoints: list[tuple[float, float]], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        header = QHBoxLayout()
        title = QLabel("任务地图与实时航迹")
        title.setObjectName("sectionTitle")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.progress_text = QLabel("进度 0%")
        self.progress_text.setObjectName("chipInfo")
        self.progress_text.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.progress_text)
        layout.addLayout(header)
        self.map = MissionMap(waypoints)
        layout.addWidget(self.map, 1)

    def set_state(self, state: DroneState) -> None:
        self.map.set_state(state)
        self.progress_text.setText(f"进度 {state.mission_progress:.0f}%")


class EventTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 8, parent)
        self.setHorizontalHeaderLabels(
            ["事件 ID", "时间", "事件", "置信度", "位置 / 高度", "来源", "审核状态", "命令 ID"]
        )
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.setColumnWidth(0, 92)
        self.setColumnWidth(1, 82)
        self.setColumnWidth(3, 78)
        self.setColumnWidth(4, 150)
        self.setColumnWidth(6, 92)
        self.setColumnWidth(7, 92)

    def add_event(self, event: DetectionEvent) -> None:
        self.insertRow(0)
        values = [
            event.event_id,
            event.created_at.strftime("%H:%M:%S"),
            event.target_type,
            f"{event.confidence:.0%}",
            f"({event.x:.1f}, {event.y:.1f}) · {event.altitude:.1f} m",
            event.source,
            event.review_state,
            event.command_id or "—",
        ]
        for column, value in enumerate(values):
            self.setItem(0, column, QTableWidgetItem(value))

    def update_review_state(self, event_id: str, state: str) -> None:
        for row in range(self.rowCount()):
            identifier = self.item(row, 0)
            if identifier and identifier.text() == event_id:
                self.setItem(row, 6, QTableWidgetItem(state))
                return


class VoicePanel(QWidget):
    command_proposed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._asr_process: QProcess | None = None
        self._asr_script = (
            Path(__file__).resolve().parents[1]
            / "voice_asr"
            / "asr_realtime_openvino.py"
        )
        self._asr_python = self._find_asr_python()
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("启用语音输入")
        self.enabled.setChecked(True)
        layout.addWidget(self.enabled)
        self.health = QLabel("来源正常 · 尚无输入")
        self.health.setObjectName("chipGood")
        layout.addWidget(self.health)
        note = QLabel("语音只生成候选指令，高风险动作仍需屏幕确认。")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        self.input = QLineEdit("开始巡逻")
        self.input.setPlaceholderText("输入或转写语音，例如：返回起点")
        layout.addWidget(self.input)
        self.result = QLabel("等待语音输入")
        self.result.setWordWrap(True)
        self.result.setObjectName("chipInfo")
        layout.addWidget(self.result)
        parse = QPushButton("模拟识别并生成候选指令")
        parse.setObjectName("primaryButton")
        parse.clicked.connect(self._parse)
        layout.addWidget(parse)
        asr_controls = QHBoxLayout()
        self.asr_start = QPushButton("启动实时识别")
        self.asr_start.clicked.connect(self._start_asr)
        asr_controls.addWidget(self.asr_start)
        self.asr_stop = QPushButton("停止识别")
        self.asr_stop.setEnabled(False)
        self.asr_stop.clicked.connect(self._stop_asr)
        asr_controls.addWidget(self.asr_stop)
        layout.addLayout(asr_controls)
        self.asr_log = QPlainTextEdit()
        self.asr_log.setReadOnly(True)
        self.asr_log.setMaximumHeight(120)
        self.asr_log.setPlaceholderText("实时语音识别状态会显示在这里")
        layout.addWidget(self.asr_log)
        layout.addStretch()

    def _set_health(self, text: str, object_name: str) -> None:
        self.health.setText(text)
        self.health.setObjectName(object_name)
        self.health.style().unpolish(self.health)
        self.health.style().polish(self.health)

    def _parse(self) -> None:
        if not self.enabled.isChecked():
            self._set_health("语音输入已禁用", "chipWarn")
            return
        text = self.input.text().strip()
        mappings = [
            (("返航", "返回起点"), "RTL", "返回起点", "high", True),
            (("降落",), "LAND", "自动降落", "high", True),
            (("暂停", "悬停"), "HOLD", "暂停并悬停", "medium", False),
            (("继续",), "CONTINUE", "继续任务", "medium", False),
            (("开始巡逻", "开始任务"), "START_MISSION", "开始巡逻", "high", True),
            (("起飞",), "TAKEOFF", "自动起飞", "high", True),
            (("截图",), "SNAPSHOT", "保存截图", "low", False),
        ]
        for keywords, action, label, risk, confirm in mappings:
            if any(keyword in text for keyword in keywords):
                self.result.setText(
                    f"识别文本：{text}\n候选动作：{label}\n置信度：96%"
                )
                self.health.setText(
                    f"来源正常 · 最近输入 {datetime.now().strftime('%H:%M:%S')} · 96%"
                )
                self.command_proposed.emit(
                    CommandIntent(
                        action=action,
                        source="语音",
                        label=label,
                        confidence=0.96,
                        risk_level=risk,
                        requires_confirmation=confirm,
                    )
                )
                return
        self.result.setText(f"无法解析：{text}\n请使用受支持的安全命令")

    def _start_asr(self) -> None:
        if self._asr_process is not None:
            return
        if not self._asr_script.exists():
            self.asr_log.appendPlainText("未找到语音识别脚本，请确认 voice_asr 目录存在。")
            self._set_health("实时语音识别不可用", "chipWarn")
            return
        process = QProcess(self)
        process.setProgram(str(self._asr_python))
        process.setArguments(
            [
                str(self._asr_script),
                "--ov-device",
                "GPU",
                "--language",
                "zh",
                "--task",
                "transcribe",
            ]
        )
        process.setWorkingDirectory(str(self._asr_script.parent))
        process.readyReadStandardOutput.connect(self._read_asr_stdout)
        process.readyReadStandardError.connect(self._read_asr_stderr)
        process.errorOccurred.connect(self._asr_error)
        process.finished.connect(self._asr_finished)
        self._asr_process = process
        self.asr_log.clear()
        self.asr_log.appendPlainText(
            f"正在启动实时语音识别：{self._asr_python}"
        )
        self.asr_log.appendPlainText("首次加载模型可能较慢。")
        self._set_health("实时语音识别启动中", "chipInfo")
        self.asr_start.setEnabled(False)
        self.asr_stop.setEnabled(True)
        process.start()

    def _stop_asr(self) -> None:
        if self._asr_process is None:
            return
        self.asr_log.appendPlainText("正在停止实时语音识别...")
        self._asr_process.terminate()
        if not self._asr_process.waitForFinished(1500):
            self._asr_process.kill()

    def _read_asr_stdout(self) -> None:
        if self._asr_process is None:
            return
        data = bytes(self._asr_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if not line.strip():
                continue
            self.asr_log.appendPlainText(line)
            text = self._extract_asr_text(line)
            if text:
                self.input.setText(text)
                self._parse()

    def _read_asr_stderr(self) -> None:
        if self._asr_process is None:
            return
        data = bytes(self._asr_process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if line.strip():
                self.asr_log.appendPlainText(f"提示：{line}")

    def _asr_error(self, _error) -> None:
        self.asr_log.appendPlainText(
            "实时识别启动失败。请先双击 install_voice_asr_deps.bat 安装语音依赖。"
        )
        self._set_health("实时语音识别启动失败", "chipWarn")

    def _asr_finished(self, exit_code: int, _exit_status) -> None:
        self._asr_process = None
        self.asr_start.setEnabled(True)
        self.asr_stop.setEnabled(False)
        if exit_code == 0:
            self._set_health("实时语音识别已停止", "chipInfo")
        else:
            self._set_health("实时语音识别已退出，请查看日志", "chipWarn")

    def _extract_asr_text(self, line: str) -> str:
        if not line.startswith("[segment="):
            return ""
        match = re.search(r"\]\s*([^\[\]]+)$", line)
        if not match:
            return ""
        return match.group(1).strip()

    def _find_asr_python(self) -> Path:
        candidates = [
            Path.home() / ".conda" / "envs" / "gluon" / "python.exe",
            Path("C:/ProgramData/anaconda3/envs/gluon/python.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path(sys.executable)


class GesturePanel(QWidget):
    command_proposed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("启用手势输入")
        self.enabled.setChecked(True)
        layout.addWidget(self.enabled)
        preview = QLabel("操作员摄像头预览\n\n手部关键点与骨架将在此显示")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumHeight(150)
        preview.setStyleSheet(
            "background:#081522;border:1px dashed #31516b;border-radius:10px;color:#678198;"
        )
        layout.addWidget(preview)
        self.combo = QComboBox()
        self.combo.addItems(
            ["五指张开 · 暂停悬停", "握拳 · 取消选择", "竖拇指 · 确认候选"]
        )
        layout.addWidget(self.combo)
        self.confidence = QLabel("模拟识别置信度：94% · 已持续 1.2 秒")
        self.confidence.setObjectName("chipGood")
        layout.addWidget(self.confidence)
        button = QPushButton("提交当前手势")
        button.clicked.connect(self._submit)
        layout.addWidget(button)
        layout.addStretch()

    def _submit(self) -> None:
        if not self.enabled.isChecked():
            self.confidence.setText("手势输入已禁用")
            self.confidence.setObjectName("chipWarn")
            self.confidence.style().unpolish(self.confidence)
            self.confidence.style().polish(self.confidence)
            return
        index = self.combo.currentIndex()
        data = [
            ("HOLD", "暂停并悬停", "medium", False),
            ("CANCEL_SELECTION", "取消目标选择", "low", False),
            ("CONFIRM_CANDIDATE", "确认候选操作", "medium", False),
        ][index]
        self.command_proposed.emit(
            CommandIntent(
                action=data[0],
                source="手势",
                label=data[1],
                confidence=0.94,
                risk_level=data[2],
                requires_confirmation=data[3],
            )
        )
        self.confidence.setText(
            f"来源正常 · 最近输入 {datetime.now().strftime('%H:%M:%S')} · 94%"
        )


class GazePanel(QWidget):
    command_proposed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("启用视线输入")
        self.enabled.setChecked(True)
        layout.addWidget(self.enabled)
        self.calibration = QLabel("视线校准：良好 · 误差 1.4°")
        self.calibration.setObjectName("chipGood")
        layout.addWidget(self.calibration)
        preview = QLabel("注视点预览\n\n当前注视：视频目标 FIRE-01")
        preview.setAlignment(Qt.AlignCenter)
        preview.setMinimumHeight(150)
        preview.setStyleSheet(
            "background:#081522;border:1px dashed #31516b;border-radius:10px;color:#8ca6ba;"
        )
        layout.addWidget(preview)
        note = QLabel(
            "视线只负责选择目标。选择后需要通过按钮、语音或手势确认。"
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        button = QPushButton("将注视目标设为候选")
        button.clicked.connect(self._submit)
        layout.addWidget(button)
        layout.addStretch()

    def _submit(self) -> None:
        if not self.enabled.isChecked():
            self.calibration.setText("视线输入已禁用")
            self.calibration.setObjectName("chipWarn")
            self.calibration.style().unpolish(self.calibration)
            self.calibration.style().polish(self.calibration)
            return
        self.calibration.setText(
            f"校准良好 · 最近输入 {datetime.now().strftime('%H:%M:%S')} · 89%"
        )
        self.command_proposed.emit(
            CommandIntent(
                action="SELECT_TARGET",
                source="视线",
                label="选择目标 FIRE-01",
                confidence=0.89,
                risk_level="low",
                parameters={"target_id": "FIRE-01"},
            )
        )


class DevicePanel(QWidget):
    connect_camera = pyqtSignal(str)
    lens_correction_changed = pyqtSignal(bool, int)
    LENS_STRENGTH_LEVELS = (35, 50, 65)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.camera_url = QLineEdit("auto")
        self.camera_url.setPlaceholderText(
            "auto 或 rtsp://设备IP:554（旧固件可填 /snapshot.jpg）"
        )
        self.telemetry_port = QComboBox()
        self.telemetry_port.addItems(["模拟器", "COM3", "COM8"])
        self.protocol = QComboBox()
        self.protocol.addItems(["模拟遥测", "MAVLink", "自定义串口"])
        form.addRow("AMB82 地址", self.camera_url)
        form.addRow("飞控端口", self.telemetry_port)
        form.addRow("通信协议", self.protocol)
        self.lens_correction = QCheckBox("启用实时桶形畸变校正")
        self.lens_correction.setChecked(True)
        self.lens_strength = QSlider(Qt.Horizontal)
        self.lens_strength.setRange(0, 2)
        self.lens_strength.setSingleStep(1)
        self.lens_strength.setPageStep(1)
        self.lens_strength.setTickPosition(QSlider.TicksBelow)
        self.lens_strength.setTickInterval(1)
        self.lens_strength.setValue(1)
        self.lens_strength_label = QLabel("50% · 中")
        strength_row = QHBoxLayout()
        strength_row.addWidget(QLabel("35"))
        strength_row.addWidget(self.lens_strength, 1)
        strength_row.addWidget(QLabel("65"))
        strength_row.addWidget(self.lens_strength_label)
        form.addRow("镜头校正", self.lens_correction)
        form.addRow("校正强度", strength_row)
        layout.addLayout(form)
        self.lens_correction.toggled.connect(self._emit_lens_settings)
        self.lens_strength.valueChanged.connect(self._on_lens_strength_changed)
        camera_button = QPushButton("测试并连接 AMB82")
        camera_button.setObjectName("primaryButton")
        camera_button.clicked.connect(
            lambda: self.connect_camera.emit(self.camera_url.text().strip() or "auto")
        )
        layout.addWidget(camera_button)
        info = QLabel(
            "图传优先使用 720p/15 FPS H.264 RTSP，并自动兼容旧快照固件。"
            "当前飞控仍默认使用模拟器；接入真实飞控前，应先完成只读遥测验证。"
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        layout.addStretch()

    def _on_lens_strength_changed(self, index: int) -> None:
        value = self.LENS_STRENGTH_LEVELS[index]
        names = ("轻", "中", "强")
        self.lens_strength_label.setText(f"{value}% · {names[index]}")
        self._emit_lens_settings()

    def _emit_lens_settings(self) -> None:
        self.lens_correction_changed.emit(
            self.lens_correction.isChecked(),
            self.LENS_STRENGTH_LEVELS[self.lens_strength.value()],
        )

    def set_lens_correction(self, enabled: bool, strength: int) -> None:
        index = min(
            range(len(self.LENS_STRENGTH_LEVELS)),
            key=lambda item: abs(self.LENS_STRENGTH_LEVELS[item] - strength),
        )
        self.lens_correction.blockSignals(True)
        self.lens_strength.blockSignals(True)
        self.lens_correction.setChecked(enabled)
        self.lens_strength.setValue(index)
        names = ("轻", "中", "强")
        self.lens_strength_label.setText(
            f"{self.LENS_STRENGTH_LEVELS[index]}% · {names[index]}"
        )
        self.lens_strength.blockSignals(False)
        self.lens_correction.blockSignals(False)


class CommandBar(QFrame):
    command_requested = pyqtSignal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("commandBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        title = QLabel("安全命令中心")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.candidate = QFrame()
        self.candidate.setObjectName("candidateIdle")
        candidate_layout = QHBoxLayout(self.candidate)
        candidate_layout.setContentsMargins(9, 4, 6, 4)
        candidate_layout.setSpacing(6)
        self.candidate_text = QLabel("当前候选：无")
        self.candidate_text.setObjectName("candidateText")
        self.confirm_candidate = QPushButton("确认目标")
        self.confirm_candidate.setObjectName("primaryButton")
        self.confirm_candidate.setEnabled(False)
        self.confirm_candidate.clicked.connect(
            lambda: self.command_requested.emit(
                "CONFIRM_CANDIDATE", "确认候选目标"
            )
        )
        self.cancel_candidate = QPushButton("取消")
        self.cancel_candidate.setEnabled(False)
        self.cancel_candidate.clicked.connect(
            lambda: self.command_requested.emit(
                "CANCEL_SELECTION", "取消目标选择"
            )
        )
        candidate_layout.addWidget(self.candidate_text)
        candidate_layout.addWidget(self.confirm_candidate)
        candidate_layout.addWidget(self.cancel_candidate)
        layout.addWidget(self.candidate)
        layout.addStretch()
        buttons = [
            ("自动起飞", "TAKEOFF", "primaryButton"),
            ("开始巡逻", "START_MISSION", ""),
            ("暂停 / 悬停", "HOLD", "warningButton"),
            ("继续任务", "CONTINUE", ""),
            ("返航", "RTL", "warningButton"),
            ("降落", "LAND", "dangerButton"),
        ]
        for label, action, object_name in buttons:
            button = QPushButton(label)
            if object_name:
                button.setObjectName(object_name)
            button.clicked.connect(
                lambda _checked=False, a=action, label=label: self.command_requested.emit(
                    a, label
                )
            )
            layout.addWidget(button)

    def set_candidate(
        self,
        target_id: str,
        confidence: float,
        source: str,
        state: str,
    ) -> None:
        self.candidate_text.setText(
            f"候选 {target_id} · {confidence:.0%} · {source} · {state}"
        )
        pending = state == "待确认"
        self.confirm_candidate.setEnabled(pending)
        self.cancel_candidate.setEnabled(pending)
        self.candidate.setObjectName(
            "candidatePending"
            if pending
            else "candidateConfirmed"
            if state == "已确认"
            else "candidateCancelled"
        )
        self.candidate.style().unpolish(self.candidate)
        self.candidate.style().polish(self.candidate)

    def clear_candidate(self) -> None:
        self.candidate_text.setText("当前候选：无")
        self.confirm_candidate.setEnabled(False)
        self.cancel_candidate.setEnabled(False)
        self.candidate.setObjectName("candidateIdle")
        self.candidate.style().unpolish(self.candidate)
        self.candidate.style().polish(self.candidate)


class LogPanel(QPlainTextEdit):
    COLORS = {
        "INFO": "#8fb8d8",
        "WARNING": "#f1c16f",
        "ERROR": "#ff7b86",
        "COMMAND": "#71e1b4",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(1000)

    def append_log(self, level: str, message: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(level, "#a8bed2")
        self.appendHtml(
            f'<span style="color:#617b92">[{now}]</span> '
            f'<b style="color:{color}">{level}</b> '
            f'<span style="color:#c6d7e8">{message}</span>'
        )


class HealthPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        title = QLabel("设备健康")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.chips: dict[str, QLabel] = {}
        for key, label in [
            ("flight", "飞控 在线"),
            ("camera", "相机 模拟"),
            ("telemetry", "数传 在线"),
            ("ai", "AI 就绪"),
            ("position", "定位 良好"),
        ]:
            chip = QLabel(label)
            chip.setObjectName("miniChipGood" if key != "camera" else "miniChipInfo")
            chip.setAlignment(Qt.AlignCenter)
            self.chips[key] = chip
            row.addWidget(chip)
        layout.addLayout(row)
        self.camera_diagnostics = QLabel(
            "图传诊断：未连接 · 无实时画面"
        )
        self.camera_diagnostics.setObjectName("muted")
        self.camera_diagnostics.setWordWrap(True)
        layout.addWidget(self.camera_diagnostics)

    def set_state(self, state: DroneState, camera: CameraState) -> None:
        self._set_chip("flight", "飞控 在线" if state.connected else "飞控 离线", state.connected)
        self._set_chip(
            "camera",
            "相机 在线" if camera.connected else "相机 模拟",
            camera.connected,
            info=not camera.connected,
        )
        self._set_chip(
            "telemetry",
            "数传 在线" if state.telemetry_connected else "数传 离线",
            state.telemetry_connected,
        )
        self._set_chip("ai", "AI 就绪" if state.ai_ready else "AI 离线", state.ai_ready)
        positioning_ok = state.optical_flow_quality >= 55
        self._set_chip(
            "position",
            "定位 良好" if positioning_ok else "定位 降级",
            positioning_ok,
        )
        if camera.connected:
            self.camera_diagnostics.setText(
                f"图传诊断：{camera.source_kind.upper()} · {camera.fps:.1f} FPS · "
                f"帧龄 {camera.frame_age_ms} ms · 重连 {camera.reconnect_count} 次"
            )
        else:
            error = camera.last_error or "等待连接 AMB82"
            self.camera_diagnostics.setText(
                f"图传诊断：离线 · 重连 {camera.reconnect_count} 次 · {error}"
            )

    def _set_chip(self, key: str, text: str, good: bool, info: bool = False) -> None:
        chip = self.chips[key]
        chip.setText(text)
        if info:
            chip.setObjectName("miniChipInfo")
        else:
            chip.setObjectName("miniChipGood" if good else "miniChipWarn")
        chip.style().unpolish(chip)
        chip.style().polish(chip)


class RightSidebar(QWidget):
    def __init__(self, waypoints: list[tuple[float, float]], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rightSidebar")
        self.setMinimumWidth(285)
        self.setMaximumWidth(370)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.status_panel = StatusPanel()
        self.health_panel = HealthPanel()
        self.map_panel = MapPanel(waypoints)
        self.map_panel.map.setMinimumHeight(170)
        layout.addWidget(self.status_panel, 0)
        layout.addWidget(self.health_panel, 0)
        layout.addWidget(self.map_panel, 1)

    def set_display_scale(self, large: bool) -> None:
        self.setMinimumWidth(620 if large else 285)
        self.setMaximumWidth(760 if large else 370)
        self.status_panel.set_display_scale(large)

    def set_state(self, state: DroneState, camera: CameraState) -> None:
        self.status_panel.set_state(state)
        self.health_panel.set_state(state, camera)
        self.map_panel.set_state(state)

    def set_compact(self, compact: bool) -> None:
        self.status_panel.set_compact(compact)
        self.map_panel.map.setMinimumHeight(100 if compact else 190)


class CompactStatusBar(QFrame):
    details_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("compactStatusBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(8)
        self.phase = QLabel("待命")
        self.phase.setObjectName("chipInfo")
        self.flight = QLabel("飞控 在线")
        self.flight.setObjectName("miniChipGood")
        self.camera = QLabel("图传 离线")
        self.camera.setObjectName("miniChipInfo")
        self.telemetry = QLabel("数传 在线")
        self.telemetry.setObjectName("miniChipGood")
        self.metrics = QLabel("高度 0.00 m · 电量 92% · 链路 26 ms")
        self.metrics.setObjectName("compactMetrics")
        details = QPushButton("状态 / 地图")
        details.setObjectName("ghostButton")
        details.clicked.connect(self.details_requested)
        for widget in (
            self.phase,
            self.flight,
            self.camera,
            self.telemetry,
            self.metrics,
        ):
            layout.addWidget(widget)
        layout.addStretch()
        layout.addWidget(details)

    def set_state(self, state: DroneState, camera: CameraState) -> None:
        self.phase.setText(state.flight_phase)
        self.flight.setText(
            "飞控 在线" if state.connected else "飞控 离线"
        )
        self.flight.setObjectName(
            "miniChipGood" if state.connected else "miniChipWarn"
        )
        self.camera.setText(
            f"图传 {camera.fps:.0f} FPS" if camera.connected else "图传 离线"
        )
        self.camera.setObjectName(
            "miniChipGood"
            if camera.connected
            else "miniChipWarn"
            if camera.last_error
            else "miniChipInfo"
        )
        self.telemetry.setText(
            "数传 在线" if state.telemetry_connected else "数传 离线"
        )
        self.telemetry.setObjectName(
            "miniChipGood" if state.telemetry_connected else "miniChipWarn"
        )
        self.metrics.setText(
            f"高度 {state.altitude:.2f} m · 电量 {state.battery_percent:.0f}% · "
            f"链路 {state.link_latency_ms} ms"
        )
        for chip in (self.flight, self.camera, self.telemetry):
            chip.style().unpolish(chip)
            chip.style().polish(chip)


class RecentEventsPanel(QFrame):
    open_full_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("recentEvents")
        self._items: list[dict] = []
        self._compact = False
        self._flash_remaining = 0
        self._flash_on = False
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(260)
        self._flash_timer.timeout.connect(self._advance_alert_flash)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 9)
        layout.setSpacing(5)
        header = QHBoxLayout()
        self.title = QLabel("最近事件")
        self.title.setObjectName("sectionTitle")
        self.summary = QLabel("任务待命")
        self.summary.setObjectName("muted")
        full_button = QPushButton("完整事件")
        full_button.setObjectName("ghostButton")
        full_button.clicked.connect(self.open_full_requested)
        clear_button = QPushButton("清除告警")
        clear_button.setObjectName("ghostButton")
        clear_button.clicked.connect(self.clear_requested)
        header.addWidget(self.title)
        header.addWidget(self.summary)
        header.addStretch()
        header.addWidget(full_button)
        header.addWidget(clear_button)
        layout.addLayout(header)

        self.compact_alert = QLabel("暂无关键告警")
        self.compact_alert.setObjectName("compactAlert")
        self.compact_alert.setWordWrap(False)
        self.compact_alert.setVisible(False)
        layout.addWidget(self.compact_alert)

        self.rows_widget = QWidget()
        self.rows = QHBoxLayout(self.rows_widget)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(7)
        layout.addWidget(self.rows_widget)
        self.add_system_event("系统就绪", "模拟遥测已启动", "good")
        self.add_system_event("相机状态", "等待连接 AMB82", "info")
        self.add_system_event("任务状态", "待命 · 航点 0/10", "info")

    def add_detection(self, event: DetectionEvent) -> None:
        self.add_system_event(
            f"发现 {event.target_type}",
            f"置信度 {event.confidence:.0%} · ({event.x:.1f}, {event.y:.1f})",
            "fire",
        )
        self.flash_fire_alert()

    def flash_fire_alert(self) -> None:
        self._flash_remaining = 14
        self._flash_on = False
        self.title.setText("⚠ 火源告警")
        self._advance_alert_flash()
        if not self._flash_timer.isActive():
            self._flash_timer.start()

    def _advance_alert_flash(self) -> None:
        if self._flash_remaining <= 0:
            self._flash_timer.stop()
            self.setObjectName("recentEvents")
            self.title.setText("最近事件")
            self._refresh_style()
            return
        self._flash_on = not self._flash_on
        self.setObjectName(
            "recentEventsAlertRed" if self._flash_on else "recentEventsAlertAmber"
        )
        self._flash_remaining -= 1
        self._refresh_style()

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def add_system_event(self, title: str, detail: str, level: str = "info") -> None:
        self._items.insert(
            0,
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "title": title,
                "detail": detail,
                "level": level,
            },
        )
        self._items = self._items[:3]
        self._render()

    def update_task_summary(self, state: DroneState) -> None:
        self.summary.setText(
            f"{state.flight_phase} · 航点 {state.current_waypoint}/{state.total_waypoints}"
        )

    def clear_alerts(self) -> None:
        self._items = [
            item
            for item in self._items
            if item["level"] not in {"warn", "error", "fire"}
        ]
        if not self._items:
            self.add_system_event("系统状态", "暂无活动告警", "good")
        else:
            self._render()

    def set_compact(self, compact: bool) -> None:
        if self._compact == compact:
            return
        self._compact = compact
        self.rows_widget.setVisible(not compact)
        self.compact_alert.setVisible(compact)
        self._render()

    def _render(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for event in self._items:
            card = QFrame()
            card.setObjectName(f"eventCard{event['level'].title()}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(1)
            top = QHBoxLayout()
            name = QLabel(event["title"])
            name.setObjectName("eventTitle")
            timestamp = QLabel(event["time"])
            timestamp.setObjectName("muted")
            top.addWidget(name)
            top.addStretch()
            top.addWidget(timestamp)
            detail = QLabel(event["detail"])
            detail.setObjectName("eventDetail")
            detail.setWordWrap(False)
            card_layout.addLayout(top)
            card_layout.addWidget(detail)
            self.rows.addWidget(card, 1)
        if self._items:
            important = next(
                (
                    item
                    for item in self._items
                    if item["level"] in {"fire", "error", "warn"}
                ),
                self._items[0],
            )
            prefix = "⚠" if important["level"] in {"fire", "error", "warn"} else "●"
            self.compact_alert.setText(
                f"{prefix} {important['time']}  {important['title']}：{important['detail']}"
            )
            self.compact_alert.setObjectName(
                "compactAlertDanger"
                if important["level"] in {"fire", "error", "warn"}
                else "compactAlert"
            )
            self.compact_alert.style().unpolish(self.compact_alert)
            self.compact_alert.style().polish(self.compact_alert)


class SideNavigation(QFrame):
    navigation_requested = pyqtSignal(str)
    expanded_changed = pyqtSignal(bool)

    ITEMS = [
        ("mission", "任", "任务"),
        ("status", "态", "状态"),
        ("voice", "语", "语音"),
        ("gesture", "势", "手势"),
        ("gaze", "视", "视线"),
        ("events", "事", "事件"),
        ("logs", "志", "日志"),
        ("device", "设", "设备"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sideNav")
        self._expanded = False
        self._large_display = False
        self._buttons: list[tuple[QToolButton, str, str]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(5)
        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("navToggle")
        self.toggle_button.setText("☰")
        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_button)
        for key, icon, label in self.ITEMS:
            button = QToolButton()
            button.setObjectName("navButton")
            button.setToolTip(label)
            button.clicked.connect(
                lambda _checked=False, item_key=key: self.navigation_requested.emit(
                    item_key
                )
            )
            self._buttons.append((button, icon, label))
            layout.addWidget(button)
        layout.addStretch()
        self._apply_width()

    @property
    def expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._apply_width()
        self.expanded_changed.emit(self._expanded)

    def collapse(self) -> None:
        if self._expanded:
            self._expanded = False
            self._apply_width()
            self.expanded_changed.emit(False)

    def set_display_scale(self, large: bool) -> None:
        if self._large_display == large:
            return
        self._large_display = large
        self._apply_width()

    def _apply_width(self) -> None:
        if self._large_display:
            width = 330 if self._expanded else 118
        else:
            width = 148 if self._expanded else 58
        self.setFixedWidth(width)
        self.toggle_button.setText("收起" if self._expanded else "☰")
        for button, icon, label in self._buttons:
            button.setText(f"{icon}   {label}" if self._expanded else icon)
            button.setToolButtonStyle(
                Qt.ToolButtonTextOnly if self._expanded else Qt.ToolButtonTextOnly
            )
