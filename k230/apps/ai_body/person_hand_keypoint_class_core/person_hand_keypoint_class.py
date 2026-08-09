# 导入需要的库文件
# Import required libraries
from libs.PipeLine import PipeLine, ScopedTiming  # 导入管道处理和计时器相关的类 / Import pipeline processing and timer classes
from libs.AIBase import AIBase                    # 导入AI基础类 / Import AI base class 
from libs.AI2D import Ai2d                       # 导入2D图像处理类 / Import 2D image processing class
import os
import ujson                                     # JSON数据处理库 / JSON data processing library
from media.media import *                        # 多媒体处理相关库 / Multimedia processing library
from time import *
import nncase_runtime as nn                      # Neural Network运行时库 / Neural Network runtime library
import ulab.numpy as np                          # 类numpy数学计算库 / NumPy-like mathematical computation library
import time
import image                                     # 图像处理库 / Image processing library
import aicube                                    # AI模型推理库 / AI model inference library
import random
import gc                                        # 垃圾回收 / Garbage collection
import sys
from machine import TOUCH
uart = None
# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)
# 全局变量用于存储手部关键点分类器实例

class HandDetApp(AIBase):
    """
    手掌检测应用类 / Hand detection application class
    主要功能: / Main functions:
    1. 检测图像中的手掌位置 / Detect hand positions in images
    2. 对检测到的手掌进行预处理 / Preprocess detected hands
    """
    def __init__(self, kmodel_path, labels, model_input_size, anchors, confidence_threshold=0.2, 
                nms_threshold=0.5, nms_option=False, strides=[8,16,32], 
                rgb888p_size=[1920,1080], display_size=[1920,1080], debug_mode=0):
        """
        初始化函数 / Initialization function
        """
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        
        # 初始化模型相关参数 / Initialize model-related parameters
        self.kmodel_path = kmodel_path            # 模型路径 / Model path
        self.labels = labels                      # 标签列表 / Label list
        self.model_input_size = model_input_size  # 模型输入大小 / Model input size
        self.confidence_threshold = confidence_threshold  # 置信度阈值 / Confidence threshold
        self.nms_threshold = nms_threshold        # NMS阈值 / NMS threshold
        self.anchors = anchors                    # 锚框 / Anchor boxes
        self.strides = strides                    # 步长 / Strides
        self.nms_option = nms_option             # NMS选项 / NMS option
        
        # 初始化图像处理相关参数 / Initialize image processing parameters
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16), rgb888p_size[1]]  # 输入图像大小(宽度16字节对齐) / Input image size (width aligned to 16 bytes)
        self.display_size = [ALIGN_UP(display_size[0],16), display_size[1]]   # 显示大小 / Display size
        self.debug_mode = debug_mode             # 调试模式 / Debug mode
        
        # 创建AI2D实例用于图像预处理 / Create AI2D instance for image preprocessing
        self.ai2d = Ai2d(debug_mode)            
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        """
        配置预处理操作 / Configure preprocessing operations
        """
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            
            # 计算并配置padding参数 / Calculate and configure padding parameters
            top, bottom, left, right = self.get_padding_param()
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [114, 114, 114])
            
            # 配置resize操作 / Configure resize operation
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            
            # 构建预处理pipeline / Build preprocessing pipeline
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                          [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        """
        后处理函数 / Post-processing function
        处理模型输出结果 / Process model output results
        """
        with ScopedTiming("postprocess", self.debug_mode > 0):
            # 使用aicube库进行后处理 / Use aicube library for post-processing
            dets = aicube.anchorbasedet_post_process(results[0], results[1], results[2], 
                    self.model_input_size, self.rgb888p_size, self.strides, 
                    len(self.labels), self.confidence_threshold, self.nms_threshold, 
                    self.anchors, self.nms_option)
            return dets

    def get_padding_param(self):
        """
        计算padding参数 / Calculate padding parameters
        确保输入图像尺寸与模型输入尺寸匹配 / Ensure input image size matches model input size
        """
        dst_w = self.model_input_size[0]
        dst_h = self.model_input_size[1]
        input_width = self.rgb888p_size[0]
        input_high = self.rgb888p_size[1]
        
        # 添加输入验证
        if input_width <= 0 or input_high <= 0:
            raise ValueError("Input image dimensions must be greater than 0")
        
        # 计算缩放比例 / Calculate scaling ratios
        ratio_w = dst_w / input_width
        ratio_h = dst_h / input_high
        ratio = min(ratio_w, ratio_h)
        
        # 计算新的尺寸 / Calculate new dimensions
        new_w = int(ratio * input_width)
        new_h = int(ratio * input_high)
        
        # 计算padding值 / Calculate padding values
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        top = int(round(dh - 0.1))
        bottom = int(round(dh + 0.1))
        left = int(round(dw - 0.1))
        right = int(round(dw + 0.1))
        return top, bottom, left, right
    
class HandKPClassApp(AIBase):
    """
    手势关键点分类应用类 / Hand keypoint classification application class
    主要功能：识别手势关键点并进行分类 / Main function: Recognize hand keypoints and classify gestures
    """
    def __init__(self, kmodel_path, model_input_size, rgb888p_size=[1920,1080], 
                display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        
        # 初始化基本参数 / Initialize basic parameters
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16), display_size[1]]
        self.crop_params = []
        self.debug_mode = debug_mode
        
        # 初始化AI2D预处理器 / Initialize AI2D preprocessor
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)

    def config_preprocess(self, det, input_image_size=None):
        """
        配置预处理操作 / Configure preprocessing operations
        """
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            self.crop_params = self.get_crop_param(det)
            self.ai2d.crop(self.crop_params[0], self.crop_params[1], 
                          self.crop_params[2], self.crop_params[3])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                          [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        """
        后处理函数 / Post-processing function
        处理模型输出得到手势类别和关键点 / Process model output to get gesture type and keypoints
        """
        with ScopedTiming("postprocess", self.debug_mode > 0):
            results = results[0].reshape(results[0].shape[0] * results[0].shape[1])
            results_show = np.zeros(results.shape, dtype=np.int16)
            
            # 将关键点坐标转换到原始图像空间 / Convert keypoint coordinates to original image space
            results_show[0::2] = results[0::2] * self.crop_params[3] + self.crop_params[0]
            results_show[1::2] = results[1::2] * self.crop_params[2] + self.crop_params[1]
            
            # 识别手势 / Recognize gesture
            gesture = self.hk_gesture(results_show)
            
            # 调整显示坐标 / Adjust display coordinates
            results_show[0::2] = results_show[0::2] * (self.display_size[0] / self.rgb888p_size[0])
            results_show[1::2] = results_show[1::2] * (self.display_size[1] / self.rgb888p_size[1])
            return results_show, gesture

    def get_crop_param(self, det_box):
        """
        计算裁剪参数 / Calculate cropping parameters
        """
        x1, y1, x2, y2 = det_box[2], det_box[3], det_box[4], det_box[5]
        w, h = int(x2 - x1), int(y2 - y1)
        
        # 计算裁剪区域 / Calculate cropping region
        length = max(w, h)/2
        cx = (x1 + x2)/2
        cy = (y1 + y2)/2
        ratio_num = 1.26 * length
        
        # 确保裁剪区域在图像范围内 / Ensure cropping region is within image bounds
        x1_kp = int(max(0, cx-ratio_num))
        y1_kp = int(max(0, cy-ratio_num))
        x2_kp = int(min(self.rgb888p_size[0]-1, cx+ratio_num))
        y2_kp = int(min(self.rgb888p_size[1]-1, cy+ratio_num))
        w_kp = int(x2_kp - x1_kp + 1)
        h_kp = int(y2_kp - y1_kp + 1)
        
        return [x1_kp, y1_kp, w_kp, h_kp]

    def hk_vector_2d_angle(self, v1, v2):
        with ScopedTiming("hk_vector_2d_angle", self.debug_mode > 0):
            v1_x, v1_y, v2_x, v2_y = v1[0], v1[1], v2[0], v2[1]
            
            # 计算向量的范数 / Calculate vector norms
            v1_norm = np.sqrt(v1_x * v1_x + v1_y * v1_y)
            v2_norm = np.sqrt(v2_x * v2_x + v2_y * v2_y)
            
            # 添加检查以避免除零错误
            if v1_norm == 0 or v2_norm == 0:
                return 65535.  # 返回一个特殊值表示无效角度
            
            # 计算向量的点积和夹角 / Calculate dot product and angle
            dot_product = v1_x * v2_x + v1_y * v2_y
            cos_angle = dot_product/(v1_norm * v2_norm)
            
            # 确保cos_angle在有效范围内
            cos_angle = max(min(cos_angle, 1.0), -1.0)
            angle = np.acos(cos_angle) * 180/np.pi
            return angle
    
    def hk_gesture(self, results):
        """
        识别手势类别 / Recognize gesture type
        通过分析手指关键点的角度来判断手势 / Analyze finger keypoint angles to determine gesture
        """
        with ScopedTiming("hk_gesture", self.debug_mode > 0):
            angle_list = []
            
            # 计算每个手指的角度 / Calculate angle for each finger
            for i in range(5):
                angle = self.hk_vector_2d_angle(
                    [(results[0]-results[i*8+4]), (results[1]-results[i*8+5])],
                    [(results[i*8+6]-results[i*8+8]), (results[i*8+7]-results[i*8+9])]
                )
                angle_list.append(angle)
            
            # 设置角度阈值 / Set angle thresholds
            thr_angle, thr_angle_thumb, thr_angle_s = 65., 53., 49.
            gesture_str = None
            
            # 根据角度组合判断手势类别 / Determine gesture type based on angle combinations
            if 65535. not in angle_list:
                if (angle_list[0]>thr_angle_thumb) and all(angle>thr_angle for angle in angle_list[1:]):
                    gesture_str = "fist"
                elif all(angle<thr_angle_s for angle in angle_list):
                    gesture_str = "five"
                elif (angle_list[0]<thr_angle_s) and (angle_list[1]<thr_angle_s) and \
                     all(angle>thr_angle for angle in angle_list[2:]):
                    gesture_str = "gun"
                elif (angle_list[0]<thr_angle_s) and (angle_list[1]<thr_angle_s) and \
                     all(angle>thr_angle for angle in angle_list[2:4]) and angle_list[4]<thr_angle_s:
                    gesture_str = "love"
                elif (angle_list[0]>5) and (angle_list[1]<thr_angle_s) and \
                     all(angle>thr_angle for angle in angle_list[2:]):
                    gesture_str = "one"
                elif (angle_list[0]<thr_angle_s) and (angle_list[1]>thr_angle) and \
                     all(angle>thr_angle for angle in angle_list[2:4]) and angle_list[4]<thr_angle_s:
                    gesture_str = "six"
                elif (angle_list[0]>thr_angle_thumb) and all(angle<thr_angle_s for angle in angle_list[1:4]) and \
                     angle_list[4]>thr_angle:
                    gesture_str = "three"
                elif (angle_list[0]<thr_angle_s) and all(angle>thr_angle for angle in angle_list[1:]):
                    gesture_str = "thumbUp"
                elif (angle_list[0]>thr_angle_thumb) and (angle_list[1]<thr_angle_s) and \
                     (angle_list[2]<thr_angle_s) and all(angle>thr_angle for angle in angle_list[3:]):
                    gesture_str = "yeah"
            return gesture_str

class HandKeyPointClass:
    """
    手掌关键点分类整合类 / Hand keypoint classification integration class
    整合了手掌检测和手势识别功能 / Integrates hand detection and gesture recognition
    """
    def __init__(self, hand_det_kmodel, hand_kp_kmodel, det_input_size, kp_input_size,
                labels, anchors, confidence_threshold=0.25, nms_threshold=0.3,
                nms_option=False, strides=[8,16,32], rgb888p_size=[1280,720],
                display_size=[1920,1080], debug_mode=0):
        
        # 初始化检测和识别模型 / Initialize detection and recognition models
        self.hand_det = HandDetApp(hand_det_kmodel, labels, model_input_size=det_input_size,
                                anchors=anchors, confidence_threshold=confidence_threshold,
                                nms_threshold=nms_threshold, nms_option=nms_option,
                                strides=strides, rgb888p_size=rgb888p_size,
                                display_size=display_size, debug_mode=0)
        
        self.hand_kp = HandKPClassApp(hand_kp_kmodel, model_input_size=kp_input_size,
                                    rgb888p_size=rgb888p_size, display_size=display_size)
        
        # 配置检测模型预处理 / Configure detection model preprocessing
        self.hand_det.config_preprocess()

    def run(self, input_np):
        """
        执行手势识别流程 / Execute gesture recognition process
        
        参数/Parameters:
            input_np: 输入图像/Input image
            
        返回/Returns:
            boxes: 有效检测框/Valid detection boxes
            gesture_res: 手势识别结果/Gesture recognition results
        """
        try:
            # 执行手掌检测 / Perform hand detection  
            det_boxes = self.hand_det.run(input_np)
            boxes = []
            gesture_res = []

            # 限制最大处理的手掌数量为3个 / Limit max hands to 3
            max_hands = 1
            if len(det_boxes) > max_hands:
                det_boxes = det_boxes[:max_hands]
            
            # 对每个检测到的手掌进行关键点识别 / Perform keypoint recognition for each detected hand
            for det_box in det_boxes:
                try:
                    x1, y1, x2, y2 = det_box[2], det_box[3], det_box[4], det_box[5]
                    w, h = int(x2 - x1), int(y2 - y1)
                    
                    # 过滤无效检测框 / Filter invalid detection boxes
                    if (h < (0.1 * self.hand_det.rgb888p_size[1])):
                        continue
                    if (w < (0.25 * self.hand_det.rgb888p_size[0]) and 
                        ((x1 < (0.03 * self.hand_det.rgb888p_size[0])) or 
                        (x2 > (0.97 * self.hand_det.rgb888p_size[0])))):
                        continue
                    if (w < (0.15 * self.hand_det.rgb888p_size[0]) and 
                        ((x1 < (0.01 * self.hand_det.rgb888p_size[0])) or 
                        (x2 > (0.99 * self.hand_det.rgb888p_size[0])))):
                        continue
                        
                    # 执行关键点识别 / Perform keypoint recognition
                    self.hand_kp.config_preprocess(det_box)
                    results_show, gesture = self.hand_kp.run(input_np)
                    gesture_res.append((results_show, gesture))
                    boxes.append(det_box)

                except Exception as e:
                    print(f"Hand keypoint recognition error: {e}")
                    continue

            return boxes, gesture_res

        except Exception as e:
            print(f"Hand detection run error: {e}")
            return [], []

    def draw_result(self, pl, dets, gesture_res):
        """
        绘制识别结果 / Draw recognition results
        """
        pl.osd_img.clear()
        if len(dets) > 0:
            for k in range(len(dets)):
                det_box = dets[k]
                x1, y1, x2, y2 = det_box[2], det_box[3], det_box[4], det_box[5]
                w, h = int(x2 - x1), int(y2 - y1)
                
                # 过滤无效检测框 / Filter invalid detection boxes
                if (h < (0.1 * self.hand_det.rgb888p_size[1])):
                    continue
                if (w < (0.25 * self.hand_det.rgb888p_size[0]) and 
                    ((x1 < (0.03 * self.hand_det.rgb888p_size[0])) or 
                     (x2 > (0.97 * self.hand_det.rgb888p_size[0])))):
                    continue
                if (w < (0.15 * self.hand_det.rgb888p_size[0]) and 
                    ((x1 < (0.01 * self.hand_det.rgb888p_size[0])) or 
                     (x2 > (0.99 * self.hand_det.rgb888p_size[0])))):
                    continue
                
                # 计算显示尺寸 / Calculate display dimensions
                w_det = int(float(x2 - x1) * self.hand_det.display_size[0] // self.hand_det.rgb888p_size[0])
                h_det = int(float(y2 - y1) * self.hand_det.display_size[1] // self.hand_det.rgb888p_size[1])
                x_det = int(x1 * self.hand_det.display_size[0] // self.hand_det.rgb888p_size[0])
                y_det = int(y1 * self.hand_det.display_size[1] // self.hand_det.rgb888p_size[1])
                
                # 绘制检测框 / Draw detection box
                pl.osd_img.draw_rectangle(x_det, y_det, w_det, h_det, color=(255, 0, 255, 0), thickness=2)

                results_show = gesture_res[k][0]
                # 绘制关键点 / Draw keypoints
                for i in range(len(results_show)//2):
                    pl.osd_img.draw_circle(results_show[i*2], results_show[i*2+1], 1, 
                                         color=(255, 0, 255, 0), fill=False)
                
                # 绘制手指连线 / Draw finger connections
                for i in range(5):
                    j = i * 8
                    # 为每个手指设置不同的颜色 / Set different colors for each finger
                    colors = [(255,255,0,0), (255,255,0,255), (255,255,255,0),
                             (255,0,255,0), (255,0,0,255)]
                    R, G, B = colors[i][1], colors[i][2], colors[i][3]
                    
                    # 绘制手指的连线 / Draw finger connections
                    points = [(results_show[0], results_show[1]),
                            (results_show[j+2], results_show[j+3]),
                            (results_show[j+4], results_show[j+5]),
                            (results_show[j+6], results_show[j+7]),
                            (results_show[j+8], results_show[j+9])]
                    
                    for idx in range(len(points)-1):
                        pl.osd_img.draw_line(points[idx][0], points[idx][1],
                                           points[idx+1][0], points[idx+1][1],
                                           color=(255,R,G,B), thickness=3)

                # 显示手势类别 / Display gesture type
                gesture_str = gesture_res[k][1]
                pl.osd_img.draw_string_advanced(x_det, y_det-50, 32,
                                              " " + str(gesture_str),
                                              color=(255,0,255,0))
                # uart.send(f"${x_det},{y_det},{w_det},{h_det},{str(gesture_str)}#")
                
class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.hkc = None
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
        # 手掌检测模型路径
        # 获取显示参数 / Get display parameters
        display_mode = self.pl.display_mode
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
                
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()

        
        # 配置模型路径和参数 / Configure model paths and parameters
        hand_det_kmodel_path = "/sdcard/kmodel/hand_det.kmodel"
        hand_kp_kmodel_path = "/sdcard/kmodel/handkp_det.kmodel"
        anchors_path = "/sdcard/utils/prior_data_320.bin"
        hand_det_input_size = [512,512]
        hand_kp_input_size = [256,256]
        confidence_threshold = 0.2
        nms_threshold = 0.5
        labels = ["hand"]
        anchors = [26,27, 53,52, 75,71, 80,99, 106,82, 99,134, 140,113, 161,172, 245,276]
        
        try:
            # 初始化手势识别系统 / Initialize gesture recognition system
            self.hkc = HandKeyPointClass(hand_det_kmodel_path, hand_kp_kmodel_path,
                                det_input_size=hand_det_input_size,
                                kp_input_size=hand_kp_input_size,
                                labels=labels, anchors=anchors,
                                confidence_threshold=confidence_threshold,
                                nms_threshold=nms_threshold,
                                nms_option=False, strides=[8,16,32],
                                rgb888p_size=rgb888p_size,
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
                img = self.pl.get_frame()                           # 获取图像帧 / Get image frame
                det_boxes, gesture_res = self.hkc.run(img)          # 执行识别 / Perform recognition
                self.hkc.draw_result(self.pl, det_boxes, gesture_res)    # 绘制结果 / Draw results
                self.pl.show_image()                                # 显示图像 / Display image
                gc.collect()                                   # 垃圾回收 / Garbage collection
                time.sleep_us(1)
                    
        except Exception as e:
            pass

    def exit_demo(self):
        return