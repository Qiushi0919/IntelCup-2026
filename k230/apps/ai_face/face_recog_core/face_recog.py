from apps.ai_face.base_demo_page import BaseDemoPage
import lvgl as lv
from ybUtils.Configuration import *
import apps.ai_face.face_recog_core.face_recognition as face_recog
from media.display import *
from media.media import *
import gc,time,os

def list_bin_files(directory):
    """
    列出指定目录下的所有二进制人脸数据文件，返回不带后缀的文件名，用换行符分隔
    """
    # 常见图片文件后缀
    image_extensions = ('.bin')
    
    # 存储图片文件名的列表
    image_files = []
    
    # 列出目录中的所有文件
    for file in os.listdir(directory):
        # 检查文件是否为图片（逐个检查后缀）
        is_image = False
        for ext in image_extensions:
            if file.lower().endswith(ext):
                is_image = True
                break
        
        if is_image:
            # 获取文件名（不含后缀）
            # 在MicroPython中手动分离文件名和后缀
            dot_pos = file.rfind('.')
            if dot_pos > 0:  # 确保找到了点号且不是在开头
                basename = file[:dot_pos]
                image_files.append(basename)
    
    # 使用换行符拼接文件名
    result = '\n'.join(image_files)
    return result
    
  
class FaceRecogPage(BaseDemoPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config, text_config)
    
    def get_image_source(self):
        # 返回图片源
        try:
            with open("/sdcard/apps/ai_face/face_recog_core/banner.png", 'rb') as f:
                img_cache = f.read()
                return lv.img_dsc_t({
                    'data_size': len(img_cache),
                    'data': img_cache
                })
        except Exception as e:
            print("Error loading image: ", e)
            return None
    
    def get_title(self):
        return self.text_config.get_section("AI_face")["face_recog"]["title"]

    
    def get_description(self):
        return self.text_config.get_section("AI_face")["face_recog"]["info"]
    
    def get_button_text(self):
        return self.text_config.get_section("System")["Boot"]
    
    def on_button_click(self, evt):
        db_path = self.config.get_section("AI")["face_database_path"]
        reg_list = None
        try:
            reg_list = list_bin_files(db_path)
            print(reg_list)
        except Exception as e:
            print("Exc ", e)
            self.app.model_dialog.show(
                title=self.text_config.get_section("AI_face")["face_recog"]["title"],
                content=f"{self.text_config.get_section("AI_face")["face_recog"]["modal_info_no_face"]}\n{e}",
                icon_symbol=lv.SYMBOL.WARNING,
                btn_texts=[self.text_config.get_section("System")["Ok"]],
                width=480,
                height=300
            )
            return
        if reg_list is "" or reg_list is None:
            self.app.model_dialog.show(
                title=self.text_config.get_section("AI_face")["face_recog"]["title"],
                content=self.text_config.get_section("AI_face")["face_recog"]["modal_info_no_face"],
                icon_symbol=lv.SYMBOL.WARNING,
                btn_texts=[self.text_config.get_section("System")["Ok"]],
                width=480,
                height=300
            )
            return
        
        img2 = image.Image(640, 480, image.RGB565)
        img2.clear()
        # 绘制返回箭头的水平线
        img2.draw_line(20, 30, 50, 30, color=(255, 255, 255), thickness=4)
        # 绘制返回箭头的左上斜线
        img2.draw_line(20, 30, 35, 15, color=(255, 255, 255), thickness=4)
        # 绘制返回箭头的左下斜线
        img2.draw_line(20, 30, 35, 45, color=(255, 255, 255), thickness=4)
        Display.show_image(img2,0,0,Display.LAYER_OSD0)
        self.run_demo(db_path) 
        
    def run_demo(self, db_path):
        if self.app.pl is None:
            print("未找到播放器")
        else:
            md = None
            try:
                print("初始化人脸识别模块")
                md = face_recog.YAHBOOM_DEMO(self.app.pl, self.app.uart)
                md.exce_demo(db_path, self.text_config.get_section("System")["Loading"])
                print("人脸识别模块运行完成")
            except Exception as e:
                print("人脸识别模块运行失败: ", e)
            finally:
                # 清理图像显示
                img2 = image.Image(640, 480, image.RGB565)
                img2.clear()
                Display.show_image(img2, 0, 0, Display.LAYER_OSD3)
                
                # 确保md被完全清理
                if md:
                    del md
                
                # 更彻底的内存回收
                gc.collect()
                time.sleep(0.5)  # 增加延时，给系统更多时间清理
                gc.collect()