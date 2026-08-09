# 导入所需的库文件 Import required libraries
from libs.PipeLine import PipeLine, ScopedTiming  # 导入视频处理管道和计时器 Import video pipeline and timer
from libs.AIBase import AIBase  # 导入AI基类 Import AI base class
from libs.AI2D import Ai2d  # 导入2D图像处理类 Import 2D image processing class
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
import gc  # 垃圾回收模块 Garbage collection module
import sys
import aicube

from machine import TOUCH
from libs.YbProtocol import YbProtocol

uart = None
pto = YbProtocol()

# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)

class HandDetectionApp(AIBase):
    """
    手掌检测应用类 Hand Detection Application Class
    继承自AIBase基类 Inherits from AIBase
    """
    def __init__(self, kmodel_path, model_input_size, labels, anchors, confidence_threshold=0.2, 
                 nms_threshold=0.5, nms_option=False, strides=[8,16,32], 
                 rgb888p_size=[224,224], display_size=[1920,1080], debug_mode=0):
        """
        初始化函数 Initialization function
        参数 Parameters:
        - kmodel_path: 模型文件路径 Model file path
        - model_input_size: 模型输入尺寸 Model input size
        - labels: 检测类别标签 Detection class labels
        - anchors: 锚框尺寸 Anchor box sizes
        - confidence_threshold: 置信度阈值 Confidence threshold
        - nms_threshold: 非极大值抑制阈值 Non-maximum suppression threshold
        - 等等 etc.
        """
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.labels = labels
        self.anchors = anchors
        self.strides = strides
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.nms_option = nms_option
        # 确保尺寸是16的倍数 Ensure sizes are multiples of 16
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        # 设置AI2D数据格式和类型 Set AI2D data format and type
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, 
                                np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        """
        配置图像预处理步骤 Configure image preprocessing steps
        包括填充和缩放操作 Including padding and scaling operations
        """
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            # 计算填充参数 Calculate padding parameters
            top, bottom, left, right = self.get_padding_param()
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [0, 0, 0])
            # 设置双线性插值缩放 Set bilinear interpolation scaling
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                          [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        """
        后处理函数 Postprocessing function
        处理模型的原始输出 Process model's raw output
        """
        with ScopedTiming("postprocess", self.debug_mode > 0):
            # 使用aicube进行后处理 Use aicube for postprocessing
            dets = aicube.anchorbasedet_post_process(results[0], results[1], results[2], 
                                                   self.model_input_size, self.rgb888p_size, 
                                                   self.strides, len(self.labels), 
                                                   self.confidence_threshold, self.nms_threshold, 
                                                   self.anchors, self.nms_option)
            return dets

    def draw_result(self, pl, dets):
        """
        绘制检测结果 Draw detection results
        在图像上绘制边界框和标签 Draw bounding boxes and labels on image
        """
        with ScopedTiming("display_draw", self.debug_mode > 0):
            if dets:
                pl.osd_img.clear()  # 清除旧的绘制内容 Clear old drawings
                for det_box in dets:
                    # 计算边界框坐标 Calculate bounding box coordinates
                    x1, y1, x2, y2 = det_box[2], det_box[3], det_box[4], det_box[5]
                    # 调整坐标到显示尺寸 Adjust coordinates to display size
                    w = float(x2 - x1) * self.display_size[0] // self.rgb888p_size[0]
                    h = float(y2 - y1) * self.display_size[1] // self.rgb888p_size[1]
                    x1 = int(x1 * self.display_size[0] // self.rgb888p_size[0])
                    y1 = int(y1 * self.display_size[1] // self.rgb888p_size[1])
                    x2 = int(x2 * self.display_size[0] // self.rgb888p_size[0])
                    y2 = int(y2 * self.display_size[1] // self.rgb888p_size[1])
                    
                    # 过滤小目标 Filter small objects
                    if (h < (0.1 * self.display_size[0])):
                        continue
                    if (w < (0.25 * self.display_size[0]) and 
                        ((x1 < (0.03 * self.display_size[0])) or 
                         (x2 > (0.97 * self.display_size[0])))):
                        continue
                    if (w < (0.15 * self.display_size[0]) and 
                        ((x1 < (0.01 * self.display_size[0])) or 
                         (x2 > (0.99 * self.display_size[0])))):
                        continue
                    
                    # 绘制矩形框和标签 Draw rectangle and label
                    pl.osd_img.draw_rectangle(x1, y1, int(w), int(h), 
                                           color=(255, 0, 255, 0), thickness=3)
                    pl.osd_img.draw_string_advanced(x1, y1-50, 32, 
                                                  " " + self.labels[det_box[0]] + " " + 
                                                  str(round(det_box[1], 2)), 
                                                  color=(255, 0, 255, 0))
                    pto_data = pto.get_hand_detect_data(x1, y1, w, h)
                    uart.send(pto_data)
                    print(pto_data)
            else:
                pl.osd_img.clear()

    def get_padding_param(self):
        """
        计算填充参数 Calculate padding parameters
        确保图像保持原始比例 Ensure image maintains original aspect ratio
        """
        dst_w = self.model_input_size[0]
        dst_h = self.model_input_size[1]
        input_width = self.rgb888p_size[0]
        input_high = self.rgb888p_size[1]
        
        # 计算缩放比例 Calculate scaling ratio
        ratio_w = dst_w / input_width
        ratio_h = dst_h / input_high
        ratio = min(ratio_w, ratio_h)
        
        # 计算新尺寸 Calculate new dimensions
        new_w = int(ratio * input_width)
        new_h = int(ratio * input_high)
        
        # 计算填充量 Calculate padding amounts
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        top = int(round(dh - 0.1))
        bottom = int(round(dh + 0.1))
        left = int(round(dw - 0.1))
        right = int(round(dw + 0.1))
        return top, bottom, left, right

# 主程序部分 Main program section

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.person_kp = None
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
        """
        执行演示函数 Execute demonstration function
        运行手掌检测循环 Run hand detection loop
        """

        rgb888p_size=self.pl.rgb888p_size
        display_size = self.pl.display_size
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()
        # 设置模型和参数 Set model and parameters
        kmodel_path = "/sdcard/kmodel/hand_det.kmodel"
        confidence_threshold = 0.2
        nms_threshold = 0.5
        labels = ["hand"]
        anchors = [26,27, 53,52, 75,71, 80,99, 106,82, 99,134, 140,113, 161,172, 245,276]

        try:
            # 初始化检测器 Initialize detector
            self.hand_det = HandDetectionApp(kmodel_path, model_input_size=[512,512], 
                                    labels=labels, anchors=anchors,
                                    confidence_threshold=confidence_threshold,
                                    nms_threshold=nms_threshold, nms_option=False,
                                    strides=[8,16,32], rgb888p_size=rgb888p_size,
                                    display_size=display_size, debug_mode=0)
            self.hand_det.config_preprocess()
            
            # 主循环 Main loop
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
                img = self.pl.get_frame()         # 获取帧 Get frame
                res = self.hand_det.run(img)      # 运行检测 Run detection
                self.hand_det.draw_result(self.pl,res) # 绘制结果 Draw results
                self.pl.show_image()              # 显示图像 Show image
                gc.collect()                 # 垃圾回收 Garbage collection
                time.sleep_us(1)
        except Exception as e:
            pass

    def exit_demo(self):
        return