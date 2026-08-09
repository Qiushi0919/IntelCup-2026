from apps.color_det.base_demo_page import BaseDemoPage
import lvgl as lv
from ybUtils.Configuration import *
import apps.color_det.color_recog.color_recognition as color_recogection
from media.display import *
from media.media import *

class ColorRecogPage(BaseDemoPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config, text_config)
    
    def get_image_source(self):
        # 返回图片源
        try:
            with open("/sdcard/apps/color_det/color_recog/banner.png", 'rb') as f:
                img_cache = f.read()
                return lv.img_dsc_t({
                    'data_size': len(img_cache),
                    'data': img_cache
                })
        except Exception as e:
            pass
            return None
    
    def get_title(self):
        return self.text_config.get_section("ColorDet")["color_recog"]["title"]
    
    def get_description(self):
        return self.text_config.get_section("ColorDet")["color_recog"]["info"]
    
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
        Display.show_image(img2,0,0,Display.LAYER_OSD3)
        self.run_demo(color_recogection)
        