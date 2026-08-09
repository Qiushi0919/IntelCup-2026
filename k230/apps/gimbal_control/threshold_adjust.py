import gc
import os
import time
import image
import lvgl as lv

from machine import TOUCH
from media.sensor import CAM_CHN_ID_1
from media.display import Display
from apps.gimbal_control.threshold_store import ThresholdStore


class ThresholdAdjustPage:
    """LAB threshold capture, editing and management."""

    DEFAULT_VALUES = (0, 100, -128, 127, -128, 127)
    VALUE_SPECS = (
        ("L下限", 0, 100),
        ("L上限", 0, 100),
        ("A下限", -128, 127),
        ("A上限", -128, 127),
        ("B下限", -128, 127),
        ("B上限", -128, 127),
    )

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.store = ThresholdStore()
        self.touch = TOUCH(0)
        self.values = list(self.DEFAULT_VALUES)
        self.step = 1
        self.step_label = None
        self.editor_active = False
        self.value_labels = []
        self.status_label = None
        self.manage_list = None
        self.lvgl_blank = None
        self.editor_canvas = None
        self.black_background = None

    def display(self):
        self.show_threshold_menu()

    def _make_button(self, parent, text, callback, width=110, height=46,
                     color=0x2563EB):
        btn = lv.btn(parent)
        btn.set_size(width, height)
        btn.set_style_radius(10, 0)
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

    def _clear_page(self):
        self.values = list(self.DEFAULT_VALUES)
        self.step = 1
        self.step_label = None
        self.editor_active = False
        self.value_labels = []
        self.status_label = None
        self.manage_list = None
        self.parent.clean()
        gc.collect()

    def show_threshold_menu(self, event=None):
        self._clear_page()
        self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 总菜单", self.app.show_program_menu,
            105, 42, 0x64748B).set_pos(12, 5)
        self._make_label(self.parent, "阈值调节", 135, 16, 0x111827)
        self._make_label(
            self.parent, "拍摄并编辑 LAB 阈值，或管理已经保存的阈值。",
            135, 48, 0x6B7280)

        confirm = lv.btn(self.parent)
        confirm.set_pos(70, 115)
        confirm.set_size(220, 190)
        confirm.set_style_radius(18, 0)
        confirm.set_style_bg_color(lv.color_hex(0x2563EB), 0)
        confirm.add_event(self.show_capture_page, lv.EVENT.CLICKED, None)
        confirm_label = lv.label(confirm)
        confirm_label.set_text("阈值确认\n\n拍照并编辑 LAB 范围")
        confirm_label.center()

        manage = lv.btn(self.parent)
        manage.set_pos(350, 115)
        manage.set_size(220, 190)
        manage.set_style_radius(18, 0)
        manage.set_style_bg_color(lv.color_hex(0x0F766E), 0)
        manage.add_event(self.show_manage_page, lv.EVENT.CLICKED, None)
        manage_label = lv.label(manage)
        manage_label.set_text("阈值管理\n\n查看或删除保存的阈值")
        manage_label.center()

    def show_capture_page(self, event=None):
        self._clear_page()
        self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 返回", self.show_threshold_menu,
            92, 42, 0x64748B).set_pos(12, 5)
        self._make_label(self.parent, "阈值确认", 125, 16, 0x111827)
        self._make_label(
            self.parent,
            "打开摄像头后，点击右侧圆形快门拍照；点击左上角箭头可取消。",
            45, 90, 0x6B7280)
        self._make_button(
            self.parent, "打开摄像头", self._open_camera,
            200, 70, 0x2563EB).set_pos(220, 175)
        self._make_label(
            self.parent, "拍照后将进入六通道 LAB 阈值编辑。",
            165, 285, 0x9CA3AF)

    def _set_lvgl_visible(self, visible):
        """Make the LVGL application layer transparent during direct draw."""
        try:
            if visible:
                self.app.screen.set_style_bg_opa(255, 0)
                self.app.title_bar.clear_flag(lv.obj.FLAG.HIDDEN)
                self.parent.clear_flag(lv.obj.FLAG.HIDDEN)
            else:
                self.app.screen.set_style_bg_opa(0, 0)
                self.app.title_bar.add_flag(lv.obj.FLAG.HIDDEN)
                self.parent.add_flag(lv.obj.FLAG.HIDDEN)
            self.app.screen.invalidate()
            lv.refr_now(None)
            if visible:
                # lv.refr_now() submits the normal LVGL frame with the
                # Display.show_image default alpha (255).  It therefore
                # restores the default OSD layer after we disabled it below.
                if self.lvgl_blank is not None:
                    Display.show_image(
                        self.lvgl_blank, 0, 0, Display.LAYER_OSD2, alpha=0)
                    Display.show_image(
                        self.lvgl_blank, 0, 0, Display.LAYER_OSD3, alpha=0)
                time.sleep_ms(30)
                self.lvgl_blank = None
                self.editor_canvas = None
                self.black_background = None
            else:
                # Explicitly disable the default LVGL OSD layer with global
                # alpha=0.  Do not rely on per-pixel transparency because the
                # firmware/display combination may retain an opaque old frame.
                self.lvgl_blank = image.Image(640, 480, image.BGRA8888)
                self.lvgl_blank.clear()
                Display.show_image(self.lvgl_blank, alpha=0)
                time.sleep_ms(30)
        except Exception as exc:
            print("threshold LVGL layer:", exc)

    def _open_camera(self, event=None):
        captured_image = None
        overlay = image.Image(640, 480, image.RGB565)
        overlay.clear()
        Display.show_image(overlay, 0, 0, Display.LAYER_OSD3)
        time.sleep_ms(100)
        try:
            while True:
                points = self.touch.read(1)
                if len(points):
                    point = points[0]
                    if point.event == TOUCH.EVENT_DOWN:
                        if point.x < 75 and point.y < 75:
                            break
                        if 520 < point.x < 640 and 150 < point.y < 320:
                            photo = self.app.app_manager.pl.sensor.snapshot(
                                chn=CAM_CHN_ID_1)
                            # Keep the frozen RGB565 image in RAM.  The
                            # threshold editor must not use SD-card files or
                            # compressed images because both make interaction
                            # noticeably slower on K230.
                            captured_image = photo.mean_pooled(2, 2)
                            photo = None
                            gc.collect()
                            # The direct image editor is on a separate OSD
                            # layer.  Make the old LVGL page fully transparent
                            # before drawing it, otherwise the opaque app
                            # background remains visible above the preview.
                            self._set_lvgl_visible(False)
                            break

                frame = self.app.app_manager.pl.sensor.snapshot(
                    chn=CAM_CHN_ID_1)
                frame.draw_circle(580, 235, 32, color=(255, 255, 255),
                                  thickness=4)
                frame.draw_circle(580, 235, 24, color=(255, 255, 255),
                                  thickness=3, fill=True)
                frame.draw_line(20, 30, 55, 30, color=(255, 255, 255),
                                thickness=4)
                frame.draw_line(20, 30, 38, 13, color=(255, 255, 255),
                                thickness=4)
                frame.draw_line(20, 30, 38, 47, color=(255, 255, 255),
                                thickness=4)
                Display.show_image(frame, 0, 0, Display.LAYER_OSD3)
                time.sleep_ms(20)
        except Exception as exc:
            print("threshold camera:", exc)
        finally:
            clear = image.Image(640, 480, image.RGB565)
            clear.clear()
            Display.show_image(clear, 0, 0, Display.LAYER_OSD3)
            time.sleep_ms(100)

        if captured_image is not None:
            try:
                self._run_direct_editor(captured_image)
            finally:
                captured_image = None
                gc.collect()
                self.show_threshold_menu()
                self._set_lvgl_visible(True)

    def _current_values(self):
        raw = self.values
        return [
            min(raw[0], raw[1]), max(raw[0], raw[1]),
            min(raw[2], raw[3]), max(raw[2], raw[3]),
            min(raw[4], raw[5]), max(raw[4], raw[5]),
        ]

    def _draw_direct_button(self, canvas, x, y, width, height, text,
                            color=(90, 120, 160), font_size=24):
        canvas.draw_rectangle(
            x, y, width, height, color=color, thickness=2, fill=True)
        text_x = x + max(4, (width - len(text) * font_size) // 2)
        text_y = y + max(2, (height - font_size) // 2)
        canvas.draw_string_advanced(
            text_x, text_y, font_size, text, color=(255, 255, 255))

    def _draw_direct_ui(self, canvas):
        canvas.clear()
        canvas.draw_rectangle(
            0, 0, 640, 480, color=(245, 247, 250), thickness=1,
            fill=True)
        canvas.draw_string_advanced(
            12, 8, 28, "LAB阈值编辑", color=(20, 30, 45))
        canvas.draw_string_advanced(
            335, 8, 22, "步长", color=(20, 30, 45))
        self._draw_direct_button(canvas, 400, 4, 55, 36, "-1")
        self._draw_direct_button(
            canvas, 535, 4, 55, 36, "+1", (35, 100, 190))

        canvas.draw_rectangle(
            4, 54, 322, 242, color=(35, 45, 55), thickness=1,
            fill=True)
        for index, spec in enumerate(self.VALUE_SPECS):
            y = 52 + index * 52
            canvas.draw_string_advanced(
                338, y + 9, 21, spec[0], color=(30, 40, 55))
            self._draw_direct_button(canvas, 430, y, 48, 40, "-")
            self._draw_direct_button(
                canvas, 550, y, 48, 40, "+", (35, 100, 190))

        self._draw_direct_button(
            canvas, 330, 392, 130, 58, "保存", (25, 145, 75), 26)
        self._draw_direct_button(
            canvas, 480, 392, 130, 58, "放弃", (200, 55, 55), 26)

    def _draw_direct_values(self, canvas, status):
        canvas.draw_rectangle(
            464, 4, 62, 36, color=(255, 255, 255), thickness=1,
            fill=True)
        canvas.draw_string_advanced(
            475, 9, 24, str(self.step), color=(20, 30, 45))
        for index in range(6):
            y = 52 + index * 52
            canvas.draw_rectangle(
                484, y, 60, 40, color=(255, 255, 255), thickness=1,
                fill=True)
            canvas.draw_string_advanced(
                489, y + 9, 21, str(self.values[index]),
                color=(20, 30, 45))
        canvas.draw_rectangle(
            4, 300, 322, 70, color=(245, 247, 250), thickness=1,
            fill=True)
        canvas.draw_string_advanced(
            10, 310, 20, status, color=(45, 75, 110))

    def _render_direct_preview(self, canvas, source, status=None):
        if status is None:
            status = "点击按钮调整，预览实时更新"
        # Use a fresh image copy exactly like the proven offline-threshold
        # example.  RGB565 copy_from() is unreliable on some CanMV firmware
        # builds and can leave the reusable destination buffer filled with 0.
        processed = source.copy()
        processed.binary([tuple(self._current_values())])
        # RGB565 binary black is transparent on this OSD path.  OSD2 carries
        # an opaque black background, so transparent pixels intentionally
        # reveal black instead of the live camera video.
        canvas.draw_image(processed, 5, 55, alpha=256)
        self._draw_direct_values(canvas, status)
        # The latest on-device test (a completely black screen when the black
        # cover was on OSD3) proves OSD3 is above OSD2 on this firmware.  Put
        # the editor on OSD3 and its black background on OSD2.
        Display.show_image(canvas, 0, 0, Display.LAYER_OSD3, alpha=255)
        processed = None

    def _direct_hit_test(self, x, y):
        if 400 <= x < 455 and 4 <= y < 40:
            return ("step", -1)
        if 535 <= x < 590 and 4 <= y < 40:
            return ("step", 1)
        for index in range(6):
            row_y = 52 + index * 52
            if row_y <= y < row_y + 40:
                if 430 <= x < 478:
                    return ("value", index, -1)
                if 550 <= x < 598:
                    return ("value", index, 1)
        if 330 <= x < 460 and 392 <= y < 450:
            return ("save",)
        if 480 <= x < 610 and 392 <= y < 450:
            return ("discard",)
        return None

    def _run_direct_editor(self, source):
        self.values = list(self.DEFAULT_VALUES)
        self.step = 1
        # Cover the permanently bound VIDEO1 camera layer.  ARGB black uses an
        # explicit alpha value of 255, so it is opaque rather than color-keyed.
        self.black_background = image.Image(640, 480, image.ARGB8888)
        self.black_background.draw_rectangle(
            0, 0, 640, 480, color=(255, 0, 0, 0), thickness=1, fill=True)
        Display.show_image(
            self.black_background, 0, 0, Display.LAYER_OSD2, alpha=255)
        # Keep the exact RGB565 drawing path that is known to work on this
        # board.  Its transparent black pixels reveal the black OSD2 layer.
        canvas = image.Image(640, 480, image.RGB565)
        self.editor_canvas = canvas
        try:
            print(
                "LAB source:", source.width(), source.height(),
                source.format(), source.get_pixel(
                    source.width() // 2, source.height() // 2))
        except Exception as exc:
            print("LAB source inspect:", exc)
        self._draw_direct_ui(canvas)
        self._render_direct_preview(canvas, source)
        saved = False
        try:
            while True:
                os.exitpoint()
                points = self.touch.read(1)
                if not len(points):
                    time.sleep_ms(10)
                    continue
                point = points[0]
                if point.event != TOUCH.EVENT_DOWN:
                    time.sleep_ms(10)
                    continue
                action = self._direct_hit_test(point.x, point.y)
                if action is None:
                    continue
                if action[0] == "discard":
                    break
                if action[0] == "save":
                    item = self.store.add(self._current_values())
                    if item:
                        saved = True
                        break
                    self._render_direct_preview(
                        canvas, source, "保存失败或阈值数量已达30个")
                    continue
                if action[0] == "step":
                    self.step = max(1, min(50, self.step + action[1]))
                elif action[0] == "value":
                    index = action[1]
                    spec = self.VALUE_SPECS[index]
                    value = self.values[index] + action[2] * self.step
                    self.values[index] = max(spec[1], min(spec[2], value))
                self._render_direct_preview(canvas, source)
        except Exception as exc:
            print("LAB direct editor:", exc)
        finally:
            # Keep the canvas alive until _set_lvgl_visible(True) submits a
            # fresh LVGL frame to this same display layer.
            gc.collect()
        return saved

    def show_manage_page(self, event=None):
        self._clear_page()
        self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 返回", self.show_threshold_menu,
            92, 42, 0x64748B).set_pos(12, 5)
        self._make_label(self.parent, "阈值管理", 125, 16, 0x111827)
        self.manage_list = lv.obj(self.parent)
        self.manage_list.set_pos(15, 58)
        self.manage_list.set_size(610, 340)
        self.manage_list.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self.manage_list.set_style_border_width(0, 0)
        self.manage_list.set_style_pad_all(6, 0)
        self.manage_list.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.manage_list.set_style_pad_row(6, 0)
        self.manage_list.set_scroll_dir(lv.DIR.VER)
        self.manage_list.set_scrollbar_mode(lv.SCROLLBAR_MODE.AUTO)
        self._refresh_manage_list()

    def _refresh_manage_list(self):
        self.manage_list.clean()
        thresholds = self.store.load()
        if not thresholds:
            empty = lv.label(self.manage_list)
            empty.set_text("还没有保存 LAB 阈值。")
            empty.set_style_text_color(lv.color_hex(0x6B7280), 0)
            return
        for item in thresholds:
            row = lv.obj(self.manage_list)
            row.set_size(lv.pct(100), 65)
            row.set_style_border_width(1, 0)
            row.set_style_border_color(lv.color_hex(0xE5E7EB), 0)
            row.set_style_radius(8, 0)
            row.set_style_pad_all(0, 0)
            row.clear_flag(lv.obj.FLAG.SCROLLABLE)
            self._make_label(row, item["name"], 12, 10, 0x111827)
            self._make_label(
                row, "({},{},{},{},{},{})".format(*item["values"]),
                12, 36, 0x6B7280)
            self._make_button(
                row, "删除",
                lambda event, threshold_id=item["id"]:
                    self._delete_threshold(threshold_id),
                75, 40, 0xDC2626).set_pos(505, 12)

    def _delete_threshold(self, threshold_id):
        if self.store.delete(threshold_id):
            self._refresh_manage_list()

    def cleanup(self):
        self.values = list(self.DEFAULT_VALUES)
        self.step = 1
        self.step_label = None
        self.editor_active = False
        self.value_labels = []
        self.status_label = None
        self.manage_list = None
        self.lvgl_blank = None
        self.editor_canvas = None
        self.black_background = None
        gc.collect()
