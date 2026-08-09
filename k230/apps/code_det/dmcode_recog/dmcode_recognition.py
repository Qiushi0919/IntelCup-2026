import time
import math
import os
import gc
import sys

from media.sensor import *
from media.display import *
from media.media import *
from libs.YbProtocol import YbProtocol
from ybUtils.YbUart import YbUart
uart = None
# uart = YbUart(baudrate=115200)
pto = YbProtocol()
# 定义检测图像的宽度和高度
# Define the width and height of the image for detection
DETECT_WIDTH = 640
DETECT_HEIGHT = 480

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)



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
            # 遍历图像中的 Data Matrix 条形码
            # Iterate through the Data Matrix codes found in the image
            matrixs = img.find_datamatrices()
            img.clear()
            for matrix in matrixs:
                # 绘制识别到的 Data Matrix 码的矩形框
                # Draw the rectangle around the detected Data Matrix code
                (x, y, w, h) = matrix.rect()
                y = y - 25 if y - 25 > 0 else y
                img.draw_rectangle([v for v in matrix.rect()], color=(255, 0, 0), thickness=5)
                # 打印矩阵的行列数、内容、旋转角度（度）以及当前的 FPS
                # pass
                print_args = (matrix.payload(), (180 * matrix.rotation()) / math.pi)
                img.draw_string_advanced(x, y, 20, "%s [%.2f]°" % print_args, color=(255,0,0))
                x, y, w, h = matrix.rect()
                pto_data = pto.get_dmcode_data(x, y, w, h, matrix.payload(), (180*matrix.rotation())/math.pi)
                uart.send(pto_data)
                print(pto_data)
                pass

            # 将结果显示到屏幕上
            # Display the result on the screen
            Display.show_image(img)

            # 进行垃圾回收，释放内存
            # Perform garbage collection to release memory
            gc.collect()
            time.sleep_us(1)

    def exit_demo(self):
        pass