# 导入必要的模块 Import required modules
import time, os, sys, gc
from media.sensor import *
from media.display import *
from media.media import *

DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480
from libs.YbProtocol import YbProtocol
from ybUtils.YbUart import YbUart
uart = None
pto = YbProtocol()
# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)

THRESHOLDS = [
    (32, 55, 26, 92, -3, 41),    # 红色阈值 / Red threshold
    (42, 100, -128, -17, 6, 66),     # 绿色阈值 / Green threshold
    (43, 99, -43, -4, -56, -7),       # 蓝色阈值 / Blue threshold
    (37, 100, -128, 127, -128, -27)    # 亚博智能Logo的颜色 color of YAHBOOM
]


def process_blobs(img, blobs, color):
    """处理检测到的色块 / Process detected color blobs"""
    for blob in blobs:
        img.draw_rectangle(blob[0:4], color=color, thickness=4)
        img.draw_cross(blob[5], blob[6], color=color, thickness=2)
            
class YAHBOOM_DEMO:
    def __init__(self, pl,  _uart = None):
        global uart
        self.pl = pl
        uart = _uart
        
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
            img = self.pl.sensor.snapshot(chn=CAM_CHN_ID_1)

            # 检测指定颜色 / Detect specified color
            blobs = img.find_blobs([THRESHOLDS[0]])
            img.clear()
            if blobs:
                process_blobs(img, blobs, (255,0,0))

            Display.show_image(img)
            time.sleep_us(1)

    def exit_demo(self):
        pass