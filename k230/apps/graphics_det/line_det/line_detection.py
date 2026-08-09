# 导入必要的模块 Import required modules
import time, os, sys, gc
from media.sensor import *
from media.display import *
from media.media import *

# 图像分辨率设置 Image resolution settings
PICTURE_WIDTH = 160
PICTURE_HEIGHT = 120

# 摄像头配置 Camera configuration
sensor = None

DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)

def scale_coordinates(data_tuple, target_resolution="640x480"):
    """
    将160x120分辨率下的坐标元组等比例缩放到目标分辨率
    
    参数:
        data_tuple: 包含坐标信息的元组 (x1, y1, x2, y2)
        target_resolution: 目标分辨率，可选 "640x480" 或 "640x480"
    
    返回:
        包含缩放后坐标的新元组 (x1, y1, x2, y2, length)
    """
    # 检查输入类型
    if not isinstance(data_tuple, tuple) or len(data_tuple) < 4:
        raise TypeError(f"期望输入至少包含4个元素的元组，但收到了 {type(data_tuple).__name__}")
    
    # 解包元组
    x1, y1, x2, y2 = data_tuple[:4]
    
    # 原始分辨率
    src_width, src_height = 160, 120
    
    # 目标分辨率
    if target_resolution == "640x480":
        dst_width, dst_height = 640, 480
    elif target_resolution == "640x480":
        dst_width, dst_height = 640, 480
    else:
        raise ValueError("不支持的分辨率，请使用 '640x480' 或 '640x480'")
    
    # 计算缩放比例
    scale_x = dst_width / src_width
    scale_y = dst_height / src_height
    
    # 缩放坐标
    scaled_x1 = round(x1 * scale_x)
    scaled_y1 = round(y1 * scale_y)
    scaled_x2 = round(x2 * scale_x)
    scaled_y2 = round(y2 * scale_y)
    
    # 计算新的长度
    dx = scaled_x2 - scaled_x1
    dy = scaled_y2 - scaled_y1
    length = round((dx**2 + dy**2)**0.5)
    
    # 返回缩放后的坐标元组
    return (scaled_x1, scaled_y1, scaled_x2, scaled_y2)

class YAHBOOM_DEMO:
    def __init__(self, pl):
        self.pl = pl
    def exce_demo(self, loading_text="Loading ..."):
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

            # 捕获图像 Capture image
            img = self.pl.sensor.snapshot(chn=CAM_CHN_ID_1)
            lines = img.find_line_segments(merge_distance=20, max_theta_diff=10)
            img = image.Image(640, 480, image.ARGB8888)
            img.clear()
            pass
            for i, line in enumerate(lines):
                # 使用蓝色绘制线段 Draw lines in blue
                line = scale_coordinates(line.line())
                img.draw_line(line, color=(255,0,0), thickness=8)
                pass
            pass

            Display.show_image(img, 0,0,Display.LAYER_OSD3)
            time.sleep_us(1)

    def exit_demo(self):
        pass