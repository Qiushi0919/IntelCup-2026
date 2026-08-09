import gc
import time
import lvgl as lv

from temp import motor
from apps.gimbal_control.position_store import PositionStore


class ManualControlPage:
    """Manual two-axis control page using absolute-position mode only."""

    PAN_ID = 0
    TILT_ID = 1
    PAN_MIN = -6
    PAN_MAX = 22
    TILT_MIN = -4
    TILT_MAX = 21
    STEP_CHOICES = (1, 2, 5)

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.pan_angle = app.current_pan
        self.tilt_angle = app.current_tilt
        self.step = 1
        self.store = PositionStore()
        self.pan_value_label = None
        self.tilt_value_label = None
        self.step_label = None
        self.status_label = None

    def display(self):
        motor.set_uart(self.app.app_manager.gimbal_uart)
        self._create_ui()

    def _make_button(self, parent, text, callback, width=105, height=62,
                     color=0x2563EB):
        btn = lv.btn(parent)
        btn.set_size(width, height)
        btn.set_style_radius(12, 0)
        btn.set_style_bg_color(lv.color_hex(color), 0)
        btn.set_style_shadow_width(0, 0)
        btn.add_event(callback, lv.EVENT.CLICKED, None)
        label = lv.label(btn)
        label.set_text(text)
        label.center()
        return btn

    def _make_label(self, parent, text, x, y, color=0x1F2937):
        label = lv.label(parent)
        label.set_text(text)
        label.set_pos(x, y)
        label.set_style_text_color(lv.color_hex(color), 0)
        return label

    def _create_ui(self):
        back_btn = self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 菜单", self.app.show_program_menu,
            92, 42, 0x64748B)
        back_btn.set_pos(12, 5)

        self.status_label = self._make_label(
            self.parent, "手动调节 · 绝对位置模式", 120, 16, 0x15803D)
        self._make_label(self.parent, "步长", 390, 16)
        self._make_button(self.parent, "-", self._decrease_step,
                          44, 40, 0x64748B).set_pos(445, 5)
        self.step_label = self._make_label(
            self.parent, "{}°".format(self.step), 510, 16)
        self._make_button(self.parent, "+", self._increase_step,
                          44, 40, 0x64748B).set_pos(565, 5)

        pan_panel = self._create_axis_panel(
            15, 58, "水平轴  ID 0", "范围 -6° ～ 22°")
        self._make_button(pan_panel, "向左", self._pan_left,
                          105, 70).set_pos(24, 73)
        self._make_button(pan_panel, "向右", self._pan_right,
                          105, 70).set_pos(171, 73)
        self.pan_value_label = self._make_label(
            pan_panel, "目标：{}°".format(self.pan_angle), 103, 164, 0x111827)

        tilt_panel = self._create_axis_panel(
            325, 58, "俯仰轴  ID 1", "范围 -4° ～ 21°")
        self._make_button(tilt_panel, "向下", self._tilt_down,
                          105, 70, 0x0F766E).set_pos(24, 73)
        self._make_button(tilt_panel, "向上", self._tilt_up,
                          105, 70, 0x0F766E).set_pos(171, 73)
        self.tilt_value_label = self._make_label(
            tilt_panel, "目标：{}°".format(self.tilt_angle), 103, 164, 0x111827)

        self._make_button(self.parent, "双轴回零", self._home_both,
                          150, 62, 0x7C3AED).set_pos(155, 298)
        self._make_button(self.parent, "保存位置", self._save_position,
                          150, 62, 0xD97706).set_pos(335, 298)
        self._make_label(
            self.parent,
            "仅使用已验证的绝对角度(A)和回零(B)命令。",
            140, 380, 0x6B7280)

    def _create_axis_panel(self, x, y, title, range_text):
        panel = lv.obj(self.parent)
        panel.set_pos(x, y)
        panel.set_size(300, 225)
        panel.set_style_radius(14, 0)
        panel.set_style_border_width(0, 0)
        self._make_label(panel, title, 16, 12, 0x111827)
        self._make_label(panel, range_text, 160, 12, 0x6B7280)
        return panel

    @staticmethod
    def _clamp(value, minimum, maximum):
        return max(minimum, min(maximum, value))

    def _send_angle(self, motor_id, angle, axis_name):
        try:
            ok = motor.set_absolute_angle(motor_id, angle)
            if ok:
                self._show_status(
                    "{}：ID {}  {}°".format(axis_name, motor_id, angle), True)
            else:
                self._show_status("发送失败", False)
            return ok
        except Exception as exc:
            print("gimbal absolute position:", exc)
            self._show_status("串口发送错误", False)
            return False

    def _show_status(self, text, ok):
        if self.status_label is not None:
            self.status_label.set_text(text)
            color = 0x15803D if ok else 0xDC2626
            self.status_label.set_style_text_color(lv.color_hex(color), 0)

    def _decrease_step(self, event=None):
        index = self.STEP_CHOICES.index(self.step)
        self.step = self.STEP_CHOICES[max(0, index - 1)]
        self.step_label.set_text("{}°".format(self.step))

    def _increase_step(self, event=None):
        index = self.STEP_CHOICES.index(self.step)
        self.step = self.STEP_CHOICES[min(len(self.STEP_CHOICES) - 1,
                                         index + 1)]
        self.step_label.set_text("{}°".format(self.step))

    def _set_pan(self, requested_angle):
        target = self._clamp(requested_angle, self.PAN_MIN, self.PAN_MAX)
        if self._send_angle(self.PAN_ID, target, "水平轴"):
            self.pan_angle = target
            self.app.current_pan = target
            self.pan_value_label.set_text("目标：{}°".format(target))

    def _set_tilt(self, requested_angle):
        target = self._clamp(requested_angle, self.TILT_MIN, self.TILT_MAX)
        if self._send_angle(self.TILT_ID, target, "俯仰轴"):
            self.tilt_angle = target
            self.app.current_tilt = target
            self.tilt_value_label.set_text("目标：{}°".format(target))

    def _pan_left(self, event=None):
        self._set_pan(self.pan_angle - self.step)

    def _pan_right(self, event=None):
        self._set_pan(self.pan_angle + self.step)

    def _tilt_down(self, event=None):
        self._set_tilt(self.tilt_angle - self.step)

    def _tilt_up(self, event=None):
        self._set_tilt(self.tilt_angle + self.step)

    def _home_both(self, event=None):
        try:
            pan_ok = motor.go_to_home(self.PAN_ID)
            time.sleep_ms(10)
            tilt_ok = motor.go_to_home(self.TILT_ID)
            if pan_ok and tilt_ok:
                self.pan_angle = 0
                self.tilt_angle = 0
                self.app.current_pan = 0
                self.app.current_tilt = 0
                self.pan_value_label.set_text("目标：0°")
                self.tilt_value_label.set_text("目标：0°")
                self._show_status("双轴回零命令已发送", True)
            else:
                self._show_status("回零命令发送失败", False)
        except Exception as exc:
            print("gimbal home:", exc)
            self._show_status("回零发送错误", False)

    def _save_position(self, event=None):
        if self.store.add(self.pan_angle, self.tilt_angle, 1):
            count = len(self.store.load())
            self._show_status(
                "已保存点{}：水平{}° 俯仰{}°".format(
                    count, self.pan_angle, self.tilt_angle), True)
        else:
            self._show_status("保存失败或点位已达20个", False)

    def cleanup(self):
        # Position mode stops at its target; no speed/stop command is emitted.
        self.pan_value_label = None
        self.tilt_value_label = None
        self.step_label = None
        self.status_label = None
        gc.collect()
