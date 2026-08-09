import time
import os
import sys
from media.sensor import *
from media.display import *
from media.media import *
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)


# 常量定义 / Constants definition
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
# 待检测物体的LAB色彩空间阈值 / LAB color space thresholds
# 这里写的阈值是配套工具中【金币生成器】生成的金币的颜色
# Format: (L_min, L_max, A_min, A_max, B_min, B_max)
TRACK_THRESHOLD = [(0, 100, -7, 127, 10, 83)]
# 文字显示参数 / Text display parameters
FONT_SIZE = 25
TEXT_COLOR = (233, 233, 233)  # 白色 / White

def process_frame(img, threshold):
    """
    处理单帧图像，检测并标记目标物体
    Process single frame, detect and mark target objects

    Args:
        img: 输入图像 / Input image
        threshold: 颜色阈值 / Color threshold

    Returns:
        blobs: 检测到的物体列表 / List of detected objects
    """
    blobs = img.find_blobs([threshold])

    if blobs:
        for blob in blobs:
            # 绘制矩形框和中心十字 / Draw rectangle and center cross
            img.draw_rectangle(blob[0:4])
            img.draw_cross(blob[5], blob[6])

    return blobs

def draw_info(img, fps, blobs):
    """
    在图像上绘制信息
    Draw information on image

    Args:
        img: 输入图像 / Input image
        fps: 帧率 / Frames per second
        num_objects: 检测到的物体数量 / Number of detected objects
    """
    num_objects = len(blobs)
    info_text = f'Num: {num_objects}'
    if blobs:
        for blob in blobs:
            # 绘制矩形框和中心十字 / Draw rectangle and center cross
            img.draw_rectangle(blob[0:4])
            img.draw_cross(blob[5], blob[6])
        img.draw_string_advanced(0, 50, FONT_SIZE, info_text, color=TEXT_COLOR)
    


class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        self.pl = pl
        self.uart = _uart
        
    def exce_demo(self, loading_text="Loading ..."):
        """
        主程序入口
        Main program entry
        """

        # 创建时钟对象用于FPS计算 / Create clock object for FPS calculation

        while True:
            
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        pass
                        self.exit_demo()
                        time.sleep_ms(10)
                        break
                    
            # 捕获图像 / Capture image
            img = self.pl.sensor.snapshot(chn=CAM_CHN_ID_1)
            

            # 处理图像 / Process image
            blobs = process_frame(img, TRACK_THRESHOLD[0])

            img.clear()
            
            # 显示信息 / Display information
            draw_info(img, 1, blobs)

            # 显示图像 / Show image
            Display.show_image(img)
            
            time.sleep_us(1)

            
    def exit_demo(self):
        pass