"""
IntelCup 地面站 - 飞控指令面板
预设指令 + 复杂航线 + 自定义指令
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit,
    QLabel, QFrame, QScrollArea, QGroupBox
)


class FlightControlPanel(QWidget):
    command_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("飞控指令")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#1a3a5c;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        sw = QWidget()
        sl = QVBoxLayout(sw)
        sl.setSpacing(6)
        sl.setContentsMargins(0, 0, 0, 0)

        sl.addWidget(self._make_group("基础飞控", [
            ("TAKEOFF", "起飞"),
            ("START_MISSION", "开始巡逻"),
            ("HOLD", "悬停暂停"),
            ("CONTINUE", "继续任务"),
            ("RTL", "一键返航"),
            ("LAND", "降落"),
            ("STATUS", "查询状态"),
        ], "#27ae60"))
        sl.addWidget(self._make_group("复杂航线", [
            ("CIRCLE", "圆形航线"),
            ("FIGURE_EIGHT", "8字航线"),
            ("SQUARE", "正方形航线"),
            ("ZIGZAG", "Z字形航线"),
            ("SPIRAL 20", "螺旋上升20m"),
            ("SPIRAL 40", "螺旋上升40m"),
        ], "#8e44ad"))
        sl.addWidget(self._make_group("参数设置", [
            ("SET_ALT 5", "高度5m"),
            ("SET_ALT 15", "高度15m"),
            ("SET_ALT 30", "高度30m"),
            ("SET_SPEED 2", "速度2m/s"),
            ("SET_SPEED 5", "速度5m/s"),
            ("SET_SPEED 10", "速度10m/s"),
        ], "#2980b9"))

        # 自定义指令
        cg = QGroupBox("自定义指令")
        cg.setStyleSheet("QGroupBox{font-size:13px;font-weight:bold;color:#2c3e50;border:1px solid #ddd;border-radius:6px;margin-top:10px;padding-top:14px;}QGroupBox::title{subcontrol-origin:margin;subcontrol-position:top left;padding:2px 10px;}")
        cv = QVBoxLayout(cg)
        cv.setSpacing(4)
        self.cmd_input = QTextEdit()
        self.cmd_input.setPlaceholderText(
            "输入指令，支持多条（每行一条）\n"
            "GOTO x y [z]      飞到坐标\n"
            "SET_ALT 高度       设置高度\n"
            "SET_SPEED 速度     设置速度\n"
            "CIRCLE             圆形航线\n"
            "FIGURE_EIGHT       8字航线\n"
            "SQUARE             正方形航线\n"
            "ZIGZAG             Z字形航线\n"
            "SPIRAL [高度]      螺旋上升\n"
            "STATUS             查询状态"
        )
        self.cmd_input.setMaximumHeight(100)
        self.cmd_input.setStyleSheet("border:1px solid #ddd;border-radius:4px;padding:6px;font-size:12px;font-family:Consolas;background:#f8f9fa;")
        cv.addWidget(self.cmd_input)

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("QPushButton{background:#3498db;color:white;border:none;border-radius:4px;padding:8px;font-size:13px;font-weight:bold;}QPushButton:hover{background:#2980b9;}")
        send_btn.clicked.connect(self._send_custom)
        cv.addWidget(send_btn)

        sl.addWidget(cg)
        sl.addStretch()
        scroll.setWidget(sw)
        layout.addWidget(scroll)

        self.log = QLabel("就绪")
        self.log.setStyleSheet("font-size:11px;color:#999;padding:4px;")
        self.log.setWordWrap(True)
        layout.addWidget(self.log)

    def _make_group(self, title, commands, color):
        g = QGroupBox(title)
        g.setStyleSheet(f"QGroupBox{{font-size:13px;font-weight:bold;color:#2c3e50;border:1px solid #ddd;border-radius:6px;margin-top:10px;padding-top:14px;}}QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;padding:2px 10px;}}")
        vb = QVBoxLayout(g)
        vb.setSpacing(3)
        for cmd, label in commands:
            btn = QPushButton(label)
            btn.setMinimumHeight(28)
            btn.setStyleSheet(f"QPushButton{{background:#f8f9fa;color:#2c3e50;border:1px solid {color};border-radius:4px;padding:5px 10px;font-size:12px;text-align:left;}}QPushButton:hover{{background:{color}15;border-color:{color};}}")
            btn.clicked.connect(lambda checked, c=cmd: self._send(c))
            vb.addWidget(btn)
        return g

    def _send(self, cmd):
        self.command_sent.emit(cmd)
        self.log.setText(f"已发送: {cmd}")

    def _send_custom(self):
        text = self.cmd_input.toPlainText().strip().upper()
        if not text:
            return
        for line in text.split('\n'):
            line = line.strip()
            if line:
                self.command_sent.emit(line)
        self.log.setText("自定义指令已发送")
        self.cmd_input.clear()
