from __future__ import annotations

import json
import html
import math
import ipaddress
import re
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from PyQt5.QtCore import (
    QProcess,
    QProcessEnvironment,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from models import (
    CameraState,
    CommandIntent,
    DroneState,
    FireDetection,
)


DEFAULT_AMB82_RTSP_URL = "rtsp://10.51.117.2:554"
DEFAULT_AMB82_IP = "10.51.117.2"
DEFAULT_AMB82_PORT = "554"
CAMERA_SETTINGS_PATH = Path(__file__).resolve().parent / "camera_settings.json"


def suggested_amb82_url() -> str:
    """Return the saved AMB82 RTSP address, falling back to the default camera."""

    ip, port = load_camera_endpoint()
    return build_rtsp_url(ip, port)


def build_rtsp_url(ip: str, port: str) -> str:
    ip = ip.strip() or DEFAULT_AMB82_IP
    port = port.strip() or DEFAULT_AMB82_PORT
    return f"rtsp://{ip}:{port}"


def load_camera_endpoint() -> tuple[str, str]:
    if CAMERA_SETTINGS_PATH.exists():
        try:
            data = json.loads(CAMERA_SETTINGS_PATH.read_text(encoding="utf-8"))
            ip = str(data.get("ip", "")).strip()
            port = str(data.get("port", "")).strip()
            if ip and port:
                return ip, port
        except (OSError, ValueError, TypeError):
            pass
    return DEFAULT_AMB82_IP, DEFAULT_AMB82_PORT


def save_camera_endpoint(ip: str, port: str) -> tuple[str, str]:
    ip = ip.strip() or DEFAULT_AMB82_IP
    port = port.strip() or DEFAULT_AMB82_PORT
    try:
        parsed = ipaddress.ip_address(ip)
        ip = str(parsed)
    except ValueError:
        pass
    try:
        port_int = int(port)
    except ValueError:
        port_int = int(DEFAULT_AMB82_PORT)
    port_int = max(1, min(65535, port_int))
    port = str(port_int)
    CAMERA_SETTINGS_PATH.write_text(
        json.dumps({"ip": ip, "port": port}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ip, port


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
        self._inspection_detections: list[dict] = []
        self._inspection_hold_until = 0.0
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
        self._transition_message = ""
        self._transition_until = 0.0
        self._status_report_title = ""
        self._status_report_lines: list[str] = []
        self._detection_timer = QTimer(self)
        self._detection_timer.setInterval(200)
        self._detection_timer.timeout.connect(self._expire_detections)
        self._detection_timer.start()
        self._transition_timer = QTimer(self)
        self._transition_timer.setInterval(60)
        self._transition_timer.timeout.connect(self._tick_transition)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    def set_display_scale(self, large: bool) -> None:
        self._display_scale = 2.56 if large else 1.0
        self.update()

    def set_frame(self, frame) -> None:
        self.clear_status_report()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        self._frame_size = (width, height)
        self._frame = QImage(
            rgb.data, width, height, channels * width, QImage.Format_RGB888
        ).copy()
        self._pixmap = QPixmap.fromImage(self._frame)
        self.update()

    def clear_frame(self) -> None:
        self._frame = None
        self._pixmap = None
        self._detections = []
        self._inspection_detections = []
        self._selected_target_id = ""
        self._hover_target_id = ""
        self.update()

    def set_demo_mode(self, enabled: bool) -> None:
        self._demo_mode = enabled
        self.update()

    def show_transition(self, message: str, seconds: float = 1.2) -> None:
        self.clear_status_report()
        self._transition_message = message
        self._transition_until = time.monotonic() + seconds
        if not self._transition_timer.isActive():
            self._transition_timer.start()
        self.update()

    def show_status_report(self, title: str, lines: list[str]) -> None:
        self._status_report_title = title
        self._status_report_lines = lines
        self._transition_message = ""
        self.update()

    def clear_status_report(self) -> None:
        if not self._status_report_title and not self._status_report_lines:
            return
        self._status_report_title = ""
        self._status_report_lines = []
        self.update()

    def _tick_transition(self) -> None:
        if not self._transition_message or time.monotonic() >= self._transition_until:
            self._transition_message = ""
            self._transition_timer.stop()
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

    def set_inspection_detections(self, detections: list[dict]) -> None:
        now = time.monotonic()
        if detections:
            self._inspection_detections = list(detections)
            self._inspection_hold_until = now + 1.4
        elif now >= self._inspection_hold_until:
            self._inspection_detections = []
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
        if self._inspection_detections and now >= self._inspection_hold_until:
            self._inspection_detections = []
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

        if self._pixmap is not None and not self._pixmap.isNull():
            self._draw_fire_detections(painter, content_rect)
            self._draw_inspection_detections(painter, content_rect)

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
                "离线示例 · 结果仅用于演示",
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

        if self._transition_message and time.monotonic() < self._transition_until:
            phase = max(0.0, min(1.0, self._transition_until - time.monotonic()))
            pulse = 0.45 + 0.30 * math.sin(time.monotonic() * 9.0)
            painter.fillRect(rect, QColor(4, 12, 20, 120))
            painter.setPen(QPen(QColor(90, 190, 255, 120), 3))
            center = rect.center()
            radius = int((56 + 26 * pulse) * scale)
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QColor("#e9f7ff"))
            painter.setFont(QFont("Microsoft YaHei UI", round(22 * scale), QFont.Bold))
            painter.drawText(
                QRectF(rect).adjusted(0, -36 * scale, 0, 0),
                Qt.AlignCenter,
                self._transition_message,
            )
            painter.setFont(QFont("Microsoft YaHei UI", round(10 * scale), QFont.Bold))
            painter.setPen(QColor("#98d8ff"))
            if "起飞倒计时" in self._transition_message:
                subtitle = "航点已写入飞控，等待启动巡航"
            elif "返航倒计时" in self._transition_message:
                subtitle = "倒计时结束后自动发送返航指令"
            else:
                subtitle = "正在恢复无人机图传画面"
            painter.drawText(
                QRectF(rect).adjusted(0, 42 * scale, 0, 0),
                Qt.AlignCenter,
                subtitle,
            )
            if phase <= 0.05:
                self._transition_message = ""

        if self._status_report_title or self._status_report_lines:
            self._draw_status_report(painter, rect)

        painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -2, -2), 12, 12)

    def _draw_status_report(self, painter: QPainter, rect: QRect) -> None:
        painter.save()
        painter.setOpacity(1.0)
        scale = self._display_scale
        panel = QRectF(rect).adjusted(
            24 * scale,
            26 * scale,
            -24 * scale,
            -26 * scale,
        )
        painter.fillRect(rect, QColor(2, 8, 16, 210))
        painter.setPen(QPen(QColor(105, 206, 255, 235), max(2, round(2 * scale))))
        painter.setBrush(QColor(5, 19, 35, 252))
        painter.drawRoundedRect(panel, 14 * scale, 14 * scale)
        painter.setClipRect(panel.adjusted(2 * scale, 2 * scale, -2 * scale, -2 * scale))

        header_height = min(44 * scale, max(34 * scale, panel.height() * 0.17))
        header = QRectF(panel.left(), panel.top(), panel.width(), header_height)
        header_gradient = QLinearGradient(header.topLeft(), header.topRight())
        header_gradient.setColorAt(0.0, QColor(28, 104, 146, 245))
        header_gradient.setColorAt(1.0, QColor(12, 52, 84, 235))
        painter.fillRect(header.adjusted(1, 1, -1, 0), header_gradient)

        def draw_readable_text(target_rect: QRectF, flags: int, text: str, color: str) -> None:
            painter.setPen(QColor(0, 0, 0, 240))
            painter.drawText(target_rect.translated(2 * scale, 2 * scale), flags, text)
            painter.setPen(QColor(color))
            painter.drawText(target_rect, flags, text)

        title_size = max(12, round(18 * scale))
        painter.setFont(QFont("Microsoft YaHei UI", title_size, QFont.Black))
        title_rect = QRectF(
            panel.left() + 18 * scale,
            panel.top() + 8 * scale,
            panel.width() - 36 * scale,
            header_height - 12 * scale,
        )
        draw_readable_text(
            title_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            self._status_report_title,
            "#ffffff",
        )

        if "飞行日志预览" in self._status_report_title:
            lines = self._status_report_lines[:22]
            body_top = panel.top() + header_height + 16 * scale
            body_bottom = panel.bottom() - 14 * scale
            left = panel.left() + 26 * scale
            right = panel.right() - 26 * scale
            y = body_top
            for raw_line in lines:
                if y > body_bottom - 20 * scale:
                    break
                line = raw_line.rstrip()
                if not line:
                    y += 8 * scale
                    continue
                if line.startswith("## "):
                    painter.setFont(QFont("Microsoft YaHei UI", max(13, round(15 * scale)), QFont.Black))
                    painter.setPen(QColor(0, 0, 0, 230))
                    painter.drawText(QRectF(left + 2 * scale, y + 2 * scale, right - left, 24 * scale), Qt.AlignLeft | Qt.AlignVCenter, line)
                    painter.setPen(QColor("#9eefff"))
                    painter.drawText(QRectF(left, y, right - left, 24 * scale), Qt.AlignLeft | Qt.AlignVCenter, line)
                    y += 29 * scale
                    painter.setPen(QPen(QColor(82, 213, 255, 120), max(1, round(scale))))
                    painter.drawLine(QPointF(left, y), QPointF(right, y))
                    y += 8 * scale
                    continue
                if line.startswith("|"):
                    text = line
                    if set(text.replace("|", "").replace(" ", "").replace(":", "")) <= {"-"}:
                        continue
                    painter.setFont(QFont("Consolas", max(9, round(10 * scale)), QFont.Bold))
                    row_color = QColor(70, 140, 180, 72) if "时间" in text else QColor(255, 255, 255, 28)
                elif line.startswith("- "):
                    text = "• " + line[2:]
                    painter.setFont(QFont("Microsoft YaHei UI", max(10, round(12 * scale)), QFont.Black))
                    row_color = QColor(255, 255, 255, 22)
                else:
                    text = line
                    painter.setFont(QFont("Microsoft YaHei UI", max(10, round(12 * scale)), QFont.Black))
                    row_color = QColor(255, 255, 255, 18)
                row_rect = QRectF(left - 8 * scale, y, right - left + 16 * scale, 22 * scale)
                painter.fillRect(row_rect, row_color)
                painter.setPen(QColor(0, 0, 0, 220))
                painter.drawText(QRectF(left + 1 * scale, y + 1 * scale, right - left, 22 * scale), Qt.AlignLeft | Qt.AlignVCenter, text)
                painter.setPen(QColor("#f5fbff"))
                metrics = painter.fontMetrics()
                painter.drawText(
                    QRectF(left, y, right - left, 22 * scale),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    metrics.elidedText(text, Qt.ElideRight, int(right - left)),
                )
                y += 24 * scale
            painter.restore()
            return

        if "摄像头自检" in self._status_report_title or "图传" in self._status_report_title:
            lines = self._status_report_lines[:5]
            body_top = panel.top() + header_height + 18 * scale
            body_bottom = panel.bottom() - 18 * scale
            available_height = max(1.0, body_bottom - body_top)
            line_count = max(1, len(lines))
            line_height = min(58 * scale, max(32 * scale, available_height / line_count))
            font_size = max(16, min(round(26 * scale), round(line_height * 0.52)))
            painter.setFont(QFont("Microsoft YaHei UI", font_size, QFont.Black))
            metrics = painter.fontMetrics()
            left = panel.left() + 28 * scale
            right = panel.right() - 28 * scale
            max_width = int(right - left)
            while font_size > 14 and any(
                metrics.horizontalAdvance(line) > max_width for line in lines
            ):
                font_size -= 1
                painter.setFont(QFont("Microsoft YaHei UI", font_size, QFont.Black))
                metrics = painter.fontMetrics()
            y = body_top
            for index, line in enumerate(lines):
                is_status = index == 0 or "连接状态" in line or "链接" in line
                row_color = QColor(35, 180, 210, 145) if is_status else QColor(255, 255, 255, 52)
                if "未连接" in line or "等待" in line or "离线" in line:
                    row_color = QColor(210, 150, 40, 120)
                row_rect = QRectF(
                    left - 12 * scale,
                    y + 3 * scale,
                    right - left + 24 * scale,
                    max(1, line_height - 6 * scale),
                )
                painter.fillRect(row_rect, row_color)
                elided = metrics.elidedText(line, Qt.ElideRight, int(right - left))
                draw_readable_text(
                    QRectF(left, y, right - left, line_height),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    elided,
                    "#f8ffff",
                )
                y += line_height
            painter.restore()
            return

        lines = self._status_report_lines[:11]
        body_top = panel.top() + header_height + 8 * scale
        body_bottom = panel.bottom() - 10 * scale
        available_height = max(1.0, body_bottom - body_top)
        line_count = max(1, len(lines))
        line_height = min(24 * scale, max(15 * scale, available_height / line_count))
        body_font_size = max(8, min(round(12 * scale), round(line_height * 0.55)))
        painter.setFont(QFont("Microsoft YaHei UI", body_font_size, QFont.Black))
        y = body_top
        left = panel.left() + 20 * scale
        right = panel.right() - 20 * scale
        metrics = painter.fontMetrics()
        for line in lines:
            color = "#ffffff"
            row_color = QColor(255, 255, 255, 24)
            if "重点检查" in line:
                row_color = QColor(35, 180, 210, 92)
            if "失败" in line:
                row_color = QColor(210, 58, 72, 105)
            row_rect = QRectF(
                left - 8 * scale,
                y + 1 * scale,
                right - left + 16 * scale,
                max(1, line_height - 2 * scale),
            )
            painter.fillRect(row_rect, row_color)
            elided = metrics.elidedText(line, Qt.ElideRight, int(right - left))
            draw_readable_text(
                QRectF(left, y, right - left, line_height),
                Qt.AlignLeft | Qt.AlignVCenter,
                elided,
                color,
            )
            y += line_height
        painter.restore()

    def _draw_inspection_detections(self, painter: QPainter, rect: QRectF) -> None:
        if not self._inspection_detections:
            return
        frame_width, frame_height = self._frame_size
        if frame_width <= 0 or frame_height <= 0:
            return
        scale_x = rect.width() / frame_width
        scale_y = rect.height() / frame_height
        ui_scale = min(self._display_scale, 1.5)
        colors = {
            "face": QColor("#55d8ff"),
            "text": QColor("#61e49b"),
        }
        labels = {"face": "人脸", "text": "文字"}
        for index, detection in enumerate(self._inspection_detections[:8], start=1):
            bbox = detection.get("bbox", [])
            if len(bbox) != 4:
                continue
            x, y, width, height = (float(value) for value in bbox)
            box = QRectF(
                rect.left() + x * scale_x,
                rect.top() + y * scale_y,
                max(2.0, width * scale_x),
                max(2.0, height * scale_y),
            ).intersected(rect)
            kind = str(detection.get("kind", "face"))
            color = colors.get(kind, QColor("#55d8ff"))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color, max(2, round(2 * ui_scale))))
            painter.drawRect(box)
            confidence = float(detection.get("confidence", 0.0))
            label = f"{labels.get(kind, kind.upper())}-{index}  {confidence:.0%}"
            painter.setFont(
                QFont("Microsoft YaHei UI", max(8, round(9 * ui_scale)), QFont.Bold)
            )
            metrics = painter.fontMetrics()
            label_width = metrics.horizontalAdvance(label) + 14 * ui_scale
            label_height = max(22.0, metrics.height() + 6 * ui_scale)
            label_rect = QRectF(
                box.left(),
                max(rect.top(), box.top() - label_height),
                min(label_width, rect.right() - box.left()),
                label_height,
            )
            painter.fillRect(label_rect, QColor(color.red(), color.green(), color.blue(), 205))
            painter.setPen(QColor("#041019"))
            painter.drawText(
                label_rect.adjusted(6 * ui_scale, 0, -4 * ui_scale, 0),
                Qt.AlignLeft | Qt.AlignVCenter,
                label,
            )

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


