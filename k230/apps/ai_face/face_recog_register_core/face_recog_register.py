from apps.ai_face.base_demo_page import BaseDemoPage
import lvgl as lv
from ybUtils.Configuration import *
import apps.ai_face.face_recog_register_core.face_registration as face_recog_register
from media.display import *
from media.media import *
import _thread
import time,os,gc

def list_image_files(directory):
    """
    列出指定目录下的所有图片文件，返回不带后缀的文件名，用换行符分隔
    """
    # 常见图片文件后缀
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
    
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
    
  
class FaceRecogRegPage(BaseDemoPage):
    def __init__(self, app, detail_panel, config, text_config):
        super().__init__(app, detail_panel, config, text_config)
        # 配置蜂鸣器IO口功能
        self.bz = self.app.app_manager.ybbuzzer
    
    def get_image_source(self):
        # 返回图片源
        try:
            with open("/sdcard/apps/ai_face/face_recog_register_core/banner.png", 'rb') as f:
                img_cache = f.read()
                return lv.img_dsc_t({
                    'data_size': len(img_cache),
                    'data': img_cache
                })
        except Exception as e:
            pass
            return None
    
    def get_title(self):
        return self.text_config.get_section("AI_face")["face_recog_register"]["title"]

    
    def get_description(self):
        return self.text_config.get_section("AI_face")["face_recog_register"]["info"]
    
    def get_button_text(self):
        return self.text_config.get_section("System")["Boot"]
    
    def on_button_click(self, evt):
        
        reg_path = self.config.get_section("AI")["face_register_path"]
        db_path = self.config.get_section("AI")["face_database_path"]
        pass
        reg_list = None
        try:
            reg_list = list_image_files(reg_path)
        except Exception as e:
            self.app.model_dialog.show(
                title=self.text_config.get_section("AI_face")["face_recog_register"]["title"],
                content=f"{self.text_config.get_section("AI_face")["face_recog_register"]["modal_error_no_data"]}\n{e}",
                icon_symbol=lv.SYMBOL.WARNING,
                btn_texts=[self.text_config.get_section("System")["Ok"]],
                width=480,
                height=300
            )
            return
        if reg_list is "":
            self.app.model_dialog.show(
                title=self.text_config.get_section("AI_face")["face_recog_register"]["title"],
                content=self.text_config.get_section("AI_face")["face_recog_register"]["modal_error_no_data"],
                icon_symbol=lv.SYMBOL.WARNING,
                btn_texts=[self.text_config.get_section("System")["Ok"]],
                width=480,
                height=300
            )
            return 
        pass
        self.app.model_dialog.show(
            title=self.text_config.get_section("AI_face")["face_recog_register"]["title"],
            content=f"{self.text_config.get_section("AI_face")["face_recog_register"]["modal_info"]}\n--------------------\n{reg_list}\n--------------------",
            icon_symbol=lv.SYMBOL.WARNING,
            btn_texts=[self.text_config.get_section("System")["Cancel"],self.text_config.get_section("System")["Ok"]],
            btn_callbacks=[self.on_cancel_register, self.on_start_register],
            width=480,
            height=300
        )
        
        
    def on_start_register(self, dialog):
        reg_path = self.config.get_section("AI")["face_register_path"]
        db_path = self.config.get_section("AI")["face_database_path"]
        try:
            self.bz.beep(0.1)
            face_recog_register.exce_demo(reg_path,db_path)
            self.bz.beep(0.1)
            time.sleep_ms(50)
            # 关闭PWM输出 防止蜂鸣器吵闹
            time.sleep_ms(100)
            self.bz.beep(0.1)
            # 延时50ms
            time.sleep_ms(50)
            gc.collect()
            # 关闭PWM输出 防止蜂鸣器吵闹
            print("注册完成")
        except Exception as e:
            print(e)
            self.app.model_dialog.show(
                title=self.text_config.get_section("AI_face")["face_recog_register"]["title"],
                content=f"{self.text_config.get_section("AI_face")["face_recog_register"]["modal_train_error"]}\n\n{e}",
                icon_symbol=lv.SYMBOL.CLOSE,
                btn_texts=[self.text_config.get_section("System")["Ok"]],
                width=480,
                height=300
            ).close_after(5000)
    
    def on_cancel_register(self, dialog):
        gc.collect()
        