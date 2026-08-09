import lvgl as lv
import os,gc
import time
import binascii
from ybMain.base_app import BaseApp
from media.media import *
from media.display import *
from machine import TOUCH
from ybUtils.Configuration import Configuration

# Initialize touch sensor on pin 0
tp = TOUCH(0)

def ensure_dir(directory):
    if not directory or directory == '/':
        return
    
    directory = directory.rstrip('/')
    
    try:
        os.stat(directory)
        return
    except OSError:
        print(f"Directory does not exist, creating: {directory}")
        if '/' in directory:
            parent = directory[:directory.rindex('/')]
            if parent and parent != directory:
                ensure_dir(parent)
        
        try:
            os.mkdir(directory)
        except OSError as e:
            print(f"Error creating directory {directory}: {e}")
            try:
                os.stat(directory)
            except:
                print(f"Still does not exist: {directory}")
    except Exception as e:
        print(f"Unexpected error: {e}")

class App(BaseApp):
    def __init__(self, app_manager):
        try:
            with open("/sdcard/apps/camera/icon.png", 'rb') as f:
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            print(f"Failed to load background image: {e}")
            img_bg = None
            
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        super().__init__(app_manager, self.text_config.get_section("System")["Camera"], icon=img_bg)
        self.pl = app_manager.pl
        self.texts = self.text_config.get_section("Camera")
        self.app_manager = app_manager
        
    def initialize(self):
        self.save_path = "/data/photo/"
        self.prefix = binascii.hexlify(os.urandom(5)).decode()
        self.i = 1
        
        # 主容器
        content = lv.obj(self.screen)
        content.set_size(lv.pct(100), 420)
        content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        content.set_style_pad_all(20, 0)
        content.set_style_bg_opa(0, 0)
        content.set_flex_flow(lv.FLEX_FLOW.ROW)  # 改为水平布局
        content.clear_flag(lv.obj.FLAG.SCROLLABLE)
        
        
        # 左侧容器
        left_panel = lv.obj(content)
        left_panel.set_size(lv.pct(35), lv.pct(100))
        left_panel.set_style_bg_opa(0, 0)
        left_panel.set_style_pad_all(10, 0)
        left_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        left_panel.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER)
        left_panel.set_style_border_width(0, 0)
        left_panel.clear_flag(lv.obj.FLAG.SCROLLABLE)
        # 将现有的文本和按钮添加到左侧面板
        intro_texts = [
            self.texts["intro_texts_l1"],
            self.texts["intro_texts_l2"],
            self.texts["intro_texts_l3"],
            self.texts["intro_texts_l4"] + self.prefix,
        ]
        
        for text in intro_texts:
            label = lv.label(left_panel)
            label.set_text(text)
            label.set_long_mode(lv.label.LONG.WRAP)
            label.set_width(lv.pct(100))
            label.set_style_text_font(self.app_manager.font_16, 0)
            label.set_style_margin_bottom(10, 0)
        
        path_label = lv.label(left_panel)
        path_label.set_text(f"{self.texts['path_label_text']} {self.save_path}")
        path_label.set_width(lv.pct(100))
        path_label.set_style_text_font(self.app_manager.font_16, 0)
        path_label.set_style_margin_bottom(30, 0)

        btn = lv.btn(left_panel)
        btn.set_size(200, 50)
        btn.set_style_bg_color(lv.color_make(0, 0, 0), 0)
        btn.set_style_radius(10, 0)
        btn.add_event(self.open_camera, lv.EVENT.CLICKED, None)
        
        label = lv.label(btn)
        label.set_text(self.texts["button"])
        label.center()
        label.set_style_text_color(lv.color_make(255, 255, 255), 0)

        # 右侧容器和图片
        right_panel = lv.obj(content)
        right_panel.set_size(lv.pct(65), lv.pct(100))
        right_panel.set_style_bg_opa(0, 0)
        right_panel.set_style_pad_all(10, 0)
        right_panel.set_style_border_width(0, 0)
        right_panel.clear_flag(lv.obj.FLAG.SCROLLABLE)

        # 添加图片
        img = lv.img(right_panel)
        try:
            with open("/sdcard/apps/camera/Camera.png", 'rb') as f:
                bg_image_cache_camera = f.read()
                img_bg_camera = lv.img_dsc_t({
                    'data_size': len(bg_image_cache_camera),
                    'data': bg_image_cache_camera
                })
        except Exception as e:
            print(f"Failed to load background image: {e}")
            img_bg_camera = None

        if img_bg_camera:
            img.set_src(img_bg_camera)
            # 设置图片大小，保持原始比例
            img.set_style_transform_zoom(256, 0)  # 256 表示 100% 缩放
            img.set_style_bg_opa(0, 0)
            img.set_style_radius(10, 0)
            # 设置图片对齐方式
            img.set_align(lv.ALIGN.CENTER)
            # 禁用图片的平铺效果
            img.set_style_img_recolor_opa(0, 0)
            img.set_style_img_opa(255, 0)

    def open_camera(self, event):
        gc.collect()
        img2 = image.Image(640, 480, image.RGB565)
        img2.clear()

        screen_height = 480
        button_x = 580
        button_y = screen_height // 2
        button_radius = 30

        img2.draw_circle(button_x, button_y, button_radius, color=(255, 255, 255), thickness=3)
        img2.draw_circle(button_x, button_y, button_radius - 5, color=(255, 255, 255), thickness=3, fill=True)
        img2.draw_line(20, 30, 50, 30, color=(255, 255, 255), thickness=4)
        img2.draw_line(20, 30, 35, 15, color=(255, 255, 255), thickness=4)
        img2.draw_line(20, 30, 35, 45, color=(255, 255, 255), thickness=4)
        
        Display.show_image(img2, 0, 0, Display.LAYER_OSD0)
        
        img = None
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    # if (pt.x - button_x) ** 2 + (pt.y - button_y) ** 2 <= (button_radius ** 2) + 50:
                    if pt.x > 520 and pt.y > 150 and pt.x < 640 and pt.y < 300:
                        self.take_picture(img)
                        img.draw_rectangle(4, 4, 640 - 8, 480 - 8, (200, 0, 0), thickness=8)
                        Display.show_image(img, 0, 0, Display.LAYER_OSD3)
                        time.sleep_ms(100)
                    elif pt.x < 60 and pt.y < 60:
                        self.exit_demo()
                        time.sleep_ms(10)
                        break
            
            img = self.pl.sensor.snapshot(chn=CAM_CHN_ID_1)
            
            Display.show_image(img, 0, 0, Display.LAYER_OSD3)
            
            time.sleep_ms(10)

    def take_picture(self, img):
        ensure_dir(self.save_path + str(self.prefix) + "/")
        path = self.save_path + str(self.prefix) + "/" + str(self.i) + ".jpg"
        self.i += 1
        img.save(path)
        time.sleep_ms(2)

    def deinitialize(self):
        img2 = image.Image(640, 480, image.RGB565)
        img2.clear()
        Display.show_image(img2, 0, 0, Display.LAYER_OSD3)

    def exit_demo(self):
        self.deinitialize()
        return