class MapConfirmView(QWidget):
    waypoint_clicked = pyqtSignal(str)
    free_points_changed = pyqtSignal(object)
    FREE_POINT_COORD_OFFSET_CM = 40
    WAYPOINTS = (
        ("6", 0.32, 0.23),
        ("5", 0.55, 0.24),
        ("4", 0.78, 0.23),
        ("1", 0.32, 0.56),
        ("2", 0.55, 0.56),
        ("3", 0.78, 0.58),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap(
            str(Path(__file__).resolve().parent / "examples" / "fire_test_scene.png")
        )
        self._image_rect = QRectF()
        self._mode = "preset"
        self._free_points: list[tuple[int, int, int]] = []
        self._buttons: dict[str, QToolButton] = {}
        for number, _x_ratio, _y_ratio in self.WAYPOINTS:
            button = QToolButton(self)
            button.setText(number)
            button.setObjectName("mapWaypointButton")
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(
                "QToolButton { color: white; background: #1677d8; "
                "border: 2px solid #d7f1ff; border-radius: 18px; "
                "font: 900 20px 'Microsoft YaHei UI'; }"
                "QToolButton:hover { background: #25a4ff; }"
            )
            button.clicked.connect(lambda _checked=False, n=number: self.waypoint_clicked.emit(n))
            self._buttons[number] = button
        self.setMinimumHeight(260)

    def set_mode(self, mode: str) -> None:
        self._mode = "free" if mode == "free" else "preset"
        for button in self._buttons.values():
            button.setVisible(self._mode == "preset")
        self.update()

    def clear_free_points(self) -> None:
        self._free_points = []
        self.free_points_changed.emit([])
        self.update()

    def set_free_points(self, points: list[tuple[int, int, int]]) -> None:
        self._free_points = list(points[:10])
        self.update()

    def set_route_sequence(self, sequence: list[str]) -> None:
        selected = set(sequence)
        for number, button in self._buttons.items():
            if number in selected:
                button.setStyleSheet(
                    "QToolButton { color: #071421; background: #ffcc4d; "
                    "border: 2px solid #fff0b8; border-radius: 18px; "
                    "font: 900 20px 'Microsoft YaHei UI'; }"
                )
            else:
                button.setStyleSheet(
                    "QToolButton { color: white; background: #1677d8; "
                    "border: 2px solid #d7f1ff; border-radius: 18px; "
                    "font: 900 20px 'Microsoft YaHei UI'; }"
                    "QToolButton:hover { background: #25a4ff; }"
                )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#020811"))
        panel = QRectF(rect).adjusted(12, 12, -12, -12)
        painter.setPen(QPen(QColor("#315a79"), 2))
        painter.setBrush(QColor("#071928"))
        painter.drawRoundedRect(panel, 10, 10)
        inner = panel.adjusted(12, 12, -12, -12)
        if self._pixmap.isNull():
            painter.setPen(QColor("#e9f7ff"))
            painter.setFont(QFont("Microsoft YaHei UI", 22, QFont.Bold))
            painter.drawText(inner, Qt.AlignCenter, "任务地图加载失败")
            return
        scaled = self._pixmap.scaled(
            int(inner.width()),
            int(inner.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = int(inner.center().x() - scaled.width() / 2)
        y = int(inner.center().y() - scaled.height() / 2)
        painter.drawPixmap(x, y, scaled)
        self._image_rect = QRectF(x, y, scaled.width(), scaled.height())
        if self._mode == "free":
            self._draw_free_points(painter)
        self._update_button_positions()

    def mousePressEvent(self, event) -> None:
        if self._mode != "free" or event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        if len(self._free_points) >= 10:
            return
        field_rect = self._field_rect()
        if field_rect.isNull() or not field_rect.contains(event.pos()):
            return
        raw_x_cm = round(
            (event.pos().x() - field_rect.left()) / field_rect.width() * 480.0
        )
        raw_y_cm = round(
            (field_rect.bottom() - event.pos().y()) / field_rect.height() * 400.0
        )
        x_cm = max(0, min(480, int(raw_x_cm) - self.FREE_POINT_COORD_OFFSET_CM))
        y_cm = max(0, min(400, int(raw_y_cm) - self.FREE_POINT_COORD_OFFSET_CM))
        self._free_points.append((x_cm, y_cm, 120))
        self.free_points_changed.emit(list(self._free_points))
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_button_positions()

    def _field_rect(self) -> QRectF:
        if self._image_rect.isNull():
            return QRectF()
        return self._image_rect.adjusted(
            self._image_rect.width() * 0.067,
            self._image_rect.height() * 0.086,
            -self._image_rect.width() * 0.079,
            -self._image_rect.height() * 0.065,
        )

    def _point_to_view(self, x_cm: float, y_cm: float) -> QPointF:
        field_rect = self._field_rect()
        return QPointF(
            field_rect.left() + field_rect.width() * x_cm / 480.0,
            field_rect.bottom() - field_rect.height() * y_cm / 400.0,
        )

    def _free_point_to_view(self, x_cm: float, y_cm: float) -> QPointF:
        visual_x = max(0.0, min(480.0, x_cm + self.FREE_POINT_COORD_OFFSET_CM))
        visual_y = max(0.0, min(400.0, y_cm + self.FREE_POINT_COORD_OFFSET_CM))
        return self._point_to_view(visual_x, visual_y)

    def _draw_free_points(self, painter: QPainter) -> None:
        if not self._free_points:
            painter.setFont(QFont("Microsoft YaHei UI", 20, QFont.Black))
            painter.setPen(QColor("#2d8cff"))
            painter.drawText(
                self._field_rect(),
                Qt.AlignCenter,
                "在地图黑框内点击标定航点，最多 10 个",
            )
            return
        path = QPainterPath()
        for index, (x_cm, y_cm, _z_cm) in enumerate(self._free_points):
            point = self._free_point_to_view(x_cm, y_cm)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        painter.setPen(QPen(QColor(20, 25, 30, 210), 8, Qt.SolidLine))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#ffcc4d"), 5, Qt.SolidLine))
        painter.drawPath(path)
        painter.setFont(QFont("Microsoft YaHei UI", 11, QFont.Black))
        for index, (x_cm, y_cm, z_cm) in enumerate(self._free_points, start=1):
            point = self._free_point_to_view(x_cm, y_cm)
            painter.setBrush(QColor("#ffcc4d"))
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawEllipse(point, 12, 12)
            painter.setPen(QColor("#071421"))
            painter.drawText(
                QRectF(point.x() - 12, point.y() - 12, 24, 24),
                Qt.AlignCenter,
                str(index),
            )
            painter.setPen(QColor("#2d8cff"))
            painter.drawText(
                QPointF(point.x() + 15, point.y() - 10),
                f"({x_cm},{y_cm},{z_cm})",
            )

    def _update_button_positions(self) -> None:
        if self._image_rect.isNull():
            return
        size = max(34, min(48, int(self._image_rect.width() * 0.055)))
        for number, x_ratio, y_ratio in self.WAYPOINTS:
            button = self._buttons[number]
            if self._mode != "preset":
                button.hide()
                continue
            x = int(self._image_rect.left() + self._image_rect.width() * x_ratio - size / 2)
            y = int(self._image_rect.top() + self._image_rect.height() * y_ratio - size / 2)
            button.setGeometry(x, y, size, size)
            button.raise_()


class Attitude3DView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = DroneState()
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(self, state: DroneState) -> None:
        self._state = state
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#020811"))
        panel = QRectF(rect).adjusted(14, 14, -14, -14)
        painter.setPen(QPen(QColor("#315a79"), 2))
        painter.setBrush(QColor("#071928"))
        painter.drawRoundedRect(panel, 12, 12)

        view = panel.adjusted(18, 18, -18, -18)
        self._draw_background(painter, view)
        self._draw_model(painter, view)
        self._draw_hud(painter, view)

    def _draw_background(self, painter: QPainter, rect: QRectF) -> None:
        horizon = rect.center().y()
        sky = QLinearGradient(rect.topLeft(), QPointF(rect.left(), horizon))
        sky.setColorAt(0.0, QColor("#123d70"))
        sky.setColorAt(1.0, QColor("#1f86c7"))
        ground = QLinearGradient(QPointF(rect.left(), horizon), rect.bottomLeft())
        ground.setColorAt(0.0, QColor("#6e5d32"))
        ground.setColorAt(1.0, QColor("#1e4027"))
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), rect.height() / 2), sky)
        painter.fillRect(QRectF(rect.left(), horizon, rect.width(), rect.height() / 2), ground)
        painter.setPen(QPen(QColor(255, 255, 255, 90), 2))
        painter.drawLine(QPointF(rect.left(), horizon), QPointF(rect.right(), horizon))
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
        for offset in range(-4, 5):
            y = horizon + offset * rect.height() / 14
            painter.drawLine(QPointF(rect.left() + 20, y), QPointF(rect.right() - 20, y))

    def _rotation(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        roll = math.radians(self._state.roll)
        pitch = math.radians(self._state.pitch)
        yaw = math.radians(self._state.yaw)

        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)

        y, z = y * cr - z * sr, y * sr + z * cr
        x, z = x * cp + z * sp, -x * sp + z * cp
        x, y = x * cy - y * sy, x * sy + y * cy
        return x, y, z

    def _project(self, point: tuple[float, float, float], rect: QRectF) -> QPointF:
        x, y, z = self._rotation(*point)
        view_x = y - x * 0.42
        view_y = z + x * 0.22
        scale = min(rect.width(), rect.height()) * 0.25
        return QPointF(
            rect.center().x() + view_x * scale,
            rect.center().y() - view_y * scale + rect.height() * 0.06,
        )

    def _draw_model(self, painter: QPainter, rect: QRectF) -> None:
        body_top = [(-0.65, -0.30, 0.18), (0.65, -0.30, 0.18), (0.65, 0.30, 0.18), (-0.65, 0.30, 0.18)]
        body_bottom = [(-0.65, -0.30, -0.18), (0.65, -0.30, -0.18), (0.65, 0.30, -0.18), (-0.65, 0.30, -0.18)]
        top_poly = QPolygonF([self._project(p, rect) for p in body_top])
        bottom_poly = QPolygonF([self._project(p, rect) for p in body_bottom])

        painter.setBrush(QColor(38, 156, 218, 210))
        painter.setPen(QPen(QColor("#d9f7ff"), 2))
        painter.drawPolygon(bottom_poly)
        painter.setBrush(QColor(77, 211, 255, 230))
        painter.drawPolygon(top_poly)

        edges = list(zip(body_top, body_top[1:] + body_top[:1]))
        edges += list(zip(body_bottom, body_bottom[1:] + body_bottom[:1]))
        edges += list(zip(body_top, body_bottom))
        painter.setPen(QPen(QColor("#e8fbff"), 2))
        for a, b in edges:
            painter.drawLine(self._project(a, rect), self._project(b, rect))

        arms = [
            ((-1.45, 0, 0), (1.45, 0, 0), QColor("#ffcc4d")),
            ((0, -1.25, 0), (0, 1.25, 0), QColor("#62f0bd")),
        ]
        for a, b, color in arms:
            painter.setPen(QPen(color, 7, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(self._project(a, rect), self._project(b, rect))

        motors = [
            (-1.55, 0, 0),
            (1.55, 0, 0),
            (0, -1.35, 0),
            (0, 1.35, 0),
        ]
        for idx, motor in enumerate(motors):
            center = self._project(motor, rect)
            color = QColor("#ff5c5c") if idx < 2 else QColor("#62f0bd")
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawEllipse(center, 14, 14)

        nose = [self._project((0.82, 0, 0.28), rect), self._project((1.25, 0, 0.0), rect)]
        painter.setPen(QPen(QColor("#ffef8a"), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(nose[0], nose[1])

    def _draw_hud(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        title = "3D 航姿仪表"
        painter.drawText(QRectF(rect.left() + 18, rect.top() + 12, 240, 28), Qt.AlignLeft | Qt.AlignVCenter, title)
        values = [
            ("横滚 Roll", self._state.roll, "#ffcc4d"),
            ("俯仰 Pitch", self._state.pitch, "#62f0bd"),
            ("航向 Yaw", self._state.yaw, "#7dc8ff"),
        ]
        y = rect.top() + 52
        for label, value, color in values:
            painter.setPen(QColor(color))
            painter.drawText(
                QRectF(rect.left() + 18, y, 220, 26),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{label}: {value:.1f}°",
            )
            y += 30
        painter.setPen(QColor("#d7ecff"))
        painter.drawText(
            QRectF(rect.right() - 260, rect.bottom() - 72, 240, 58),
            Qt.AlignRight | Qt.AlignVCenter,
            f"高度 {self._state.altitude:.2f} m\n垂直速度 {self._state.vertical_speed:.2f} m/s",
        )


class AttitudeCurveWidget(QWidget):
    MAX_POINTS = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history: list[tuple[float, float, float]] = []
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(self, state: DroneState) -> None:
        self._history.append((state.pitch, state.roll, state.yaw))
        if len(self._history) > self.MAX_POINTS:
            self._history = self._history[-self.MAX_POINTS :]
        self.update()

    def clear(self) -> None:
        self._history.clear()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        painter.fillRect(self.rect(), QColor("#061827"))
        painter.setPen(QPen(QColor("#285471"), 1))
        painter.setBrush(QColor("#071d2f"))
        painter.drawRoundedRect(rect, 8, 8)

        plot = rect.adjusted(44, 34, -14, -30)
        painter.setPen(QPen(QColor("#244d68"), 1))
        for i in range(6):
            x = plot.left() + plot.width() * i / 5
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        for i in range(6):
            y = plot.top() + plot.height() * i / 5
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        painter.setPen(QColor("#e8f7ff"))
        painter.drawText(QRectF(rect.left() + 14, rect.top() + 7, 200, 24), Qt.AlignLeft, "姿态角曲线")
        painter.setFont(QFont("Microsoft YaHei UI", 8, QFont.Bold))
        painter.setPen(QColor("#9fc5df"))
        painter.drawText(QRectF(rect.left() + 8, plot.top() - 4, 34, 18), Qt.AlignRight, "360")
        painter.drawText(QRectF(rect.left() + 8, plot.bottom() - 10, 34, 18), Qt.AlignRight, "-180")
        painter.drawText(QRectF(plot.center().x() - 80, rect.bottom() - 24, 160, 18), Qt.AlignCenter, "Sampling Points")
        painter.save()
        painter.translate(rect.left() + 13, plot.center().y() + 28)
        painter.rotate(-90)
        painter.drawText(QRectF(0, 0, 100, 18), Qt.AlignCenter, "Degree")
        painter.restore()

        legend = [("Pitch", "#ff4f5e"), ("Roll", "#5cf07d"), ("Yaw", "#4c8dff")]
        legend_x = rect.right() - 174
        for idx, (name, color) in enumerate(legend):
            x = legend_x + idx * 58
            painter.setPen(QPen(QColor(color), 3))
            painter.drawLine(QPointF(x, rect.top() + 19), QPointF(x + 16, rect.top() + 19))
            painter.setPen(QColor("#d7ecff"))
            painter.drawText(QRectF(x + 20, rect.top() + 9, 42, 20), Qt.AlignLeft, name)

        if len(self._history) < 2:
            painter.setPen(QColor("#8fb6cc"))
            painter.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
            painter.drawText(plot, Qt.AlignCenter, "等待姿态数据")
            return

        def point(index: int, value: float) -> QPointF:
            x = plot.left() + plot.width() * index / max(1, self.MAX_POINTS - 1)
            clamped = max(-180.0, min(360.0, value))
            y = plot.bottom() - (clamped + 180.0) / 540.0 * plot.height()
            return QPointF(x, y)

        channels = [
            (0, QColor("#ff4f5e")),
            (1, QColor("#5cf07d")),
            (2, QColor("#4c8dff")),
        ]
        start = max(0, len(self._history) - self.MAX_POINTS)
        values = self._history[start:]
        for channel, color in channels:
            polygon = QPolygonF()
            for i, sample in enumerate(values):
                polygon.append(point(i, sample[channel]))
            painter.setPen(QPen(color, 2))
            painter.drawPolyline(polygon)


class ParameterSelfCheckPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fields: dict[str, QLabel] = {}
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            """
            QFrame#parameterCard {
                background: rgba(7, 27, 44, 235);
                border: 1px solid #25526f;
                border-radius: 8px;
            }
            QLabel#parameterTitle {
                color: #ffffff;
                font: 900 16px 'Microsoft YaHei UI';
            }
            QLabel#parameterName {
                color: #9fc5df;
                font: 700 12px 'Microsoft YaHei UI';
            }
            QLabel#parameterValue {
                color: #ffffff;
                font: 900 13px 'Microsoft YaHei UI';
            }
            QLabel#parameterHeader {
                color: #ffffff;
                font: 900 22px 'Microsoft YaHei UI';
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.header = QLabel("参数自检 · 飞控状态")
        self.header.setObjectName("parameterHeader")
        self.header.setStyleSheet("color: #ffffff; font: 900 22px 'Microsoft YaHei UI';")
        layout.addWidget(self.header)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(
            self._make_card(
                "飞控状态",
                [
                    ("pitch", "Pitch", "0.00°"),
                    ("roll", "Roll", "0.00°"),
                    ("yaw", "Yaw", "0.00°"),
                    ("alt", "融合高度", "0.00 m"),
                    ("vz", "融合垂速", "0.00 m/s"),
                    ("accelz", "融合加速度", "0.00 m/s²"),
                    ("vbat", "电池电压", "0.00 V"),
                    ("imu_temp", "IMU 温度", "0.00 ℃"),
                    ("flightmode", "飞行模式", "模式 0"),
                    ("armed", "解锁状态", "锁定"),
                ],
            ),
            0,
            0,
        )
        grid.addWidget(
            self._make_card(
                "IMU 原始数据",
                [
                    ("ax", "AX", "0"),
                    ("ay", "AY", "0"),
                    ("az", "AZ", "0"),
                    ("gx", "GX", "0"),
                    ("gy", "GY", "0"),
                    ("gz", "GZ", "0"),
                    ("mx", "MX", "0"),
                    ("my", "MY", "0"),
                    ("mz", "MZ", "0"),
                ],
            ),
            0,
            1,
        )
        grid.addWidget(
            self._make_card(
                "观测传感器数据",
                [
                    ("baro_alt", "气压高度", "0.00 m"),
                    ("ult_alt", "超声/测距", "0.00 m"),
                    ("gps_lng", "GPS 经度", "0.000000"),
                    ("gps_lat", "GPS 纬度", "0.000000"),
                    ("gps_alt", "GPS 高度", "0.00 m"),
                    ("gps_vel_e", "GPS 东向速度", "0.00 m/s"),
                    ("gps_vel_n", "GPS 北向速度", "0.00 m/s"),
                    ("numsv", "卫星数量", "0"),
                    ("opt_vel_p", "光流 P", "0.00"),
                    ("opt_vel_r", "光流 R", "0.00"),
                ],
            ),
            1,
            0,
            1,
            2,
        )

        curve_card = QFrame()
        curve_card.setObjectName("parameterCard")
        curve_layout = QVBoxLayout(curve_card)
        curve_layout.setContentsMargins(10, 10, 10, 10)
        curve_layout.setSpacing(8)
        self.curve = AttitudeCurveWidget()
        curve_layout.addWidget(self.curve, 1)
        grid.addWidget(curve_card, 0, 2, 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        layout.addLayout(grid, 1)

    def _make_card(self, title: str, items: list[tuple[str, str, str]]) -> QFrame:
        card = QFrame()
        card.setObjectName("parameterCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("parameterTitle")
        title_label.setStyleSheet("color: #ffffff; font: 900 16px 'Microsoft YaHei UI';")
        layout.addWidget(title_label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        for index, (key, name, value) in enumerate(items):
            row = index // 2
            col = (index % 2) * 2
            name_label = QLabel(name)
            name_label.setObjectName("parameterName")
            name_label.setStyleSheet("color: #a9d6f0; font: 700 12px 'Microsoft YaHei UI';")
            value_label = QLabel(value)
            value_label.setObjectName("parameterValue")
            value_label.setStyleSheet("color: #ffffff; font: 900 13px 'Microsoft YaHei UI';")
            grid.addWidget(name_label, row, col)
            grid.addWidget(value_label, row, col + 1)
            self._fields[key] = value_label
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid, 1)
        return card

    def set_state(self, state: DroneState) -> None:
        armed_text = "解锁" if state.armed else "锁定"
        values = {
            "pitch": f"{state.pitch:.2f}°",
            "roll": f"{state.roll:.2f}°",
            "yaw": f"{state.yaw:.2f}°",
            "alt": f"{state.altitude:.2f} m",
            "vz": f"{state.vertical_speed:.2f} m/s",
            "accelz": f"{state.vertical_accel:.2f} m/s²",
            "vbat": f"{state.battery_voltage:.2f} V",
            "imu_temp": f"{state.imu_temp:.2f} ℃",
            "flightmode": state.flight_mode,
            "armed": armed_text,
            "ax": str(state.ax),
            "ay": str(state.ay),
            "az": str(state.az),
            "gx": str(state.gx),
            "gy": str(state.gy),
            "gz": str(state.gz),
            "mx": str(state.mx),
            "my": str(state.my),
            "mz": str(state.mz),
            "baro_alt": f"{state.baro_altitude:.2f} m",
            "ult_alt": f"{state.ultrasonic_altitude:.2f} m",
            "gps_lng": f"{state.gps_longitude:.6f}",
            "gps_lat": f"{state.gps_latitude:.6f}",
            "gps_alt": f"{state.gps_altitude:.2f} m",
            "gps_vel_e": f"{state.gps_velocity_e:.2f} m/s",
            "gps_vel_n": f"{state.gps_velocity_n:.2f} m/s",
            "numsv": str(state.gps_satellites),
            "opt_vel_p": f"{state.optical_flow_p:.2f}",
            "opt_vel_r": f"{state.optical_flow_r:.2f}",
        }
        for key, value in values.items():
            if key in self._fields:
                self._fields[key].setText(value)
        self.curve.set_state(state)


class VideoPanel(QFrame):
    snapshot_requested = pyqtSignal()
    connect_camera_requested = pyqtSignal()
    demo_requested = pyqtSignal()
    target_selected = pyqtSignal(str, object)
    target_missed = pyqtSignal(str)
    lens_correction_toggled = pyqtSignal(bool)
    takeoff_map_confirmed = pyqtSignal(object)
    route_sequence_changed = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        toolbar = QHBoxLayout()
        self.view_title = QLabel("无人机实时画面")
        self.view_title.setObjectName("sectionTitle")
        self.mode_label = QLabel("模拟视觉链")
        self.mode_label.setObjectName("chipInfo")
        toolbar.addWidget(self.view_title)
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

        self.info_bar = QLabel("无信号 | 未连接图传 | 1280 × 720 | 15.0 帧/秒 | 高度 0.00 m")
        self.info_bar.setObjectName("videoInfoBar")
        self.info_bar.setWordWrap(True)
        layout.addWidget(self.info_bar)

        self.canvas = VideoCanvas()
        self.canvas.target_clicked.connect(self.target_selected)
        self.canvas.target_missed.connect(self.target_missed)
        layout.addWidget(self.canvas, 1)

        self.attitude_3d_panel = Attitude3DView()
        self.attitude_3d_panel.hide()
        layout.addWidget(self.attitude_3d_panel, 1)

        self.parameter_check_panel = ParameterSelfCheckPanel()
        self.parameter_check_panel.hide()
        layout.addWidget(self.parameter_check_panel, 1)

        self.simulation_host = QWidget()
        self.simulation_host.setObjectName("simulationHost")
        self.simulation_layout = QVBoxLayout(self.simulation_host)
        self.simulation_layout.setContentsMargins(0, 0, 0, 0)
        self.simulation_layout.setSpacing(0)
        self.simulation_widget: QWidget | None = None
        self.simulation_placeholder = QLabel("3D 仿真组件未加载")
        self.simulation_placeholder.setObjectName("selfCheckText")
        self.simulation_placeholder.setAlignment(Qt.AlignCenter)
        self.simulation_layout.addWidget(self.simulation_placeholder, 1)
        self.simulation_host.hide()
        layout.addWidget(self.simulation_host, 1)

        self.map_confirm_panel = QWidget()
        self._takeoff_map_mode = "preset"
        self._route_sequence: list[str] = []
        self._free_waypoints: list[tuple[int, int, int]] = []
        map_layout = QVBoxLayout(self.map_confirm_panel)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(10)
        self.map_preview = MapConfirmView()
        self.map_preview.waypoint_clicked.connect(self._add_route_waypoint)
        self.map_preview.free_points_changed.connect(self._set_free_waypoints)
        map_layout.addWidget(self.map_preview, 1)
        route_layout = QHBoxLayout()
        route_layout.addWidget(QLabel("规划航线："))
        self.route_sequence_widget = QWidget()
        self.route_sequence_layout = QHBoxLayout(self.route_sequence_widget)
        self.route_sequence_layout.setContentsMargins(0, 0, 0, 0)
        self.route_sequence_layout.setSpacing(5)
        route_layout.addWidget(self.route_sequence_widget, 1)
        self.map_confirm_button = QPushButton("确认地图，执行所选起飞项")
        self.map_confirm_button.setObjectName("primaryButton")
        self.map_confirm_button.setMinimumHeight(44)
        self.map_confirm_button.clicked.connect(self._emit_takeoff_map_confirmed)
        route_layout.addWidget(self.map_confirm_button, 0)
        map_layout.addLayout(route_layout)
        self.map_confirm_panel.hide()
        layout.addWidget(self.map_confirm_panel, 1)
        self._refresh_route_sequence()

        footer = QHBoxLayout()
        self.camera_status = QLabel("● 模拟画面")
        self.camera_status.setObjectName("chipGood")
        self.hint = QLabel("双击检测框可将目标加入候选任务")
        self.hint.setObjectName("muted")
        footer.addWidget(self.camera_status)
        footer.addStretch()
        footer.addWidget(self.hint)
        layout.addLayout(footer)

    def _emit_takeoff_map_confirmed(self) -> None:
        if self._takeoff_map_mode == "free":
            self.takeoff_map_confirmed.emit(
                {"mode": "free", "points": list(self._free_waypoints)}
            )
            return
        self.takeoff_map_confirmed.emit(list(self._route_sequence))

    def _on_lens_toggled(self, enabled: bool) -> None:
        self.lens_button.setText("去畸变 ON" if enabled else "去畸变 OFF")
        self.lens_correction_toggled.emit(enabled)

    def _add_route_waypoint(self, number: str) -> None:
        if number in self._route_sequence:
            return
        self._route_sequence.append(number)
        self._refresh_route_sequence()

    def _remove_route_waypoint(self, number: str) -> None:
        if number not in self._route_sequence:
            return
        self._route_sequence.remove(number)
        self._refresh_route_sequence()

    def _set_free_waypoints(self, points: list[tuple[int, int, int]]) -> None:
        self._free_waypoints = list(points[:10])
        self._refresh_route_sequence()

    def _remove_free_waypoint(self, index: int) -> None:
        if index < 0 or index >= len(self._free_waypoints):
            return
        self._free_waypoints.pop(index)
        self.map_preview.set_free_points(self._free_waypoints)
        self._refresh_route_sequence()

    def _refresh_route_sequence(self) -> None:
        while self.route_sequence_layout.count():
            item = self.route_sequence_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._takeoff_map_mode == "free":
            if not self._free_waypoints:
                empty = QLabel("未标定")
                empty.setObjectName("muted")
                self.route_sequence_layout.addWidget(empty)
            else:
                for index, (x_cm, y_cm, z_cm) in enumerate(self._free_waypoints):
                    button = QToolButton()
                    button.setText(f"P{index + 1}({x_cm},{y_cm},{z_cm})")
                    button.setObjectName("routeTokenButton")
                    button.setToolTip("点击删除这个自由航点")
                    button.setCursor(Qt.PointingHandCursor)
                    button.setStyleSheet(
                        "QToolButton { color: #071421; background: #ffcc4d; "
                        "border: 1px solid #ffe7a6; border-radius: 13px; "
                        "font: 900 13px 'Microsoft YaHei UI'; min-height: 30px; "
                        "padding: 0 10px; }"
                        "QToolButton:hover { background: #ffe083; }"
                    )
                    button.clicked.connect(
                        lambda _checked=False, i=index: self._remove_free_waypoint(i)
                    )
                    self.route_sequence_layout.addWidget(button)
            self.route_sequence_layout.addStretch()
            self.map_preview.set_free_points(self._free_waypoints)
            self.route_sequence_changed.emit(
                {"mode": "free", "points": list(self._free_waypoints)}
            )
            return
        if not self._route_sequence:
            empty = QLabel("未选择")
            empty.setObjectName("muted")
            self.route_sequence_layout.addWidget(empty)
        else:
            for number in self._route_sequence:
                button = QToolButton()
                button.setText(number)
                button.setObjectName("routeTokenButton")
                button.setToolTip("点击从航线中删除")
                button.setCursor(Qt.PointingHandCursor)
                button.setStyleSheet(
                    "QToolButton { color: #071421; background: #ffcc4d; "
                    "border: 1px solid #ffe7a6; border-radius: 13px; "
                    "font: 900 20px 'Microsoft YaHei UI'; min-width: 36px; "
                    "min-height: 30px; }"
                    "QToolButton:hover { background: #ffe083; }"
                )
                button.clicked.connect(lambda _checked=False, n=number: self._remove_route_waypoint(n))
                self.route_sequence_layout.addWidget(button)
        self.route_sequence_layout.addStretch()
        self.map_preview.set_route_sequence(self._route_sequence)
        self.route_sequence_changed.emit(list(self._route_sequence))

    def set_lens_correction(self, enabled: bool) -> None:
        self.lens_button.blockSignals(True)
        self.lens_button.setChecked(enabled)
        self.lens_button.setText("去畸变 ON" if enabled else "去畸变 OFF")
        self.lens_button.blockSignals(False)

    def set_state(self, state: DroneState) -> None:
        self.canvas.set_state(state)
        self.attitude_3d_panel.set_state(state)
        self.parameter_check_panel.set_state(state)

    def set_simulation_widget(self, widget: QWidget | None) -> None:
        while self.simulation_layout.count():
            item = self.simulation_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
        self.simulation_widget = widget
        if widget is None:
            self.simulation_placeholder = QLabel("3D 仿真组件未加载")
            self.simulation_placeholder.setObjectName("selfCheckText")
            self.simulation_placeholder.setAlignment(Qt.AlignCenter)
            self.simulation_layout.addWidget(self.simulation_placeholder, 1)
            return
        self.simulation_layout.addWidget(widget, 1)
        widget.hide()

    def set_camera_state(self, state: CameraState) -> None:
        self.canvas.set_camera_state(state)
        if (
            self.map_confirm_panel.isVisible()
            or self.attitude_3d_panel.isVisible()
            or self.parameter_check_panel.isVisible()
            or self.simulation_host.isVisible()
        ):
            return
        if self.canvas._status_report_title or self.canvas._status_report_lines:
            return
        if state.connected:
            self.view_title.setText("无人机实时图传")
            age_text = (
                f" · 帧龄 {state.frame_age_ms} ms"
                if state.frame_age_ms >= 0
                else ""
            )
            self.camera_status.setText(
                f"● AMB82 在线  {state.fps:.1f} 帧/秒{age_text}"
            )
            self.camera_status.setObjectName("chipGood")
            self.mode_label.setText("火源识别 ON")
            source = state.source
            status = "在线"
        else:
            self.view_title.setText("等待无人机图传")
            error = f" · {state.last_error}" if state.last_error else ""
            self.camera_status.setText(
                f"● 图传离线 · 重连 {state.reconnect_count} 次{error}"
            )
            self.camera_status.setObjectName(
                "chipWarn" if state.last_error else "chipInfo"
            )
            self.mode_label.setText("等待真实图传")
            source = "未连接图传"
            status = "无信号"
        self.info_bar.setText(
            f"{status} | {source} | {state.resolution} | "
            f"{state.fps:.1f} 帧/秒 | 高度 {self.canvas._state.altitude:.2f} m"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_demo_mode(self, detection_count: int) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.clear_status_report()
        self.canvas.set_demo_mode(True)
        self.view_title.setText("火源识别示例")
        self.mode_label.setText("火源识别示例")
        self.camera_status.setText(
            f"● 离线示例 · {detection_count} 个候选 · 非实时图传"
        )
        self.info_bar.setText(
            f"示例 | 离线识别示例 · 非实时图传 | "
            f"{self.canvas._frame_size[0]} × {self.canvas._frame_size[1]} | "
            f"高度 {self.canvas._state.altitude:.2f} m"
        )
        self.camera_status.setObjectName(
            "chipGood" if detection_count else "chipWarn"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_live_mode(self) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.clear_status_report()
        self.canvas.set_demo_mode(False)
        self.view_title.setText(
            "无人机实时图传" if self.canvas._camera.connected else "无人机实时画面"
        )
        self.hint.setText("双击检测框可将目标加入候选任务")

    def show_qwen_mode(self, status: str, lines: list[str]) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.set_demo_mode(False)
        self.canvas.set_detections([])
        self.canvas.set_inspection_detections([])
        self.canvas.show_status_report("Qwen-VL 推理工作台", lines)
        self.view_title.setText("Qwen-VL 图像分析")
        self.mode_label.setText("GPU 推理模式")
        self.camera_status.setText("● 图传读取已暂停 · 使用已保存截图")
        self.camera_status.setObjectName(
            "chipWarn" if status in {"loading", "busy", "memory"} else "chipGood"
        )
        self.hint.setText("关闭 Qwen 推理开关后，将自动重新连接无人机图传")
        self.info_bar.setText(f"Qwen推理 | {status} | 图传与OpenCV已暂停")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_returning_mode(self, task_label: str = "") -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        message = "正在切回图传"
        if task_label:
            message = f"正在切回图传\n当前任务：{task_label}"
        self.canvas.show_transition(message, 1.4)
        self.view_title.setText("正在切回图传")
        self.mode_label.setText("切回图传中")
        self.camera_status.setText("● 正在恢复无人机图传")
        self.camera_status.setObjectName("chipInfo")
        hint = "多模态识别已完成，正在切回无人机图传"
        if task_label:
            hint += f"：{task_label}"
        self.hint.setText(hint)
        self.info_bar.setText(
            f"切回图传 | 当前任务：{task_label or '多模态任务'} | 正在恢复主画面"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_takeoff_countdown(self, seconds_left: int) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.clear_status_report()
        self.canvas.set_demo_mode(False)
        self.canvas.show_transition(f"起飞倒计时\n{seconds_left}", 1.1)
        self.view_title.setText("起飞倒计时")
        self.mode_label.setText("航点已下发")
        self.camera_status.setText("● 等待巡航启动")
        self.camera_status.setObjectName("chipWarn")
        self.hint.setText("航点已经写入飞控，倒计时结束后启动 mode18 巡航")
        self.info_bar.setText(
            f"起飞倒计时 | 航点已写入飞控 | {seconds_left} 秒后启动巡航"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_return_countdown(self, seconds_left: int) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.clear_status_report()
        self.canvas.set_demo_mode(False)
        self.canvas.show_transition(f"返航倒计时\n{seconds_left}", 1.1)
        self.view_title.setText("返航倒计时")
        self.mode_label.setText("等待返航")
        self.camera_status.setText("● 10秒后返航 · 等待发送")
        self.camera_status.setObjectName("chipWarn")
        self.hint.setText("倒计时结束后，UART4 将自动发送返航指令")
        self.info_bar.setText(
            f"返航倒计时 | {seconds_left} 秒后发送 UART4 返航指令"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_multimodal_mode(self) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.clear_status_report()
        self.canvas.set_demo_mode(False)
        self.canvas.set_detections([])
        self.view_title.setText("多模态识别画面")
        self.mode_label.setText("多模态识别")
        self.camera_status.setText("● 多模态摄像头 · 手势+视线")
        self.camera_status.setObjectName("chipInfo")
        self.hint.setText("手势选择大类，倒数后用视线选择三个区域之一")
        self.info_bar.setText(
            f"多模态 | USB 摄像头 · 手势+视线 | "
            f"{self.canvas._frame_size[0]} × {self.canvas._frame_size[1]} | "
            "识别画面"
        )
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_takeoff_map_confirmation(
        self, mode: str = "preset", task_label: str = ""
    ) -> None:
        self._takeoff_map_mode = "free" if mode == "free" else "preset"
        self._route_sequence = []
        self._free_waypoints = []
        self.map_preview.set_mode(self._takeoff_map_mode)
        self.map_preview.clear_free_points()
        self._refresh_route_sequence()
        self.canvas.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.map_confirm_panel.show()
        self.view_title.setText(f"{task_label or '起飞任务'}地图确认")
        if self._takeoff_map_mode == "free":
            self.mode_label.setText("高空自由航线")
            self.camera_status.setText("● 定制航点 · 自由标定航线")
            self.hint.setText("在地图上点击标定航点，最多 10 个；点击下方坐标可删除")
            self.info_bar.setText(
                "定制航点确认 | 点击地图自由规划航线，坐标单位 cm，高度固定 120"
            )
        else:
            self.mode_label.setText("等待确认")
            self.camera_status.setText("● 手势+视线已完成 → 起飞")
            self.hint.setText("点击地图中的巡逻点规划航线，点下方数字可删除")
            self.info_bar.setText("起飞确认 | 已完成手势+视线识别，请检查地图并手动规划航线")
        self.camera_status.setObjectName("chipWarn")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_attitude_3d_mode(self, state: DroneState) -> None:
        self.map_confirm_panel.hide()
        self.canvas.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.attitude_3d_panel.show()
        self.attitude_3d_panel.set_state(state)
        self.view_title.setText("姿态自检 · 3D 航姿仪表")
        self.mode_label.setText("航姿仪表")
        self.camera_status.setText("● 姿态数据实时驱动")
        self.camera_status.setObjectName("chipInfo")
        self.hint.setText("3D 无人机模型随 Roll / Pitch / Yaw 实时旋转")
        self.info_bar.setText("姿态自检 | 3D 航姿仪表 | 数据随飞控姿态帧实时刷新")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_parameter_check_mode(self, state: DroneState) -> None:
        self.map_confirm_panel.hide()
        self.canvas.hide()
        self.attitude_3d_panel.hide()
        self.simulation_host.hide()
        self.parameter_check_panel.show()
        self.parameter_check_panel.set_state(state)
        self.view_title.setText("参数自检 · 飞控状态")
        self.mode_label.setText("参数自检")
        self.camera_status.setText("● 飞控参数实时刷新")
        self.camera_status.setObjectName("chipInfo")
        self.hint.setText("对齐无名创新：飞控状态、IMU 原始数据、观测传感器数据、姿态角曲线")
        self.info_bar.setText("参数自检 | NCLink 飞控状态页 | 数据随串口回传实时刷新")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_self_check_mode(self, title: str, lines: list[str]) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.set_demo_mode(False)
        self.canvas.set_detections([])
        self.canvas.show_status_report(title, lines)
        self.view_title.setText("飞控自检状态")
        self.mode_label.setText("自检状态")
        self.camera_status.setText("● 飞控自检 · 串口状态")
        self.camera_status.setObjectName("chipInfo")
        self.hint.setText("当前画面显示飞控数传读取到的实时状态")
        self.info_bar.setText("自检 | 串口/数传状态实时显示 | 数据随飞控回传刷新")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_flight_log_preview(self, title: str, lines: list[str], saved_path: str) -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.simulation_host.hide()
        self.canvas.show()
        self.canvas.set_demo_mode(False)
        self.canvas.set_detections([])
        self.canvas.show_status_report(title, lines)
        self.view_title.setText("飞行日志预览")
        self.mode_label.setText("日志输出")
        self.camera_status.setText("● Markdown 日志已生成")
        self.camera_status.setObjectName("chipGood")
        self.hint.setText(f"飞行日志已保存：{saved_path}")
        self.info_bar.setText("日志输出 | 最近一次飞行采样结果 | Markdown 预览")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)

    def show_simulation_mode(self, available: bool = True, error: str = "") -> None:
        self.map_confirm_panel.hide()
        self.attitude_3d_panel.hide()
        self.parameter_check_panel.hide()
        self.canvas.hide()
        self.simulation_host.show()
        if self.simulation_widget is not None:
            self.simulation_widget.show()
        self.view_title.setText("无人机3D仿真")
        self.mode_label.setText("仿真飞行")
        if available:
            self.camera_status.setText("● 3D 仿真运行中")
            self.camera_status.setObjectName("chipGood")
            self.hint.setText("使用独立仿真控制窗发送起飞、航线、自定义飞控指令")
            self.info_bar.setText("仿真飞行 | 3D 无人机模型 | 指令由独立窗口驱动")
        else:
            self.camera_status.setText("● 3D 仿真不可用")
            self.camera_status.setObjectName("chipWarn")
            self.hint.setText(error or "请安装 pyqtgraph 与 PyOpenGL 后重启地面站")
            self.info_bar.setText("仿真飞行 | 组件未加载 | 请检查 OpenGL 依赖")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)


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
        self.position = MetricBox("本地坐标", "35, 35", "cm")
        self.attitude = MetricBox("姿态 R/P", "0.0 / 0.0", "°")
        self._secondary_metrics = [self.position, self.attitude]
        grid.addWidget(self.altitude, 0, 0)
        grid.addWidget(self.speed, 0, 1)
        grid.addWidget(self.position, 1, 0)
        grid.addWidget(self.attitude, 1, 1)
        layout.addLayout(grid)

        battery_row = QHBoxLayout()
        battery_label = QLabel("电压")
        battery_label.setObjectName("muted")
        self.battery_text = QLabel("16.4 V")
        battery_row.addWidget(battery_label)
        battery_row.addStretch()
        battery_row.addWidget(self.battery_text)
        layout.addLayout(battery_row)
        self.battery = QProgressBar()
        self.battery.setRange(0, 100)
        self.battery.setValue(91)
        self.battery.setTextVisible(True)
        self.battery.setFormat("16.4V / 18V")
        layout.addWidget(self.battery)

        detail = QGridLayout()
        detail.setHorizontalSpacing(16)
        detail.setVerticalSpacing(7)
        self.phase = QLabel("任务待命")
        self.flow = QLabel("86")
        self.latency = QLabel("26 ms")
        self.waypoint = QLabel("0 / 6")
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
        self.position.set_value(f"{state.x:.0f}, {state.y:.0f}")
        self.attitude.set_value(f"{state.roll:.1f} / {state.pitch:.1f}")
        voltage_ratio = max(0.0, min(1.0, state.battery_voltage / 18.0))
        self.battery.setValue(round(voltage_ratio * 100))
        self.battery.setFormat(f"{state.battery_voltage:.1f}V / 18V")
        self.battery_text.setText(f"{state.battery_voltage:.1f} V")
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
    FIELD_WIDTH_CM = 480.0
    FIELD_HEIGHT_CM = 400.0
    FREE_POINT_DISPLAY_OFFSET_CM = 40.0
    ROUTE_WAYPOINTS = {
        "6": (145.0, 290.0),
        "5": (270.0, 285.0),
        "4": (390.0, 290.0),
        "1": (140.0, 180.0),
        "2": (270.0, 180.0),
        "3": (400.0, 170.0),
    }

    def __init__(self, waypoints: list[tuple[float, float]], parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._waypoints = waypoints
        self._state = DroneState()
        self._takeoff_point = (35.0, 35.0)
        self._return_point = (35.0, 35.0)
        self._route_points = [self._takeoff_point, *waypoints, self._return_point]
        self._track: list[tuple[float, float]] = [self._takeoff_point]
        self._drone_map_point = self._takeoff_point
        self._tracking_origin_raw: tuple[float, float] | None = None
        self._planning_sequence: list[str] = []
        self._planning_points: list[tuple[float, float]] = []
        self._planning_preview = False
        self._route_tracking = False
        self._map_pixmap = QPixmap(
            str(Path(__file__).resolve().parent / "examples" / "fire_test_scene.png")
        )

    def set_planning_route(self, sequence: list[str]) -> None:
        self._planning_sequence = [
            item for item in sequence if item in self.ROUTE_WAYPOINTS
        ]
        self._planning_points = []
        self._planning_preview = True
        self._route_tracking = False
        self.update()

    def set_planning_points(self, points: list[tuple[float, float]]) -> None:
        self._planning_sequence = []
        self._planning_points = [self._clamp_field_point(point) for point in points[:10]]
        self._planning_preview = True
        self._route_tracking = False
        self.update()

    def start_route_tracking(self, sequence: list[str]) -> None:
        self._planning_sequence = [
            item for item in sequence if item in self.ROUTE_WAYPOINTS
        ]
        self._planning_points = []
        self._planning_preview = True
        self._route_tracking = True
        self._tracking_origin_raw = None
        self._drone_map_point = self._takeoff_point
        self._track = [self._takeoff_point]
        self.update()

    def start_route_tracking_points(self, points: list[tuple[float, float]]) -> None:
        self._planning_sequence = []
        self._planning_points = [self._clamp_field_point(point) for point in points[:10]]
        self._planning_preview = True
        self._route_tracking = True
        self._tracking_origin_raw = None
        self._drone_map_point = self._takeoff_point
        self._track = [self._takeoff_point]
        self.update()

    def clear_planning_route(self) -> None:
        if (
            not self._planning_preview
            and not self._planning_sequence
            and not self._planning_points
            and not self._route_tracking
        ):
            return
        self._planning_sequence = []
        self._planning_points = []
        self._planning_preview = False
        self._route_tracking = False
        self._tracking_origin_raw = None
        self.update()

    def set_state(self, state: DroneState) -> None:
        self._state = state
        raw_point = (state.x, state.y)
        if self._route_tracking:
            if self._tracking_origin_raw is None:
                self._tracking_origin_raw = raw_point
            origin_x, origin_y = self._tracking_origin_raw
            point = (
                self._takeoff_point[0] + raw_point[0] - origin_x,
                self._takeoff_point[1] + raw_point[1] - origin_y,
            )
            point = self._clamp_field_point(point)
            self._drone_map_point = point
        else:
            point = self._clamp_field_point(raw_point)
            self._drone_map_point = point
        if not self._track:
            self._track.append(point)
        elif math.hypot(point[0] - self._track[-1][0], point[1] - self._track[-1][1]) > 0.25:
            self._track.append(point)
            self._track = self._track[-600:]
        self.update()

    def _clamp_field_point(self, point: tuple[float, float]) -> tuple[float, float]:
        if not math.isfinite(point[0]) or not math.isfinite(point[1]):
            return self._drone_map_point
        return (
            max(0.0, min(self.FIELD_WIDTH_CM, point[0])),
            max(0.0, min(self.FIELD_HEIGHT_CM, point[1])),
        )

    def _free_point_display_point(
        self, point: tuple[float, float]
    ) -> tuple[float, float]:
        return self._clamp_field_point(
            (
                point[0] + self.FREE_POINT_DISPLAY_OFFSET_CM,
                point[1] + self.FREE_POINT_DISPLAY_OFFSET_CM,
            )
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.fillRect(rect, QColor("#f6fbff"))

        if not self._map_pixmap.isNull():
            scaled = self._map_pixmap.scaled(
                rect.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            map_rect = QRectF(
                rect.left() + (rect.width() - scaled.width()) / 2,
                rect.top() + (rect.height() - scaled.height()) / 2,
                scaled.width(),
                scaled.height(),
            )
            painter.drawPixmap(map_rect, scaled, QRectF(scaled.rect()))
        else:
            map_rect = QRectF(rect)
            painter.fillRect(map_rect, QColor("#eef8ff"))
            painter.setPen(QPen(QColor("#b8e6f8"), 1))
            for i in range(0, 49, 2):
                x = map_rect.left() + map_rect.width() * i / 48
                painter.drawLine(int(x), int(map_rect.top()), int(x), int(map_rect.bottom()))
            for i in range(0, 41, 2):
                y = map_rect.bottom() - map_rect.height() * i / 40
                painter.drawLine(int(map_rect.left()), int(y), int(map_rect.right()), int(y))

        field_rect = map_rect.adjusted(
            map_rect.width() * 0.067,
            map_rect.height() * 0.086,
            -map_rect.width() * 0.079,
            -map_rect.height() * 0.065,
        )

        def point(x: float, y: float) -> QPointF:
            return QPointF(
                field_rect.left() + field_rect.width() * x / self.FIELD_WIDTH_CM,
                field_rect.bottom() - field_rect.height() * y / self.FIELD_HEIGHT_CM,
            )

        if self._planning_preview:
            planning_points = [
                self._free_point_display_point(item)
                for item in self._planning_points
            ]
            planned_points = (
                planning_points
                if planning_points
                else [
                    self.ROUTE_WAYPOINTS[number]
                    for number in self._planning_sequence
                ]
            )
            preview_points = [
                self._takeoff_point,
                *planned_points,
                self._return_point,
            ]
            if len(preview_points) > 1:
                route = QPainterPath()
                route.moveTo(point(*preview_points[0]))
                for wp in preview_points[1:]:
                    route.lineTo(point(*wp))
                painter.setPen(QPen(QColor(20, 25, 30, 210), 8, Qt.SolidLine))
                painter.drawPath(route)
                painter.setPen(QPen(QColor("#ffcc4d"), 5, Qt.SolidLine))
                painter.drawPath(route)
        else:
            painter.setPen(QPen(QColor(30, 117, 220, 230), 4, Qt.SolidLine))
            route = QPainterPath()
            route.moveTo(point(*self._route_points[0]))
            for wp in self._route_points[1:]:
                route.lineTo(point(*wp))
            painter.drawPath(route)

        takeoff = point(*self._takeoff_point)
        painter.setBrush(QColor("#ff2c2c"))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawRoundedRect(QRectF(takeoff.x() - 7, takeoff.y() - 7, 14, 14), 3, 3)
        painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(point(6.0, 55.0), "起飞")
        painter.drawText(point(6.0, 20.0), "返航")

        if self._planning_preview:
            selected = set(self._planning_sequence)
            painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
            if self._planning_points:
                for index, wp in enumerate(self._planning_points, start=1):
                    p = point(*self._free_point_display_point(wp))
                    painter.setBrush(QColor("#ffcc4d"))
                    painter.setPen(QPen(QColor("#ffffff"), 2))
                    painter.drawEllipse(p, 9, 9)
                    painter.setPen(QColor("#071421"))
                    painter.drawText(QRectF(p.x() - 9, p.y() - 9, 18, 18), Qt.AlignCenter, str(index))
            else:
                for number, wp in self.ROUTE_WAYPOINTS.items():
                    p = point(*wp)
                    active = number in selected
                    painter.setBrush(QColor("#ffcc4d") if active else QColor(30, 117, 220, 235))
                    painter.setPen(QPen(QColor("#ffffff"), 2))
                    painter.drawEllipse(p, 9, 9)
                    painter.setPen(QColor("#071421") if active else QColor("#ffffff"))
                    painter.drawText(QRectF(p.x() - 9, p.y() - 9, 18, 18), Qt.AlignCenter, number)
        else:
            for wp in self._waypoints:
                p = point(*wp)
                painter.setBrush(QColor(30, 117, 220, 235))
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawEllipse(p, 8, 8)

        if (self._route_tracking or not self._planning_preview) and len(self._track) > 1:
            pen_style = Qt.DashLine if self._route_tracking else Qt.SolidLine
            painter.setPen(QPen(QColor("#2d8cff"), 3, pen_style))
            track = QPainterPath()
            track.moveTo(point(*self._track[0]))
            for item in self._track[1:]:
                track.lineTo(point(*item))
            painter.drawPath(track)

        if self._route_tracking or not self._planning_preview:
            drone_x, drone_y = self._drone_map_point
            drone = point(drone_x, drone_y)
            painter.setBrush(QColor("#5ff0be"))
            painter.setPen(QPen(QColor("#063c2e"), 2))
            painter.drawEllipse(drone, 8, 8)
            painter.setPen(QColor("#063c2e"))
            painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
            painter.drawText(drone + QPointF(11, -8), "UAV")


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
        if self.map._route_tracking:
            if self.map._planning_points:
                route_text = f"自由{len(self.map._planning_points)}点"
            else:
                route_text = "".join(self.map._planning_sequence) if self.map._planning_sequence else "默认"
            self.progress_text.setText(f"航线 {route_text} · 跟踪中")
        elif not self.map._planning_preview:
            self.progress_text.setText(f"进度 {state.mission_progress:.0f}%")

    def set_planning_route(self, sequence: list[str]) -> None:
        self.map.set_planning_route(sequence)
        route_text = "".join(sequence) if sequence else "未选择"
        self.progress_text.setText(f"航线 {route_text}")

    def set_planning_points(self, points: list[tuple[float, float]]) -> None:
        self.map.set_planning_points(points)
        self.progress_text.setText(f"自由航点 {len(points)}")

    def start_route_tracking(self, sequence: list[str]) -> None:
        self.map.start_route_tracking(sequence)
        route_text = "".join(sequence) if sequence else "默认"
        self.progress_text.setText(f"航线 {route_text} · 跟踪中")

    def start_route_tracking_points(self, points: list[tuple[float, float]]) -> None:
        self.map.start_route_tracking_points(points)
        self.progress_text.setText(f"自由航点 {len(points)} · 跟踪中")

    def clear_planning_route(self) -> None:
        self.map.clear_planning_route()
        self.progress_text.setText(f"进度 {self.map._state.mission_progress:.0f}%")


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
        self.input.setPlaceholderText("输入或转写语音，例如：姿态自检 / 低空巡逻 / 日志输出")
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
        normalized = (
            text.replace(" ", "")
            .replace("，", "")
            .replace(",", "")
            .replace("。", "")
            .replace("！", "")
            .replace("!", "")
        )
        mappings = [
            (("起飞前预热", "起飞预热", "预热", "热机", "起飞准备"), "INFO_ACTION", "起飞前预热", "medium", False),
            (("低空巡逻",), "TAKEOFF", "低空巡逻", "high", True),
            (("定制航点",), "TAKEOFF", "定制航点", "high", True),
            (("电机自检", "电机检查", "检查电机"), "INFO_ACTION", "电机自检", "medium", False),
            (("姿态自检", "航姿仪表", "姿态检查"), "INFO_ACTION", "姿态自检", "medium", False),
            (("参数自检", "参数检查", "飞控参数", "飞控状态"), "INFO_ACTION", "参数自检", "medium", False),
            (("陀螺仪自检", "陀螺仪检查", "姿态传感器自检", "惯导自检"), "INFO_ACTION", "陀螺仪自检", "medium", False),
            (("摄像头状态", "相机状态", "检查摄像头", "检查相机", "图传状态"), "INFO_ACTION", "摄像头状态检查", "medium", False),
            (("立即返航", "马上返航", "立刻返航", "现在返航"), "RTL", "立即返航", "high", True),
            (("10秒后返航", "十秒后返航", "延迟10秒返航", "延迟十秒返航"), "INFO_ACTION", "10秒后返航", "medium", False),
            (("日志输出", "导出日志", "飞行日志", "输出日志"), "INFO_ACTION", "日志输出", "medium", False),
            (("自检", "开始自检", "执行自检"), "INFO_ACTION", "系统自检", "medium", False),
            (("返航", "返回起点"), "RTL", "返回起点", "high", True),
            (("降落",), "LAND", "自动降落", "high", True),
            (("暂停", "悬停"), "HOLD", "暂停并悬停", "medium", False),
            (("继续",), "CONTINUE", "继续任务", "medium", False),
            (("开始巡逻", "开始任务"), "START_MISSION", "开始巡逻", "high", True),
            (("起飞",), "TAKEOFF", "自动起飞", "high", True),
            (("截图",), "SNAPSHOT", "保存截图", "low", False),
        ]
        for keywords, action, label, risk, confirm in mappings:
            if any(keyword in normalized for keyword in keywords):
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
                        parameters={"raw_text": text, "matched_label": label},
                    )
                )
                return
        self.result.setText(
            "无法解析："
            f"{text}\n"
            "可输入：预热、低空巡逻、定制航点、姿态自检、参数自检、"
            "摄像头状态、立即返航、10秒后返航、日志输出"
        )

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


def find_multimodal_python() -> Path:
    app_root = Path(__file__).resolve().parents[1]
    candidates = [
        app_root / "multimodal_recognition" / ".venv" / "Scripts" / "python.exe",
        app_root.parent
        / "IntelCup-2026-multimodal-input"
        / "multimodal_recognition"
        / ".venv"
        / "Scripts"
        / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


class GesturePanel(QWidget):
    command_proposed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._script = (
            Path(__file__).resolve().parents[1]
            / "multimodal_recognition"
            / "gesture_three.py"
        )
        self._python = find_multimodal_python()
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
        controls = QHBoxLayout()
        self.start_button = QPushButton("启动手势识别")
        self.start_button.clicked.connect(self._start_recognition)
        controls.addWidget(self.start_button)
        self.stop_button = QPushButton("停止识别")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_recognition)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)
        self.recognition_log = QPlainTextEdit()
        self.recognition_log.setReadOnly(True)
        self.recognition_log.setMaximumHeight(115)
        self.recognition_log.setPlaceholderText(
            "真实手势识别状态会显示在这里"
        )
        layout.addWidget(self.recognition_log)
        layout.addStretch()

    def _set_health(self, text: str, object_name: str) -> None:
        self.confidence.setText(text)
        self.confidence.setObjectName(object_name)
        self.confidence.style().unpolish(self.confidence)
        self.confidence.style().polish(self.confidence)

    def _submit(self) -> None:
        if not self.enabled.isChecked():
            self._set_health("手势输入已禁用", "chipWarn")
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

    def _start_recognition(self) -> None:
        if self._process is not None:
            return
        if not self._script.exists():
            self._set_health("未找到手势识别程序", "chipWarn")
            self.recognition_log.appendPlainText(
                "请确认 multimodal_recognition 目录已经并入地面站。"
            )
            return
        process = QProcess(self)
        process.setProgram(str(self._python))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONIOENCODING", "utf-8")
        environment.insert("PYTHONUTF8", "1")
        process.setProcessEnvironment(environment)
        process.setArguments(
            [
                str(self._script),
                "--camera",
                "0",
                "--rotate",
                "0",
                "--min-confidence",
                "0.65",
            ]
        )
        process.setWorkingDirectory(str(self._script.parent))
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        self._process = process
        self.recognition_log.clear()
        self.recognition_log.appendPlainText(f"启动手势识别：{self._python}")
        self.recognition_log.appendPlainText("请勿同时开启视线识别，以免占用同一个摄像头。")
        self._set_health("手势识别启动中", "chipInfo")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        process.start()

    def _stop_recognition(self) -> None:
        if self._process is None:
            return
        self.recognition_log.appendPlainText("正在停止手势识别...")
        self._process.terminate()
        if not self._process.waitForFinished(1500):
            self._process.kill()

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if not line.strip():
                continue
            self.recognition_log.appendPlainText(line)
            self._handle_recognition_line(line)

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if line.strip():
                self.recognition_log.appendPlainText(f"提示：{line}")

    def _handle_recognition_line(self, line: str) -> None:
        if not line.startswith("TRIGGER:"):
            return
        mappings = [
            ("Open Palm", "HOLD", "暂停并悬停", "medium", False),
            ("Fist", "CANCEL_SELECTION", "取消目标选择", "low", False),
            ("Thumb Up", "CONFIRM_CANDIDATE", "确认候选操作", "medium", False),
        ]
        for keyword, action, label, risk, confirm in mappings:
            if keyword in line:
                confidence = self._extract_confidence(line, 0.90)
                self._set_health(
                    f"真实手势：{label} · {confidence:.0%}",
                    "chipGood",
                )
                self.command_proposed.emit(
                    CommandIntent(
                        action=action,
                        source="手势",
                        label=label,
                        confidence=confidence,
                        risk_level=risk,
                        requires_confirmation=confirm,
                    )
                )
                return

    def _process_error(self, _error) -> None:
        self._set_health("手势识别启动失败", "chipWarn")
        self.recognition_log.appendPlainText(
            "请先运行 install_multimodal_deps.bat 安装多模态依赖。"
        )

    def _process_finished(self, exit_code: int, _exit_status) -> None:
        self._process = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if exit_code == 0:
            self._set_health("手势识别已停止", "chipInfo")
        else:
            self._set_health("手势识别已退出，请查看日志", "chipWarn")

    @staticmethod
    def _extract_confidence(line: str, fallback: float) -> float:
        match = re.search(r"\((\d+)%\)", line)
        if not match:
            return fallback
        return int(match.group(1)) / 100


class GazePanel(QWidget):
    command_proposed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._script = (
            Path(__file__).resolve().parents[1]
            / "multimodal_recognition"
            / "gaze_three_point.py"
        )
        self._python = find_multimodal_python()
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
        controls = QHBoxLayout()
        self.start_button = QPushButton("启动视线识别")
        self.start_button.clicked.connect(self._start_recognition)
        controls.addWidget(self.start_button)
        self.stop_button = QPushButton("停止识别")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_recognition)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)
        self.recognition_log = QPlainTextEdit()
        self.recognition_log.setReadOnly(True)
        self.recognition_log.setMaximumHeight(115)
        self.recognition_log.setPlaceholderText(
            "真实视线识别状态会显示在这里"
        )
        layout.addWidget(self.recognition_log)
        layout.addStretch()

    def _set_health(self, text: str, object_name: str) -> None:
        self.calibration.setText(text)
        self.calibration.setObjectName(object_name)
        self.calibration.style().unpolish(self.calibration)
        self.calibration.style().polish(self.calibration)

    def _submit(self) -> None:
        if not self.enabled.isChecked():
            self._set_health("视线输入已禁用", "chipWarn")
            return
        self._set_health(
            f"校准良好 · 最近输入 {datetime.now().strftime('%H:%M:%S')} · 89%",
            "chipGood",
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

    def _start_recognition(self) -> None:
        if self._process is not None:
            return
        if not self._script.exists():
            self._set_health("未找到视线识别程序", "chipWarn")
            self.recognition_log.appendPlainText(
                "请确认 multimodal_recognition 目录已经并入地面站。"
            )
            return
        process = QProcess(self)
        process.setProgram(str(self._python))
        process.setArguments(
            [
                str(self._script),
                "--camera",
                "0",
                "--rotate",
                "0",
                "--min-confidence",
                "0.62",
                "--head-priority",
                "0.72",
                "--laser",
                "--laser-base-offset",
                "0.02",
                "--laser-vertical-scale",
                "8.0",
            ]
        )
        process.setWorkingDirectory(str(self._script.parent))
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        self._process = process
        self.recognition_log.clear()
        self.recognition_log.appendPlainText(f"启动视线识别：{self._python}")
        self.recognition_log.appendPlainText("请勿同时开启手势识别，以免占用同一个摄像头。")
        self._set_health("视线识别启动中", "chipInfo")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        process.start()

    def _stop_recognition(self) -> None:
        if self._process is None:
            return
        self.recognition_log.appendPlainText("正在停止视线识别...")
        self._process.terminate()
        if not self._process.waitForFinished(1500):
            self._process.kill()

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if not line.strip():
                continue
            self.recognition_log.appendPlainText(line)
            self._handle_recognition_line(line)

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if line.strip():
                self.recognition_log.appendPlainText(f"提示：{line}")

    def _handle_recognition_line(self, line: str) -> None:
        if line in {"CONFIRM", "CANCEL"}:
            action = "CONFIRM_CANDIDATE" if line == "CONFIRM" else "CANCEL_SELECTION"
            label = "确认候选操作" if line == "CONFIRM" else "取消目标选择"
            self._set_health(f"头部动作：{label}", "chipGood")
            self.command_proposed.emit(
                CommandIntent(
                    action=action,
                    source="视线",
                    label=label,
                    confidence=0.90,
                    risk_level="medium" if line == "CONFIRM" else "low",
                    requires_confirmation=False,
                )
            )
            return
        for direction in ("LEFT", "CENTER", "RIGHT"):
            if f": {direction} " in line or line.endswith(f": {direction}"):
                confidence = GesturePanel._extract_confidence(line, 0.85)
                self._set_health(
                    f"视线方向：{direction} · {confidence:.0%}",
                    "chipGood",
                )
                return

    def _process_error(self, _error) -> None:
        self._set_health("视线识别启动失败", "chipWarn")
        self.recognition_log.appendPlainText(
            "请先运行 install_multimodal_deps.bat 安装多模态依赖。"
        )

    def _process_finished(self, exit_code: int, _exit_status) -> None:
        self._process = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if exit_code == 0:
            self._set_health("视线识别已停止", "chipInfo")
        else:
            self._set_health("视线识别已退出，请查看日志", "chipWarn")


class MultimodalPanel(QWidget):
    command_proposed = pyqtSignal(object)
    scenario_started = pyqtSignal(str)
    scenario_stopped = pyqtSignal()
    takeoff_map_requested = pyqtSignal(object)

    def __init__(
        self,
        voice_panel: VoicePanel,
        gesture_panel: GesturePanel,
        gaze_panel: GazePanel,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._script = (
            Path(__file__).resolve().parents[1]
            / "multimodal_recognition"
            / "intent_scenario.py"
        )
        self._python = find_multimodal_python()
        self._pending_takeoff_intent: CommandIntent | None = None
        self.voice_panel = voice_panel
        self.gesture_panel = gesture_panel
        self.gaze_panel = gaze_panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.voice_panel, 0)

        scenario_controls = QHBoxLayout()
        self.scenario_start = QPushButton("启动手势+视线场景")
        self.scenario_start.setObjectName("primaryButton")
        self.scenario_start.clicked.connect(self._start_scenario)
        scenario_controls.addWidget(self.scenario_start)
        self.scenario_stop = QPushButton("停止场景识别")
        self.scenario_stop.setEnabled(False)
        self.scenario_stop.clicked.connect(self._stop_scenario)
        scenario_controls.addWidget(self.scenario_stop)
        layout.addLayout(scenario_controls)

        self.scenario_log = QPlainTextEdit()
        self.scenario_log.setReadOnly(True)
        self.scenario_log.setMaximumHeight(105)
        self.scenario_log.setPlaceholderText(
            "手势三选一确认大类后，直接进入视线三选一"
        )
        layout.addWidget(self.scenario_log)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.South)
        self.tabs.addTab(self.gesture_panel, "手势交互")
        self.tabs.addTab(self.gaze_panel, "视线交互")
        layout.addWidget(self.tabs, 1)

    def show_section(self, name: str) -> None:
        if name == "gesture":
            self.tabs.setCurrentWidget(self.gesture_panel)
        elif name == "gaze":
            self.tabs.setCurrentWidget(self.gaze_panel)

    def _start_scenario(self) -> None:
        if self._process is not None:
            return
        if not self._script.exists():
            self.scenario_log.appendPlainText("未找到场景识别程序。")
            return
        process = QProcess(self)
        process.setProgram(str(self._python))
        process.setArguments(
            [
                str(self._script),
                "--camera",
                "0",
                "--rotate",
                "0",
                "--laser",
                "--no-window",
                "--preview-file",
                str(Path(__file__).resolve().parents[1] / "work" / "multimodal_preview.jpg"),
            ]
        )
        process.setWorkingDirectory(str(self._script.parent))
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        self._process = process
        self.scenario_log.clear()
        self._pending_takeoff_intent = None
        self.scenario_log.appendPlainText(f"启动场景识别：{self._python}")
        self.scenario_log.appendPlainText(
            "流程：手势三选一选择 起飞/自检/返航 -> 视线三选一选择细项。"
        )
        self.scenario_start.setEnabled(False)
        self.scenario_stop.setEnabled(True)
        process.start()
        self.scenario_started.emit(
            str(Path(__file__).resolve().parents[1] / "work" / "multimodal_preview.jpg")
        )

    def _stop_scenario(self) -> None:
        if self._process is None:
            return
        self.scenario_log.appendPlainText("正在停止场景识别...")
        self._process.terminate()
        if not self._process.waitForFinished(1500):
            self._process.kill()

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if not line.strip():
                continue
            self.scenario_log.appendPlainText(line)
            if line.startswith("SCENARIO_RESULT:"):
                self._handle_result(line)

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if line.strip():
                self.scenario_log.appendPlainText(f"提示：{line}")

    def _handle_result(self, line: str) -> None:
        fields = dict(re.findall(r"([a-z_]+)=([^\s]+)", line))
        action = fields.get("action", "INFO_ACTION")
        label = fields.get("label", fields.get("option", "多模态场景指令"))
        option = fields.get("option", "")
        if any(char in label for char in ("�", "□", "\ufffd")):
            label = option or {
                "TAKEOFF": "起飞",
                "RTL": "返航",
                "LAND": "降落",
            }.get(action, "多模态场景指令")
        confidence = float(fields.get("confidence", "0.90"))
        risk = "high" if action in {"TAKEOFF", "RTL", "LAND"} else "medium"
        intent = CommandIntent(
            action=action,
            source="手势+视线",
            label=label,
            confidence=confidence,
            risk_level=risk,
            requires_confirmation=action in {"TAKEOFF", "RTL", "LAND"},
            parameters=fields,
        )
        if fields.get("group") == "TAKEOFF" and action == "TAKEOFF":
            self._pending_takeoff_intent = intent
            self.takeoff_map_requested.emit(intent)
            return
        self.command_proposed.emit(intent)
        self._stop_scenario()

    def confirm_takeoff_map(self, route_sequence: object | None = None) -> None:
        if self._pending_takeoff_intent is None:
            self.scenario_log.appendPlainText("当前没有待确认的起飞地图。")
            return
        intent = self._pending_takeoff_intent
        self._pending_takeoff_intent = None
        route_sequence = route_sequence or []
        self.scenario_log.appendPlainText("已确认起飞地图，准备执行所选起飞项。")
        if isinstance(route_sequence, dict) and route_sequence.get("mode") == "free":
            points = route_sequence.get("points", [])
            intent.parameters["route_mode"] = "free"
            intent.parameters["route_waypoints"] = points
            self.scenario_log.appendPlainText(f"自由标定航点：{len(points)} 个")
        elif route_sequence:
            intent.parameters["route_sequence"] = ",".join(route_sequence)
            intent.parameters["route_waypoints"] = route_sequence
            self.scenario_log.appendPlainText(f"手动规划航线：{''.join(route_sequence)}")
        else:
            self.scenario_log.appendPlainText("未选择巡逻航点，将按默认航线执行。")
        self.command_proposed.emit(intent)
        self._stop_scenario()

    def _process_error(self, _error) -> None:
        self.scenario_log.appendPlainText(
            "场景识别启动失败。请先运行 install_multimodal_deps.bat。"
        )

    def _process_finished(self, exit_code: int, _exit_status) -> None:
        self._process = None
        self.scenario_start.setEnabled(True)
        self.scenario_stop.setEnabled(False)
        message = "场景识别已停止" if exit_code == 0 else "场景识别已退出，请查看日志"
        self.scenario_log.appendPlainText(message)
        self.scenario_stopped.emit()


class InspectionEventCard(QFrame):
    def __init__(self, entry: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.entry_id = str(entry.get("id", ""))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        self.status = QLabel()
        self.status.setAlignment(Qt.AlignCenter)
        header.addWidget(self.title, 1)
        header.addWidget(self.status)
        layout.addLayout(header)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.flight = QLabel()
        self.flight.setObjectName("muted")
        self.flight.setWordWrap(True)
        layout.addWidget(self.flight)

        self.analysis = QLabel()
        self.analysis.setWordWrap(True)
        self.analysis.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.analysis)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumHeight(118)
        self.image.setMaximumHeight(185)
        self.image.setStyleSheet(
            "background:#050b12;border:1px solid #244158;border-radius:6px;"
        )
        layout.addWidget(self.image)
        self.update_entry(entry)

    def update_entry(self, entry: dict) -> None:
        self.entry_id = str(entry.get("id", self.entry_id))
        timestamp = str(entry.get("timestamp", "")).replace("T", " ")
        kind = html.escape(str(entry.get("kind", "巡检事件")))
        trigger = html.escape(str(entry.get("trigger", "自动识别")))
        summary = html.escape(str(entry.get("summary", "暂无结果")))
        self.title.setText(f"{timestamp[11:19]} · {kind}")
        self.summary.setText(
            f"<b>识别：</b>{summary}<br>"
            f"<span style='color:#7892aa'>触发：{trigger}</span>"
        )
        state = entry.get("flight_state", {})
        self.flight.setText(
            f"位置 ({float(state.get('x', 0.0)):.0f}, {float(state.get('y', 0.0)):.0f}) cm · "
            f"高度 {float(state.get('altitude', 0.0)):.2f} m · "
            f"航向 {float(state.get('yaw', 0.0)):.0f}°"
        )
        qwen_status = str(entry.get("qwen_status", "排队中"))
        qwen_text = html.escape(str(entry.get("qwen_analysis", "")).strip())
        elapsed = float(entry.get("qwen_elapsed_s", 0.0))
        if qwen_text:
            elapsed_text = f" · {elapsed:.1f}s" if elapsed > 0 else ""
            self.analysis.setText(
                f"<b>Qwen-VL{elapsed_text}：</b>{qwen_text}"
            )
        else:
            self.analysis.setText("<b>Qwen-VL：</b>等待分析…")
        status_object = (
            "miniChipGood"
            if qwen_status == "分析完成"
            else "miniChipWarn"
            if qwen_status == "分析失败"
            else "miniChipInfo"
        )
        self.status.setText(qwen_status)
        self.status.setObjectName(status_object)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

        screenshot = Path(str(entry.get("screenshot", "")))
        if screenshot.exists():
            pixmap = QPixmap(str(screenshot))
            if not pixmap.isNull():
                self.image.setPixmap(
                    pixmap.scaled(
                        300,
                        170,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self.image.setToolTip(str(screenshot))
                return
        self.image.setText("截图不可用")


class FlightInspectionLogPanel(QWidget):
    retry_qwen_requested = pyqtSignal()
    qwen_toggled = pyqtSignal(bool)

    def __init__(self, log_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_root = log_root
        self._cards: dict[str, InspectionEventCard] = {}
        self._order: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        title = QLabel("飞行巡检记录")
        title.setObjectName("sectionTitle")
        subtitle = QLabel(
            "默认只跑小模型并保留Qwen队列；手动开启Qwen后暂停图传进行分析。"
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        statuses = QHBoxLayout()
        self.vision_status = QLabel("视觉：等待图传")
        self.vision_status.setObjectName("miniChipInfo")
        self.qwen_status = QLabel("Qwen：等待图传")
        self.qwen_status.setObjectName("miniChipInfo")
        statuses.addWidget(self.vision_status)
        statuses.addWidget(self.qwen_status)
        layout.addLayout(statuses)

        buttons = QHBoxLayout()
        self.qwen_toggle = QPushButton("启动 Qwen 推理")
        self.qwen_toggle.setCheckable(True)
        self.qwen_toggle.toggled.connect(self._on_qwen_toggled)
        open_folder = QPushButton("打开日志目录")
        open_folder.clicked.connect(self._open_log_folder)
        clear_display = QPushButton("清空当前显示")
        clear_display.clicked.connect(self.clear_display)
        buttons.addWidget(self.qwen_toggle)
        buttons.addWidget(open_folder)
        buttons.addWidget(clear_display)
        layout.addLayout(buttons)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: #071321; border: none; }")
        container = QWidget()
        container.setStyleSheet("background: #071321;")
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.empty_label = QLabel("等待无人机图传。连接后自动启动巡检识别。")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumHeight(120)
        self.cards_layout.addWidget(self.empty_label)
        self.scroll.setWidget(container)
        layout.addWidget(self.scroll, 1)

        path_label = QLabel(f"本地日志：{log_root}")
        path_label.setObjectName("muted")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

    def load_entries(self, entries: list[dict]) -> None:
        for entry in entries:
            self.add_or_update_entry(entry)

    def add_or_update_entry(self, entry: dict) -> None:
        event_id = str(entry.get("id", ""))
        if not event_id:
            return
        card = self._cards.get(event_id)
        if card is not None:
            card.update_entry(entry)
            return
        self.empty_label.hide()
        card = InspectionEventCard(entry)
        self._cards[event_id] = card
        self._order.append(event_id)
        self.cards_layout.insertWidget(0, card)
        while len(self._order) > 60:
            old_id = self._order.pop(0)
            old_card = self._cards.pop(old_id, None)
            if old_card is not None:
                old_card.deleteLater()

    def set_vision_status(self, status: str, message: str) -> None:
        self._set_status(self.vision_status, "视觉", status, message)

    def set_qwen_status(self, status: str, message: str) -> None:
        self._set_status(self.qwen_status, "Qwen", status, message)

    def set_qwen_enabled(self, enabled: bool) -> None:
        self.qwen_toggle.blockSignals(True)
        self.qwen_toggle.setChecked(enabled)
        self.qwen_toggle.setText(
            "关闭 Qwen 推理" if enabled else "启动 Qwen 推理"
        )
        self.qwen_toggle.setObjectName("warningButton" if enabled else "primaryButton")
        self.qwen_toggle.style().unpolish(self.qwen_toggle)
        self.qwen_toggle.style().polish(self.qwen_toggle)
        self.qwen_toggle.blockSignals(False)

    def clear_display(self) -> None:
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()
        self._order.clear()
        self.empty_label.setText("显示已清空；本地历史日志和截图没有删除。")
        self.empty_label.show()

    def _open_log_folder(self) -> None:
        self.log_root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_root.resolve())))

    def _on_qwen_toggled(self, enabled: bool) -> None:
        self.set_qwen_enabled(enabled)
        self.qwen_toggled.emit(enabled)

    @staticmethod
    def _set_status(label: QLabel, prefix: str, status: str, message: str) -> None:
        short_message = message if len(message) <= 24 else message[:23] + "…"
        label.setText(f"{prefix}：{short_message}")
        label.setToolTip(message)
        object_name = (
            "miniChipGood"
            if status == "ready"
            else "miniChipWarn"
            if status in {"error", "memory"}
            else "miniChipInfo"
        )
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)


class DevicePanel(QWidget):
    connect_camera = pyqtSignal(str)
    connect_telemetry = pyqtSignal(str, int, str, int, str)
    disconnect_telemetry = pyqtSignal()
    lens_correction_changed = pyqtSignal(bool, int)
    LENS_STRENGTH_LEVELS = (35, 50, 65)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        saved_ip, saved_port = load_camera_endpoint()
        self.camera_ip = QLineEdit(saved_ip)
        self.camera_ip.setPlaceholderText("例如 10.51.117.2")
        self.camera_port = QLineEdit(saved_port)
        self.camera_port.setPlaceholderText("例如 554")
        camera_endpoint_row = QHBoxLayout()
        camera_endpoint_row.addWidget(self.camera_ip, 3)
        camera_endpoint_row.addWidget(QLabel(":"))
        camera_endpoint_row.addWidget(self.camera_port, 1)
        self.telemetry_port = QComboBox()
        self.telemetry_port.setEditable(True)
        self.coordinate_port = QComboBox()
        self.coordinate_port.setEditable(True)
        self._refresh_ports()
        self.protocol = QComboBox()
        self.protocol.addItems(["NCLink 只读", "模拟遥测", "自定义串口"])
        self.telemetry_baud = QComboBox()
        self.telemetry_baud.setEditable(True)
        self.telemetry_baud.addItems(["9600", "460800", "2250000", "921600", "115200"])
        self.coordinate_baud = QComboBox()
        self.coordinate_baud.setEditable(True)
        self.coordinate_baud.addItems(["115200", "9600", "460800", "921600"])
        form.addRow("图传 IP:端口", camera_endpoint_row)
        form.addRow("UART4 状态口", self.telemetry_port)
        form.addRow("通信协议", self.protocol)
        form.addRow("UART4 波特率", self.telemetry_baud)
        form.addRow("UART2 坐标口", self.coordinate_port)
        form.addRow("UART2 波特率", self.coordinate_baud)
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
        camera_buttons = QHBoxLayout()
        save_camera_button = QPushButton("保存图传地址")
        save_camera_button.clicked.connect(self._save_camera_endpoint)
        camera_button = QPushButton("测试并连接 AMB82")
        camera_button.setObjectName("primaryButton")
        camera_button.clicked.connect(self._connect_camera)
        camera_buttons.addWidget(save_camera_button)
        camera_buttons.addWidget(camera_button)
        layout.addLayout(camera_buttons)
        self.camera_endpoint_status = QLabel(
            f"当前图传地址：{build_rtsp_url(saved_ip, saved_port)}"
        )
        self.camera_endpoint_status.setObjectName("muted")
        self.camera_endpoint_status.setWordWrap(True)
        layout.addWidget(self.camera_endpoint_status)
        telemetry_buttons = QHBoxLayout()
        telemetry_connect = QPushButton("连接飞控数传")
        telemetry_connect.setObjectName("primaryButton")
        telemetry_connect.clicked.connect(self._connect_telemetry)
        telemetry_disconnect = QPushButton("断开数传")
        telemetry_disconnect.clicked.connect(self.disconnect_telemetry.emit)
        refresh_ports = QPushButton("刷新端口")
        refresh_ports.clicked.connect(self._refresh_ports)
        telemetry_buttons.addWidget(telemetry_connect)
        telemetry_buttons.addWidget(telemetry_disconnect)
        telemetry_buttons.addWidget(refresh_ports)
        layout.addLayout(telemetry_buttons)
        self.telemetry_status = QLabel("数传状态：未连接。先选择 COM 口，再连接飞控数传。")
        self.telemetry_status.setObjectName("muted")
        self.telemetry_status.setWordWrap(True)
        layout.addWidget(self.telemetry_status)
        self.coordinate_status = QLabel("坐标口：未连接。SDK1 建议切到 21 firefighting uav1。")
        self.coordinate_status.setObjectName("muted")
        self.coordinate_status.setWordWrap(True)
        layout.addWidget(self.coordinate_status)
        info = QLabel(
            "图传优先使用 720p/15 帧/秒 H.264 RTSP，并自动兼容旧快照固件。"
            "UART4 读取飞控状态，UART2 读取水平坐标；两路都只读，不向飞控发送指令。"
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        layout.addStretch()

    def _current_camera_url(self) -> str:
        return build_rtsp_url(self.camera_ip.text(), self.camera_port.text())

    def _save_camera_endpoint(self) -> None:
        ip, port = save_camera_endpoint(
            self.camera_ip.text(),
            self.camera_port.text(),
        )
        self.camera_ip.setText(ip)
        self.camera_port.setText(port)
        self.camera_endpoint_status.setText(
            f"已保存图传地址：{build_rtsp_url(ip, port)}"
        )
        self.camera_endpoint_status.setObjectName("chipGood")
        self.camera_endpoint_status.style().unpolish(self.camera_endpoint_status)
        self.camera_endpoint_status.style().polish(self.camera_endpoint_status)

    def _connect_camera(self) -> None:
        self._save_camera_endpoint()
        self.connect_camera.emit(self._current_camera_url())

    def _refresh_ports(self) -> None:
        current = self.telemetry_port.currentText().strip() if hasattr(self, "telemetry_port") else ""
        coordinate_current = (
            self.coordinate_port.currentText().strip()
            if hasattr(self, "coordinate_port")
            else ""
        )
        ports = ["模拟器"]
        try:
            from serial.tools import list_ports

            ports.extend(port.device for port in list_ports.comports())
        except Exception:
            ports.extend(["COM3", "COM8"])
        unique_ports = []
        for port in ports:
            if port and port not in unique_ports:
                unique_ports.append(port)
        self.telemetry_port.blockSignals(True)
        self.telemetry_port.clear()
        self.telemetry_port.addItems(unique_ports)
        if current:
            index = self.telemetry_port.findText(current)
            if index >= 0:
                self.telemetry_port.setCurrentIndex(index)
            else:
                self.telemetry_port.setEditText(current)
        self.telemetry_port.blockSignals(False)
        self.coordinate_port.blockSignals(True)
        self.coordinate_port.clear()
        self.coordinate_port.addItems(unique_ports)
        if coordinate_current:
            index = self.coordinate_port.findText(coordinate_current)
            if index >= 0:
                self.coordinate_port.setCurrentIndex(index)
            else:
                self.coordinate_port.setEditText(coordinate_current)
        else:
            self.coordinate_port.setCurrentIndex(0)
        self.coordinate_port.blockSignals(False)

    def _connect_telemetry(self) -> None:
        port = self.telemetry_port.currentText().strip()
        coordinate_port = self.coordinate_port.currentText().strip()
        protocol = self.protocol.currentText().strip()
        try:
            baudrate = int(self.telemetry_baud.currentText().strip())
        except ValueError:
            baudrate = 9600
            self.telemetry_baud.setEditText(str(baudrate))
        try:
            coordinate_baudrate = int(self.coordinate_baud.currentText().strip())
        except ValueError:
            coordinate_baudrate = 115200
            self.coordinate_baud.setEditText(str(coordinate_baudrate))
        self.connect_telemetry.emit(
            port, baudrate, coordinate_port, coordinate_baudrate, protocol
        )

    def set_telemetry_status(self, connected: bool, message: str) -> None:
        self.telemetry_status.setText(f"数传状态：{message}")
        self.telemetry_status.setObjectName("chipGood" if connected else "chipWarn")
        self.telemetry_status.style().unpolish(self.telemetry_status)
        self.telemetry_status.style().polish(self.telemetry_status)

    def set_coordinate_status(self, connected: bool, message: str) -> None:
        self.coordinate_status.setText(f"坐标口：{message}")
        self.coordinate_status.setObjectName("chipGood" if connected else "chipWarn")
        self.coordinate_status.style().unpolish(self.coordinate_status)
        self.coordinate_status.style().polish(self.coordinate_status)

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
            ("自检", "SELF_CHECK", ""),
            ("暂停 / 悬停", "HOLD", "warningButton"),
            ("返航", "RTL", "warningButton"),
            ("降落", "LAND", "dangerButton"),
            ("关机", "SHUTDOWN", "dangerButton"),
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
                f"图传诊断：{camera.source_kind.upper()} · {camera.fps:.1f} 帧/秒 · "
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

    def set_planning_route(self, sequence: list[str]) -> None:
        self.map_panel.set_planning_route(sequence)

    def set_planning_points(self, points: list[tuple[float, float]]) -> None:
        self.map_panel.set_planning_points(points)

    def start_route_tracking(self, sequence: list[str]) -> None:
        self.map_panel.start_route_tracking(sequence)

    def start_route_tracking_points(self, points: list[tuple[float, float]]) -> None:
        self.map_panel.start_route_tracking_points(points)

    def clear_planning_route(self) -> None:
        self.map_panel.clear_planning_route()

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
        self.metrics = QLabel("高度 0.00 m · 电压 16.4 V · 链路 26 ms")
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
            f"图传 {camera.fps:.0f} 帧/秒" if camera.connected else "图传 离线"
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
            f"高度 {state.altitude:.2f} m · 电压 {state.battery_voltage:.1f} V · "
            f"链路 {state.link_latency_ms} ms"
        )
        for chip in (self.flight, self.camera, self.telemetry):
            chip.style().unpolish(chip)
            chip.style().polish(chip)


class SideNavigation(QFrame):
    navigation_requested = pyqtSignal(str)

    ITEMS = [
        ("mission", "任", "任务"),
        ("status", "态", "状态"),
        ("voice", "语", "语音"),
        ("gesture", "势", "手势"),
        ("gaze", "视", "视线"),
        ("logs", "志", "日志"),
        ("device", "设", "设备"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sideNav")
        self._large_display = False
        self._buttons: list[tuple[QToolButton, str, str]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(5)
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

    def set_display_scale(self, large: bool) -> None:
        if self._large_display == large:
            return
        self._large_display = large
        self._apply_width()

    def _apply_width(self) -> None:
        width = 330 if self._large_display else 148
        self.setFixedWidth(width)
        for button, icon, label in self._buttons:
            button.setText(f"{icon}   {label}")
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
