from apps.ai_objects.base_demo_page import BaseDemoPage
import lvgl as lv
from ybUtils.Configuration import *
import apps.ai_objects.self_learning.self_learning_detection as self_learning_detection
from media.display import *
from media.media import *
import machine,gc,time

def debug_print(*args):
    print("[DEBUG]", args)
    
class SFLPage(BaseDemoPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config, text_config)
        self.self_learning_labels = config.get_section("AI")["self_learning_labels"]
        self.self_learning_database = config.get_section("AI")["self_learning_database"]
    
    
    def get_image_source(self):
        # 返回图片源
        try:
            with open("/sdcard/apps/ai_objects/self_learning/banner.png", 'rb') as f:
                img_cache = f.read()
                return lv.img_dsc_t({
                    'data_size': len(img_cache),
                    'data': img_cache
                })
        except Exception as e:
            pass
            return None
    
    def get_title(self):
        return self.text_config.get_section("AI_objects")["self_learning"]["title"]
    
    def get_description(self):
        return self.text_config.get_section("AI_objects")["self_learning"]["info"]
    
    def get_button_text(self):
        return self.text_config.get_section("System")["Boot"]
    
    def on_button_click(self, evt):
        pass
        
        self.app.model_dialog.show(
            title=self.text_config.get_section("AI_objects")["self_learning"]["title"],
            content=self.text_config.get_section("AI_objects")["self_learning"]["choose_mode"],
            icon_symbol=lv.SYMBOL.WARNING,
            btn_texts=[self.text_config.get_section("AI_objects")["self_learning"]["mode_rec_only"],self.text_config.get_section("AI_objects")["self_learning"]["mode_study_and_rec"]],
            btn_callbacks=[self.on_recog_only_mode, self.on_fully_mode],
            width=480,
            height=300
        )
        
    def on_fully_mode(self, modal):
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

        if self.app.pl is None:
            pass
        else:
            md = None
            try:
                md = self_learning_detection.YAHBOOM_DEMO(self.app.pl)
                md.exce_demo(loading_text="Loading ...", recong_only=False, labels=self.self_learning_labels, database_path=self.self_learning_database)
            except Exception as e:
                debug_print("on_fully_mode: ", e)
                self.app.model_dialog.show(
                    title=self.text_config.get_section("System")["Error"],
                    content=f"{self.text_config.get_section("System")["Error_text"]["default"]}\n{e}",
                    icon_symbol=lv.SYMBOL.WARNING,
                    btn_texts=[self.text_config.get_section("System")["Ok"]],
                    width=480,
                    height=300
                )
            finally:
                img2 = image.Image(640, 480, image.RGB565)
                img2.clear()
                Display.show_image(img2, 0, 0, Display.LAYER_OSD3)
                
                # 确保md被删除
                if md:
                    del md
                
                # 多次执行gc回收
                gc.collect()
                time.sleep(0.1)  # 给系统一点时间清理
                gc.collect()
    def on_recog_only_mode(self, modal):
        img2 = image.Image(640, 480, image.RGB565)
        img2.clear()
        # 绘制返回箭头的水平线
        img2.draw_line(20, 30, 50, 30, color=(255, 255, 255), thickness=4)
        # 绘制返回箭头的左上斜线
        img2.draw_line(20, 30, 35, 15, color=(255, 255, 255), thickness=4)
        # 绘制返回箭头的左下斜线
        img2.draw_line(20, 30, 35, 45, color=(255, 255, 255), thickness=4)
        Display.show_image(img2,0,0,Display.LAYER_OSD0)

        if self.app.pl is None:
            pass
        else:
            md = None
            try:
                md = self_learning_detection.YAHBOOM_DEMO(self.app.pl)
                md.exce_demo(loading_text="Loading ...", recong_only=True, labels=self.self_learning_labels, database_path=self.self_learning_database)
            except Exception as e:
                pass
                self.app.model_dialog.show(
                    title=self.text_config.get_section("System")["Error"],
                    content=f"{self.text_config.get_section("System")["Error_text"]["default"]}\n{e}",
                    icon_symbol=lv.SYMBOL.WARNING,
                    btn_texts=[self.text_config.get_section("System")["Ok"]],
                    width=480,
                    height=300
                )
            finally:
                img2 = image.Image(640, 480, image.RGB565)
                img2.clear()
                Display.show_image(img2, 0, 0, Display.LAYER_OSD3)
                
                # 确保md被删除
                if md:
                    del md
                
                # 多次执行gc回收
                gc.collect()
                time.sleep(0.1)  # 给系统一点时间清理
                gc.collect() 
        
