import lvgl as lv
from machine import PWM
from machine import FPIOA
import time

# 实例化FPIOA
fpioa = FPIOA()
# 设置PIN42为PWM通道0
fpioa.set_function(42, fpioa.PWM0)

class PWMTestPage:
    def __init__(self, app, parent, config, text_config):
        self.app = app
        self.parent = parent
        self.config = config
        self.text_config = text_config
        self.freq_slider = None
        self.duty_slider = None
        self.freq_label = None
        self.duty_label = None
        self.pwm_active = False
        self.output_switch = None
        self.pwm0 = PWM(0, 1000, 50)

    def display(self):
        # 清理之前的内容
        self.parent.clean()

        # 标题
        title = lv.label(self.parent)
        title.set_text(self.text_config.get_section("hardware_test")["pwm"]["title"])
        title.set_style_text_font(lv.font_yb_cn_16, 0)
        title.set_style_text_color(lv.color_hex(0x333333), 0)
        title.align(lv.ALIGN.TOP_LEFT, 0, 10)

        # PWM通道显示
        channel_label = lv.label(self.parent)
        channel_label.set_text(f"{self.text_config.get_section("hardware_test")["pwm"]["channel"]}: 0")
        channel_label.set_style_text_font(lv.font_yb_cn_16, 0)
        channel_label.align(lv.ALIGN.TOP_LEFT, 20, 50)

        # 输出开关
        switch_label = lv.label(self.parent)
        switch_label.set_text(self.text_config.get_section("hardware_test")["pwm"]["open"])
        switch_label.set_style_text_font(lv.font_yb_cn_16, 0)
        switch_label.align(lv.ALIGN.TOP_LEFT, 20, 90)

        self.output_switch = lv.switch(self.parent)
        self.output_switch.set_size(50, 25)
        self.output_switch.align_to(switch_label, lv.ALIGN.OUT_RIGHT_MID, 10, 0)
        # self.output_switch.add_state(lv.STATE.CHECKED)
        self.output_switch.add_event(self.on_output_switch, lv.EVENT.VALUE_CHANGED, None)
        self.output_switch.set_style_bg_color(lv.color_hex(0xe0e0e0), lv.PART.MAIN)
        self.output_switch.set_style_bg_color(lv.color_hex(0x1a73e8), lv.PART.INDICATOR)
        self.output_switch.set_style_border_width(0, lv.PART.MAIN)

        # 频率控制
        freq_title = lv.label(self.parent)
        freq_title.set_text(self.text_config.get_section("hardware_test")["pwm"]["freq"])
        freq_title.set_style_text_font(lv.font_yb_cn_16, 0)
        freq_title.set_style_text_color(lv.color_hex(0x333333), 0)
        freq_title.align(lv.ALIGN.TOP_LEFT, 20, 140)

        self.freq_label = lv.label(self.parent)
        self.freq_label.set_text("1000 Hz")
        self.freq_label.set_style_text_font(lv.font_yb_cn_16, 0)
        self.freq_label.set_style_text_color(lv.color_hex(0x1a73e8), 0)
        self.freq_label.align(lv.ALIGN.TOP_RIGHT, -20, 140)

        self.freq_slider = lv.slider(self.parent)
        self.freq_slider.set_range(1000, 4000)  # 1000Hz - 4000Hz
        self.freq_slider.set_value(1000, lv.ANIM.OFF)
        self.freq_slider.set_width(200)
        self.freq_slider.align(lv.ALIGN.TOP_LEFT, 20, 170)
        self.freq_slider.set_style_bg_color(lv.color_hex(0xe0e0e0), lv.PART.MAIN)
        self.freq_slider.set_style_bg_color(lv.color_hex(0x1a73e8), lv.PART.INDICATOR)
        self.freq_slider.set_style_bg_color(lv.color_hex(0xffffff), lv.PART.KNOB)
        self.freq_slider.set_style_border_color(lv.color_hex(0x1a73e8), lv.PART.KNOB)
        self.freq_slider.set_style_border_width(2, lv.PART.KNOB)
        self.freq_slider.set_style_radius(10, lv.PART.MAIN)
        self.freq_slider.add_event(self.on_freq_change, lv.EVENT.VALUE_CHANGED, None)

        # 占空比控制
        duty_title = lv.label(self.parent)
        duty_title.set_text(self.text_config.get_section("hardware_test")["pwm"]["duty"])
        duty_title.set_style_text_font(lv.font_yb_cn_16, 0)
        duty_title.set_style_text_color(lv.color_hex(0x333333), 0)
        duty_title.align(lv.ALIGN.TOP_LEFT, 20, 210)

        self.duty_label = lv.label(self.parent)
        self.duty_label.set_text("50 %")
        self.duty_label.set_style_text_font(lv.font_yb_cn_16, 0)
        self.duty_label.set_style_text_color(lv.color_hex(0x1a73e8), 0)
        self.duty_label.align(lv.ALIGN.TOP_RIGHT, -20, 210)

        self.duty_slider = lv.slider(self.parent)
        self.duty_slider.set_range(0, 100)  # 0% - 100%
        self.duty_slider.set_value(50, lv.ANIM.OFF)
        self.duty_slider.set_width(200)
        self.duty_slider.align(lv.ALIGN.TOP_LEFT, 20, 240)
        self.duty_slider.set_style_bg_color(lv.color_hex(0xe0e0e0), lv.PART.MAIN)
        self.duty_slider.set_style_bg_color(lv.color_hex(0x1a73e8), lv.PART.INDICATOR)
        self.duty_slider.set_style_bg_color(lv.color_hex(0xffffff), lv.PART.KNOB)
        self.duty_slider.set_style_border_color(lv.color_hex(0x1a73e8), lv.PART.KNOB)
        self.duty_slider.set_style_border_width(2, lv.PART.KNOB)
        self.duty_slider.set_style_radius(10, lv.PART.MAIN)
        self.duty_slider.add_event(self.on_duty_change, lv.EVENT.VALUE_CHANGED, None)

        # 初始设置PWM
        self.pwm_active = True
        self.update_pwm_settings()
        
    def on_freq_change(self, e):
        freq = self.freq_slider.get_value()
        self.pwm0.freq(freq)
        self.freq_label.set_text(f"{freq} Hz")
        self.update_pwm_settings()

    def on_duty_change(self, e):
        duty = self.duty_slider.get_value()
        self.pwm0.duty(duty)
        self.duty_label.set_text(f"{duty} %")
        self.update_pwm_settings()

    def on_output_switch(self, e):
        self.pwm_active = self.output_switch.has_state(lv.STATE.CHECKED)
        self.update_pwm_settings()

    def update_pwm_settings(self):
        # 获取当前设置
        try:
            channel = 0  # 固定使用通道0
            freq = self.freq_slider.get_value()
            duty = self.duty_slider.get_value()
            output_enabled = self.pwm_active
            print("output_enabled: ", output_enabled)
            
            # 这里调用实际的PWM控制代码
            self.pwm0.freq(freq)
            self.pwm0.duty(duty)
            time.sleep(0.1)
            if output_enabled:
                pass
            else:
                pass
                self.pwm0.duty(0)
                pass
            
        except Exception as e:
            print("pwm control error: ", e)
        # set_pwm(channel, freq, duty, output_enabled)

    def cleanup(self):
        # 确保停止PWM输出
        # stop_pwm(0)
        self.pwm0.duty(0)
        pass