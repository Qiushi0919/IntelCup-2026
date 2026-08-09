from __future__ import annotations

import argparse
import math
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
from face_recognition_service import FaceRecognitionThread
from ocr_recognition_service import OCRRecognitionThread
from k230_color_detector import (
    K230RedBlobDetector,
    RedBlobConfirmationTracker,
    create_red_blob_demo_frame,
)
from flight_log_recorder import FlightLogRecorder
try:
    from drone_3d import Drone3DView
except Exception as exc:  # pragma: no cover - depends on local OpenGL packages
    Drone3DView = None
    DRONE_3D_IMPORT_ERROR = exc
else:
    DRONE_3D_IMPORT_ERROR = None

try:
    from flight_control import FlightControlPanel
except Exception as exc:  # pragma: no cover - defensive fallback for local installs
    FlightControlPanel = None
    FLIGHT_CONTROL_IMPORT_ERROR = exc
else:
    FLIGHT_CONTROL_IMPORT_ERROR = None

from models import (
    bbox_inside_center_roi,
    CameraState,
    CommandIntent,
    DetectionEvent,
    DroneState,
    FaceMatch,
    fire_detection_inside_center_roi,
    FireDetection,
    OCRMatch,
    SelectionState,
)
from simulator import DroneSimulator
from styles import APP_STYLE, LARGE_DISPLAY_STYLE
from telemetry_service import (
    FORCE_SDK_MODE18_FRAME,
    SAFETY_HOLD_FRAME,
    SAFETY_LAND_FRAME,
    SAFETY_RTL_FRAME,
    SAFETY_SHUTDOWN_FRAME,
    CoordinateThread,
    FiretruckFrame,
    TelemetryThread,
    build_waypoint_clear_frame,
    build_waypoint_write_frame,
)
from widgets import (
    CommandBar,
    CompactStatusBar,
    DevicePanel,
    GazePanel,
    GesturePanel,
    LogPanel,
    MultimodalPanel,
    RightSidebar,
    SideNavigation,
    VideoPanel,
    VisionRecognitionPanel,
    VoicePanel,
    suggested_amb82_url,
)


APP_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = APP_DIR / "captures"
TAKEOFF_ROUTE_WAYPOINTS_CM = {
    "1": (60, 115, 120),
    "2": (215, 115, 120),
    "3": (370, 85, 120),
    "4": (370, 265, 120),
    "5": (230, 265, 120),
    "6": (75, 265, 120),
}
TAKEOFF_FRAME_REPEAT_COUNT = 10
TAKEOFF_FRAME_REPEAT_INTERVAL_MS = 60
TAKEOFF_CLEAR_FRAME_REPEAT_COUNT = 2
TAKEOFF_CLEAR_FRAME_REPEAT_INTERVAL_MS = 2500
TAKEOFF_CLEAR_TO_WAYPOINT_DELAY_MS = 7500
TAKEOFF_WAYPOINT_STEP_DELAY_MS = 1000
OCR_MAP_CANDIDATES = {
    "图书馆": "图",
    "汉堡王": "汉",
    "教学楼": "教",
    "必胜客": "必",
    "食堂": "食",
}
OCR_MAP_MIN_CONFIDENCE = 0.50
SAFETY_UART4_COMMANDS = {
    "HOLD": ("暂停 / 悬停", SAFETY_HOLD_FRAME),
    "RTL": ("返航", SAFETY_RTL_FRAME),
    "LAND": ("降落", SAFETY_LAND_FRAME),
    "SHUTDOWN": ("关机", SAFETY_SHUTDOWN_FRAME),
}


