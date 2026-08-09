from apps.setting.base_setting_page import BaseSettingPage
import lvgl as lv
from ybUtils.Configuration import Configuration

class SecuritySettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config)
        self.text_config = text_config
        pass
    
    def display(self):
        """显示安全设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        
        # 添加类别标题
        title = self._create_title("安全设置")
        
        # 添加水平线
        self._create_divider()
        
        # 安全项目列表
        items = [
            {"name": "密码解锁", "type": "switch", "config_section": "safety", "config_key": "password_enabled",
             "value": 1 if (self.config.get_section("safety")["password"] is not None) else 0, 
             "callback": self._on_password_switch},
            {"name": "人脸解锁", "type": "switch", "config_section": "safety", "config_key": "face_recognition",
             "value": self.config.get_section("safety")["face_recognition"], 
             "callback": self._on_face_switch},
            {"name": "语音唤醒", "type": "switch", "config_section": "safety", "config_key": "kws",
             "value": self.config.get_section("safety")["kws"], 
             "callback": self._on_voice_switch},
        ]
        
        # 创建安全设置项
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
    
    def _on_password_switch(self, event):
        """密码解锁开关回调"""
        sw = lv.switch.__cast__(event.get_target())
        state = sw.get_state() & lv.STATE.CHECKED
        pass
        # 这里添加控制密码解锁的代码
    
    def _on_face_switch(self, event):
        """人脸解锁开关回调"""
        sw = lv.switch.__cast__(event.get_target())
        state = sw.get_state() & lv.STATE.CHECKED
        pass
        # 这里添加控制人脸解锁的代码
    
    def _on_voice_switch(self, event):
        """语音唤醒开关回调"""
        sw = lv.switch.__cast__(event.get_target())
        state = sw.get_state() & lv.STATE.CHECKED
        pass
        # 这里添加控制语音唤醒的代码