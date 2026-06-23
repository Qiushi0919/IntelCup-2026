from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from camera_service import CameraThread
from fire_detector import FireDetector
from models import (
    CameraState,
    CommandIntent,
    DetectionEvent,
    DroneState,
    FireDetection,
)
from simulator import DroneSimulator
from styles import APP_STYLE, LARGE_DISPLAY_STYLE
from widgets import (
    CommandBar,
    DevicePanel,
    EventTable,
    GazePanel,
    GesturePanel,
    LogPanel,
    RecentEventsPanel,
    RightSidebar,
    SideNavigation,
    VideoPanel,
    VoicePanel,
)


APP_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = APP_DIR / "captures"


class GroundStationWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("智驭低空枢纽 · 无人机地面站")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)

        self.camera_state = CameraState()
        self.drone_state = DroneState()
        self.camera_thread: CameraThread | None = None
        self.lens_correction_enabled = True
        self.lens_correction_strength = 50
        self._right_sidebar_user_hidden = False
        self._last_responsive_mode = ""
        self._large_display = False

        self.simulator = DroneSimulator(self)
        self.simulator.state_changed.connect(self._on_state_changed)
        self.simulator.event_generated.connect(self._on_event)
        self.simulator.log_generated.connect(self._append_log)

        self._build_menu()
        self._build_central_ui()
        self._build_docks()
        self._build_status_bar()

        self._append_log("INFO", "地面站启动，当前使用模拟无人机数据")
        self._append_log("INFO", "多模态输入处于候选指令模式")
        QTimer.singleShot(0, self._apply_responsive_layout)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        snapshot_action = QAction("保存当前截图", self)
        snapshot_action.triggered.connect(self.save_snapshot)
        file_menu.addAction(snapshot_action)
        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        self.view_menu = self.menuBar().addMenu("窗口")
        help_menu = self.menuBar().addMenu("帮助")
        about = QAction("关于此原型", self)
        about.triggered.connect(
            lambda: QMessageBox.information(
                self,
                "关于",
                "智驭低空枢纽 · 地面站 UI 原型\n\n"
                "中心画面、状态、地图和安全命令常驻；"
                "多模态与完整日志使用可停靠工具窗口。",
            )
        )
        help_menu.addAction(about)

    def _build_central_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 6, 8, 5)
        root_layout.setSpacing(6)

        root_layout.addWidget(self._build_header())

        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.vertical_splitter.setHandleWidth(4)
        root_layout.addWidget(self.vertical_splitter, 1)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(6)

        self.side_nav = SideNavigation()
        self.side_nav.navigation_requested.connect(self._handle_navigation)
        workspace_layout.addWidget(self.side_nav)

        self.horizontal_splitter = QSplitter(Qt.Horizontal)
        self.horizontal_splitter.setChildrenCollapsible(False)
        self.horizontal_splitter.setHandleWidth(4)
        workspace_layout.addWidget(self.horizontal_splitter, 1)

        self.video_panel = VideoPanel()
        self.video_panel.snapshot_requested.connect(self.save_snapshot)
        self.video_panel.connect_camera_requested.connect(
            lambda: self.connect_camera("auto")
        )
        self.video_panel.demo_requested.connect(self._load_fire_demo)
        self.video_panel.target_selected.connect(self._select_target)
        self.video_panel.lens_correction_toggled.connect(
            self._toggle_lens_correction
        )
        self.horizontal_splitter.addWidget(self.video_panel)

        self.right_sidebar = RightSidebar(self.simulator.waypoints)
        self.horizontal_splitter.addWidget(self.right_sidebar)
        self.horizontal_splitter.setStretchFactor(0, 1)
        self.horizontal_splitter.setStretchFactor(1, 0)
        self.horizontal_splitter.setSizes([930, 320])
        self.vertical_splitter.addWidget(workspace)

        self.bottom_panel = QFrame()
        self.bottom_panel.setObjectName("bottomPanel")
        bottom_layout = QVBoxLayout(self.bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(5)
        self.command_bar = CommandBar()
        self.command_bar.command_requested.connect(self._button_command)
        bottom_layout.addWidget(self.command_bar)
        self.recent_events = RecentEventsPanel()
        self.recent_events.open_full_requested.connect(
            lambda: self._show_dock("events")
        )
        self.recent_events.clear_requested.connect(self._clear_alerts)
        bottom_layout.addWidget(self.recent_events)
        self.vertical_splitter.addWidget(self.bottom_panel)
        self.vertical_splitter.setStretchFactor(0, 1)
        self.vertical_splitter.setStretchFactor(1, 0)
        self.vertical_splitter.setSizes([650, 148])

        self.setCentralWidget(root)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 6, 12, 6)
        header_layout.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("智驭低空枢纽")
        title.setObjectName("title")
        self.task_name = QLabel("DK-2500 · 当前任务：G 题覆盖巡逻")
        self.task_name.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(self.task_name)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)

        self.flight_chip = QPushButton("● 飞控 在线")
        self.flight_chip.setObjectName("statusGood")
        self.flight_chip.clicked.connect(lambda: self._toggle_right_sidebar(True))
        self.camera_chip = QPushButton("● 相机 模拟")
        self.camera_chip.setObjectName("statusInfo")
        self.camera_chip.clicked.connect(lambda: self.connect_camera("auto"))
        self.telemetry_chip = QPushButton("● 数传 在线")
        self.telemetry_chip.setObjectName("statusGood")
        self.telemetry_chip.clicked.connect(lambda: self._show_dock("device"))
        self.ai_chip = QPushButton("● AI 就绪")
        self.ai_chip.setObjectName("statusGood")
        self.ai_chip.clicked.connect(lambda: self._show_dock("events"))
        for chip in [
            self.flight_chip,
            self.camera_chip,
            self.telemetry_chip,
            self.ai_chip,
        ]:
            header_layout.addWidget(chip)

        self.layout_mode_button = QPushButton("布局")
        self.layout_mode_button.clicked.connect(self._reset_layout)
        device_button = QPushButton("设备")
        device_button.clicked.connect(lambda: self._show_dock("device"))
        fullscreen_button = QPushButton("全屏")
        fullscreen_button.clicked.connect(self._toggle_fullscreen)
        header_layout.addWidget(self.layout_mode_button)
        header_layout.addWidget(device_button)
        header_layout.addWidget(fullscreen_button)
        return header

    def _build_docks(self) -> None:
        self.docks: dict[str, QDockWidget] = {}

        self.event_table = EventTable()
        self._add_dock(
            "events",
            "完整事件中心",
            self.event_table,
            Qt.BottomDockWidgetArea,
            False,
        )

        self.log_panel = LogPanel()
        self._add_dock(
            "logs", "系统日志 · 开发模式", self.log_panel, Qt.BottomDockWidgetArea, False
        )

        self.voice_panel = VoicePanel()
        self.voice_panel.command_proposed.connect(self._propose_command)
        self._add_dock(
            "voice", "语音交互", self.voice_panel, Qt.LeftDockWidgetArea, False
        )

        self.gesture_panel = GesturePanel()
        self.gesture_panel.command_proposed.connect(self._propose_command)
        self._add_dock(
            "gesture", "手势交互", self.gesture_panel, Qt.LeftDockWidgetArea, False
        )

        self.gaze_panel = GazePanel()
        self.gaze_panel.command_proposed.connect(self._propose_command)
        self._add_dock(
            "gaze", "视线交互", self.gaze_panel, Qt.LeftDockWidgetArea, False
        )

        self.device_panel = DevicePanel()
        self.device_panel.connect_camera.connect(self.connect_camera)
        self.device_panel.lens_correction_changed.connect(
            self._set_lens_correction
        )
        self._add_dock(
            "device",
            "设备、串口与网络",
            self.device_panel,
            Qt.RightDockWidgetArea,
            False,
        )

        self.tabifyDockWidget(self.docks["voice"], self.docks["gesture"])
        self.tabifyDockWidget(self.docks["gesture"], self.docks["gaze"])
        self.tabifyDockWidget(self.docks["events"], self.docks["logs"])

    def _add_dock(
        self,
        name: str,
        title: str,
        widget: QWidget,
        area: Qt.DockWidgetArea,
        visible: bool,
    ) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"{name}Dock")
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        dock.setVisible(visible)
        self.docks[name] = dock
        self.view_menu.addAction(dock.toggleViewAction())

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.status_message = QLabel("模拟器运行中 · 等待任务")
        bar.addWidget(self.status_message, 1)
        self.clock = QLabel()
        bar.addPermanentWidget(self.clock)
        timer = QTimer(self)
        timer.timeout.connect(self._update_clock)
        timer.start(1000)
        self._clock_timer = timer
        self._update_clock()

    def _handle_navigation(self, name: str) -> None:
        if name == "mission":
            self._toggle_right_sidebar(True)
            return
        if name == "status":
            self._toggle_right_sidebar()
            return
        self._show_dock(name)

    def _show_dock(self, name: str) -> None:
        dock = self.docks.get(name)
        if not dock:
            return
        dock.setVisible(True)
        dock.raise_()
        area = self.dockWidgetArea(dock)
        if area in {Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea}:
            self.resizeDocks([dock], [650 if self._large_display else 310], Qt.Horizontal)
        elif area in {Qt.TopDockWidgetArea, Qt.BottomDockWidgetArea}:
            self.resizeDocks([dock], [390 if self._large_display else 190], Qt.Vertical)

    def _toggle_right_sidebar(self, force_show: bool = False) -> None:
        if force_show:
            visible = True
        else:
            visible = not self.right_sidebar.isVisible()
        self._right_sidebar_user_hidden = not visible
        self.right_sidebar.setVisible(visible)
        if visible:
            sidebar_width = 680 if self._large_display else min(
                340, max(285, self.width() // 4)
            )
            self.horizontal_splitter.setSizes(
                [max(650, self.width() - sidebar_width - 90), sidebar_width]
            )

    def _on_state_changed(self, state: DroneState) -> None:
        self.drone_state = state
        self.video_panel.set_state(state)
        self.right_sidebar.set_state(state, self.camera_state)
        self.recent_events.update_task_summary(state)
        self.status_message.setText(
            f"{state.flight_phase}  ·  坐标 ({state.x:.1f}, {state.y:.1f})  ·  "
            f"高度 {state.altitude:.2f} m  ·  电量 {state.battery_percent:.0f}%"
        )

    def _on_event(self, event: DetectionEvent) -> None:
        self.event_table.add_event(event)
        self.recent_events.add_detection(event)

    def _button_command(self, action: str, label: str) -> None:
        risk = (
            "high"
            if action in {"TAKEOFF", "START_MISSION", "RTL", "LAND"}
            else "medium"
        )
        self._propose_command(
            CommandIntent(
                action=action,
                source="主界面按钮",
                label=label,
                risk_level=risk,
                requires_confirmation=risk == "high",
            )
        )

    def _propose_command(self, intent: CommandIntent) -> None:
        if intent.confidence < 0.75:
            self._append_log(
                "WARNING",
                f"{intent.source}候选指令置信度过低，已拒绝：{intent.label}",
            )
            return

        if intent.action == "SNAPSHOT":
            self.save_snapshot()
            return

        if intent.action == "SELECT_TARGET":
            self._append_log(
                "COMMAND",
                f"{intent.source}选择候选目标 "
                f"{intent.parameters.get('target_id', '')}",
            )
            self.recent_events.add_system_event(
                "候选目标",
                f"{intent.parameters.get('target_id', '')} · 等待确认",
                "info",
            )
            return

        if intent.action in {"CANCEL_SELECTION", "CONFIRM_CANDIDATE"}:
            self._append_log("COMMAND", f"{intent.source}：{intent.label}")
            return

        if intent.requires_confirmation:
            message = (
                f"指令来源：{intent.source}\n"
                f"候选动作：{intent.label}\n"
                f"置信度：{intent.confidence:.0%}\n"
                f"当前状态：{self.drone_state.flight_phase}\n\n"
                "确认执行此高风险操作吗？"
            )
            answer = QMessageBox.question(
                self,
                "安全确认",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._append_log(
                    "WARNING", f"用户取消 {intent.source} 指令：{intent.label}"
                )
                return

        ok, message = self.simulator.apply_command(intent.action)
        level = "COMMAND" if ok else "WARNING"
        self._append_log(level, f"{intent.source} → {intent.label}：{message}")
        if ok:
            self.recent_events.add_system_event(intent.label, message, "good")
        else:
            QMessageBox.warning(self, "命令未执行", message)

    def _select_target(self, target_id: str) -> None:
        self._propose_command(
            CommandIntent(
                action="SELECT_TARGET",
                source="视频画面",
                label=f"选择目标 {target_id}",
                parameters={"target_id": target_id},
            )
        )

    def connect_camera(self, url: str = "auto") -> None:
        if self.camera_thread and self.camera_thread.isRunning():
            message = (
                "AMB82 已连接，无需重复连接"
                if self.camera_state.connected
                else "AMB82 正在连接，请稍候"
            )
            self._append_log("WARNING", message)
            self.statusBar().showMessage(message, 4000)
            return
        self.camera_chip.setText("● 相机 连接中")
        self.camera_chip.setObjectName("statusWarn")
        self._refresh_style(self.camera_chip)
        self._append_log("INFO", f"正在连接 AMB82-Mini：{url}")
        self.recent_events.add_system_event("相机连接", "正在搜索 AMB82", "info")
        self.camera_thread = CameraThread(
            url,
            self,
            self.lens_correction_enabled,
            self.lens_correction_strength,
        )
        self.camera_thread.frame_ready.connect(self._on_camera_frame)
        self.camera_thread.fire_confirmed.connect(self._on_fire_confirmed)
        self.camera_thread.status_changed.connect(self._on_camera_status)
        self.camera_thread.start()

    def _toggle_lens_correction(self, enabled: bool) -> None:
        self._set_lens_correction(enabled, self.lens_correction_strength)

    def _set_lens_correction(self, enabled: bool, strength: int) -> None:
        self.lens_correction_enabled = enabled
        self.lens_correction_strength = max(0, min(65, int(strength)))
        self.video_panel.set_lens_correction(enabled)
        self.device_panel.set_lens_correction(
            enabled,
            self.lens_correction_strength,
        )
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.set_lens_correction(
                enabled,
                self.lens_correction_strength,
            )
        state = (
            f"已启用，强度 {self.lens_correction_strength}%"
            if enabled
            else "已关闭，显示原始镜头画面"
        )
        self.statusBar().showMessage(f"镜头去畸变{state}", 4000)

    def _load_fire_demo(self) -> None:
        source_path = APP_DIR / "examples" / "fire_test_scene.png"
        frame = cv2.imread(str(source_path))
        if frame is None:
            QMessageBox.warning(
                self,
                "示例不可用",
                f"未能读取火源测试图：\n{source_path}",
            )
            return

        detections = FireDetector().detect(frame)
        self.video_panel.canvas.set_frame(frame)
        self.video_panel.canvas.set_detections(detections)
        self.video_panel.show_demo_mode(len(detections))
        if detections:
            detection = detections[0]
            self.recent_events.add_system_event(
                "火源识别示例",
                f"检测成功 · 置信度 {detection.confidence:.0%}",
                "fire",
            )
            self.recent_events.flash_fire_alert()
            self.statusBar().showMessage(
                f"示例检测成功：火源置信度 {detection.confidence:.0%}", 6000
            )
        else:
            self.recent_events.add_system_event(
                "火源识别示例", "未发现候选目标", "info"
            )

    def _on_camera_frame(
        self, frame, detections: list[FireDetection]
    ) -> None:
        self.video_panel.canvas.set_frame(frame)
        self.video_panel.canvas.set_detections(detections)
        height, width = frame.shape[:2]
        self.camera_state.resolution = f"{width} × {height}"

    def _on_fire_confirmed(self, detection: FireDetection) -> None:
        self.video_panel.canvas.confirm_detection(detection)
        event = DetectionEvent(
            target_type="火源",
            confidence=detection.confidence,
            x=self.drone_state.x,
            y=self.drone_state.y,
            altitude=self.drone_state.altitude,
            source="AMB82 火源识别",
            bbox=detection.bbox,
        )
        self._on_event(event)
        self._append_log(
            "WARNING",
            "火源识别已连续帧确认："
            f"{detection.confidence:.0%}，像素中心 "
            f"({detection.center_x}, {detection.center_y})",
        )
        self.statusBar().showMessage(
            f"发现火源：置信度 {detection.confidence:.0%}", 8000
        )

    def _on_camera_status(self, connected: bool, message: str, fps: float) -> None:
        was_connected = self.camera_state.connected
        self.camera_state.connected = connected
        self.camera_state.source = message if connected else "模拟画面"
        self.camera_state.fps = fps if connected else 20.0
        self.video_panel.set_camera_state(self.camera_state)
        self.right_sidebar.health_panel.set_state(self.drone_state, self.camera_state)
        if connected:
            self.camera_chip.setText(f"● 火源识别 {fps:.1f} FPS")
            self.camera_chip.setObjectName("statusGood")
            if not was_connected:
                self.recent_events.add_system_event(
                    "相机在线", f"{fps:.1f} FPS · {message}", "good"
                )
        else:
            self.camera_chip.setText("● 相机 模拟")
            self.camera_chip.setObjectName("statusInfo")
        self._refresh_style(self.camera_chip)

    def save_snapshot(self) -> None:
        CAPTURE_DIR.mkdir(exist_ok=True)
        filename = CAPTURE_DIR / (
            "ground_station_"
            + self.drone_state.last_update.strftime("%Y%m%d_%H%M%S")
            + ".png"
        )
        self.video_panel.canvas.grab().save(str(filename))
        self._append_log("INFO", f"截图已保存：{filename.name}")
        self.recent_events.add_system_event("截图已保存", filename.name, "info")
        self.statusBar().showMessage(f"截图已保存：{filename}", 5000)

    def _clear_alerts(self) -> None:
        self.recent_events.clear_alerts()
        self._append_log("INFO", "用户清除了当前告警摘要")

    def _append_log(self, level: str, message: str) -> None:
        self.log_panel.append_log(level, message)
        if level in {"WARNING", "ERROR"} and hasattr(self, "recent_events"):
            self.recent_events.add_system_event(
                "系统警告" if level == "WARNING" else "系统错误",
                message,
                "warn" if level == "WARNING" else "error",
            )

    def _update_clock(self) -> None:
        from datetime import datetime

        self.clock.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        QTimer.singleShot(80, self._apply_responsive_layout)

    def _reset_layout(self) -> None:
        self.side_nav.collapse()
        self._right_sidebar_user_hidden = False
        self.right_sidebar.setVisible(True)
        self.horizontal_splitter.setSizes(
            [1100, 680] if self._large_display else [930, 320]
        )
        self.recent_events.setVisible(True)
        self.vertical_splitter.setSizes(
            [720, 300] if self._large_display else [650, 148]
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        width = self.centralWidget().width() if self.centralWidget() else self.width()
        height = self.centralWidget().height() if self.centralWidget() else self.height()
        large_display = width >= 1800 and height >= 950
        if self.isFullScreen() and width >= 1600 and height >= 850:
            large_display = True
        self._apply_display_scale(large_display)

        if width < 1200:
            mode = "narrow"
            self.side_nav.collapse()
            if not self._right_sidebar_user_hidden:
                self.right_sidebar.setVisible(False)
        elif width < 1550:
            mode = "medium"
            if not self._right_sidebar_user_hidden:
                self.right_sidebar.setVisible(True)
                self.right_sidebar.setMaximumWidth(330)
                self.horizontal_splitter.setSizes([max(700, width - 400), 300])
        else:
            mode = "wide"
            if not self._right_sidebar_user_hidden:
                self.right_sidebar.setVisible(True)
                sidebar_width = 680 if large_display else 340
                self.right_sidebar.setMaximumWidth(760 if large_display else 370)
                self.horizontal_splitter.setSizes(
                    [max(850, width - sidebar_width - 100), sidebar_width]
                )

        compact_height = height < (1500 if large_display else 930)
        self.right_sidebar.set_compact(compact_height)
        if height < 710:
            self.recent_events.setVisible(False)
            self.vertical_splitter.setSizes([height - 58, 58])
        else:
            self.recent_events.setVisible(True)
            if large_display:
                bottom_height = 260 if compact_height else 310
            else:
                bottom_height = 125 if compact_height else 148
            self.vertical_splitter.setSizes([max(430, height - bottom_height), bottom_height])

        if mode != self._last_responsive_mode:
            self._last_responsive_mode = mode
            self.layout_mode_button.setText(
                {"wide": "宽屏", "medium": "标准", "narrow": "紧凑"}[mode]
            )

    def _apply_display_scale(self, large: bool) -> None:
        if self._large_display == large:
            return
        self._large_display = large
        app = QApplication.instance()
        if app:
            app.setStyleSheet(APP_STYLE + (LARGE_DISPLAY_STYLE if large else ""))
        self.side_nav.set_display_scale(large)
        self.video_panel.canvas.set_display_scale(large)
        self.right_sidebar.set_display_scale(large)
        self.horizontal_splitter.setHandleWidth(6 if large else 4)
        self.vertical_splitter.setHandleWidth(6 if large else 4)

    @staticmethod
    def _refresh_style(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def closeEvent(self, event) -> None:
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
        event.accept()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IntelCup ground station UI prototype")
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Render the UI and save one screenshot, then exit.",
    )
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("智驭低空枢纽")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = GroundStationWindow()
    window.resize(args.width, args.height)
    window.show()

    if args.screenshot:
        output = args.screenshot.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        def capture() -> None:
            window.grab().save(str(output))
            app.quit()

        QTimer.singleShot(1600, capture)

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
