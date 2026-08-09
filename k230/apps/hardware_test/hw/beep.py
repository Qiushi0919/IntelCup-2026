import lvgl as lv

class BEEPTestPage:
    def __init__(self, app, parent, config, text_config):
        self.app = app
        self.parent = parent
        self.config = config
        self.text_config = text_config
        self.beep_active = False
        self.btn = None

    def display(self):
        # 清理之前的内容
        self.parent.clean()

        # 设置父容器样式
        self.parent.set_style_bg_color(lv.color_hex(0xf5f5f5), 0)
        self.parent.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # 标题
        title = lv.label(self.parent)
        title.set_text(self.text_config.get_section("hardware_test")["beep"]["title"])
        title.set_style_text_font(lv.font_yb_cn_16, 0)
        title.set_style_text_color(lv.color_hex(0x333333), 0)
        title.align(lv.ALIGN.TOP_LEFT, 0, 10)
        title.set_size(lv.pct(100), 50)

        # 创建按钮
        self.btn = lv.btn(self.parent)
        self.btn.set_size(150, 40)
        self.btn.center()
        self.btn.set_style_radius(35, 0)
        self.btn.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.btn.set_style_bg_color(lv.color_hex(0x333333), lv.STATE.PRESSED)
        self.btn.add_event(self.on_btn_click, lv.EVENT.CLICKED, None)

        # 按钮文字
        self.btn_label = lv.label(self.btn)
        self.btn_label.set_text(self.text_config.get_section("hardware_test")["beep"]["open"])
        self.btn_label.set_style_text_font(lv.font_yb_cn_16, 0)
        self.btn_label.set_style_text_color(lv.color_hex(0xffffff), 0)
        self.btn_label.center()

    def on_btn_click(self, e):
        self.app.app_manager.ybbuzzer.beep(0.1)

    def cleanup(self):
        if self.beep_active:
            self.beep_active = False
            # stop_beep()