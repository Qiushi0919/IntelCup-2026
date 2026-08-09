import time, os, sys
from media.sensor import *
from media.display import *
from media.media import *
# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)


# 显示参数 / Display parameters
DISPLAY_WIDTH = 640    # LCD显示宽度 / LCD display width
DISPLAY_HEIGHT = 480   # LCD显示高度 / LCD display height

# 颜色阈值(LAB色彩空间) / Color thresholds (LAB color space)
# (L Min, L Max, A Min, A Max, B Min, B Max)
COLOR_THRESHOLDS = [
    (54, 96, -13, 122, 12, 127),    # 红色阈值 / Red threshold
    (55, 100, -128, -17, -3, 127),     # 绿色阈值 / Green threshold
    (52, 100, -74, 44, -128, -9)       # 蓝色阈值 / Blue threshold
]


# 显示颜色定义 / Display color definitions
# DRAW_COLORS = [(255, 255,0,0), (255, 0,255,0), (255, 0, 0, 255)]  # RGB颜色 / RGB colors
DRAW_COLORS = [(255, 255,0,0), (255, 255,0,0), (255, 255,0,0)]  # RGB颜色 / RGB colors
# DRAW_COLORS = [(0,0,0), (0,0,0), (0,0,0)]  # RGB颜色 / RGB colors
COLOR_LABELS = ['RED', 'GREEN', 'BLUE']           # 颜色标签 / Color labels

def process_blobs(img, threshold_idx):
    """处理颜色区块检测 / Process color blob detection"""
    blobs = img.find_blobs([COLOR_THRESHOLDS[threshold_idx]])
    if blobs:
        for blob in blobs:
            # 绘制检测框和标记 / Draw detection box and markers
            img.draw_rectangle(blob[0:4], thickness=4, color=DRAW_COLORS[threshold_idx])
            img.draw_cross(blob[5], blob[6], thickness=2)
            img.draw_string_advanced(blob[0], blob[1]-35, 30,
                                   COLOR_LABELS[threshold_idx],
                                   color=DRAW_COLORS[threshold_idx])

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        self.pl = pl
        self.uart = _uart
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

            # 检测三种颜色 / Detect three colors
            for i in range(3):
                process_blobs(img, i)
            # 显示图像并打印FPS / Display image and pass
            Display.show_image(img)
            time.sleep_us(2)
            
    def exit_demo(self):
        pass