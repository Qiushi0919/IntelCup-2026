from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
import os
from ybUtils.Configuration import *
import ybUtils.monitor
# 暂时不需要
class MoreSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        self.text_config = text_config
        
    def display(self):
        """显示语言设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        # 添加类别标题
        title = self._create_title(self.text_config.get_section("Settings")["more"]["title"])
        
        # 添加水平线
        self._create_divider()
        
        # 语言项目列表
        items = [
            {"name": self.text_config.get_section("Settings")["more"]["title"], "type": "button", "value": self.text_config.get_section("Settings")["more"]["button"], 
             "callback": self._on_more_settings},
        ]
        
        # 创建语言设置项
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

    
    def _on_more_settings(self, event=None, option=None):
        pass
        self.app.model_dialog.show(
            title=self.text_config.get_section("Settings")["more"]["title"],
            content=self.text_config.get_section("Settings")["more"]["more_info_disable"],
            icon_symbol=lv.SYMBOL.CLOSE,
            btn_texts=[self.text_config.get_section("System")["Ok"]],
            width=480,
            height=300
        )
        # if self.app.ybnet.sta.isconnected():
        #     pass
        #     # ybUtils.monitor.run(network_connected=True, setting_mode=True)
        #     self.app.model_dialog.show(
        #         title=self.text_config.get_section("Settings")["more"]["title"],
        #         content=self.text_config.get_section("Settings")["more"]["alert_no_wifi"],
        #         icon_symbol=lv.SYMBOL.WIFI,
        #         btn_texts=[self.text_config.get_section("System")["Ok"]],
        #         width=480,
        #         height=300
        #     ).close_after(5000)
        #     pass
        # else:
        #     self.app.model_dialog.show(
        #         title=self.text_config.get_section("Settings")["more"]["title"],
        #         content=self.text_config.get_section("Settings")["more"]["alert_no_wifi"],
        #         icon_symbol=lv.SYMBOL.WIFI,
        #         btn_texts=[self.text_config.get_section("System")["Ok"]],
        #         width=480,
        #         height=300
        #     ).close_after(5000)
            
        
