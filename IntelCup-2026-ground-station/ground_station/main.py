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
    SelectionState,
)
from simulator import DroneSimulator
from styles import APP_STYLE, LARGE_DISPLAY_STYLE
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
        self._camera_connecting = False
        self.selection_state: SelectionState | None = None
        self._main_view_mode = "flight"
        self._multimodal_preview_path: Path | None = None
        self._multimodal_preview_mtime = 0.0

        self.simulator = DroneSimulator(self)
        self.simulator.state_changed.connect(self._on_state_changed)
        self.simulator.event_generated.connect(self._on_event)
        self.simulator.log_generated.connect(self._append_log)

        self._build_menu()
        self._build_central_ui()
        self._build_docks()
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
            ("连接相机", "C", lambda: self.connect_camera("auto")),
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
            lambda: self.connect_camera("auto")
        )
        self.video_panel.demo_requested.connect(self._load_fire_demo)
        self.video_panel.target_selected.connect(self._select_target)
        self.video_panel.target_missed.connect(
            lambda message: self.statusBar().showMessage(message, 3500)
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
            lambda: self.connect_camera("auto")
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
        self._add_dock(
            "multimodal",
            "多模态交互",
            self.multimodal_panel,
            Qt.LeftDockWidgetArea,
            True,
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
            True,
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
        for name in ("multimodal", "logs", "device"):
            dock = self.docks.get(name)
            if dock:
                dock.raise_()

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
        self.drone_state = state
        self.video_panel.set_state(state)
        self.right_sidebar.set_state(state, self.camera_state)
        self.compact_status.set_state(state, self.camera_state)
        self._update_header_status()
        self.status_message.setText(
            f"{state.flight_phase}  ·  坐标 ({state.x:.1f}, {state.y:.1f})  ·  "
            f"高度 {state.altitude:.2f} m  ·  电量 {state.battery_percent:.0f}%"
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

        if intent.action == "INFO_ACTION":
            message = f"{intent.source}选择：{intent.label}"
            self._append_log("COMMAND", message)
            self.statusBar().showMessage(message, 4500)
            self._exit_multimodal_view(intent.label)
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
        if self._main_view_mode != "flight":
            return
        self.video_panel.canvas.set_frame(frame)
        self.video_panel.canvas.set_detections(detections)
        self.video_panel.show_live_mode()
        height, width = frame.shape[:2]
        self.camera_state.resolution = f"{width} × {height}"

    def _enter_multimodal_view(self, preview_path: str) -> None:
        self._main_view_mode = "multimodal"
        self._multimodal_preview_path = Path(preview_path)
        self._multimodal_preview_mtime = 0.0
        self.video_panel.show_multimodal_mode()
        self.statusBar().showMessage("主画面已切换到多模态摄像头", 4000)
        if not self._multimodal_timer.isActive():
            self._multimodal_timer.start()

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
        self._multimodal_timer.stop()
        self.video_panel.show_live_mode()
        if not self.camera_state.connected:
            self.video_panel.canvas.clear_frame()
        self.video_panel.set_camera_state(self.camera_state)
        self.statusBar().showMessage("主画面已切回无人机图传", 4000)

    def _refresh_multimodal_preview(self) -> None:
        if (
            self._main_view_mode != "multimodal"
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

    def _clear_alerts(self) -> None:
        self._append_log("INFO", "当前界面不再显示独立事件窗口")

    def _append_log(self, level: str, message: str) -> None:
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
