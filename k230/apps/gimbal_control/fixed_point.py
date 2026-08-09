import gc
import time
import lvgl as lv

from temp import motor
from apps.gimbal_control.position_store import PositionStore


class FixedPointPage:
    """Edit and run an ordered list of saved gimbal positions."""

    PAN_ID = 0
    TILT_ID = 1
    HOME_WAIT_MS = 1200

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.store = PositionStore()
        self.list_panel = None
        self.status_label = None
        self.timer = None
        self.running = False
        self.run_positions = []
        self.run_index = 0
        self.run_generation = 0

    def display(self):
        motor.set_uart(self.app.app_manager.gimbal_uart)
        self._create_ui()
        self._refresh_list()

    def _make_button(self, parent, text, callback, width=70, height=40,
                     color=0x2563EB):
        btn = lv.btn(parent)
        btn.set_size(width, height)
        btn.set_style_radius(9, 0)
        btn.set_style_bg_color(lv.color_hex(color), 0)
        btn.set_style_shadow_width(0, 0)
        btn.set_style_pad_all(0, 0)
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
        self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 菜单", self.app.show_program_menu,
            92, 42, 0x64748B).set_pos(12, 5)
        self.status_label = self._make_label(
            self.parent, "定点移动 · 等待运行", 120, 16, 0x15803D)
        self._make_button(
            self.parent, "立即回零", self._home_now,
            110, 42, 0xDC2626).set_pos(515, 5)

        self.list_panel = lv.obj(self.parent)
        self.list_panel.set_pos(15, 55)
        self.list_panel.set_size(610, 270)
        self.list_panel.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self.list_panel.set_style_border_width(0, 0)
        self.list_panel.set_style_radius(12, 0)
        self.list_panel.set_style_pad_all(5, 0)
        self.list_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.list_panel.set_style_pad_row(5, 0)
        self.list_panel.set_scroll_dir(lv.DIR.VER)
        self.list_panel.set_scrollbar_mode(lv.SCROLLBAR_MODE.AUTO)

        self._make_button(
            self.parent, "运行全部点位", self._start_run,
            180, 58, 0x16A34A).set_pos(230, 340)

    def _refresh_list(self):
        self.list_panel.clean()
        positions = self.store.load()
        if not positions:
            empty = lv.label(self.list_panel)
            empty.set_text("还没有保存点位，请先到“手动调节”中保存。")
            empty.set_style_text_color(lv.color_hex(0x6B7280), 0)
            return

        for index, point in enumerate(positions):
            row = lv.obj(self.list_panel)
            row.set_size(lv.pct(100), 62)
            row.set_style_radius(8, 0)
            row.set_style_border_width(1, 0)
            row.set_style_border_color(lv.color_hex(0xE5E7EB), 0)
            row.set_style_pad_all(0, 0)
            row.clear_flag(lv.obj.FLAG.SCROLLABLE)

            self._make_label(
                row,
                "点{}  水平{}°  俯仰{}°".format(
                    index + 1, point["pan"], point["tilt"]),
                10, 21, 0x111827)
            self._make_button(
                row, "↑", lambda e, i=index: self._move_position(i, -1),
                36, 36, 0x64748B).set_pos(205, 12)
            self._make_button(
                row, "↓", lambda e, i=index: self._move_position(i, 1),
                36, 36, 0x64748B).set_pos(246, 12)
            self._make_label(row, "停留", 292, 21, 0x6B7280)
            self._make_button(
                row, "-", lambda e, i=index: self._change_dwell(i, -1),
                36, 36, 0x0F766E).set_pos(340, 12)
            self._make_label(
                row, "{}秒".format(point["dwell"]), 384, 21, 0x111827)
            self._make_button(
                row, "+", lambda e, i=index: self._change_dwell(i, 1),
                36, 36, 0x0F766E).set_pos(438, 12)
            self._make_button(
                row, "删除", lambda e, i=index: self._delete_position(i),
                66, 36, 0xDC2626).set_pos(500, 12)

    def _cancel_run(self, message=None):
        # Invalidate every callback captured by the previous run.  A numeric
        # generation is reliable across CanMV/LVGL Python wrapper objects.
        self.run_generation += 1
        if self.timer is not None:
            try:
                lv.timer_del(self.timer)
            except Exception:
                pass
            self.timer = None
        was_running = self.running
        self.running = False
        self.run_positions = []
        self.run_index = 0
        if was_running and message:
            self._show_status(message, False)

    def _delete_position(self, index):
        self._cancel_run("任务已取消")
        if self.store.delete(index):
            self._show_status("点位已删除", True)
            self._refresh_list()
        else:
            self._show_status("删除失败", False)

    def _change_dwell(self, index, delta):
        self._cancel_run("任务已取消")
        positions = self.store.load()
        if index < 0 or index >= len(positions):
            return
        value = positions[index]["dwell"] + delta
        if self.store.set_dwell(index, value):
            self._refresh_list()

    def _move_position(self, index, offset):
        self._cancel_run("任务已取消")
        if self.store.move(index, offset):
            self._show_status("点位顺序已更新", True)
            self._refresh_list()

    def _start_run(self, event=None):
        self._cancel_run()
        self.run_positions = self.store.load()
        if not self.run_positions:
            self._show_status("没有可运行的点位", False)
            return
        self.running = True
        self.run_index = 0
        # Establish the same mechanical reference before every run.  This also
        # clears any residual driver state left by the previous sequence.
        try:
            pan_ok = motor.go_to_home(self.PAN_ID)
            time.sleep_ms(10)
            tilt_ok = motor.go_to_home(self.TILT_ID)
            if not (pan_ok and tilt_ok):
                self._cancel_run()
                self._show_status("运行前回零命令发送失败", False)
                return
            self.app.current_pan = 0
            self.app.current_tilt = 0
            self._show_status("运行前双轴回零，请稍候", True)
            generation = self.run_generation
            self.timer = lv.timer_create(
                lambda timer, gen=generation: self._on_home_finished(timer, gen),
                self.HOME_WAIT_MS, None)
        except Exception as exc:
            print("prepare fixed point run:", exc)
            self._cancel_run()
            self._show_status("运行准备失败", False)

    def _on_home_finished(self, timer, generation):
        try:
            lv.timer_del(timer)
        except Exception:
            pass
        if generation != self.run_generation:
            return
        self.timer = None
        if self.running:
            self._move_to_current_point()

    def _move_to_current_point(self):
        if not self.running or self.run_index >= len(self.run_positions):
            return
        point = self.run_positions[self.run_index]
        try:
            pan_ok = motor.set_absolute_angle(self.PAN_ID, point["pan"])
            time.sleep_ms(10)
            tilt_ok = motor.set_absolute_angle(self.TILT_ID, point["tilt"])
            if not (pan_ok and tilt_ok):
                self._cancel_run()
                self._show_status("点{}发送失败".format(self.run_index + 1), False)
                return
            self.app.current_pan = point["pan"]
            self.app.current_tilt = point["tilt"]
            self._show_status(
                "运行点{}/{}，停留{}秒".format(
                    self.run_index + 1, len(self.run_positions), point["dwell"]),
                True)
            generation = self.run_generation
            self.timer = lv.timer_create(
                lambda timer, gen=generation: self._on_dwell_finished(timer, gen),
                point["dwell"] * 1000, None)
        except Exception as exc:
            print("run fixed positions:", exc)
            self._cancel_run()
            self._show_status("串口发送错误", False)

    def _on_dwell_finished(self, timer, generation):
        try:
            lv.timer_del(timer)
        except Exception:
            pass
        if generation != self.run_generation:
            return
        self.timer = None
        if not self.running:
            return
        if self.run_index >= len(self.run_positions) - 1:
            total = len(self.run_positions)
            self.running = False
            self.run_positions = []
            self._show_status("运行完成，停在点{}".format(total), True)
            return
        self.run_index += 1
        self._move_to_current_point()

    def _home_now(self, event=None):
        self._cancel_run()
        try:
            pan_ok = motor.go_to_home(self.PAN_ID)
            time.sleep_ms(10)
            tilt_ok = motor.go_to_home(self.TILT_ID)
            if pan_ok and tilt_ok:
                self.app.current_pan = 0
                self.app.current_tilt = 0
                self._show_status("任务已结束，双轴正在回零", True)
            else:
                self._show_status("回零命令发送失败", False)
        except Exception as exc:
            print("fixed point home:", exc)
            self._show_status("回零发送错误", False)

    def _show_status(self, text, ok):
        if self.status_label is not None:
            self.status_label.set_text(text)
            color = 0x15803D if ok else 0xDC2626
            self.status_label.set_style_text_color(lv.color_hex(color), 0)

    def cleanup(self):
        self._cancel_run()
        self.list_panel = None
        self.status_label = None
        gc.collect()
