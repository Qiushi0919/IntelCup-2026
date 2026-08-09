# 导入所需库 Import required libraries
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
import aicube

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
uart = None
# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)

# 自定义OCR检测类 Custom OCR Detection Class
class OCRDetectionApp(AIBase):
    def __init__(self,kmodel_path,model_input_size,mask_threshold=0.5,box_threshold=0.2,rgb888p_size=[224,224],display_size=[1920,1080],debug_mode=0):
        """
        初始化OCR检测类
        Initialize OCR detection class
        
        参数 Parameters:
        kmodel_path: 模型路径 Model path
        model_input_size: 模型输入尺寸 Model input size
        mask_threshold: 掩码阈值 Mask threshold
        box_threshold: 边界框阈值 Box threshold
        rgb888p_size: RGB图像尺寸 RGB image size
        display_size: 显示尺寸 Display size
        debug_mode: 调试模式 Debug mode
        """
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path=kmodel_path
        self.model_input_size=model_input_size
        self.mask_threshold=mask_threshold
        self.box_threshold=box_threshold
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode=debug_mode
        self.ai2d=Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,input_image_size=None):
        """
        配置预处理操作
        Configure preprocessing operations
        """
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size=input_image_size if input_image_size else self.rgb888p_size
            top,bottom,left,right=self.get_padding_param()
            self.ai2d.pad([0,0,0,0,top,bottom,left,right], 0, [0,0,0])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        """
        后处理操作
        Postprocessing operations
        
        返回值 Returns:
        all_boxes_pos: 检测到的文本框位置列表 List of detected text box positions
        """
        with ScopedTiming("postprocess",self.debug_mode > 0):
            hwc_array=self.chw2hwc(self.cur_img)
            det_boxes = aicube.ocr_post_process(results[0][:,:,:,0].reshape(-1), hwc_array.reshape(-1),self.model_input_size,self.rgb888p_size, self.mask_threshold, self.box_threshold)
            all_boxes_pos=[]
            for det_box in det_boxes:
                all_boxes_pos.append(det_box[1])
            return all_boxes_pos
    def draw_result(self,pl,all_boxes_pos):
        """
        绘制检测结果
        Draw detection results
        
        参数 Parameters:
        pl: PipeLine实例 PipeLine instance
        all_boxes_pos: 检测框位置列表 List of detection box positions
        """
        with ScopedTiming("display_draw",self.debug_mode >0):
            pl.osd_img.clear()
            # 绘制每个检测到的文本框的四条边 Draw four edges for each detected text box
            for i in range(len(all_boxes_pos)):
                for j in range(4):
                    x1=all_boxes_pos[i][2*j]*self.display_size[0]//self.rgb888p_size[0]
                    y1=all_boxes_pos[i][2*j+1]*self.display_size[1]//self.rgb888p_size[1]
                    x2=all_boxes_pos[i][(2*j+2)%8]*self.display_size[0]//self.rgb888p_size[0]
                    y2=all_boxes_pos[i][(2*j+3)%8]*self.display_size[1]//self.rgb888p_size[1]
                    pl.osd_img.draw_line(int(x1),int(y1),int(x2),int(y2),color=(255,255,0,0),thickness=4)
                    uart.send(f"${x1},{y1},{x2},{y2}#")

    def get_padding_param(self):
        """
        计算padding参数
        Calculate padding parameters
        
        返回值 Returns:
        top, bottom, left, right: padding的四个方向参数 Four directional parameters for padding
        """
        dst_w = self.model_input_size[0]
        dst_h = self.model_input_size[1]
        input_width = self.rgb888p_size[0]
        input_high = self.rgb888p_size[1]
        # 计算缩放比例 Calculate scaling ratio
        ratio_w = dst_w / input_width
        ratio_h = dst_h / input_high
        ratio = ratio_w if ratio_w < ratio_h else ratio_h
        new_w = (int)(ratio * input_width)
        new_h = (int)(ratio * input_high)
        # 计算padding值 Calculate padding values
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        top = (int)(round(0))
        bottom = (int)(round(dh * 2 + 0.1))
        left = (int)(round(0))
        right = (int)(round(dw * 2 - 0.1))
        return top, bottom, left, right

    def chw2hwc(self,features):
        """
        将CHW格式转换为HWC格式
        Convert CHW format to HWC format
        
        参数 Parameters:
        features: CHW格式的数组 Array in CHW format
        
        返回值 Returns:
        hwc_array: HWC格式的数组 Array in HWC format
        """
        ori_shape = (features.shape[0], features.shape[1], features.shape[2])
        c_hw_ = features.reshape((ori_shape[0], ori_shape[1] * ori_shape[2]))
        hw_c_ = c_hw_.transpose()
        new_array = hw_c_.copy()
        hwc_array = new_array.reshape((ori_shape[1], ori_shape[2], ori_shape[0]))
        del c_hw_
        del hw_c_
        del new_array
        return hwc_array
    
class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.ocr_det = None
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
        gc.collect()
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()

        # 设置模型参数 Set model parameters
        kmodel_path = "/sdcard/kmodel/ocr_det_int16.kmodel"
        mask_threshold = 0.25
        box_threshold = 0.3
        # 初始化OCR检测 Initialize OCR detection
        self.ocr_det = OCRDetectionApp(kmodel_path,model_input_size=[640,640],mask_threshold=mask_threshold,
                                box_threshold=box_threshold,rgb888p_size=rgb888p_size,
                                display_size=display_size,debug_mode=0)
        self.ocr_det.config_preprocess()
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        pass
                        time.sleep_ms(10)
                        break
            img = self.pl.get_frame()                # 获取图像帧 Get image frame
            res = self.ocr_det.run(img)             # 运行检测 Run detection
            self.ocr_det.draw_result(self.pl,res)        # 绘制结果 Draw results
            self.pl.show_image()                    # 显示图像 Display image
            gc.collect()                       # 垃圾回收 Garbage collection
            time.sleep_us(1)