class SimulationControlWindow(QWidget):
    def __init__(self, command_handler, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Window)
        self._closing = False
        self._panel = None
        self.setWindowTitle("仿真飞行控制台")
        self.resize(360, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("仿真飞行控制台")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("这些按钮只驱动本地 3D 仿真，不会发送真实无人机串口指令。")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        if FlightControlPanel is None:
            message = QLabel(
                "参考版本飞控指令面板未能加载："
                f"{FLIGHT_CONTROL_IMPORT_ERROR or '未知错误'}"
            )
            message.setWordWrap(True)
            message.setObjectName("selfCheckText")
            layout.addWidget(message, 1)
            return

        self._panel = FlightControlPanel()
        self._panel.command_sent.connect(command_handler)
        layout.addWidget(self._panel, 1)

    def set_result(self, ok: bool, message: str) -> None:
        if self._panel is not None and hasattr(self._panel, "log"):
            prefix = "成功" if ok else "失败"
            self._panel.log.setText(f"{prefix}：{message}")

    def close_for_shutdown(self) -> None:
        self._closing = True
        self.close()

    def closeEvent(self, event) -> None:
        if self._closing:
            event.accept()
            return
        self.hide()
        event.ignore()


class GroundStationWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("智驭低空枢纽 · 无人机地面站")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)

        self.camera_state = CameraState()
        self.drone_state = DroneState()
        self.camera_thread: CameraThread | None = None
        self.face_recognition_thread: FaceRecognitionThread | None = None
        self.ocr_recognition_thread: OCRRecognitionThread | None = None
        self.telemetry_thread: TelemetryThread | None = None
        self.coordinate_thread: CoordinateThread | None = None
        self.lens_correction_enabled = True
        self.lens_correction_strength = 50
        self.fire_detection_enabled = False
        self.face_recognition_enabled = False
        self.ocr_recognition_enabled = False
        self._right_sidebar_user_hidden = False
        self._last_responsive_mode = ""
        self._large_display = False
        self._camera_connecting = False
        self._real_telemetry_active = False
        self._last_telemetry_status = ""
        self._coordinate_active = False
        self._last_coordinate_status = ""
        self._self_check_active = False
        self._self_check_label = "系统自检"
        self.selection_state: SelectionState | None = None
        self._main_view_mode = "flight"
        self._multimodal_preview_path: Path | None = None
        self._multimodal_preview_mtime = 0.0
        self._multimodal_waiting_map_confirm = False
        self._takeoff_countdown_timer = QTimer(self)
        self._takeoff_countdown_timer.setInterval(1000)
        self._takeoff_countdown_timer.timeout.connect(self._tick_takeoff_countdown)
        self._takeoff_countdown_value = 0
        self._return_countdown_timer = QTimer(self)
        self._return_countdown_timer.setInterval(1000)
        self._return_countdown_timer.timeout.connect(self._tick_return_countdown)
        self._return_countdown_value = 0
        self._pending_takeoff_route: list[str] = []
        self._pending_takeoff_label = ""
        self._pending_takeoff_task = ""
        self._takeoff_sequence_active = False
        self._fire_mapping_task_active = False
        self._fire_location_marked = False
        self._face_mapping_task_active = False
        self._face_locations_marked: set[str] = set()
        self._ocr_mapping_task_active = False
        self._ocr_locations_marked: set[str] = set()
        self.drone_3d_view = None
        self.simulation_control_window: SimulationControlWindow | None = None
        self.flight_log_recorder = FlightLogRecorder(APP_DIR / "flight_logs")

        self.simulator = DroneSimulator(self)
        self.simulator.state_changed.connect(self._on_state_changed)
        self.simulator.event_generated.connect(self._on_event)
        self.simulator.log_generated.connect(self._append_log)

        self._build_menu()
        self._build_central_ui()
        self._build_docks()
        self._build_simulation_feature()
        self._build_status_bar()
        self._build_multimodal_preview_timer()

        self._append_log("INFO", "地面站启动，当前使用模拟无人机数据")
        self._append_log("INFO", "多模态输入处于候选指令模式")
        QTimer.singleShot(120, self._show_default_docks)
        QTimer.singleShot(0, self._apply_responsive_layout)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        snapshot_action = QAction("保存当前截图", self)
        snapshot_action.setShortcut("Ctrl+S")
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

        shortcuts = [
            ("连接相机", "C", lambda: self.connect_camera(suggested_amb82_url())),
            ("全屏", "F", self._toggle_fullscreen),
            ("全屏 F11", "F11", self._toggle_fullscreen),
            (
                "暂停并悬停",
                "Space",
                lambda: self._button_command("HOLD", "暂停 / 悬停"),
            ),
            (
                "取消候选",
                "Escape",
                lambda: self._button_command(
                    "CANCEL_SELECTION", "取消目标选择"
                ),
            ),
            ("状态与地图", "M", lambda: self._toggle_right_sidebar(True)),
        ]
        for text, shortcut, callback in shortcuts:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.setShortcutContext(Qt.ApplicationShortcut)
            action.triggered.connect(callback)
            self.addAction(action)

    def _build_central_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 6, 8, 5)
        root_layout.setSpacing(6)

        root_layout.addWidget(self._build_header())
        self.compact_status = CompactStatusBar()
        self.compact_status.details_requested.connect(
            lambda: self._toggle_right_sidebar(True)
        )
        self.compact_status.setVisible(False)
        root_layout.addWidget(self.compact_status)

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
            lambda: self.connect_camera(suggested_amb82_url())
        )
        self.video_panel.demo_requested.connect(self._load_fire_demo)
        self.video_panel.target_selected.connect(self._select_target)
        self.video_panel.target_missed.connect(
            lambda message: self.statusBar().showMessage(message, 3500)
        )
        self.video_panel.takeoff_map_confirmed.connect(
            self._confirm_multimodal_takeoff_map
        )
        self.video_panel.route_sequence_changed.connect(
            self._update_multimodal_route_preview
        )
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
        self.vertical_splitter.addWidget(self.bottom_panel)
        self.vertical_splitter.setStretchFactor(0, 1)
        self.vertical_splitter.setStretchFactor(1, 0)
        self.vertical_splitter.setSizes([650, 70])

        self.setCentralWidget(root)

    def _build_simulation_feature(self) -> None:
        self.simulation_control_window = SimulationControlWindow(
            self._on_simulation_command,
            self,
        )
        if Drone3DView is None:
            self.video_panel.set_simulation_widget(None)
            self._append_log(
                "WARNING",
                f"3D 仿真组件未加载：{DRONE_3D_IMPORT_ERROR}",
            )
            return
        try:
            self.drone_3d_view = Drone3DView()
            self.drone_3d_view.set_waypoints(
                [self._simulation_xy_to_3d(x, y) for x, y in self.simulator.waypoints]
            )
            self.drone_3d_view.stop()
            self.video_panel.set_simulation_widget(self.drone_3d_view)
            self._update_drone_3d_view(self.simulator.state)
        except Exception as exc:
            self.drone_3d_view = None
            self.video_panel.set_simulation_widget(None)
            self._append_log("WARNING", f"3D 仿真初始化失败：{exc}")

    def _simulation_xy_to_3d(self, x_cm: float, y_cm: float) -> tuple[float, float]:
        return x_cm / 10.0 - 24.0, y_cm / 10.0 - 20.0

    def _update_drone_3d_view(self, state: DroneState) -> None:
        if self.drone_3d_view is None:
            return
        x, y = self._simulation_xy_to_3d(state.x, state.y)
        self.drone_3d_view.set_drone_state(
            x=x,
            y=y,
            z=max(0.0, state.altitude * 8.0),
            roll=math.radians(state.roll),
            pitch=math.radians(state.pitch),
            yaw=math.radians(state.yaw),
        )

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

        self.flight_chip = QLabel("● 飞控 在线")
        self.flight_chip.setObjectName("chipGood")
        self.camera_chip = QLabel("● 相机 离线")
        self.camera_chip.setObjectName("chipInfo")
        self.telemetry_chip = QLabel("● 数传 在线")
        self.telemetry_chip.setObjectName("chipGood")
        self.ai_chip = QLabel("● AI 就绪")
        self.ai_chip.setObjectName("chipGood")
        for chip in [
            self.flight_chip,
            self.camera_chip,
            self.telemetry_chip,
            self.ai_chip,
        ]:
            header_layout.addWidget(chip)

        self.layout_mode_button = QPushButton("布局")
        self.layout_mode_button.clicked.connect(self._reset_layout)
        self.connect_camera_button = QPushButton("连接相机")
        self.connect_camera_button.clicked.connect(
            lambda: self.connect_camera(suggested_amb82_url())
        )
        device_button = QPushButton("设备")
        device_button.clicked.connect(lambda: self._show_dock("device"))
        fullscreen_button = QPushButton("全屏")
        fullscreen_button.clicked.connect(self._toggle_fullscreen)
        header_layout.addWidget(self.layout_mode_button)
        header_layout.addWidget(self.connect_camera_button)
        header_layout.addWidget(device_button)
        header_layout.addWidget(fullscreen_button)
        return header

    def _build_docks(self) -> None:
        self.docks: dict[str, QDockWidget] = {}
        self._default_visible_docks: set[str] = set()

        self.log_panel = LogPanel()
        self._add_dock(
            "logs", "系统日志 · 开发模式", self.log_panel, Qt.BottomDockWidgetArea, True
        )

        self.voice_panel = VoicePanel()
        self.voice_panel.command_proposed.connect(self._propose_command)
        self.gesture_panel = GesturePanel()
        self.gesture_panel.command_proposed.connect(self._propose_command)
        self.gaze_panel = GazePanel()
        self.gaze_panel.command_proposed.connect(self._propose_command)
        self.multimodal_panel = MultimodalPanel(
            self.voice_panel,
            self.gesture_panel,
            self.gaze_panel,
        )
        self.multimodal_panel.command_proposed.connect(self._propose_command)
        self.multimodal_panel.scenario_started.connect(
            self._enter_multimodal_view
        )
        self.multimodal_panel.scenario_stopped.connect(
            self._exit_multimodal_view
        )
        self.multimodal_panel.takeoff_map_requested.connect(
            self._show_multimodal_takeoff_map
        )
        self._add_dock(
            "multimodal",
            "多模态交互",
            self.multimodal_panel,
            Qt.LeftDockWidgetArea,
            True,
        )

        self.device_panel = DevicePanel()
        self.device_panel.connect_camera.connect(self.connect_camera)
        self.device_panel.connect_telemetry.connect(self.connect_telemetry)
        self.device_panel.disconnect_telemetry.connect(self.disconnect_telemetry)
        self.device_panel.lens_correction_changed.connect(
            self._set_lens_correction
        )
        self._add_dock(
            "device",
            "设备、串口与网络",
            self.device_panel,
            Qt.RightDockWidgetArea,
            True,
        )

        self.vision_recognition_panel = VisionRecognitionPanel()
        self.vision_recognition_panel.fire_detection_toggled.connect(
            self._toggle_fire_detection
        )
        self.vision_recognition_panel.face_recognition_toggled.connect(
            self._toggle_face_recognition
        )
        self.vision_recognition_panel.ocr_recognition_toggled.connect(
            self._toggle_ocr_recognition
        )
        self._add_dock(
            "visionRecognition",
            "视觉识别",
            self.vision_recognition_panel,
            Qt.RightDockWidgetArea,
            True,
        )
        self.splitDockWidget(
            self.docks["device"],
            self.docks["visionRecognition"],
            Qt.Vertical,
        )

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
        dock.setVisible(False)
        if visible:
            self._default_visible_docks.add(name)
        self.docks[name] = dock
        self.view_menu.addAction(dock.toggleViewAction())

    def _show_default_docks(self) -> None:
        for name in self._default_visible_docks:
            dock = self.docks.get(name)
            if dock:
                dock.setVisible(True)
        for name in ("multimodal", "logs", "device", "visionRecognition"):
            dock = self.docks.get(name)
            if dock:
                dock.raise_()
        device_dock = self.docks.get("device")
        recognition_dock = self.docks.get("visionRecognition")
        if device_dock and recognition_dock:
            self.resizeDocks(
                [device_dock, recognition_dock],
                [720, 160],
                Qt.Vertical,
            )

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

    def _build_multimodal_preview_timer(self) -> None:
        self._multimodal_timer = QTimer(self)
        self._multimodal_timer.setInterval(120)
        self._multimodal_timer.timeout.connect(self._refresh_multimodal_preview)

    def _handle_navigation(self, name: str) -> None:
        if name == "mission":
            self._toggle_right_sidebar(True)
            return
        if name == "status":
            self._toggle_right_sidebar()
            return
        if name in {"voice", "gesture", "gaze"}:
            self._show_multimodal(name)
            return
        self._show_dock(name)

    def _show_multimodal(self, name: str) -> None:
        dock = self.docks.get("multimodal")
        if not dock:
            return
        dock.setVisible(True)
        dock.raise_()
        self.multimodal_panel.show_section(name)

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
        if self._real_telemetry_active and self.sender() is self.simulator:
            if self._main_view_mode == "simulation":
                self._update_drone_3d_view(state)
            return
        self.drone_state = state
        self.video_panel.set_state(state)
        if self.sender() is self.simulator or not self._real_telemetry_active:
            self._update_drone_3d_view(state)
        if self._self_check_active:
            self._refresh_self_check_view()
        self.right_sidebar.set_state(state, self.camera_state)
        self._observe_flight_log_state(state)
        self.compact_status.set_state(state, self.camera_state)
        self._update_header_status()
        self.status_message.setText(
            f"{state.flight_phase}  ·  坐标 ({state.x:.0f}, {state.y:.0f}) cm  ·  "
            f"高度 {state.altitude:.2f} m  ·  电压 {state.battery_voltage:.1f} V"
        )

    def _update_header_status(self) -> None:
        statuses = [
            (
                self.flight_chip,
                "● 飞控 在线"
                if self.drone_state.connected
                else "● 飞控 离线",
                "chipGood" if self.drone_state.connected else "chipWarn",
            ),
            (
                self.telemetry_chip,
                "● 数传 在线"
                if self.drone_state.telemetry_connected
                else "● 数传 离线",
                "chipGood"
                if self.drone_state.telemetry_connected
                else "chipWarn",
            ),
            (
                self.ai_chip,
                "● AI 就绪"
                if self.drone_state.ai_ready
                else "● AI 离线",
                "chipGood" if self.drone_state.ai_ready else "chipWarn",
            ),
        ]
        if self.camera_state.connected:
            camera_text = f"● 图传 {self.camera_state.fps:.1f} FPS"
            camera_style = "chipGood"
        elif self._camera_connecting:
            camera_text = "● 图传 重连中"
            camera_style = "chipWarn"
        else:
            camera_text = "● 图传 离线"
            camera_style = (
                "chipWarn" if self.camera_state.last_error else "chipInfo"
            )
        statuses.append((self.camera_chip, camera_text, camera_style))
        for chip, text, object_name in statuses:
            chip.setText(text)
            chip.setObjectName(object_name)
            self._refresh_style(chip)

    def _on_event(self, event: DetectionEvent) -> None:
        self._append_log(
            "WARNING",
            f"发现{event.target_type}，置信度 {event.confidence:.0%}，来源 {event.source}",
        )

    def _button_command(self, action: str, label: str) -> None:
        if action == "SELF_CHECK":
            self._show_self_check_view(label, "主界面按钮")
            return
        if action in SAFETY_UART4_COMMANDS:
            self._send_immediate_safety_command(action, label)
            return
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

    def _send_immediate_safety_command(self, action: str, label: str) -> None:
        command_name, frame = SAFETY_UART4_COMMANDS[action]
        if action == "RTL" and self._return_countdown_timer.isActive():
            self._return_countdown_timer.stop()
            self._return_countdown_value = 0
        if self.telemetry_thread is None or not self.telemetry_thread.isRunning():
            message = f"UART4 未连接，{command_name}保护指令没有发送。"
            self._append_log("ERROR", message)
            QMessageBox.warning(self, "UART4 未连接", message)
            return
        self.telemetry_thread.send_bytes(frame)
        self._append_log(
            "COMMAND",
            f"安全指令中心：已立即发送{command_name}指令 {frame.hex(' ').upper()}",
        )
        self.statusBar().showMessage(f"{command_name}保护指令已发送", 5000)

        ok, message = self.simulator.apply_command(action)
        level = "COMMAND" if ok else "INFO"
        self._append_log(level, f"主界面按钮 → {label}：{message}")
        self._leave_self_check_view()
        self._exit_multimodal_view(label)

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

        if intent.action == "INFO_ACTION":
            message = f"{intent.source}选择：{intent.label}"
            self._append_log("COMMAND", message)
            self.statusBar().showMessage(message, 4500)
            if intent.label == "10秒后返航":
                self._start_return_countdown()
                return
            if intent.label == "日志输出":
                self._export_latest_flight_log()
                return
            if intent.label == "仿真飞行":
                self._show_simulation_flight(intent.source)
                return
            if self._is_self_check_label(intent.label):
                self._show_self_check_view(intent.label, intent.source)
                return
            self._exit_multimodal_view(intent.label)
            return

        if (
            intent.action == "RTL"
            and intent.source == "手势+视线"
            and intent.label == "立即返航"
        ):
            self._send_immediate_safety_command("RTL", intent.label)
            return

        if intent.action == "SELECT_TARGET":
            target_id = intent.parameters.get("target_id", "")
            detection = self.video_panel.canvas.get_detection(target_id)
            if detection is None:
                message = f"当前画面中不存在可验证目标 {target_id}"
                self._append_log("WARNING", f"{intent.source}：{message}")
                self.statusBar().showMessage(message, 4500)
                return
            selection = SelectionState(
                target_id=target_id,
                source=intent.source,
                confidence=detection.confidence,
                bbox=detection.bbox,
                command_id=intent.command_id,
            )
            event = DetectionEvent(
                target_type=f"候选火源 {target_id}",
                confidence=detection.confidence,
                x=self.drone_state.x,
                y=self.drone_state.y,
                altitude=self.drone_state.altitude,
                source=intent.source,
                review_state="待确认",
                command_id=intent.command_id,
                bbox=detection.bbox,
            )
            selection.event_id = event.event_id
            self.selection_state = selection
            self.video_panel.canvas.select_target(target_id)
            self.command_bar.set_candidate(
                target_id,
                detection.confidence,
                intent.source,
                selection.review_state,
            )
            self._append_log(
                "COMMAND",
                f"{intent.source}选择候选目标 {target_id}，等待确认",
            )
            return

        if intent.action == "CANCEL_SELECTION":
            if self.selection_state is None:
                self.statusBar().showMessage("当前没有可取消的候选目标", 3500)
                return
            self.selection_state.review_state = "已取消"
            self.command_bar.set_candidate(
                self.selection_state.target_id,
                self.selection_state.confidence,
                self.selection_state.source,
                "已取消",
            )
            self.video_panel.canvas.clear_selection()
            self._append_log("COMMAND", f"{intent.source}：{intent.label}")
            return

        if intent.action == "CONFIRM_CANDIDATE":
            if self.selection_state is None:
                self.statusBar().showMessage("当前没有可确认的候选目标", 3500)
                return
            if self.selection_state.review_state != "待确认":
                self.statusBar().showMessage(
                    f"候选目标已处于{self.selection_state.review_state}状态",
                    3500,
                )
                return
            self.selection_state.review_state = "已确认"
            self.command_bar.set_candidate(
                self.selection_state.target_id,
                self.selection_state.confidence,
                self.selection_state.source,
                "已确认",
            )
            self._append_log(
                "COMMAND",
                f"{intent.source}确认候选 {self.selection_state.target_id}",
            )
            return

        if intent.requires_confirmation:
            message = (
                f"指令来源：{intent.source}\n"
                f"候选动作：{intent.label}\n"
                f"置信度：{intent.confidence:.0%}\n"
                f"当前状态：{self.drone_state.flight_phase}\n"
                f"风险等级：{intent.risk_level}\n\n"
                "确认执行此高风险操作吗？\n"
                "执行后会写入任务日志，请持续观察飞行状态。"
            )
            dialog = QMessageBox(self)
            dialog.setWindowTitle("高风险命令确认")
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(f"准备执行：{intent.label}")
            dialog.setInformativeText(message)
            execute_button = dialog.addButton(
                "确认执行", QMessageBox.AcceptRole
            )
            cancel_button = dialog.addButton(
                "取消", QMessageBox.RejectRole
            )
            dialog.setDefaultButton(cancel_button)
            dialog.setEscapeButton(cancel_button)
            dialog.exec_()
            if dialog.clickedButton() is not execute_button:
                self._append_log(
                    "WARNING", f"用户取消 {intent.source} 指令：{intent.label}"
                )
                return

        ok, message = self.simulator.apply_command(intent.action)
        level = "COMMAND" if ok else "WARNING"
        self._append_log(level, f"{intent.source} → {intent.label}：{message}")
        if ok:
            self._leave_self_check_view()
            self._exit_multimodal_view(intent.label)
        else:
            QMessageBox.warning(self, "命令未执行", message)

    def _select_target(
        self, target_id: str, detection: FireDetection
    ) -> None:
        self._propose_command(
            CommandIntent(
                action="SELECT_TARGET",
                source="视频画面",
                label=f"选择目标 {target_id}",
                confidence=detection.confidence,
                parameters={
                    "target_id": target_id,
                    "bbox": detection.bbox,
                },
            )
        )

    def connect_telemetry(
        self,
        port: str,
        baudrate: int,
        coordinate_port: str,
        coordinate_baudrate: int,
        protocol: str,
    ) -> None:
        port = port.strip()
        coordinate_port = coordinate_port.strip()
        if not port or port == "模拟器" or protocol == "模拟遥测":
            self.disconnect_telemetry()
            self._append_log("INFO", "飞控数传切换为模拟遥测")
            self.device_panel.set_telemetry_status(True, "已使用模拟遥测")
            return

        if protocol != "NCLink 只读":
            QMessageBox.warning(
                self,
                "暂不支持",
                "当前只接入 NCLink 只读协议。请选择“NCLink 只读”。",
            )
            return

        self._stop_telemetry_thread()
        self._stop_coordinate_thread()
        self._real_telemetry_active = True
        self._coordinate_active = bool(coordinate_port and coordinate_port != "模拟器")
        if self.simulator.timer.isActive():
            self.simulator.timer.stop()

        self.drone_state.connected = False
        self.drone_state.telemetry_connected = False
        self.drone_state.flight_mode = "CONNECTING"
        self.drone_state.flight_phase = "连接飞控数传中"
        self.drone_state.warning = "正在等待真实飞控数据"
        self._on_state_changed(self.drone_state)
        self.device_panel.set_telemetry_status(False, f"UART4 正在连接 {port} @ {baudrate}")
        if self._coordinate_active:
            self.device_panel.set_coordinate_status(
                False,
                f"UART2 正在连接 {coordinate_port} @ {coordinate_baudrate}",
            )
        else:
            self.device_panel.set_coordinate_status(
                False, "未启用；选择 UART2 坐标口后可接收实时 x/y"
            )
        self._append_log("INFO", f"正在连接 UART4 状态口：{port} @ {baudrate}，NCLink 只读")

        self.telemetry_thread = TelemetryThread(port, baudrate, self)
        self.telemetry_thread.state_changed.connect(self._on_telemetry_state)
        self.telemetry_thread.status_changed.connect(self._on_telemetry_status)
        self.telemetry_thread.log_generated.connect(self._append_log)
        self.telemetry_thread.start()

        if self._coordinate_active:
            self._append_log(
                "INFO",
                f"正在连接 UART2 坐标口：{coordinate_port} @ {coordinate_baudrate}，等待 FC FF E1",
            )
            self.coordinate_thread = CoordinateThread(
                coordinate_port, coordinate_baudrate, self
            )
            self.coordinate_thread.coordinate_changed.connect(
                self._on_coordinate_frame
            )
            self.coordinate_thread.status_changed.connect(
                self._on_coordinate_status
            )
            self.coordinate_thread.log_generated.connect(self._append_log)
            self.coordinate_thread.start()

    def disconnect_telemetry(self) -> None:
        self._stop_telemetry_thread()
        self._stop_coordinate_thread()
        self._real_telemetry_active = False
        self._coordinate_active = False
        if not self.simulator.timer.isActive():
            self.simulator.timer.start(250)
        self.drone_state.warning = ""
        self.drone_state.telemetry_connected = True
        self.drone_state.connected = True
        self.device_panel.set_telemetry_status(True, "已恢复模拟遥测")
        self.device_panel.set_coordinate_status(False, "已断开，当前使用模拟轨迹")
        self._append_log("INFO", "飞控数传已断开，恢复模拟无人机数据")

    def _stop_telemetry_thread(self) -> None:
        if self.telemetry_thread is None:
            return
        self.telemetry_thread.stop()
        self.telemetry_thread = None

    def _stop_coordinate_thread(self) -> None:
        if self.coordinate_thread is None:
            return
        self.coordinate_thread.stop()
        self.coordinate_thread = None

    def _on_telemetry_state(self, state: DroneState) -> None:
        if not self._real_telemetry_active:
            return
        if self._coordinate_active:
            state.x = self.drone_state.x
            state.y = self.drone_state.y
            state.distance_travelled = self.drone_state.distance_travelled
        self._on_state_changed(state)

    def _on_coordinate_frame(self, frame: FiretruckFrame) -> None:
        if not self._real_telemetry_active or not self._coordinate_active:
            return
        self.drone_state.x = frame.x_cm
        self.drone_state.y = frame.y_cm
        if frame.z_cm > 0:
            self.drone_state.altitude = frame.z_cm / 100.0
        if frame.distance_cm >= 0:
            self.drone_state.rangefinder_distance = frame.distance_cm / 100.0
        self.drone_state.telemetry_connected = True
        self.drone_state.connected = True
        self._on_state_changed(self.drone_state)

    def _on_coordinate_status(
        self, connected: bool, message: str, diagnostics: dict
    ) -> None:
        self.device_panel.set_coordinate_status(connected, message)
        if message != self._last_coordinate_status:
            level = "INFO" if connected else "WARNING"
            if diagnostics:
                packets = diagnostics.get("packets", 0)
                invalid = diagnostics.get("invalid", 0)
                self._append_log(level, f"{message} · 坐标包 {packets} · 异常帧 {invalid}")
            else:
                self._append_log(level, message)
            self._last_coordinate_status = message

    def _on_telemetry_status(
        self, connected: bool, message: str, diagnostics: dict
    ) -> None:
        self.device_panel.set_telemetry_status(connected, message)
        if self._real_telemetry_active:
            self.drone_state.connected = connected
            self.drone_state.telemetry_connected = connected
            if not connected:
                self.drone_state.flight_mode = "WAITING"
                self.drone_state.flight_phase = "等待飞控数传"
                self.drone_state.warning = message
            self.video_panel.set_state(self.drone_state)
            if self._self_check_active:
                self._refresh_self_check_view()
            self.right_sidebar.set_state(self.drone_state, self.camera_state)
            self.compact_status.set_state(self.drone_state, self.camera_state)
            self._update_header_status()
        if message != self._last_telemetry_status:
            level = "INFO" if connected else "WARNING"
            if diagnostics:
                packets = diagnostics.get("packets", 0)
                invalid = diagnostics.get("invalid", 0)
                self._append_log(level, f"{message} · 有效包 {packets} · 异常帧 {invalid}")
            else:
                self._append_log(level, message)
            self._last_telemetry_status = message

    @staticmethod
    def _is_self_check_label(label: str) -> bool:
        keywords = ("自检", "检查", "状态")
        return any(keyword in label for keyword in keywords)

    def _show_self_check_view(self, label: str, source: str) -> None:
        self._leave_simulation_view()
        self._self_check_active = True
        self._self_check_label = label or "系统自检"
        self._main_view_mode = "self_check"
        self._multimodal_preview_path = None
        self._multimodal_preview_mtime = 0.0
        if self._multimodal_timer.isActive():
            self._multimodal_timer.stop()
        self._append_log("COMMAND", f"{source}进入自检状态显示：{self._self_check_label}")
        self._refresh_self_check_view()
        self.statusBar().showMessage("主画面已切换到飞控自检状态", 4000)

    def _leave_self_check_view(self) -> None:
        if not self._self_check_active:
            return
        self._self_check_active = False
        if self._main_view_mode == "self_check":
            self._main_view_mode = "flight"
            self.video_panel.show_live_mode()
            self.video_panel.set_camera_state(self.camera_state)

    def _refresh_self_check_view(self) -> None:
        if not self._self_check_active:
            return
        state = self.drone_state
        source = "真实飞控串口" if self._real_telemetry_active else "模拟遥测"
        telemetry = self._last_telemetry_status or (
            "等待真实飞控数据" if self._real_telemetry_active else "未连接真实数传，当前显示模拟状态"
        )
        connected_text = "在线" if state.telemetry_connected else "离线/等待"
        armed_text = "已解锁" if state.armed else "未解锁"
        warning = state.warning or "无"
        altitude_check_failed = state.altitude > 1.5
        self_check_result = (
            "自检失败：高度超过 1.5 m，请先下降到安全高度"
            if altitude_check_failed
            else "自检通过：高度处于安全范围"
        )
        label = self._self_check_label
        if "姿态自检" in label:
            self.video_panel.show_attitude_3d_mode(state)
            return
        if "参数自检" in label:
            self.video_panel.show_parameter_check_mode(state)
            return
        if "陀螺" in label or "惯导" in label:
            focus_line = (
                f"重点检查：陀螺仪/姿态角 · 横滚 {state.roll:.1f}° · "
                f"俯仰 {state.pitch:.1f}° · 航向 {state.yaw:.1f}°"
            )
            detail_lines = [
                f"飞控状态：{state.flight_phase} · 模式 {state.flight_mode} · {armed_text}",
                f"高度：{state.altitude:.2f} m · 垂直速度 {state.vertical_speed:.2f} m/s",
                f"链路：{connected_text} · {telemetry}",
            ]
        elif "电机" in label:
            focus_line = (
                f"重点检查：电机安全条件 · {armed_text} · 电源 "
                f"{state.battery_voltage:.2f} V"
            )
            detail_lines = [
                f"高度：{state.altitude:.2f} m · 垂直速度 {state.vertical_speed:.2f} m/s",
                f"飞控状态：{state.flight_phase} · 模式 {state.flight_mode}",
                f"链路：{connected_text} · {telemetry}",
            ]
        elif "摄像" in label or "相机" in label or "图传" in label:
            if self.camera_state.connected:
                address = self.camera_state.source or suggested_amb82_url()
                if "·" in address:
                    address = address.rsplit("·", 1)[-1].strip()
            else:
                address = suggested_amb82_url()
            display_address = address
            if display_address.lower().startswith("rtsp://"):
                display_address = display_address[7:]
            display_address = display_address.rstrip("/")
            connection = "已连接" if self.camera_state.connected else "未连接"
            fps = self.camera_state.fps if self.camera_state.connected else 0.0
            frame_age = self.camera_state.frame_age_ms if self.camera_state.connected else -1
            quality = (
                "正常"
                if self.camera_state.connected
                and fps >= 10
                and frame_age <= 500
                else "等待图传"
            )
            camera_text = (
                f"在线 · {fps:.1f} 帧/秒 · {self.camera_state.resolution}"
                if self.camera_state.connected
                else f"离线 · {self.camera_state.last_error or '等待图传'}"
            )
            focus_line = f"重点检查：摄像头/图传 · {camera_text}"
            detail_lines = [
                f"AMB82：{display_address}",
                f"链接：{connection} · {self.camera_state.last_error or '无错误'}",
                f"画质：{quality} · {fps:.1f} 帧/秒",
                f"分辨率：{self.camera_state.resolution} · 帧龄 {frame_age} ms",
            ]
            lines = [
                f"摄像头自检：{connection}",
                *detail_lines,
            ]
            self.video_panel.show_self_check_mode(
                "摄像头自检状态",
                lines,
            )
            return
        else:
            focus_line = "重点检查：系统综合状态 · 飞控/数传/传感器"
            detail_lines = [
                f"飞控状态：{state.flight_phase} · 模式 {state.flight_mode} · {armed_text}",
                f"姿态角：横滚 {state.roll:.1f}° · 俯仰 {state.pitch:.1f}° · 航向 {state.yaw:.1f}°",
                f"高度：{state.altitude:.2f} m · 垂直速度 {state.vertical_speed:.2f} m/s",
            ]
        lines = [
            self_check_result,
            focus_line,
            f"来源：{source} · 数传 {connected_text} · {telemetry}",
            *detail_lines,
            f"电源电压：{state.battery_voltage:.2f} V",
            f"传感器：光流 {state.optical_flow_quality}% · 测距 {state.rangefinder_distance:.2f} m · 链路 {state.link_latency_ms} ms",
            f"警告：{warning} · 更新 {state.last_update.strftime('%H:%M:%S')}",
        ]
        self.video_panel.show_self_check_mode(
            f"飞控自检状态 · {self._self_check_label}",
            lines,
        )

    def _show_simulation_flight(self, source: str = "多模态指令") -> None:
        self._self_check_active = False
        self._main_view_mode = "simulation"
        self._multimodal_preview_path = None
        self._multimodal_preview_mtime = 0.0
        self._multimodal_waiting_map_confirm = False
        if self._multimodal_timer.isActive():
            self._multimodal_timer.stop()
        if not self.simulator.timer.isActive():
            self.simulator.timer.start(250)

        if self.drone_3d_view is not None:
            self.drone_3d_view.set_waypoints(
                [self._simulation_xy_to_3d(x, y) for x, y in self.simulator.waypoints]
            )
            self._update_drone_3d_view(self.simulator.state)
            self.drone_3d_view.start()

        available = self.drone_3d_view is not None
        error = "" if available else str(DRONE_3D_IMPORT_ERROR or "3D 仿真初始化失败")
        self.video_panel.show_simulation_mode(available, error)
        if self.simulation_control_window is not None:
            self.simulation_control_window.show()
            self.simulation_control_window.raise_()
            self.simulation_control_window.activateWindow()
        self._append_log("COMMAND", f"{source}进入仿真飞行：中心画面已切换到 3D 仿真")
        self.statusBar().showMessage("仿真飞行已启动，可在独立控制窗发送仿真指令", 5000)

    def _on_simulation_command(self, command: str) -> None:
        command = command.strip().upper()
        if not command:
            return
        if self._main_view_mode != "simulation":
            self._show_simulation_flight("仿真控制窗")
        ok, message = self.simulator.apply_command(command)
        level = "COMMAND" if ok else "WARNING"
        self._append_log(level, f"仿真指令 {command}：{message}")
        if self.simulation_control_window is not None:
            self.simulation_control_window.set_result(ok, message)
        self.statusBar().showMessage(message, 4500)

    def _leave_simulation_view(self) -> None:
        if self._main_view_mode != "simulation":
            return
        if self.drone_3d_view is not None:
            self.drone_3d_view.stop()
        if self.simulation_control_window is not None:
            self.simulation_control_window.hide()
        self._main_view_mode = "flight"

    def connect_camera(self, url: str = "auto") -> None:
        url = suggested_amb82_url() if url.strip().lower() == "auto" else url.strip()
        if self.camera_thread and self.camera_thread.isRunning():
            message = (
                "AMB82 已连接，无需重复连接"
                if self.camera_state.connected
                else "AMB82 正在连接，请稍候"
            )
            self._append_log("WARNING", message)
            self.statusBar().showMessage(message, 4000)
            return
        self._camera_connecting = True
        self.camera_chip.setText("● 相机 连接中")
        self.camera_chip.setObjectName("chipWarn")
        self._refresh_style(self.camera_chip)
        self.connect_camera_button.setEnabled(False)
        self.connect_camera_button.setText("连接中…")
        self._append_log("INFO", f"正在连接 AMB82-Mini：{url}")
        self.camera_thread = CameraThread(
            url,
            self,
            self.lens_correction_enabled,
            self.lens_correction_strength,
            self.fire_detection_enabled,
        )
        self.camera_thread.frame_ready.connect(self._on_camera_frame)
        self.camera_thread.fire_confirmed.connect(self._on_fire_confirmed)
        self.camera_thread.fire_recognition_ready.connect(
            self._on_fire_recognition_result
        )
        self.camera_thread.status_changed.connect(self._on_camera_status)
        self.camera_thread.start()

    def _toggle_lens_correction(self, enabled: bool) -> None:
        self._set_lens_correction(enabled, self.lens_correction_strength)

    def _toggle_fire_detection(self, enabled: bool) -> None:
        self.fire_detection_enabled = bool(enabled)
        self.video_panel.set_fire_detection_enabled(enabled)
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.set_fire_detection_enabled(enabled)
        if not enabled:
            self.video_panel.canvas.clear_detections()
        state = "已开启" if enabled else "已关闭"
        detail = (
            "正在对实时图传逐帧检测红色模拟火源"
            if enabled and self.camera_state.connected
            else "连接图传后开始检测"
            if enabled
            else "实时图传不执行火源检测"
        )
        self._append_log("INFO", f"火源目标识别{state}：{detail}")
        self.statusBar().showMessage(f"火源目标识别{state} · {detail}", 4500)
        self.video_panel.set_camera_state(self.camera_state)

    def _toggle_face_recognition(self, enabled: bool) -> None:
        self.face_recognition_enabled = bool(enabled)
        self.video_panel.set_face_recognition_enabled(enabled)
        if enabled:
            if (
                self.face_recognition_thread is None
                or not self.face_recognition_thread.isRunning()
            ):
                self.face_recognition_thread = FaceRecognitionThread(self)
                self.face_recognition_thread.recognition_ready.connect(
                    self._on_face_recognition_results
                )
                self.face_recognition_thread.status_changed.connect(
                    self._on_face_recognition_status
                )
                self.face_recognition_thread.set_enabled(True)
                self.face_recognition_thread.start()
            else:
                self.face_recognition_thread.set_enabled(True)
        elif self.face_recognition_thread is not None:
            self.face_recognition_thread.set_enabled(False)
            self.video_panel.canvas.clear_face_matches()

        state = "已开启" if enabled else "已关闭"
        detail = (
            "正在本机实时识别 Lucy、Mark 和陌生人"
            if enabled and self.camera_state.connected
            else "连接图传后开始识别"
            if enabled
            else "实时图传不执行人脸识别"
        )
        self._append_log("INFO", f"人脸目标识别{state}：{detail}")
        self.statusBar().showMessage(
            f"人脸目标识别{state} · {detail}", 4500
        )
        self.video_panel.set_camera_state(self.camera_state)

    def _on_face_recognition_status(self, ready: bool, message: str) -> None:
        level = "INFO" if ready else "ERROR"
        self._append_log(level, f"人脸识别：{message}")
        self.statusBar().showMessage(f"人脸识别 · {message}", 6000)
        if not ready and self.face_recognition_enabled:
            self.face_recognition_enabled = False
            self.vision_recognition_panel.set_face_recognition_enabled(False)

    def _on_face_recognition_results(
        self,
        matches: list[FaceMatch],
        recognition_frame=None,
    ) -> None:
        if not self.face_recognition_enabled or self._main_view_mode != "flight":
            return
        self.video_panel.canvas.set_face_matches(matches)
        if not self._face_mapping_task_active:
            return
        for match in matches:
            marker = {"lucy": "L", "mark": "M"}.get(match.name.casefold())
            if (
                not match.matched
                or marker is None
                or marker in self._face_locations_marked
            ):
                continue
            if not bbox_inside_center_roi(
                match.bbox,
                match.frame_width,
                match.frame_height,
            ):
                continue
            map_x, map_y = self.right_sidebar.mark_face_at_current_position(marker)
            self._face_locations_marked.add(marker)
            self.flight_log_recorder.record_recognition(
                target_type="人脸识别",
                label=match.name,
                confidence=match.confidence,
                state=self.drone_state,
                bbox=match.bbox,
                frame_width=match.frame_width,
                frame_height=match.frame_height,
                overlay_label=f"FACE {match.name}",
                recognition_frame=recognition_frame,
            )
            self._append_log(
                "WARNING",
                f"首次识别到 {match.name}（置信度 {match.confidence:.1%}）："
                f"水平坐标 ({self.drone_state.x:.0f}, "
                f"{self.drone_state.y:.0f}) cm，地图标记 {marker} "
                f"位于 ({map_x:.0f}, {map_y:.0f}) cm",
            )
            self.statusBar().showMessage(
                f"已在任务地图标记 {marker}：{match.name}",
                7000,
            )

    def _toggle_ocr_recognition(self, enabled: bool) -> None:
        self.ocr_recognition_enabled = bool(enabled)
        self.video_panel.set_ocr_recognition_enabled(enabled)
        if enabled:
            if (
                self.ocr_recognition_thread is None
                or not self.ocr_recognition_thread.isRunning()
            ):
                self.ocr_recognition_thread = OCRRecognitionThread(self)
                self.ocr_recognition_thread.recognition_ready.connect(
                    self._on_ocr_recognition_results
                )
                self.ocr_recognition_thread.status_changed.connect(
                    self._on_ocr_recognition_status
                )
                self.ocr_recognition_thread.set_enabled(True)
                self.ocr_recognition_thread.start()
            else:
                self.ocr_recognition_thread.set_enabled(True)
        elif self.ocr_recognition_thread is not None:
            self.ocr_recognition_thread.set_enabled(False)
            self.video_panel.canvas.clear_ocr_matches()

        state = "已开启" if enabled else "已关闭"
        detail = (
            "正在本机实时识别图传中的中英文文字"
            if enabled and self.camera_state.connected
            else "连接图传后开始识别"
            if enabled
            else "实时图传不执行 OCR 识别"
        )
        self._append_log("INFO", f"OCR 文字识别{state}：{detail}")
        self.statusBar().showMessage(
            f"OCR 文字识别{state} · {detail}", 4500
        )
        self.video_panel.set_camera_state(self.camera_state)

    def _on_ocr_recognition_status(self, ready: bool, message: str) -> None:
        level = "INFO" if ready else "ERROR"
        self._append_log(level, f"OCR 识别：{message}")
        self.statusBar().showMessage(f"OCR 识别 · {message}", 6000)
        if not ready and self.ocr_recognition_enabled:
            self.ocr_recognition_enabled = False
            self.vision_recognition_panel.set_ocr_recognition_enabled(False)

    def _on_ocr_recognition_results(
        self,
        matches: list[OCRMatch],
        recognition_frame=None,
    ) -> None:
        if not self.ocr_recognition_enabled or self._main_view_mode != "flight":
            return
        self.video_panel.canvas.set_ocr_matches(matches)
        if not self._ocr_mapping_task_active:
            return
        for match in matches:
            if match.confidence < OCR_MAP_MIN_CONFIDENCE:
                continue
            normalized_text = "".join(
                character for character in match.text if character.isalnum()
            )
            candidates = [
                (word, marker)
                for word, marker in OCR_MAP_CANDIDATES.items()
                if word in normalized_text and word not in self._ocr_locations_marked
            ]
            if not candidates:
                continue
            x_values = [point[0] for point in match.polygon]
            y_values = [point[1] for point in match.polygon]
            bbox = (
                min(x_values),
                min(y_values),
                max(x_values) - min(x_values),
                max(y_values) - min(y_values),
            )
            if not bbox_inside_center_roi(
                bbox,
                match.frame_width,
                match.frame_height,
            ):
                continue
            for word, marker in candidates:
                map_x, map_y = self.right_sidebar.mark_text_at_current_position(
                    marker
                )
                self._ocr_locations_marked.add(word)
                self.flight_log_recorder.record_recognition(
                    target_type="文字识别",
                    label=word,
                    confidence=match.confidence,
                    state=self.drone_state,
                    bbox=bbox,
                    frame_width=match.frame_width,
                    frame_height=match.frame_height,
                    overlay_label="OCR",
                    recognition_frame=recognition_frame,
                )
                self._append_log(
                    "WARNING",
                    f"首次识别到文字“{word}”（置信度 {match.confidence:.1%}）："
                    f"水平坐标 ({self.drone_state.x:.0f}, "
                    f"{self.drone_state.y:.0f}) cm，地图标记“{marker}”位于 "
                    f"({map_x:.0f}, {map_y:.0f}) cm",
                )
                self.statusBar().showMessage(
                    f"已在任务地图标记“{marker}”：{word}",
                    7000,
                )

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
        self._leave_simulation_view()
        self._leave_self_check_view()
        frame = create_red_blob_demo_frame()
        detector = K230RedBlobDetector()
        tracker = RedBlobConfirmationTracker(required_frames=20)
        detections: list[FireDetection] = []
        confirmed = None
        for _ in range(20):
            detections = detector.detect(frame)
            confirmed = tracker.update(detections) or confirmed
        if confirmed is not None:
            detections = [confirmed]
        self.video_panel.canvas.set_frame(frame)
        self.video_panel.canvas.set_detections(detections)
        self.video_panel.show_demo_mode(len(detections))
        if detections:
            detection = detections[0]
            self._append_log(
                "INFO",
                f"火源识别示例检测成功，置信度 {detection.confidence:.0%}",
            )
            self.statusBar().showMessage(
                f"示例检测成功：火源置信度 {detection.confidence:.0%}", 6000
            )
        else:
            self._append_log("INFO", "火源识别示例未发现候选目标")

    def _on_camera_frame(
        self, frame, detections: list[FireDetection]
    ) -> None:
        self.flight_log_recorder.update_latest_frame(frame)
        if (
            self.face_recognition_enabled
            and self.face_recognition_thread is not None
            and self.face_recognition_thread.isRunning()
            and self._main_view_mode == "flight"
        ):
            self.face_recognition_thread.submit_frame(frame)
        if (
            self.ocr_recognition_enabled
            and self.ocr_recognition_thread is not None
            and self.ocr_recognition_thread.isRunning()
            and self._main_view_mode == "flight"
        ):
            self.ocr_recognition_thread.submit_frame(frame)
        if not self.fire_detection_enabled:
            detections = []
        if self._main_view_mode != "flight":
            return
        self.video_panel.canvas.set_frame(frame)
        self.video_panel.canvas.set_detections(detections)
        self.video_panel.show_live_mode()
        height, width = frame.shape[:2]
        self.camera_state.resolution = f"{width} × {height}"

    def _enter_multimodal_view(self, preview_path: str) -> None:
        self._leave_simulation_view()
        self._leave_self_check_view()
        self._main_view_mode = "multimodal"
        self._multimodal_preview_path = Path(preview_path)
        self._multimodal_preview_mtime = 0.0
        self._multimodal_waiting_map_confirm = False
        self.video_panel.show_multimodal_mode()
        self.statusBar().showMessage("主画面已切换到多模态摄像头", 4000)
        if not self._multimodal_timer.isActive():
            self._multimodal_timer.start()

    def _show_multimodal_takeoff_map(self, intent: CommandIntent | None = None) -> None:
        if self._main_view_mode != "multimodal":
            return
        self._multimodal_waiting_map_confirm = True
        task = intent.label if intent is not None else "起飞选项"
        self._pending_takeoff_task = task
        mode = "free" if task == "定制航点" else "preset"
        self.video_panel.show_takeoff_map_confirmation(mode=mode, task_label=task)
        if mode == "free":
            self.right_sidebar.set_planning_points([])
        else:
            self.right_sidebar.set_planning_route([])
        self.statusBar().showMessage(f"已完成识别：{task}，请确认任务地图", 5000)

    def _update_multimodal_route_preview(self, route_sequence: object) -> None:
        if self._main_view_mode == "multimodal" and self._multimodal_waiting_map_confirm:
            if isinstance(route_sequence, dict) and route_sequence.get("mode") == "free":
                points = self._payload_xy_points(route_sequence)
                self.right_sidebar.set_planning_points(points)
            else:
                self.right_sidebar.set_planning_route(route_sequence)

    def _confirm_multimodal_takeoff_map(self, route_sequence: object | None = None) -> None:
        if self._main_view_mode != "multimodal":
            return
        if self._takeoff_sequence_active:
            self.statusBar().showMessage("起飞航线正在写入，请勿重复确认", 3500)
            return
        route_sequence = route_sequence or []
        write_wait_ms = self._send_takeoff_waypoints(route_sequence)
        if write_wait_ms is None:
            return
        self._takeoff_sequence_active = True
        self._multimodal_waiting_map_confirm = False
        if isinstance(route_sequence, dict) and route_sequence.get("mode") == "free":
            self.right_sidebar.start_route_tracking_points(
                self._payload_xy_points(route_sequence)
            )
        else:
            self.right_sidebar.start_route_tracking(route_sequence)
        self.multimodal_panel.confirm_takeoff_map(route_sequence)
        self.statusBar().showMessage("正在写入飞控航点，写入完成后自动进入起飞倒计时", 5000)
        QTimer.singleShot(
            write_wait_ms,
            lambda payload=route_sequence: self._begin_takeoff_countdown_after_write(payload),
        )

    def _payload_xy_points(self, route_payload: object) -> list[tuple[float, float]]:
        if not isinstance(route_payload, dict):
            return []
        points = []
        for point in route_payload.get("points", [])[:10]:
            if len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
        return points

    def _takeoff_waypoints_from_payload(
        self, route_payload: object
    ) -> tuple[list[tuple[int, int, int, str]], str] | None:
        if isinstance(route_payload, dict) and route_payload.get("mode") == "free":
            items: list[tuple[int, int, int, str]] = []
            for index, point in enumerate(route_payload.get("points", [])[:10], start=1):
                if len(point) < 2:
                    continue
                x_cm = max(0, min(480, int(round(float(point[0])))))
                y_cm = max(0, min(400, int(round(float(point[1])))))
                z_cm = int(round(float(point[2]))) if len(point) >= 3 else 120
                items.append((x_cm, y_cm, z_cm, f"自由点{index}"))
            label = f"高空自由航线 {len(items)} 点"
            return items, label
        sequence = list(route_payload) if route_payload else []
        items = []
        for region in sequence:
            waypoint = TAKEOFF_ROUTE_WAYPOINTS_CM.get(region)
            if waypoint is None:
                continue
            x_cm, y_cm, z_cm = waypoint
            items.append((x_cm, y_cm, z_cm, f"区域{region}"))
        label = "".join(sequence)
        return items, label

    def _send_takeoff_waypoints(self, route_sequence: object) -> int | None:
        parsed = self._takeoff_waypoints_from_payload(route_sequence)
        if parsed is None:
            return None
        waypoints, route_label = parsed
        if not waypoints:
            QMessageBox.warning(self, "未选择航线", "请先在地图中选择至少一个巡逻航点。")
            return None
        if self.telemetry_thread is None or not self.telemetry_thread.isRunning():
            QMessageBox.warning(
                self,
                "UART4 未连接",
                "请先连接 UART4 状态口，然后再确认地图执行起飞项。",
            )
            return None

        frames: list[tuple[int, bytes, str, int, int]] = [
            (
                0,
                build_waypoint_clear_frame(),
                "清空飞控原航点",
                TAKEOFF_CLEAR_FRAME_REPEAT_COUNT,
                TAKEOFF_CLEAR_FRAME_REPEAT_INTERVAL_MS,
            )
        ]
        delay_ms = TAKEOFF_CLEAR_TO_WAYPOINT_DELAY_MS
        for index, (x_cm, y_cm, z_cm, label) in enumerate(waypoints, start=1):
            frames.append(
                (
                    delay_ms,
                    build_waypoint_write_frame(index, x_cm, y_cm, z_cm),
                    f"P{index}={label}({x_cm},{y_cm},{z_cm})",
                    TAKEOFF_FRAME_REPEAT_COUNT,
                    TAKEOFF_FRAME_REPEAT_INTERVAL_MS,
                )
            )
            delay_ms += TAKEOFF_WAYPOINT_STEP_DELAY_MS

        self._pending_takeoff_label = route_label or f"{len(waypoints)} 个航点"
        for delay, frame, description, repeat_count, repeat_interval_ms in frames:
            QTimer.singleShot(
                delay,
                lambda payload=frame, label=description, repeats=repeat_count, interval=repeat_interval_ms: self._send_queued_takeoff_frame(
                    payload, label, repeats, interval
                ),
            )
        self._append_log(
            "INFO",
            f"开始写入起飞航线：{self._pending_takeoff_label}，共 {len(frames) - 1} 个航点，"
            f"清空指令发送 {TAKEOFF_CLEAR_FRAME_REPEAT_COUNT} 遍后等待 {TAKEOFF_CLEAR_TO_WAYPOINT_DELAY_MS / 1000:.1f} 秒，"
            f"航点指令每条重复发送 {TAKEOFF_FRAME_REPEAT_COUNT} 遍",
        )
        return delay_ms + 900

    def _send_queued_takeoff_frame(
        self, frame: bytes, description: str, repeat_count: int, repeat_interval_ms: int
    ) -> None:
        if self.telemetry_thread is None or not self.telemetry_thread.isRunning():
            self._append_log("ERROR", f"UART4 已断开，未发送：{description}")
            return
        self._send_repeated_takeoff_frame(
            frame, description, repeat_count, repeat_interval_ms
        )

    def _send_repeated_takeoff_frame(
        self,
        frame: bytes,
        description: str,
        repeat_count: int = TAKEOFF_FRAME_REPEAT_COUNT,
        repeat_interval_ms: int = TAKEOFF_FRAME_REPEAT_INTERVAL_MS,
    ) -> None:
        self._append_log(
            "COMMAND",
            f"UART4 排队发送 {description} ×{repeat_count}：{frame.hex(' ').upper()}",
        )
        for repeat_index in range(repeat_count):
            QTimer.singleShot(
                repeat_index * repeat_interval_ms,
                lambda payload=frame, label=description, attempt=repeat_index + 1: self._send_takeoff_frame_once(
                    payload, label, attempt, repeat_count
                ),
            )

    def _send_takeoff_frame_once(
        self, frame: bytes, description: str, attempt: int, repeat_count: int
    ) -> None:
        if self.telemetry_thread is None or not self.telemetry_thread.isRunning():
            self._append_log(
                "ERROR",
                f"UART4 已断开，未发送：{description} 第 {attempt}/{repeat_count} 遍",
            )
            return
        self.telemetry_thread.send_bytes(frame)

    def _start_return_countdown(self) -> None:
        self._return_countdown_value = 10
        self.video_panel.show_return_countdown(self._return_countdown_value)
        if self._return_countdown_timer.isActive():
            self._return_countdown_timer.stop()
        self._return_countdown_timer.start()
        self._append_log("INFO", "10秒后返航倒计时开始")
        self.statusBar().showMessage("10秒后发送返航指令", 5000)

    def _tick_return_countdown(self) -> None:
        self._return_countdown_value -= 1
        if self._return_countdown_value > 0:
            self.video_panel.show_return_countdown(self._return_countdown_value)
            return
        self._return_countdown_timer.stop()
        self._append_log("INFO", "返航倒计时结束，准备发送 UART4 返航指令")
        self._send_immediate_safety_command("RTL", "10秒后返航")

    def _begin_takeoff_countdown_after_write(self, route_sequence: object) -> None:
        if not self._takeoff_sequence_active:
            return
        if self.telemetry_thread is None or not self.telemetry_thread.isRunning():
            self._takeoff_sequence_active = False
            self._append_log("ERROR", "航点写入后 UART4 已断开，起飞倒计时取消")
            QMessageBox.warning(self, "UART4 已断开", "航点写入后 UART4 已断开，未能启动起飞倒计时。")
            return
        self._append_log("INFO", "航点写入等待完成，开始 5 秒起飞倒计时")
        self.statusBar().showMessage("航点写入完成，起飞倒计时开始", 5000)
        self._start_takeoff_countdown(route_sequence)

    def _start_takeoff_countdown(self, route_sequence: object) -> None:
        self._pending_takeoff_route = list(route_sequence) if not isinstance(route_sequence, dict) else []
        if isinstance(route_sequence, dict) and not self._pending_takeoff_label:
            self._pending_takeoff_label = f"高空自由航线 {len(route_sequence.get('points', []))} 点"
        self._takeoff_countdown_value = 5
        self.video_panel.show_takeoff_countdown(self._takeoff_countdown_value)
        if self._takeoff_countdown_timer.isActive():
            self._takeoff_countdown_timer.stop()
        self._takeoff_countdown_timer.start()

    def _tick_takeoff_countdown(self) -> None:
        self._takeoff_countdown_value -= 1
        if self._takeoff_countdown_value > 0:
            self.video_panel.show_takeoff_countdown(self._takeoff_countdown_value)
            return
        self._takeoff_countdown_timer.stop()
        if self.telemetry_thread is not None and self.telemetry_thread.isRunning():
            route_text = self._pending_takeoff_label or "".join(self._pending_takeoff_route) or "默认航线"
            self._send_repeated_takeoff_frame(
                FORCE_SDK_MODE18_FRAME,
                f"启动 mode18 巡航：航线 {route_text}",
            )
            self._start_detection_mapping_task()
            self.statusBar().showMessage("mode18 巡航指令已重复发送", 5000)
        else:
            self._append_log("ERROR", "倒计时结束时 UART4 已断开，mode18 未发送")
            QMessageBox.warning(self, "UART4 已断开", "倒计时结束时 UART4 已断开，未能启动巡航。")
        self._takeoff_sequence_active = False
        self._exit_multimodal_view("起飞巡航")

    def _start_detection_mapping_task(self) -> None:
        mapping_enabled = self._pending_takeoff_task in {
            "低空巡逻",
            "定制航点",
        }
        self._fire_mapping_task_active = mapping_enabled
        self._fire_location_marked = False
        self._face_mapping_task_active = mapping_enabled
        self._face_locations_marked = set()
        self._ocr_mapping_task_active = mapping_enabled
        self._ocr_locations_marked = set()
        self.right_sidebar.clear_fire_marker()
        self.right_sidebar.clear_face_markers()
        self.right_sidebar.clear_text_markers()
        if mapping_enabled:
            self._append_log(
                "INFO",
                f"{self._pending_takeoff_task}已启动：等待 ROI 内首次确认火源、人脸和候选文字",
            )

    def _exit_multimodal_view(self, task_label: str = "") -> None:
        if self._main_view_mode != "multimodal":
            return
        self._main_view_mode = "returning"
        self.video_panel.show_returning_mode(task_label)
        status = "主画面正在切回无人机图传"
        if task_label:
            status += f"：{task_label}"
        self.statusBar().showMessage(status, 3000)
        QTimer.singleShot(1400, self._finish_exit_multimodal_view)

    def _finish_exit_multimodal_view(self) -> None:
        if self._main_view_mode not in {"multimodal", "returning"}:
            return
        self._main_view_mode = "flight"
        self._multimodal_preview_path = None
        self._multimodal_preview_mtime = 0.0
        self._multimodal_waiting_map_confirm = False
        self._multimodal_timer.stop()
        self.video_panel.show_live_mode()
        if not self.camera_state.connected:
            self.video_panel.canvas.clear_frame()
        self.video_panel.set_camera_state(self.camera_state)
        self.statusBar().showMessage("主画面已切回无人机图传", 4000)

    def _refresh_multimodal_preview(self) -> None:
        if (
            self._main_view_mode != "multimodal"
            or self._multimodal_waiting_map_confirm
            or self._multimodal_preview_path is None
            or not self._multimodal_preview_path.exists()
        ):
            return
        try:
            mtime = self._multimodal_preview_path.stat().st_mtime
        except OSError:
            return
        if mtime <= self._multimodal_preview_mtime:
            return
        frame = cv2.imread(str(self._multimodal_preview_path))
        if frame is None:
            return
        self._multimodal_preview_mtime = mtime
        self.video_panel.canvas.set_frame(frame)
        self.video_panel.canvas.set_detections([])
        self.video_panel.show_multimodal_mode()

    def _on_fire_confirmed(self, detection: FireDetection) -> None:
        if not self.fire_detection_enabled:
            return
        self.video_panel.canvas.confirm_detection(detection)
        event = DetectionEvent(
            target_type="火源",
            confidence=detection.confidence,
            x=self.drone_state.x,
            y=self.drone_state.y,
            altitude=self.drone_state.altitude,
            source="K230 颜色识别",
            bbox=detection.bbox,
        )
        self._on_event(event)
        self._append_log(
            "WARNING",
            "K230 红色目标已连续 20 帧确认："
            f"{detection.confidence:.0%}，像素中心 "
            f"({detection.center_x}, {detection.center_y})",
        )
        self.statusBar().showMessage(
            f"发现火源：置信度 {detection.confidence:.0%}", 8000
        )

    def _on_fire_recognition_result(
        self,
        detection: FireDetection,
        recognition_frame,
    ) -> None:
        if (
            not self.fire_detection_enabled
            or not self._fire_mapping_task_active
            or self._fire_location_marked
        ):
            return
        if not fire_detection_inside_center_roi(detection):
            return

        map_x, map_y = self.right_sidebar.mark_fire_at_current_position()
        self._fire_location_marked = True
        self.flight_log_recorder.record_recognition(
            target_type="火源识别",
            label="火源",
            confidence=detection.confidence,
            state=self.drone_state,
            bbox=detection.bbox,
            frame_width=detection.frame_width,
            frame_height=detection.frame_height,
            overlay_label="FIRE",
            recognition_frame=recognition_frame,
        )
        self._append_log(
            "WARNING",
            f"首次火源坐标已锁定（置信度 {detection.confidence:.1%}）："
            f"水平坐标 ({self.drone_state.x:.0f}, {self.drone_state.y:.0f}) cm，"
            f"地图位置 ({map_x:.0f}, {map_y:.0f}) cm",
        )
        self.statusBar().showMessage(
            f"火源已标记：({self.drone_state.x:.0f}, {self.drone_state.y:.0f}) cm",
            8000,
        )

    def _on_camera_status(
        self,
        connected: bool,
        message: str,
        fps: float,
        diagnostics: dict,
    ) -> None:
        was_connected = self.camera_state.connected
        previous_error = self.camera_state.last_error
        self.camera_state.connected = connected
        self.camera_state.source = message if connected else "未连接图传"
        self.camera_state.fps = fps if connected else 0.0
        self.camera_state.frame_age_ms = int(
            diagnostics.get("frame_age_ms", -1)
        )
        self.camera_state.reconnect_count = int(
            diagnostics.get("reconnect_count", 0)
        )
        self.camera_state.last_error = str(
            diagnostics.get("last_error", "")
        )
        self.camera_state.source_kind = str(
            diagnostics.get("source_kind", "none")
        )
        self._camera_connecting = (
            not connected
            and bool(self.camera_thread)
            and self.camera_thread.isRunning()
            and diagnostics.get("source_kind") != "stopped"
        )
        if self._self_check_active:
            self._refresh_self_check_view()
        elif self._main_view_mode == "flight":
            self.video_panel.set_camera_state(self.camera_state)
        self.right_sidebar.health_panel.set_state(self.drone_state, self.camera_state)
        self.compact_status.set_state(self.drone_state, self.camera_state)
        thread_active = bool(
            self.camera_thread and self.camera_thread.isRunning()
        )
        self.connect_camera_button.setEnabled(not thread_active)
        self.connect_camera_button.setText(
            "相机已连接"
            if connected
            else "重连中…"
            if thread_active
            else "重新连接"
        )
        if connected and not was_connected:
            self._append_log("INFO", f"相机在线：{fps:.1f} FPS · {message}")
        elif (
            self.camera_state.last_error
            and self.camera_state.last_error != previous_error
        ):
            self._append_log("WARNING", f"图传重连：{self.camera_state.last_error}")
        self._update_header_status()

    def save_snapshot(self) -> None:
        CAPTURE_DIR.mkdir(exist_ok=True)
        filename = CAPTURE_DIR / (
            "ground_station_"
            + self.drone_state.last_update.strftime("%Y%m%d_%H%M%S")
            + ".png"
        )
        self.video_panel.canvas.grab().save(str(filename))
        self._append_log("INFO", f"截图已保存：{filename.name}")
        self.statusBar().showMessage(f"截图已保存：{filename}", 5000)

    def _observe_flight_log_state(self, state: DroneState) -> None:
        event, _record = self.flight_log_recorder.observe_state(
            state,
            self.camera_state,
            self._current_route_sequence(),
            self._current_route_track(),
            TAKEOFF_ROUTE_WAYPOINTS_CM,
        )
        if event == "started":
            self._append_log("INFO", "飞行日志开始记录：检测到无人机解锁")
        elif event == "completed":
            self._fire_mapping_task_active = False
            self._face_mapping_task_active = False
            self._ocr_mapping_task_active = False
            self._append_log("INFO", "飞行日志记录完成：检测到无人机重新锁定")

    def _current_route_sequence(self) -> list[str]:
        try:
            sequence = self.right_sidebar.map_panel.map._planning_sequence
        except AttributeError:
            sequence = []
        if sequence:
            return list(sequence)
        return list(self._pending_takeoff_route)

    def _current_route_track(self) -> list[tuple[float, float]]:
        try:
            return list(self.right_sidebar.map_panel.map._track)
        except AttributeError:
            return []

    def _export_latest_flight_log(self) -> None:
        log_root = APP_DIR / "flight_logs"
        log_root.mkdir(exist_ok=True)
        map_snapshot = log_root / "_latest_route_map.png"
        try:
            self.right_sidebar.map_panel.map.grab().save(str(map_snapshot))
        except Exception:
            map_snapshot = None
        try:
            output_path = self.flight_log_recorder.export_markdown(map_snapshot)
        except RuntimeError as exc:
            QMessageBox.warning(self, "暂无飞行日志", str(exc))
            self._append_log("WARNING", f"日志输出失败：{exc}")
            return
        self._append_log("INFO", f"飞行日志已输出：{output_path}")
        self.statusBar().showMessage(f"飞行日志已保存：{output_path}", 7000)
        preview_lines = self._flight_log_preview_lines(output_path)
        self._main_view_mode = "flight_log"
        self._multimodal_preview_path = None
        self._multimodal_preview_mtime = 0.0
        if self._multimodal_timer.isActive():
            self._multimodal_timer.stop()
        self.video_panel.show_flight_log_preview(
            "飞行日志预览",
            preview_lines,
            str(output_path),
        )
        QMessageBox.information(
            self,
            "飞行日志已输出",
            f"飞行日志已保存到：\n{output_path}",
        )

    @staticmethod
    def _flight_log_preview_lines(output_path: Path) -> list[str]:
        try:
            lines = output_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ["- 预览读取失败，但 Markdown 文件已经保存。"]
        preview: list[str] = []
        for line in lines:
            if line.startswith("!["):
                continue
            preview.append(line)
            if len(preview) >= 30:
                break
        return preview

    def _clear_alerts(self) -> None:
        self._append_log("INFO", "当前界面不再显示独立事件窗口")

    def _append_log(self, level: str, message: str) -> None:
        if hasattr(self, "flight_log_recorder"):
            self.flight_log_recorder.append_system_log(level, message)
        self.log_panel.append_log(level, message)

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
        self._right_sidebar_user_hidden = False
        self.right_sidebar.setVisible(True)
        self.horizontal_splitter.setSizes(
            [1100, 680] if self._large_display else [930, 320]
        )
        self.compact_status.setVisible(False)
        self.vertical_splitter.setSizes(
            [720, 90] if self._large_display else [650, 70]
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
            self.compact_status.setVisible(True)
            if not self._right_sidebar_user_hidden:
                self.right_sidebar.setVisible(False)
        elif width < 1550:
            mode = "medium"
            self.compact_status.setVisible(False)
            if not self._right_sidebar_user_hidden:
                self.right_sidebar.setVisible(True)
                self.right_sidebar.setMaximumWidth(330)
                self.horizontal_splitter.setSizes([max(700, width - 400), 300])
        else:
            mode = "wide"
            self.compact_status.setVisible(False)
            if not self._right_sidebar_user_hidden:
                self.right_sidebar.setVisible(True)
                sidebar_width = 680 if large_display else 340
                self.right_sidebar.setMaximumWidth(760 if large_display else 370)
                self.horizontal_splitter.setSizes(
                    [max(850, width - sidebar_width - 100), sidebar_width]
                )

        compact_height = height < (1500 if large_display else 930)
        self.right_sidebar.set_compact(compact_height)
        bottom_height = 90 if large_display else 70
        self.vertical_splitter.setSizes(
            [max(430, height - bottom_height), bottom_height]
        )

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
        if (
            self.face_recognition_thread
            and self.face_recognition_thread.isRunning()
        ):
            self.face_recognition_thread.stop()
        if (
            self.ocr_recognition_thread
            and self.ocr_recognition_thread.isRunning()
        ):
            self.ocr_recognition_thread.stop()
        if self.drone_3d_view is not None:
            self.drone_3d_view.stop()
        if self.simulation_control_window is not None:
            self.simulation_control_window.close_for_shutdown()
        self._stop_telemetry_thread()
        self._stop_coordinate_thread()
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
