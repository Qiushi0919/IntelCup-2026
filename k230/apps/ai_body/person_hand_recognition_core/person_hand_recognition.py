# 导入必要的库 Import necessary libraries
from libs.PipeLine import PipeLine, ScopedTiming  # 导入管道处理和计时工具 Import pipeline and timing tools
from libs.AIBase import AIBase  # 导入AI基类 Import AI base class
from libs.AI2D import Ai2d  # 导入2D图像处理工具 Import 2D image processing tool
import os
import ujson
from media.media import *
from time import *
import nncase_runtime as nn  # 导入神经网络运行时 Import neural network runtime
import ulab.numpy as np  # 导入numpy库 Import numpy library
import time
import image
import aicube  # 导入AI立方体处理库 Import AI cube processing library
import random
import gc  # 导入垃圾回收模块 Import garbage collection module
import sys

from machine import TOUCH

# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)
# 全局变量用于存储手部关键点分类器实例

class HandDetApp(AIBase):
    """
    手掌检测应用类 Hand Detection Application Class
    继承自AIBase基类 Inherits from AIBase
    """
    def __init__(self,kmodel_path,model_input_size,anchors,confidence_threshold=0.2,nms_threshold=0.5,nms_option=False, strides=[8,16,32],rgb888p_size=[1920,1080],display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 Initialization function
        参数说明 Parameters:
        kmodel_path: 模型文件路径 Model file path
        model_input_size: 模型输入尺寸 Model input size
        anchors: 锚框参数 Anchor box parameters
        confidence_threshold: 置信度阈值 Confidence threshold
        nms_threshold: NMS阈值 NMS threshold
        nms_option: NMS选项 NMS option
        strides: 步长列表 Stride list
        rgb888p_size: 输入图像尺寸 Input image size
        display_size: 显示尺寸 Display size
        debug_mode: 调试模式 Debug mode
        """
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path=kmodel_path
        self.model_input_size=model_input_size
        self.confidence_threshold=confidence_threshold
        self.nms_threshold=nms_threshold
        self.anchors=anchors  # 锚框，用于目标检测 Anchor boxes for object detection
        self.strides = strides  # 特征图的步长 Feature map strides
        self.nms_option = nms_option
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]  # 确保宽度16字节对齐 Ensure width is aligned to 16 bytes
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode=debug_mode
        self.ai2d=Ai2d(debug_mode)  # 创建AI2D实例用于图像预处理 Create AI2D instance for image preprocessing
        # 设置AI2D参数 Set AI2D parameters
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,input_image_size=None):
        """
        配置预处理参数 Configure preprocessing parameters
        包括padding和resize操作 Including padding and resize operations
        """
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right = self.get_padding_param()  # 获取padding参数 Get padding parameters
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [114, 114, 114])  # 设置padding Fill with gray color
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)  # 设置resize方法 Set resize method
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        """
        后处理函数 Postprocessing function
        处理模型的原始输出 Process raw model output
        """
        with ScopedTiming("postprocess",self.debug_mode > 0):
            # 使用aicube库进行后处理 Use aicube library for postprocessing
            dets = aicube.anchorbasedet_post_process(results[0], results[1], results[2], 
                                                   self.model_input_size, self.rgb888p_size, 
                                                   self.strides, 1, self.confidence_threshold, 
                                                   self.nms_threshold, self.anchors, self.nms_option)
            return dets

    def get_padding_param(self):
        """
        计算padding参数 Calculate padding parameters
        返回上下左右padding的像素数 Return pixels for top, bottom, left, right padding
        """
        dst_w = self.model_input_size[0]  # 目标宽度 Target width
        dst_h = self.model_input_size[1]  # 目标高度 Target height
        input_width = self.rgb888p_size[0]  # 输入宽度 Input width
        input_high = self.rgb888p_size[1]  # 输入高度 Input height
        
        # 计算缩放比例 Calculate scaling ratio
        ratio_w = dst_w / input_width
        ratio_h = dst_h / input_high
        ratio = min(ratio_w, ratio_h)  # 选择较小的比例 Choose smaller ratio
        
        # 计算新的尺寸 Calculate new dimensions
        new_w = int(ratio * input_width)
        new_h = int(ratio * input_high)
        
        # 计算padding值 Calculate padding values
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        
        # 返回padding参数 Return padding parameters
        return (int(round(dh - 0.1)), int(round(dh + 0.1)), 
                int(round(dw - 0.1)), int(round(dw + 0.1)))

class HandRecognitionApp(AIBase):
    """
    手势识别应用类 Hand Recognition Application Class
    继承自AIBase基类 Inherits from AIBase
    """
    def __init__(self,kmodel_path,model_input_size,labels,rgb888p_size=[1920,1080],display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 Initialization function
        参数说明 Parameters:
        kmodel_path: 模型文件路径 Model file path
        model_input_size: 模型输入尺寸 Model input size
        labels: 标签列表 Label list
        rgb888p_size: 输入图像尺寸 Input image size
        display_size: 显示尺寸 Display size
        debug_mode: 调试模式 Debug mode
        """
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path=kmodel_path
        self.model_input_size=model_input_size
        self.labels=labels  # 手势标签列表 Hand gesture label list
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.crop_params=[]  # 存储裁剪参数 Store cropping parameters
        self.debug_mode=debug_mode
        self.ai2d=Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,det,input_image_size=None):
        """
        配置预处理参数 Configure preprocessing parameters
        包括裁剪和缩放操作 Including crop and resize operations
        """
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size=input_image_size if input_image_size else self.rgb888p_size
            self.crop_params = self.get_crop_param(det)  # 获取裁剪参数 Get cropping parameters
            self.ai2d.crop(self.crop_params[0],self.crop_params[1],self.crop_params[2],self.crop_params[3])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        """
        后处理函数 Postprocessing function
        处理模型输出并返回识别结果 Process model output and return recognition result
        """
        with ScopedTiming("postprocess",self.debug_mode > 0):
            result=results[0].reshape(results[0].shape[0]*results[0].shape[1])
            x_softmax = self.softmax(result)
            idx = np.argmax(x_softmax)
            text = " " + self.labels[idx] + ": " + str(round(x_softmax[idx],2))
            return text

    def get_crop_param(self,det_box):
        """
        计算裁剪参数 Calculate cropping parameters
        根据检测框位置计算合适的裁剪区域 Calculate appropriate cropping area based on detection box
        """
        x1, y1, x2, y2 = det_box[2],det_box[3],det_box[4],det_box[5]
        w,h = int(x2 - x1),int(y2 - y1)
        length = max(w, h)/2
        cx = (x1+x2)/2
        cy = (y1+y2)/2
        ratio_num = 1.26*length
        x1_kp = int(max(0,cx-ratio_num))
        y1_kp = int(max(0,cy-ratio_num))
        x2_kp = int(min(self.rgb888p_size[0]-1, cx+ratio_num))
        y2_kp = int(min(self.rgb888p_size[1]-1, cy+ratio_num))
        w_kp = int(x2_kp - x1_kp + 1)
        h_kp = int(y2_kp - y1_kp + 1)
        return [x1_kp, y1_kp, w_kp, h_kp]

    def softmax(self,x):
        """
        实现softmax函数 Implement softmax function
        将输入转换为概率分布 Convert input to probability distribution
        """
        x -= np.max(x)  # 数值稳定性处理 Numerical stability processing
        x = np.exp(x) / np.sum(np.exp(x))
        return x

