import gc
import lvgl as lv

from apps.gimbal_control.laser_tracking import LaserTrackingPage
from apps.gimbal_control.laser_tracing import LaserTracingPage


class TaskSelectionPage:
    """Menu for autonomous K230 gimbal tasks."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.task_list = None
        self.child_page = None

    def display(self):
        self.show_menu()

    def _make_label(self, parent, text, x, y, color=0x1F2937):
        label = lv.label(parent)
        label.set_text(text)
        label.set_pos(x, y)
        label.set_style_text_color(lv.color_hex(color), 0)
        return label

    def _make_button(self, parent, text, callback, width=105, height=42,
                     color=0x64748B):
        button = lv.btn(parent)
        button.set_size(width, height)
        button.set_style_radius(10, 0)
        button.set_style_bg_color(lv.color_hex(color), 0)
        button.set_style_shadow_width(0, 0)
        button.set_style_pad_all(0, 0)
        button.add_event(callback, lv.EVENT.CLICKED, None)
        label = lv.label(button)
        label.set_text(text)
        label.center()
        return button

    def show_menu(self, event=None):
        if self.child_page is not None:
            self.child_page.cleanup()
            self.child_page = None
        self.parent.clean()
        self.task_list = None

        self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 总菜单",
            self.app.show_program_menu).set_pos(12, 5)
        self._make_label(self.parent, "任务选择", 135, 16, 0x111827)
        self._make_label(
            self.parent, "选择需要 K230 独立完成的任务程序。",
            135, 45, 0x6B7280)

        self.task_list = lv.obj(self.parent)
        self.task_list.set_pos(20, 82)
        self.task_list.set_size(600, 295)
        self.task_list.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self.task_list.set_style_border_width(1, 0)
        self.task_list.set_style_border_color(lv.color_hex(0xE5E7EB), 0)
        self.task_list.set_style_radius(14, 0)
        self.task_list.set_style_pad_all(0, 0)
        self.task_list.clear_flag(lv.obj.FLAG.SCROLLABLE)

        task = lv.btn(self.task_list)
        task.set_pos(20, 20)
        task.set_size(560, 105)
        task.set_style_radius(12, 0)
        task.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        task.set_style_bg_color(lv.color_hex(0xF3F4F6), lv.STATE.PRESSED)
        task.set_style_border_width(2, 0)
        task.set_style_border_color(lv.color_hex(0xDC2626), 0)
        task.set_style_shadow_width(0, 0)
        task.add_event(self._open_laser_tracking, lv.EVENT.CLICKED, None)

        icon = lv.label(task)
        icon.set_text(lv.SYMBOL.GPS)
        icon.set_pos(18, 18)
        icon.set_style_text_color(lv.color_hex(0xDC2626), 0)
        self._make_label(task, "激光跟踪", 62, 17, 0x111827)
        self._make_label(
            task, "识别红/绿激光，PID 控制云台使绿光跟随红光",
            18, 56, 0x6B7280)
        arrow = lv.label(task)
        arrow.set_text(lv.SYMBOL.RIGHT)
        arrow.align(lv.ALIGN.RIGHT_MID, -18, 0)
        arrow.set_style_text_color(lv.color_hex(0xDC2626), 0)

        tracing = lv.btn(self.task_list)
        tracing.set_pos(20, 145)
        tracing.set_size(560, 105)
        tracing.set_style_radius(12, 0)
        tracing.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        tracing.set_style_bg_color(
            lv.color_hex(0xF3F4F6), lv.STATE.PRESSED)
        tracing.set_style_border_width(2, 0)
        tracing.set_style_border_color(lv.color_hex(0x0891B2), 0)
        tracing.set_style_shadow_width(0, 0)
        tracing.add_event(self._open_laser_tracing, lv.EVENT.CLICKED, None)

        tracing_icon = lv.label(tracing)
        tracing_icon.set_text(lv.SYMBOL.REFRESH)
        tracing_icon.set_pos(18, 18)
        tracing_icon.set_style_text_color(lv.color_hex(0x0891B2), 0)
        self._make_label(tracing, "激光循迹", 62, 17, 0x111827)
        self._make_label(
            tracing, "提取最大黑线骨架，控制红色激光沿路径运行一次",
            18, 56, 0x6B7280)
        tracing_arrow = lv.label(tracing)
        tracing_arrow.set_text(lv.SYMBOL.RIGHT)
        tracing_arrow.align(lv.ALIGN.RIGHT_MID, -18, 0)
        tracing_arrow.set_style_text_color(lv.color_hex(0x0891B2), 0)

    def _open_laser_tracking(self, event=None):
        self.parent.clean()
        self.child_page = LaserTrackingPage(
            self.app, self.parent, self.show_menu)
        self.child_page.display()

    def _open_laser_tracing(self, event=None):
        self.parent.clean()
        self.child_page = LaserTracingPage(
            self.app, self.parent, self.show_menu)
        self.child_page.display()

    def cleanup(self):
        if self.child_page is not None:
            self.child_page.cleanup()
            self.child_page = None
        self.task_list = None
        gc.collect()
