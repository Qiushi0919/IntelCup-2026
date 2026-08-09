from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
import machine
from ybUtils.Configuration import *

class DisplaySettingsPage(BaseSettingPage):
    
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        self.text_config = text_config
    
    def display(self):
        """显示显示设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        
        # 添加类别标题
        title = self._create_title(self.text_config.get_section("Settings")["display"]["title"])
        
        # 添加水平线
        self._create_divider()
        
        # 显示项目列表
        items = [
            {"name": self.text_config.get_section("Settings")["display"]["Brightness"], "type": "info", "value": self.text_config.get_section("Settings")["display"]["not_support_set_bri"]},
            {"name": self.text_config.get_section("Settings")["display"]["Resolution"], "type": "button", "value": self.text_config.get_section("Settings")["display"]["Choose_resolution"],
             "callback": self._on_choose_resolution_click},
        ]
        
        # 创建显示设置项
        for item in items:
            self.create_item(item)
    
    def _create_title(self, text):
        """创建标题"""
        title = lv.label(self.detail_panel)
        title.set_text(text)
        title.set_width(lv.pct(100))
        title.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
        return title
    
    def _create_divider(self):
        """创建分隔线"""
        line = lv.line(self.detail_panel)
        points = [{"x": 0, "y": 0}, {"x": self.detail_panel.get_width() - 20, "y": 0}]
        line.set_points(points, 2)
        line.set_style_line_width(1, 0)
        line.set_style_line_color(lv.color_hex(0xdddddd), 0)
        line.set_style_margin_top(5, 0)
        line.set_style_margin_bottom(15, 0)
    
    def _on_brightness_change(self, event):
        """亮度变化回调"""
        slider = lv.slider.__cast__(event.get_target())
        value = slider.get_value()
        pass
        # 这里添加控制亮度的代码
    
    
    def _set_sensor_pix_160(self, dialog):
        if self.config.get_section("sensor")["ch1_width"] == 160 and self.config.get_section("sensor")["ch1_height"] == 120:
            return
        self.config.set_value("sensor",  "ch1_width", 160)
        self.config.set_value("sensor",  "ch1_height", 120)
        self.config.save_to_file('/sdcard/configs/sys_config.json')
        machine.reset()   
        
    def _set_sensor_pix_640(self, dialog):
        if self.config.get_section("sensor")["ch1_width"] == 640 and self.config.get_section("sensor")["ch1_height"] == 480:
            return
        self.config.set_value("sensor",  "ch1_width", 640)
        self.config.set_value("sensor",  "ch1_height", 480)
        self.config.save_to_file('/sdcard/configs/sys_config.json')
        machine.reset()
       
    def _on_choose_resolution_click(self, event):
        self.app.model_dialog.show(
            title=self.text_config.get_section("Settings")["display"]["Choose_resolution"],
            content=self.text_config.get_section("Settings")["display"]["Choose_resolution_text"],
            icon_symbol=lv.SYMBOL.REFRESH,
            btn_texts=["160 x 120", "640 x 480"],
            btn_callbacks=[self._set_sensor_pix_160, self._set_sensor_pix_640],
            width=480,
            height=300
        )