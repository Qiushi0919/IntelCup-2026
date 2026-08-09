# 导入必要的模块 Import required modules
import time, os, sys, gc
from machine import Pin
from media.sensor import *     # 摄像头接口 / Camera interface
from media.display import *    # 显示接口 / Display interface
from media.media import *      # 媒体资源管理器 / Media manager
import _thread
import cv_lite                 # cv_lite扩展模块 / cv_lite extension module
import ulab.numpy as np
import image

image_shape = [480, 640]

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)

# -------------------------------
# 霍夫圆检测参数 / Hough Circle parameters
# -------------------------------
dp = 1           # 累加器分辨率与图像分辨率的反比 / Inverse ratio of accumulator resolution
minDist = 30     # 检测到的圆心最小距离 / Minimum distance between detected centers
param1 = 80      # Canny边缘检测高阈值 / Higher threshold for Canny edge detection
param2 = 20      # 霍夫变换圆心检测阈值 / Threshold for center detection in accumulator
minRadius = 10   # 检测圆最小半径 / Minimum circle radius
maxRadius = 50   # 检测圆最大半径 / Maximum circle radius

class YAHBOOM_DEMO:
    def __init__(self, pl):
        self.pl = pl
        
    def exce_demo(self, loading_text="Loading ..."):
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x < 100 and pt.y < 100:
                        pass
                        self.exit_demo()
                        time.sleep_ms(10)
                        break

            # 捕获图像 Capture image
            img = self.pl.sensor.snapshot(chn=CAM_CHN_ID_1)
            img = img.to_rgb888()  # 转换为 RGB888 格式 / Convert to RGB888 format
            img_np = img.to_numpy_ref()  # 获取 RGB888 ndarray 引用 / Get RGB888 ndarray reference

            # 调用 cv_lite 扩展的霍夫圆检测函数，返回圆参数列表 [x, y, r, ...]
            # Call cv_lite extension Hough circle detection function, returns circle parameters [x, y, r, ...]
            circles = cv_lite.rgb888_find_circles(
                image_shape, img_np, dp, minDist, param1, param2, minRadius, maxRadius
            )

            # 创建新的图像用于显示 Create new image for display
            img = image.Image(640, 480, image.ARGB8888)
            img.clear()
            
            # 遍历检测到的圆形，绘制圆形框 Iterate detected circles and draw them
            for i in range(0, len(circles), 3):
                x = circles[i]
                y = circles[i + 1]
                r = circles[i + 2]
                img.draw_circle(x, y, r, color=(255, 0, 0), thickness=2)  # 红色圆圈 Red circles

            # 显示带有检测圆的图像 Display image with circles drawn
            Display.show_image(img, 0, 0, Display.LAYER_OSD3)
            
            # 释放临时变量内存 Free temporary variables memory
            del img_np
            
            # 进行垃圾回收 Perform garbage collection
            gc.collect()
            
            time.sleep_us(1)

    def exit_demo(self):
        pass
