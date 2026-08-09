from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
from ybUtils.Configuration import Configuration

class SoundSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        self.text_config = text_config
        pass
    
    def display(self):
        """显示声音设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        
        # 添加类别标题
        title = self._create_title("Sound & Voice")
        
        # 添加水平线
        self._create_divider()
        
        # 声音项目列表
        items = [
            {"name": self.text_config.get_section("Settings")["sound"]["Volume"], "type": "slider", "config_section": "sound", "config_key": "volume",
             "value": self.config.get_section("sound")["volume"],
             "min": 0, "max": 100, "callback": self._on_volume_change},
        ]
        
        # 创建声音设置项
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
    
    def _on_volume_change(self, event):
        """音量变化回调"""
        slider = lv.slider.__cast__(event.get_target())
        value = slider.get_value()
        pass
        # 这里添加控制音量的代码