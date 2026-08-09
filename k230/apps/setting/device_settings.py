import machine
import lvgl as lv
from apps.setting.base_setting_page import BaseSettingPage
from ybUtils.Configuration import Configuration
class DeviceSettingsPage(BaseSettingPage):
    def __init__(self, app, detail_panel, config, text_config):
        self.text_config = text_config.get_section("Settings")["my_device"]
        super().__init__(app, detail_panel, config)

        
    def display(self):
        """显示设备设置页面"""
        # 清除面板
        self.detail_panel.clean()
        self.detail_items = []
        
        # 添加类别标题
        title = self._create_title(self.text_config["title"])
        
        # 添加水平线
        self._create_divider()
        
        # 设备信息列表
        items = [
            {"name": self.text_config["chip_id"], "type": "info", "value": self._get_chip_id()},
            {"name": self.text_config["os_version"], "type": "info", "value": self.config.get_section("SYS_INFO")["os_version"]},
            {"name": self.text_config["fw_version"], "type": "info", "value": " -- "},
            {"name": self.text_config["hw_version"], "type": "info", "value": self.config.get_section("SYS_INFO")["hw_version"]},
            {"name": self.text_config["tmp"], "type": "info", "value": self._get_temperature()},
        ]
        
        # 创建设备信息项
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
        import lvgl as lv
        line = lv.line(self.detail_panel)
        points = [{"x": 0, "y": 0}, {"x": self.detail_panel.get_width() - 20, "y": 0}]
        line.set_points(points, 2)
        line.set_style_line_width(1, 0)
        line.set_style_line_color(lv.color_hex(0xdddddd), 0)
        line.set_style_margin_top(5, 0)
        line.set_style_margin_bottom(15, 0)
    
    def _get_chip_id(self):
        """获取芯片ID"""
        pass
        # 模拟芯片ID
        return ''.join(['%02x' % b for b in machine.chipid()])
    
    def _get_temperature(self):
        # 模拟设备温度
        return machine.temperature()