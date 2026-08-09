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
# 边缘检测参数 / Edge detection parameters (Canny thresholds)
# -------------------------------
threshold1 = 50   # Canny 边缘检测低阈值 / Lower threshold for Canny
threshold2 = 80   # Canny 边缘检测高阈值 / Higher threshold for Canny

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

            # 调用 cv_lite 扩展的边缘检测函数，返回灰度边缘图 ndarray
            # Call cv_lite extension edge detection function, returns grayscale edge image ndarray
            edge_np = cv_lite.rgb888_find_edges(image_shape, img_np, threshold1, threshold2)

            # 构造灰度图像对象用于显示 Create grayscale image object for display
            img_out = image.Image(image_shape[1], image_shape[0], image.GRAYSCALE, alloc=image.ALLOC_REF, data=edge_np)

            # 显示边缘检测结果 Display edge detection result
            Display.show_image(img_out, 0, 0, Display.LAYER_OSD3)
            
            # 释放临时变量内存 Free temporary variables memory
            del img_np
            del img_out
            
            # 进行垃圾回收 Perform garbage collection
            gc.collect()
            
            time.sleep_us(1)

    def exit_demo(self):
        pass
