from apps.ai_body.base_demo_page import BaseDemoPage
import lvgl as lv
from ybUtils.Configuration import *
import apps.ai_body.person_det_core.person_detection as person_detection
from media.display import *
from media.media import *

class PersonDetPage(BaseDemoPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config, text_config)
    
    def get_image_source(self):
        # 返回图片源
        try:
            with open("/sdcard/apps/ai_body/person_det_core/banner.png", 'rb') as f:
                img_cache = f.read()
                return lv.img_dsc_t({
                    'data_size': len(img_cache),
                    'data': img_cache
                })
        except Exception as e:
            pass
            return None
    
    def get_title(self):
        return self.text_config.get_section("AI_body")["person_det"]["title"]
    
    def get_description(self):
        return self.text_config.get_section("AI_body")["person_det"]["info"]
    
    def get_button_text(self):
        return self.text_config.get_section("System")["Boot"]
    
    def on_button_click(self, evt):
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
        self.run_demo(person_detection)
        