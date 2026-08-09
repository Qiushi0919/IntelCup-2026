from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
from ybUtils.Configuration import Configuration

class HotspotSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        pass
        self.text_config = text_config
    
    def display(self):
        """显示热点设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        
        # 添加类别标题
        title = self._create_title(self.text_config.get_section("Settings")["AP"]["title"])
        
        # 添加水平线
        self._create_divider()
        
        # 热点项目列表
        items = [
            {"name": self.text_config.get_section("Settings")["AP"]["switch_text"], "type": "switch", "config_section": "AP", "config_key": "default_status", 
             "value": self.config.get_section("AP")["default_status"], "callback": self._on_ap_switch},
            {"name": self.text_config.get_section("Settings")["AP"]["set_text"], "type": "button", "value": "设置", "callback": self._on_ap_settings},
        ]
        
        # 创建热点设置项
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
    
    def _on_ap_switch(self, event):
        """AP开关回调"""
        sw = lv.switch.__cast__(event.get_target()) 
        state = sw.get_state() & lv.STATE.CHECKED
        pass
        # 这里添加控制AP的代码
    
    def _on_ap_settings(self, event):
        """AP设置回调"""
        pass
        # 创建AP设置对话框
        # TODO: 实现AP设置对话框