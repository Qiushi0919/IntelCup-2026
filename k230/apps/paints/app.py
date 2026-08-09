import lvgl as lv
from ybMain.base_app import BaseApp
import time, os, urandom, sys,gc

# Import display and media related modules
# 导入显示和媒体相关模块
from media.display import *
from media.media import *

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH

# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)
# Define display resolution constants
# 定义显示分辨率常量
DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480

def display_test():
    """
    Function to test display and touch functionality
    测试显示和触摸功能的函数
    """

    # Create main background image with white color
    # 创建白色背景的主图像
    # img = image.Image(DISPLAY_WIDTH, 480, image.ARGB8888)
    # img.clear()


    # Create secondary image for drawing
    # 创建用于绘画的次要图像
    img2 = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.ARGB8888)
    img2.clear()
    img2.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT,color=(255,255,255),fill=True)
    img2.draw_line(20, 30, 50, 30, color=(33, 37, 43), thickness=4)
    img2.draw_line(20, 30, 35, 15, color=(33, 37, 43), thickness=4)
    img2.draw_line(20, 30, 35, 45, color=(33, 37, 43), thickness=4)
    Display.show_image(img2,0,0,Display.LAYER_OSD3)

    try:
        # Variables to store previous touch coordinates
        # 存储上一次触摸坐标的变量
        last_x = None
        last_y = None
        count = 0
        while True:
            # Read touch point data
            # 读取触摸点数据
            point = tp.read(1)

            if len(point):
                pt = point[0]
                # Handle touch events (down or move)
                # 处理触摸事件（按下或移动）
                # print("pt:", pt.x, pt.y, pt.event)
                if pt.event == 0 or pt.event == TOUCH.EVENT_UP or pt.event == TOUCH.EVENT_DOWN : # or pt.event == TOUCH.EVENT_MOVE
                    if pt.x<60 and pt.y<60:
                        time.sleep_ms(1)
                        break
                    if((last_x is not None) and (last_y is not None)): # and pt.event is not 2
                        # Draw line between previous and current touch points
                        # 在上一个触摸点和当前触摸点之间画线
                        img2.draw_line(last_x,last_y,pt.x, pt.y, color=(0,0,0), thickness = 5)
                        count = 0
                        # print("draw line")
                        Display.show_image(img2,0,0,Display.LAYER_OSD3)
                    last_x = pt.x
                    last_y = pt.y
            else:
                count = count + 1
                if count > 50:
                    last_x = None
                    last_y = None
            # Update display with background image
            # 更新显示背景图像
            # Display.show_image(img,0,50,Display.LAYER_OSD2)
            time.sleep_us(1)
    except BaseException as e:
        print(f"Exception {e}")
    finally:
        img2 = image.Image(640, 480, image.RGB565)
        img2.clear()
        Display.show_image(img2, 0, 0, Display.LAYER_OSD3)
        # Display.show_image(img2, 0, 0, Display.LAYER_OSD2)
        # 多次执行gc回收
        gc.collect()
        time.sleep(0.1)  # 给系统一点时间清理
        gc.collect()

class App(BaseApp):
    def __init__(self, app_manager):
        try:
            print("DEBUG: 尝试加载图标文件")
            with open("/sdcard/apps/paints/icon.png", 'rb') as f:
                bg_image_cache = f.read()
                img_bg = lv.img_dsc_t({
                    'data_size': len(bg_image_cache),
                    'data': bg_image_cache
                })
        except Exception as e:
            print(f"DEBUG: 图标加载失败: {str(e)}")
            img_bg = None
            
        try:
            self.app_manager = app_manager        
            self.config = app_manager.config
            self.text_config = app_manager.text_config
        except Exception as e:
            print(f"DEBUG: 基础配置初始化失败: {str(e)}")
            raise

        try:
            super().__init__(app_manager, self.text_config.get_section("System")["Paints"], icon=img_bg)
        except Exception as e:
            print(f"DEBUG: 父类初始化失败: {str(e)}")
            raise

        try:
            self.pl = app_manager.pl
            self.texts = self.text_config.get_section("Paints")
        except Exception as e:
            print(f"DEBUG: 其他配置加载失败: {str(e)}")
        
    def initialize(self):
        display_test()
        time.sleep(0.1)
        self.on_back()
        

    
    def deinitialize(self):
        print("DEBUG: 开始清理资源")