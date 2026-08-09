from apps.graphics_det.base_demo_page import BaseDemoPage
import lvgl as lv
from ybUtils.Configuration import *
import apps.graphics_det.rect_det.rect_detection as rect_detection
from media.display import *
from media.media import *
import machine

class RectDetPage(BaseDemoPage):
    def __init__(self, app, detail_panel, config):
        super().__init__(app, detail_panel, config)
        try:
            lang_path = self.config.get_section("language").get("text_path", "")
            self.text_config = Configuration.load_from_file(lang_path)
        except Exception as e:
            pass
            self.text_config = {}
    
    def get_image_source(self):
        # 返回图片源
        try:
            with open("/sdcard/apps/graphics_det/rect_det/banner.png", 'rb') as f:
                img_cache = f.read()
                return lv.img_dsc_t({
                    'data_size': len(img_cache),
                    'data': img_cache
                })
        except Exception as e:
            pass
            return None
    
    def get_title(self):
        return self.text_config.get_section("GraphicsDet")["rect_det"]["title"]
    
    def get_description(self):
        return self.text_config.get_section("GraphicsDet")["rect_det"]["info"]
    
    def get_button_text(self):
        return self.text_config.get_section("System")["Boot"]
    
    def on_button_click(self, evt):
        
        # 判断是否会超内存
        # ch1_width = self.config.get_section("sensor")["ch1_width"]
        # ch1_height = self.config.get_section("sensor")["ch1_height"]
        # if ch1_width>160 or ch1_height>120:
        #     self.app.model_dialog.show(
        #         title=self.text_config.get_section("GraphicsDet")["rect_det"]["title"],
        #         content=self.text_config.get_section("GraphicsDet")["alert"]["size_too_large"],
        #         icon_symbol=lv.SYMBOL.WARNING,
        #         btn_texts=[self.text_config.get_section("System")["Cancel"], self.text_config.get_section("System")["Ok"]],
        #         btn_callbacks=[None, self._callback_on_reset],
        #         width=480,
        #         height=300
        #     )
        #     return
        
        
        pass
        # img2 = image.Image(640, 480, image.RGB565)
        img2 = image.Image(640, 480, image.RGB565)
        img2.clear()
        # 绘制返回箭头的水平线
        img2.draw_line(20, 30, 50, 30, color=(255, 255, 255), thickness=4)
        # 绘制返回箭头的左上斜线
        img2.draw_line(20, 30, 35, 15, color=(255, 255, 255), thickness=4)
        # 绘制返回箭头的左下斜线
        img2.draw_line(20, 30, 35, 45, color=(255, 255, 255), thickness=4)
        Display.show_image(img2,0,0,Display.LAYER_OSD0)
        self.run_demo(rect_detection)
    
    def _callback_on_reset(self, dialog):
        self.config.set_value("sensor",  "ch1_width", 160)
        self.config.set_value("sensor",  "ch1_height", 120)
        self.config.save_to_file('/sdcard/configs/sys_config.json')
        machine.reset()