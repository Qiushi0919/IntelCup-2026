from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
import time
from ybUtils.Configuration import Configuration

class DateTimeSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        pass
        self.text_config = text_config.get_section("Settings")["time_date"]

        
    def display(self):
        """显示日期和时间设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        
        # 添加类别标题
        pass
        title = self._create_title(self.text_config["title"])
        
        # 添加水平线
        self._create_divider()
        
        # 日期和时间项目列表
        items = [
            {"name": self.text_config["text_async_time"], "type": "switch", "config_section": "date", "config_key": "async_time_by_wlan",
             "value": self.config.get_section("date")["async_time_by_wlan"], 
             "callback": self._on_auto_time_switch},
            {"name": self.text_config["text_setting_time"], "type": "button", "value": self.text_config["text_setting"], 
             "callback": self._on_time_settings},
        ]
        
        # 创建日期和时间设置项
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
    
    def _on_auto_time_switch(self, event):
        """自动同步时间开关回调"""
        sw = lv.switch.__cast__(event.get_target())
        state = sw.get_state() & lv.STATE.CHECKED
        pass
        # 这里添加控制时间同步的代码
    
    def _on_time_settings(self, event):
        """时间设置回调"""
        pass
        # 创建时间设置对话框
        current_time = time.localtime()
        self.app.dialog_helper.create_time_settings_dialog(current_time, self._save_time_settings)
    
    def _save_time_settings(self, time_str):
        """保存时间设置"""
        pass
        self.config.set_value("date", "time_set", time_str)
        self.config.save_to_file('/sdcard/configs/sys_config.json')
        pass
        self.display()  # 刷新显示