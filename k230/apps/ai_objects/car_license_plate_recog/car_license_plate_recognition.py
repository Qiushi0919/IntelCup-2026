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
import image
import aidemo
import random
import gc
import sys
# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
uart = None
from libs.YbProtocol import YbProtocol
pto = YbProtocol()
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
            else:
                pl.osd_img.clear()


class LicenceRecognitionApp(AIBase):
    def __init__(self,kmodel_path,model_input_size,rgb888p_size=[1920,1080],display_size=[1920,1080],debug_mode=0):
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        # kmodel路径
        self.kmodel_path=kmodel_path
        # 检测模型输入分辨率
        self.model_input_size=model_input_size
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        # 视频输出VO分辨率，宽16字节对齐
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        # debug模式
        self.debug_mode=debug_mode
        # 车牌字符字典
        self.dict_rec = ["挂", "使", "领", "澳", "港", "皖", "沪", "津", "渝", "冀", "晋", "蒙", "辽", "吉", "黑", "苏", "浙", "京", "闽", "赣", "鲁", "豫", "鄂", "湘", "粤", "桂", "琼", "川", "贵", "云", "藏", "陕", "甘", "青", "宁", "新", "警", "学", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "_", "-"]
        self.dict_size = len(self.dict_rec)
        self.ai2d=Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    
    def config_preprocess(self,input_image_size=None):
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size=input_image_size if input_image_size else self.rgb888p_size
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        with ScopedTiming("postprocess",self.debug_mode > 0):
            output_data=results[0].reshape((-1,self.dict_size))
            max_indices = np.argmax(output_data, axis=1)
            result_str = ""
            for i in range(max_indices.shape[0]):
                index = max_indices[i]
                if index > 0 and (i == 0 or index != max_indices[i - 1]):
                    result_str += self.dict_rec[index - 1]
            return result_str

