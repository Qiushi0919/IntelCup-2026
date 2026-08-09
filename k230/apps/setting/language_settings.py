from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
import os
from ybUtils.Configuration import *

class LanguageSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        self.text_config = text_config
        
    def display(self):
        """显示语言设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        # 添加类别标题
        title = self._create_title(self.text_config.get_section("Settings")["language"]["title"])
        
        # 添加水平线
        self._create_divider()
        
        # 语言项目列表
        items = [
            {"name": self.text_config.get_section("Settings")["language"]["choose_language"], "type": "select", "options": self._scan_languages(), 
             "value": self._get_setting_language(), 
             "callback": self._on_language_change},
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
    
    def _get_setting_language(self):
        """获取当前语言设置"""
        return self.config.get_section("language").get("text_path", "").split("/")[-1].split(".")[-2]

    def _scan_languages(self):
        """扫描可用语言"""
        pass
        # 模拟语言扫描结果
        language_list = os.listdir("/sdcard/configs/languages")
        for i, lang in enumerate(language_list):
            language_list[i] = lang.split(".")[0] if lang.endswith(".json") else lang

        return language_list
    
    def _on_language_change(self, event, option):

        pass
        """语言变化回调"""
        current_language = option.strip().replace('\u0000', '')
        pass

        self.config.set_value("language", "text_path", "/sdcard/configs/languages/" + current_language + ".json")
        self.config.save_to_file('/sdcard/configs/sys_config.json')
        self.text_config = Configuration.load_from_file("/sdcard/configs/languages/" + current_language + ".json")
        self.app.model_dialog.show(
            title=self.text_config.get_section("Settings")["language"]["title"],
            content=self.text_config.get_section("Settings")["language"]["finish_changing"],
            icon_symbol=lv.SYMBOL.REFRESH,
            btn_texts=[self.text_config.get_section("System")["Ok"]],
            width=480,
            height=300
        ).close_after(3000)
        
        # # 更新语言配置
        # if current_language == "Chinese" or current_language == "zh_cn":
        #     self.config.set_value("language", "text_path", "/sdcard/configs/languages/zh_cn.json")
        # else:
        #     self.config.set_value("language", "text_path", "/sdcard/configs/languages/en.json")
        
        # self.config.save_to_file('/sdcard/configs/sys_config.json')
        # pass