# 导入必要的模块 Import required modules
import time, os, sys, gc
from machine import Pin
from media.sensor import *     # 摄像头接口 / Camera interface
from media.display import *    # 显示接口 / Display interface
from media.media import *      # 媒体资源管理器 / Media manager
import _thread
import cv_lite                 # cv_lite扩展模块 / cv_lite extension module
import ulab.numpy as np

image_shape = [480, 640]

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)
# -------------------------------
# 可调参数（建议调试时调整）/ Adjustable parameters (recommended for tuning)
# -------------------------------
canny_thresh1       = 50        # Canny 边缘检测低阈值 / Canny edge low threshold
canny_thresh2       = 150       # Canny 边缘检测高阈值 / Canny edge high threshold
approx_epsilon      = 0.04      # 多边形拟合精度（比例） / Polygon approximation precision (ratio)
area_min_ratio      = 0.001     # 最小面积比例（0~1） / Minimum area ratio (0~1)
max_angle_cos       = 0.5       # 最大角余弦（值越小越接近矩形） / Max cosine of angle (smaller closer to rectangle)
gaussian_blur_size  = 5         # 高斯模糊核大小（奇数） / Gaussian blur kernel size (odd number)

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
            img = img.to_rgb888()  # 转换为 RGB888 格式 / Convert to RGB888 format
            img_np = img.to_numpy_ref()  # 获取 RGB888 ndarray 引用 / Get RGB888 ndarray reference

            # 调用底层矩形检测函数，返回矩形列表 [x0, y0, w0, h0, x1, y1, w1, h1, ...]
            # Call underlying rectangle detection function, returns list of rectangles [x, y, w, h, ...]
            rects = cv_lite.rgb888_find_rectangles(
                image_shape, img_np,
                canny_thresh1, canny_thresh2,
                approx_epsilon,
                area_min_ratio,
                max_angle_cos,
                gaussian_blur_size
            )
            img = image.Image(640, 480, image.ARGB8888)
            img.clear()
            for i in range(0, len(rects), 4):
                x = rects[i]
                y = rects[i + 1]
                w = rects[i + 2]
                h = rects[i + 3]
                img.draw_rectangle(x, y, w, h, color=(255, 0, 0), thickness=2)

            Display.show_image(img, 0,0,Display.LAYER_OSD3)
            time.sleep_us(1)

    def exit_demo(self):
        pass