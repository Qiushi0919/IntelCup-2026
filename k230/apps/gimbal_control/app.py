import gc
import lvgl as lv

from ybMain.base_app import BaseApp
from apps.gimbal_control.manual_control import ManualControlPage
from apps.gimbal_control.fixed_point import FixedPointPage
from apps.gimbal_control.threshold_adjust import ThresholdAdjustPage
from apps.gimbal_control.task_selection import TaskSelectionPage


class App(BaseApp):
    """Gimbal application shell and subprogram menu."""

    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.content = None
        self.current_page = None
        self.current_pan = 0
        self.current_tilt = 0
        super().__init__(app_manager, name="云台控制", icon=None)

    def initialize(self):
        self.content = lv.obj(self.screen)
        self.content.set_size(lv.pct(100), 420)
        self.content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.content.set_style_bg_color(lv.color_hex(0xF3F4F6), 0)
        self.content.set_style_border_width(0, 0)
        self.content.set_style_pad_all(0, 0)
        self.content.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)
        self.show_program_menu()

    def _make_label(self, parent, text, x, y, color=0x1F2937):
        label = lv.label(parent)
        label.set_text(text)
        label.set_pos(x, y)
        label.set_style_text_color(lv.color_hex(color), 0)
        return label

    def show_program_menu(self, event=None):
        if self.current_page is not None:
            self.current_page.cleanup()
            self.current_page = None
        self.content.clean()

        title = self._make_label(self.content, "选择子程序", 30, 28, 0x111827)
        title.set_style_text_font(self.app_manager.font_16, 0)
        self._make_label(
            self.content,
            "选择一种云台工作方式。运行中的子程序返回后会释放页面资源。",
            30, 55, 0x6B7280)

        self._make_program_card(
            20, 82, "手动调节", "手动控制双轴并保存点位",
            lv.SYMBOL.SETTINGS, 0x2563EB, self._open_manual_control)
        self._make_program_card(
            330, 82, "定点移动", "按设定顺序运行保存点位",
            lv.SYMBOL.FILE, 0x0F766E, self._open_fixed_point)
        self._make_program_card(
            20, 222, "阈值调节", "拍照编辑并管理 LAB 阈值",
            lv.SYMBOL.IMAGE, 0xD97706, self._open_threshold_adjust)
        self._make_program_card(
            330, 222, "任务选择", "选择需要 K230 执行的任务",
            lv.SYMBOL.PLAY, 0x7C3AED, self._open_task_selection)

        self._make_label(
            self.content, "云台运动与视觉参数均保存在 /sdcard/configs",
            30, 372, 0x9CA3AF)

    def _make_program_card(self, x, y, name_text, description_text, symbol,
                           color, callback):
        card = lv.btn(self.content)
        card.set_pos(x, y)
        card.set_size(290, 125)
        card.set_style_radius(18, 0)
        card.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        card.set_style_bg_color(lv.color_hex(0xF3F4F6), lv.STATE.PRESSED)
        card.set_style_border_width(2, 0)
        card.set_style_border_color(lv.color_hex(color), 0)
        card.set_style_shadow_width(10, 0)
        card.set_style_shadow_opa(30, 0)
        card.add_event(callback, lv.EVENT.CLICKED, None)

        icon = lv.label(card)
        icon.set_text(symbol)
        icon.set_pos(16, 16)
        icon.set_style_text_color(lv.color_hex(color), 0)
        name = lv.label(card)
        name.set_text(name_text)
        name.set_pos(55, 16)
        name.set_style_text_color(lv.color_hex(0x111827), 0)
        description = lv.label(card)
        description.set_text(description_text)
        description.set_pos(16, 58)
        description.set_style_text_color(lv.color_hex(0x6B7280), 0)
        arrow = lv.label(card)
        arrow.set_text(lv.SYMBOL.RIGHT)
        arrow.align(lv.ALIGN.BOTTOM_RIGHT, -12, -12)
        arrow.set_style_text_color(lv.color_hex(color), 0)

    def _open_manual_control(self, event=None):
        self.content.clean()
        self.current_page = ManualControlPage(self, self.content)
        self.current_page.display()

    def _open_fixed_point(self, event=None):
        self.content.clean()
        self.current_page = FixedPointPage(self, self.content)
        self.current_page.display()

    def _open_threshold_adjust(self, event=None):
        self.content.clean()
        self.current_page = ThresholdAdjustPage(self, self.content)
        self.current_page.display()

    def _open_task_selection(self, event=None):
        self.content.clean()
        self.current_page = TaskSelectionPage(self, self.content)
        self.current_page.display()

    def deinitialize(self):
        if self.current_page is not None:
            self.current_page.cleanup()
            self.current_page = None
        if self.content is not None:
            self.content.delete()
            self.content = None
        gc.collect()