class HandRecognition:
    """
    手势识别主类 Main Hand Recognition Class
    整合检测和识别功能 Integrate detection and recognition functions
    """
    def __init__(self,hand_det_kmodel,hand_kp_kmodel,det_input_size,kp_input_size,labels,anchors,
                 confidence_threshold=0.25,nms_threshold=0.3,nms_option=False,strides=[8,16,32],
                 rgb888p_size=[1280,720],display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 Initialization function
        """
        self.hand_det_kmodel=hand_det_kmodel  # 手掌检测模型路径 Hand detection model path
        self.hand_kp_kmodel=hand_kp_kmodel    # 手势识别模型路径 Hand recognition model path
        self.det_input_size=det_input_size    # 检测模型输入尺寸 Detection model input size
        self.kp_input_size=kp_input_size      # 识别模型输入尺寸 Recognition model input size
        self.labels=labels                     # 手势标签 Gesture labels
        self.anchors=anchors                   # 锚框参数 Anchor parameters
        self.confidence_threshold=confidence_threshold  # 置信度阈值 Confidence threshold
        self.nms_threshold=nms_threshold       # NMS阈值 NMS threshold
        self.nms_option=nms_option            # NMS选项 NMS option
        self.strides=strides                  # 特征图步长 Feature map strides
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode=debug_mode

        # 创建检测和识别实例 Create detection and recognition instances
        self.hand_det=HandDetApp(self.hand_det_kmodel,model_input_size=self.det_input_size,
                                anchors=self.anchors,confidence_threshold=self.confidence_threshold,
                                nms_threshold=self.nms_threshold,nms_option=self.nms_option,
                                strides=self.strides,rgb888p_size=self.rgb888p_size,
                                display_size=self.display_size,debug_mode=0)
        self.hand_rec=HandRecognitionApp(self.hand_kp_kmodel,model_input_size=self.kp_input_size,
                                        labels=self.labels,rgb888p_size=self.rgb888p_size,
                                        display_size=self.display_size)
        self.hand_det.config_preprocess()

    def run(self,input_np):
        """
        运行手势识别 Run hand gesture recognition
        """
        # 执行手掌检测 Perform hand detection
        det_boxes=self.hand_det.run(input_np)
        hand_rec_res=[]  # 存储识别结果 Store recognition results
        hand_det_res=[]  # 存储检测结果 Store detection results

        for det_box in det_boxes:
            # 对每个检测到的手掌进行处理 Process each detected hand
            x1, y1, x2, y2 = det_box[2],det_box[3],det_box[4],det_box[5]
            w,h= int(x2 - x1),int(y2 - y1)
            
            # 过滤条件 Filtering conditions
            if (h<(0.1*self.rgb888p_size[1])):
                continue
            if (w<(0.25*self.rgb888p_size[0]) and ((x1<(0.03*self.rgb888p_size[0])) or (x2>(0.97*self.rgb888p_size[0])))):
                continue
            if (w<(0.15*self.rgb888p_size[0]) and ((x1<(0.01*self.rgb888p_size[0])) or (x2>(0.99*self.rgb888p_size[0])))):
                continue
            
            # 执行手势识别 Perform gesture recognition
            self.hand_rec.config_preprocess(det_box)
            text=self.hand_rec.run(input_np)
            hand_det_res.append(det_box)
            hand_rec_res.append(text)
        return hand_det_res,hand_rec_res

    def draw_result(self,pl,hand_det_res,hand_rec_res):
        """
        绘制识别结果 Draw recognition results
        """
        pl.osd_img.clear()  # 清除上一帧的绘制内容 Clear previous frame drawings
        if hand_det_res:
            for k in range(len(hand_det_res)):
                # 获取检测框坐标 Get detection box coordinates
                det_box=hand_det_res[k]
                x1, y1, x2, y2 = det_box[2],det_box[3],det_box[4],det_box[5]
                w,h= int(x2 - x1),int(y2 - y1)
                # 转换到显示尺寸 Convert to display size
                w_det = int(float(x2 - x1) * self.display_size[0] // self.rgb888p_size[0])
                h_det = int(float(y2 - y1) * self.display_size[1] // self.rgb888p_size[1])
                x_det = int(x1*self.display_size[0] // self.rgb888p_size[0])
                y_det = int(y1*self.display_size[1] // self.rgb888p_size[1])
                # 绘制检测框和识别结果 Draw detection box and recognition result
                pl.osd_img.draw_rectangle(x_det, y_det, w_det, h_det, color=(255, 0, 255, 0), thickness = 2)
                pl.osd_img.draw_string_advanced(x_det, y_det-50, 32, hand_rec_res[k], color=(255,0, 255, 0))

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        self.pl = pl
        self.hr = None
    def exce_demo(self, loading_text="Loading ..."):
        # 手掌检测模型路径
        # 获取显示参数 / Get display parameters
        display_mode = self.pl.display_mode
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()

        # 模型和参数配置 Model and parameter configuration
        hand_det_kmodel_path="/sdcard/kmodel/hand_det.kmodel"  # 手掌检测模型路径 Hand detection model path
        hand_rec_kmodel_path="/sdcard/kmodel/hand_reco.kmodel" # 手势识别模型路径 Hand recognition model path
        anchors_path="/sdcard/utils/prior_data_320.bin"        # 锚框数据路径 Anchor data path
        hand_det_input_size=[512,512]      # 检测模型输入尺寸 Detection model input size
        hand_rec_input_size=[224,224]      # 识别模型输入尺寸 Recognition model input size
        confidence_threshold=0.2           # 置信度阈值 Confidence threshold
        nms_threshold=0.5                 # NMS阈值 NMS threshold
        labels=["gun","other","yeah","five"]  # 手势标签 Gesture labels
        anchors = [26,27, 53,52, 75,71, 80,99, 106,82, 99,134, 140,113, 161,172, 245,276]  # 锚框参数 Anchor parameters

        try:
            # 创建手势识别实例 Create hand recognition instance
            self.hr=HandRecognition(hand_det_kmodel_path,hand_rec_kmodel_path,det_input_size=hand_det_input_size,
                            kp_input_size=hand_rec_input_size,labels=labels,anchors=anchors,
                            confidence_threshold=confidence_threshold,nms_threshold=nms_threshold,
                            nms_option=False,strides=[8,16,32],rgb888p_size=rgb888p_size,
                            display_size=display_size)

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
                img=self.pl.get_frame()                              # 获取当前帧 Get current frame
                hand_det_res,hand_rec_res=self.hr.run(img)           # 执行识别 Perform recognition
                self.hr.draw_result(self.pl,hand_det_res,hand_rec_res)    # 绘制结果 Draw results
                self.pl.show_image()                                 # 显示图像 Show image
                gc.collect()                                    # 垃圾回收 Garbage collection
                time.sleep_us(1)
        except Exception as e:
            print(e)
            pass

    def exit_demo(self):
        return