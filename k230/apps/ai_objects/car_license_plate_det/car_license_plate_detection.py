# 导入所需的库文件 Import required libraries
from libs.PipeLine import PipeLine, ScopedTiming
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
import os
import ujson
from media.media import *
from time import *
import nncase_runtime as nn
import ulab.numpy as np
import time
import utime
import image
import random
import gc
import sys
import aidemo
# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH

uart = None
# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)
# 车牌检测类 License Plate Detection Class
class LicenceDetectionApp(AIBase):
    """
    车牌检测应用类，继承自AIBase
    License plate detection application class, inherited from AIBase
    """
    def __init__(self, kmodel_path, model_input_size, confidence_threshold=0.5, nms_threshold=0.2, rgb888p_size=[224,224], display_size=[1920,1080], debug_mode=0):
        """
        初始化函数 Initialization function
        参数 Parameters:
            kmodel_path: 模型路径 Model path
            model_input_size: 模型输入尺寸 Model input size
            confidence_threshold: 置信度阈值 Confidence threshold
            nms_threshold: NMS阈值 NMS threshold
            rgb888p_size: 输入图像尺寸 Input image size
            display_size: 显示尺寸 Display size
            debug_mode: 调试模式 Debug mode
        """
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        # 确保宽度是16的倍数 Ensure width is multiple of 16
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        
        # 初始化AI2D实例用于图像预处理 Initialize AI2D instance for image preprocessing
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)
        self.crop_x = 0
        self.crop_y = 0
        self.crop_w = 0
        self.crop_h = 0

    def config_preprocess(self, input_image_size=None):
        """
        配置图像预处理参数 Configure image preprocessing parameters
        """
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            
            # 计算 Center Crop 参数，保持 1:1 比例输入给模型，避免拉伸变形
            # Calculate Center Crop parameters to keep 1:1 aspect ratio for model input, avoiding stretching
            w = ai2d_input_size[0]
            h = ai2d_input_size[1]
            crop_size = min(w, h)
            self.crop_w = crop_size
            self.crop_h = crop_size
            self.crop_x = (w - crop_size) // 2
            self.crop_y = (h - crop_size) // 2
            
            # 配置 Crop 和 Resize
            self.ai2d.crop(self.crop_x, self.crop_y, self.crop_w, self.crop_h)
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        """
        后处理函数 Postprocessing function
        对模型输出结果进行处理 Process model output results
        """
        with ScopedTiming("postprocess", self.debug_mode > 0):
            # 传入 Crop 后的尺寸，让 aidemo 计算出相对于 Crop 区域的坐标
            det_res = aidemo.licence_det_postprocess(results, 
                                                   [self.crop_h, self.crop_w], 
                                                   self.model_input_size, 
                                                   self.confidence_threshold, 
                                                   self.nms_threshold)
            
            # 将坐标还原为相对于原图 (Input Image) 的坐标
            if det_res:
                for i in range(len(det_res)):
                    for j in range(4):
                        det_res[i][j * 2 + 0] += self.crop_x
                        det_res[i][j * 2 + 1] += self.crop_y
            
            return det_res

    def draw_result(self, pl, dets):
        """
        绘制检测结果 Draw detection results
        参数 Parameters:
            pl: PipeLine实例 PipeLine instance
            dets: 检测结果 Detection results
        """
        with ScopedTiming("display_draw", self.debug_mode > 0):
            if dets:
                pl.osd_img.clear()
                point_8 = np.zeros((8), dtype=np.int16)
                for det in dets:
                    # 坐标转换 Coordinate conversion
                    for i in range(4):
                        # 此时 det 已经是相对于原图的坐标了，直接映射到显示屏幕坐标
                        x = det[i * 2 + 0] / self.rgb888p_size[0] * self.display_size[0]
                        y = det[i * 2 + 1] / self.rgb888p_size[1] * self.display_size[1]
                        
                        point_8[i * 2 + 0] = int(x)
                        point_8[i * 2 + 1] = int(y)
                    # 绘制检测框 Draw detection box
                    for i in range(4):
                        pl.osd_img.draw_line(point_8[i * 2 + 0], 
                                           point_8[i * 2 + 1], 
                                           point_8[(i + 1) % 4 * 2 + 0], 
                                           point_8[(i + 1) % 4 * 2 + 1], 
                                           color=(255, 0, 255, 0), 
                                           thickness=4)
                        uart.send(f"${point_8[i * 2 + 0]},{point_8[i * 2 + 1]},{point_8[(i + 1) % 4 * 2 + 0]},{point_8[(i + 1) % 4 * 2 + 1]}#")
            else:
                pl.osd_img.clear()

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.licence_det = None
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
        gc.collect()
        # 使用 PipeLine 的真实输入尺寸，避免因尺寸不匹配导致的 Stride 错位（双框/乱码）和坐标偏差
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        # print(f"rgb888p_size:{rgb888p_size},display_size:{display_size}")
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()
        kmodel_path="/sdcard/kmodel/LPD_640.kmodel"
        # 恢复默认阈值，与 good.py 保持一致
        confidence_threshold = 0.2
        nms_threshold = 0.2
        
        # 初始化车牌检测实例 Initialize license plate detection instance
        self.licence_det=LicenceDetectionApp(kmodel_path,
                                    model_input_size=[640,640],
                                    confidence_threshold=confidence_threshold,
                                    nms_threshold=nms_threshold,
                                    rgb888p_size=rgb888p_size,
                                    display_size=display_size,
                                    debug_mode=0)
        self.licence_det.config_preprocess()
        
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        pass
                        time.sleep_ms(10)
                        break
            img=self.pl.get_frame()  # 获取图像帧 Get image frame
            res=self.licence_det.run(img)  # 执行检测 Run detection
            self.licence_det.draw_result(self.pl,res)  # 绘制结果 Draw results
            self.pl.show_image()  # 显示图像 Show image
            gc.collect()  # 垃圾回收 Garbage collection
            time.sleep_us(1)
            

    def exit_demo():
        pass