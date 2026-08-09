import lvgl as lv

class RGBTestPage:
    def __init__(self, app, parent, config, text_config):
        self.app = app
        self.parent = parent
        self.config = config
        self.text_config = text_config
        self.r_slider = None
        self.g_slider = None
        self.b_slider = None
        self.color_preview = None
        self.rgb_switch = None
        self.r_value = 0
        self.g_value = 0
        self.b_value = 0
        self.rgb_led_enabled = False

    def display(self):
        # 清理之前的内容
        self.parent.clean()

        # 标题
        title = lv.label(self.parent)
        title.set_text(self.text_config.get_section("hardware_test")["rgb"]["title"])
        title.set_style_text_font(lv.font_yb_cn_16, 0)
        title.set_style_text_color(lv.color_hex(0x333333), 0)
        title.align(lv.ALIGN.TOP_LEFT, 0, 10)

        # 开关按钮和文字
        switch_label = lv.label(self.parent)
        switch_label.set_text(self.text_config.get_section("hardware_test")["rgb"]["open"])
        switch_label.align(lv.ALIGN.TOP_LEFT, 20, 50)

        self.rgb_switch = lv.switch(self.parent)
        self.rgb_switch.align_to(switch_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        # self.rgb_switch.add_state(lv.STATE.CHECKED)
        self.rgb_switch.add_event(self.on_rgb_switch, lv.EVENT.VALUE_CHANGED, None)

        # 颜色预览
        preview_label = lv.label(self.parent)
        preview_label.set_text(self.text_config.get_section("hardware_test")["rgb"]["color"])
        preview_label.align(lv.ALIGN.TOP_LEFT, 20, 90)

        self.color_preview = lv.obj(self.parent)
        self.color_preview.set_size(30, 30)
        self.color_preview.align_to(preview_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)

        # 红色滑块
        r_label = lv.label(self.parent)
        r_label.set_text(self.text_config.get_section("hardware_test")["rgb"]["red"])
        r_label.align(lv.ALIGN.TOP_LEFT, 20, 140)

        self.r_slider = lv.slider(self.parent)
        self.r_slider.set_range(0, 255)
        self.r_slider.set_width(200)
        self.r_slider.align_to(r_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        self.r_slider.add_event(self.on_r_change, lv.EVENT.VALUE_CHANGED, None)

        # 绿色滑块
        g_label = lv.label(self.parent)
        g_label.set_text(self.text_config.get_section("hardware_test")["rgb"]["green"])
        g_label.align(lv.ALIGN.TOP_LEFT, 20, 180)

        self.g_slider = lv.slider(self.parent)
        self.g_slider.set_range(0, 255)
        self.g_slider.set_width(200)
        self.g_slider.align_to(g_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        self.g_slider.add_event(self.on_g_change, lv.EVENT.VALUE_CHANGED, None)

        # 蓝色滑块
        b_label = lv.label(self.parent)
        b_label.set_text(self.text_config.get_section("hardware_test")["rgb"]["blue"])
        b_label.align(lv.ALIGN.TOP_LEFT, 20, 220)

        self.b_slider = lv.slider(self.parent)
        self.b_slider.set_range(0, 255)
        self.b_slider.set_width(200)
        self.b_slider.align_to(b_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        self.b_slider.add_event(self.on_b_change, lv.EVENT.VALUE_CHANGED, None)

        # 初始化颜色预览
        self.update_color_preview()

    def on_rgb_switch(self, e):
        self.rgb_led_enabled = self.rgb_switch.has_state(lv.STATE.CHECKED)
        self.update_rgb_output()

    def on_r_change(self, e):
        if e.code == lv.EVENT.VALUE_CHANGED:
            self.r_value = self.r_slider.get_value()
            self.update_color_preview()
            self.update_rgb_output()

    def on_g_change(self, e):
        if e.code == lv.EVENT.VALUE_CHANGED:
            self.g_value = self.g_slider.get_value()
            self.update_color_preview()
            self.update_rgb_output()

    def on_b_change(self, e):
        if e.code == lv.EVENT.VALUE_CHANGED:
            self.b_value = self.b_slider.get_value()
            self.update_color_preview()
            self.update_rgb_output()

    def update_color_preview(self):
        color_hex = (self.r_value << 16) | (self.g_value << 8) | self.b_value
        self.color_preview.set_style_bg_color(lv.color_hex(color_hex), 0)

    def update_rgb_output(self):
        try:
            if self.rgb_led_enabled:
                # 这里调用实际控制RGB LED的代码
                # set_rgb_led(self.r_value, self.g_value, self.b_value)
                self.app.app_manager.YbRGB.show_rgb((self.r_value, self.g_value, self.b_value))
                pass
            else:
                # 关闭RGB LED
                self.app.app_manager.YbRGB.show_rgb((0,0,0))
                pass
        except Exception as e:
            print("Error updating RGB LED output:", e)

    def cleanup(self):
        # 关闭RGB LED
        # set_rgb_led(0, 0, 0)
        self.app.app_manager.YbRGB.show_rgb((0,0,0))
        pass