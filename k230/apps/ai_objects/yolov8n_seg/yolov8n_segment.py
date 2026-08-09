# 导入必要的库 Import required libraries
from libs.PipeLine import PipeLine, ScopedTiming  # 导入视频处理Pipline和计时器 Import video pipeline and timer
from libs.AIBase import AIBase  # 导入AI基类 Import AI base class
from libs.AI2D import Ai2d    # 导入图像预处理类 Import image preprocessing class
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

# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)

class SegmentationApp(AIBase):
    """
    YOLOv8分割应用类 / YOLOv8 Segmentation Application Class
    """
    def __init__(self,kmodel_path,labels,model_input_size,confidence_threshold=0.2,nms_threshold=0.5,mask_threshold=0.5,rgb888p_size=[224,224],display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 / Initialization function
        
        参数 / Parameters:
        kmodel_path: 模型路径 / Model path
        labels: 类别标签 / Category labels
        model_input_size: 模型输入尺寸 / Model input size
        confidence_threshold: 置信度阈值 / Confidence threshold
        nms_threshold: NMS阈值 / NMS threshold
        mask_threshold: 掩码阈值 / Mask threshold
        rgb888p_size: 输入图像尺寸 / Input image size
        display_size: 显示尺寸 / Display size
        debug_mode: 调试模式 / Debug mode
        """
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        
        # 初始化各种参数 Initialize parameters
        self.kmodel_path = kmodel_path
        self.labels = labels  
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.mask_threshold = mask_threshold
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode = debug_mode
        
        # 检测框预置颜色值 / Predefined colors for detection boxes
        self.color_four = [(255, 220, 20, 60), (255, 119, 11, 32), (255, 0, 0, 142), (255, 0, 0, 230),
                        (255, 106, 0, 228), (255, 0, 60, 100), (255, 0, 80, 100), (255, 0, 0, 70),
                        (255, 0, 0, 192), (255, 250, 170, 30), (255, 100, 170, 30), (255, 220, 220, 0),
                        (255, 175, 116, 175), (255, 250, 0, 30), (255, 165, 42, 42), (255, 255, 77, 255),
                        (255, 0, 226, 252), (255, 182, 182, 255), (255, 0, 82, 0), (255, 120, 166, 157)]
        
        # 初始化掩码数组 / Initialize mask array
        self.masks = np.zeros((1,self.display_size[1],self.display_size[0],4))
        
        # 初始化AI2D预处理器 / Initialize AI2D preprocessor
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,input_image_size=None):
        """
        配置图像预处理参数 / Configure image preprocessing parameters
        """
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top,bottom,left,right = self.get_padding_param()
            # 设置padding和resize参数 / Set padding and resize parameters
            self.ai2d.pad([0,0,0,0,top,bottom,left,right], 0, [114,114,114])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                          [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        """
        后处理函数 / Post-processing function
        """
        with ScopedTiming("postprocess",self.debug_mode > 0):
            # 调用aidemo进行分割后处理 / Call aidemo for segmentation post-processing
            seg_res = aidemo.segment_postprocess(results,
                                               [self.rgb888p_size[1],self.rgb888p_size[0]],
                                               self.model_input_size,
                                               [self.display_size[1],self.display_size[0]],
                                               self.confidence_threshold,
                                               self.nms_threshold,
                                               self.mask_threshold,
                                               self.masks)
            return seg_res

    def draw_result(self,pl,seg_res):
        """
        绘制分割结果 / Draw segmentation results
        """
        with ScopedTiming("display_draw",self.debug_mode >0):
            if seg_res[0]:
                pl.osd_img.clear()
                # 创建掩码图像 / Create mask image
                mask_img = image.Image(self.display_size[0], self.display_size[1], 
                                     image.ARGB8888,alloc=image.ALLOC_REF,data=self.masks)
                pl.osd_img.copy_from(mask_img)
                dets,ids,scores = seg_res[0],seg_res[1],seg_res[2]
                # 绘制检测框和标签 / Draw detection boxes and labels
                for i, det in enumerate(dets):
                    x1, y1, w, h = map(lambda x: int(round(x, 0)), det)
                    pl.osd_img.draw_string_advanced(x1,y1-50,32, 
                                                  " " + self.labels[int(ids[i])] + " " + str(round(scores[i],2)), 
                                                  color=self.get_color(int(ids[i])))
            else:
                pl.osd_img.clear()

    def get_padding_param(self):
        """
        计算padding参数 / Calculate padding parameters
        返回值：top, bottom, left, right padding的像素值 / Returns: padding pixels for top, bottom, left, right
        """
        dst_w = self.model_input_size[0]
        dst_h = self.model_input_size[1]
        # 计算宽高缩放比例 / Calculate width and height scaling ratios
        ratio_w = float(dst_w) / self.rgb888p_size[0]
        ratio_h = float(dst_h) / self.rgb888p_size[1]
        # 选择较小的缩放比例，保持长宽比 / Choose smaller ratio to maintain aspect ratio
        ratio = ratio_w if ratio_w < ratio_h else ratio_h
        
        # 计算缩放后的新尺寸 / Calculate new dimensions after scaling
        new_w = (int)(ratio * self.rgb888p_size[0])
        new_h = (int)(ratio * self.rgb888p_size[1])
        
        # 计算需要填充的像素数 / Calculate padding pixels
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        
        # 向上取整获取最终padding值 / Round up to get final padding values
        top = (int)(round(dh - 0.1))
        bottom = (int)(round(dh + 0.1))
        left = (int)(round(dw - 0.1))
        right = (int)(round(dw + 0.1))
        return top, bottom, left, right

    def get_color(self, x):
        """
        获取颜色值 / Get color value
        参数 x: 类别索引 / Parameter x: category index
        返回值：对应的颜色元组 / Returns: corresponding color tuple
        """
        idx = x % len(self.color_four)
        return self.color_four[idx]

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        self.pl = pl
        self.seg = None
    def exce_demo(self, loading_text="Loading ..."):
        gc.collect()
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()

        # 模型和参数配置 / Model and parameter configuration
        kmodel_path = "/sdcard/kmodel/yolov8n_seg_320.kmodel"
        # 检测类别标签 / Detection category labels
        labels = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", 
                "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", 
                "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", 
                "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", 
                "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", 
                "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", 
                "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", 
                "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", 
                "scissors", "teddy bear", "hair drier", "toothbrush"]
        
        # 设置阈值参数 / Set threshold parameters
        confidence_threshold = 0.2
        nms_threshold = 0.5
        mask_threshold = 0.5
        # 初始化分割应用 / Initialize segmentation application
        self.seg = SegmentationApp(kmodel_path, 
                            labels=labels,
                            model_input_size=[320,320],
                            confidence_threshold=confidence_threshold,
                            nms_threshold=nms_threshold,
                            mask_threshold=mask_threshold,
                            rgb888p_size=rgb888p_size,
                            display_size=display_size,
                            debug_mode=0)
        self.seg.config_preprocess()
        
        # 主循环 / Main loop
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        pass
                        time.sleep_ms(10)
                        break
            img = self.pl.get_frame()  # 获取当前帧 / Get current frame
            seg_res = self.seg.run(img)  # 执行分割 / Perform segmentation
            self.seg.draw_result(self.pl,seg_res)  # 绘制结果 / Draw results
            self.pl.show_image()  # 显示图像 / Display image
            gc.collect()  # 垃圾回收 / Garbage collection
            time.sleep_us(1)
            
    def exit_demo():
        pass