class LicenceRec:
    """
    车牌检测和识别的整合类，包含检测和识别两个功能模块
    Integrated class for license plate detection and recognition, including detection and recognition modules
    """
    def __init__(self, licence_det_kmodel, licence_rec_kmodel, det_input_size, rec_input_size, 
                 confidence_threshold=0.25, nms_threshold=0.3, rgb888p_size=[1920,1080], 
                 display_size=[1920,1080], debug_mode=0):
        """
        初始化函数
        Initialization function

        参数说明 Parameters:
        licence_det_kmodel: 车牌检测模型路径 Path to license plate detection model
        licence_rec_kmodel: 车牌识别模型路径 Path to license plate recognition model
        det_input_size: 检测模型的输入尺寸 Input size for detection model
        rec_input_size: 识别模型的输入尺寸 Input size for recognition model
        confidence_threshold: 置信度阈值 Confidence threshold for detection
        nms_threshold: 非极大值抑制阈值 Non-maximum suppression threshold
        rgb888p_size: 输入图像尺寸 Input image size
        display_size: 显示尺寸 Display size
        debug_mode: 调试模式 Debug mode
        """
        # 初始化成员变量 Initialize member variables 
        self.licence_det_kmodel = licence_det_kmodel
        self.licence_rec_kmodel = licence_rec_kmodel
        self.det_input_size = det_input_size
        self.rec_input_size = rec_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        
        # 确保图像宽度是16的倍数 Ensure image width is multiple of 16
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16), display_size[1]]
        self.debug_mode = debug_mode

        # 初始化检测和识别模型 Initialize detection and recognition models
        self.licence_det = LicenceDetectionApp(
            self.licence_det_kmodel,
            model_input_size=self.det_input_size,
            confidence_threshold=self.confidence_threshold,
            nms_threshold=self.nms_threshold,
            rgb888p_size=self.rgb888p_size,
            display_size=self.display_size,
            debug_mode=0)
        self.licence_rec = LicenceRecognitionApp(
            self.licence_rec_kmodel,
            model_input_size=self.rec_input_size,
            rgb888p_size=self.rgb888p_size)
            
        # 配置检测模型的预处理 Configure preprocessing for detection model
        self.licence_det.config_preprocess()

    def run(self, input_np):
        """
        执行车牌检测和识别的主要流程
        Main pipeline for license plate detection and recognition
        
        参数 Parameters:
        input_np: 输入图像(numpy array格式) Input image in numpy array format
        
        返回 Returns:
        det_boxes: 检测到的车牌位置 Detected license plate positions
        rec_res: 识别的车牌字符 Recognized license plate characters
        """
        # 执行车牌检测 Perform license plate detection
        det_boxes = self.licence_det.run(input_np)
        
        # 对检测到的区域进行预处理 Preprocess detected regions
        imgs_array_boxes = aidemo.ocr_rec_preprocess(
            input_np,
            [self.rgb888p_size[1], self.rgb888p_size[0]],
            det_boxes)
        imgs_array = imgs_array_boxes[0]
        boxes = imgs_array_boxes[1]
        
        # 对每个检测到的车牌进行识别 Recognize each detected license plate
        rec_res = []
        for img_array in imgs_array:
            # 配置预处理参数 Configure preprocessing parameters
            self.licence_rec.config_preprocess(
                input_image_size=[img_array.shape[3], img_array.shape[2]])
            # 执行识别 Perform recognition
            licence_str = self.licence_rec.run(img_array)
            rec_res.append(licence_str)
            gc.collect()  # 垃圾回收 Garbage collection
            
        return det_boxes, rec_res

    def draw_result(self, pl, det_res, rec_res):
        """
        在图像上绘制检测和识别结果
        Draw detection and recognition results on image
        
        参数 Parameters:
        pl: PipeLine对象 PipeLine object
        det_res: 检测结果 Detection results
        rec_res: 识别结果 Recognition results
        """
        # 清除上一帧的绘制内容 Clear previous frame drawings
        pl.osd_img.clear()
        
        if det_res:
            # 创建坐标数组 Create coordinates array
            point_8 = np.zeros((8), dtype=np.int16)
            
            # 遍历每个检测到的车牌 Iterate through each detected plate
            for det_index in range(len(det_res)):
                # 坐标转换 Coordinate conversion
                for i in range(4):
                    x = det_res[det_index][i * 2 + 0] / self.rgb888p_size[0] * self.display_size[0]
                    y = det_res[det_index][i * 2 + 1] / self.rgb888p_size[1] * self.display_size[1]
                    point_8[i * 2 + 0] = int(x)
                    point_8[i * 2 + 1] = int(y)
                
                # 绘制检测框 Draw detection box
                for i in range(4):
                    pl.osd_img.draw_line(
                        point_8[i * 2 + 0],
                        point_8[i * 2 + 1],
                        point_8[(i+1) % 4 * 2 + 0],
                        point_8[(i+1) % 4 * 2 + 1],
                        color=(255, 0, 255, 0),
                        thickness=4
                    )
                
                # 绘制识别结果文本 Draw recognition result text
                pl.osd_img.draw_string_advanced(
                    point_8[6],
                    point_8[7] + 20,
                    40,
                    rec_res[det_index],
                    color=(255,255,153,18)
                )
                uart.send(f"${rec_res[det_index]}#")

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.lr = None
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
        gc.collect()
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()

        # 车牌检测模型路径
        licence_det_kmodel_path="/sdcard/kmodel/LPD_640.kmodel"
        # 车牌识别模型路径
        licence_rec_kmodel_path="/sdcard/kmodel/licence_reco.kmodel"
        # 其它参数
        licence_det_input_size=[640,640]
        licence_rec_input_size=[220,32]
        confidence_threshold=0.2
        nms_threshold=0.2

        self.lr=LicenceRec(licence_det_kmodel_path,licence_rec_kmodel_path,det_input_size=licence_det_input_size,rec_input_size=licence_rec_input_size,confidence_threshold=confidence_threshold,nms_threshold=nms_threshold,rgb888p_size=rgb888p_size,display_size=display_size)
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        pass
                        time.sleep_ms(10)
                        break
            img=self.pl.get_frame()                  # 获取当前帧
            det_res,rec_res=self.lr.run(img)         # 推理当前帧
            self.lr.draw_result(self.pl,det_res,rec_res)  # 绘制当前帧推理结果
            self.pl.show_image()                     # 展示推理结果
            gc.collect()
            time.sleep_us(1)
