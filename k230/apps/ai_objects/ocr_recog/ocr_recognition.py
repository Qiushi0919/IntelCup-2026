# 导入所需库 Import required libraries
from libs.PipeLine import PipeLine, ScopedTiming  # 导入管道处理和计时器类 Import pipeline and timer classes
from libs.AIBase import AIBase                    # 导入AI基础类 Import AI base class  
from libs.AI2D import Ai2d                       # 导入2D图像处理类 Import 2D image processing class
from media.media import *                        # 导入媒体处理库 Import media processing library
from time import *                               # 导入时间处理库 Import time library
import nncase_runtime as nn                      # 导入nncase运行时库 Import nncase runtime library
import ulab.numpy as np                          # 导入numpy库 Import numpy library
import aicube                                    # 导入AI立方库 Import AI cube library
import gc                                        # 导入垃圾回收库 Import garbage collection library
# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH

from libs.YbProtocol import YbProtocol

uart = None

pto = YbProtocol()
# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)

class OCRDetectionApp(AIBase):
    """
    OCR检测类，用于检测图像中的文本区域
    OCR detection class for detecting text regions in images
    """
    def __init__(self,kmodel_path,model_input_size,mask_threshold=0.5,box_threshold=0.2,rgb888p_size=[224,224],display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 Initialization function
        
        参数 Parameters:
        kmodel_path: kmodel文件路径 Path to kmodel file
        model_input_size: 模型输入大小 Model input size
        mask_threshold: 掩码阈值 Mask threshold
        box_threshold: 边界框阈值 Box threshold
        rgb888p_size: RGB图像大小 RGB image size
        display_size: 显示大小 Display size
        debug_mode: 调试模式 Debug mode
        """
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size    # 模型输入分辨率 Model input resolution
        self.mask_threshold = mask_threshold        # 分类阈值 Classification threshold
        self.box_threshold = box_threshold
        # sensor给到AI的图像分辨率 Image resolution from sensor to AI
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode = debug_mode
        # 实例化Ai2d，用于实现模型预处理 Initialize Ai2d for model preprocessing
        self.ai2d = Ai2d(debug_mode)
        # 设置Ai2d参数 Set Ai2d parameters
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,input_image_size=None):
        """
        配置预处理操作 Configure preprocessing operations
        支持pad和resize等操作 Support operations like pad and resize
        """
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            # 初始化ai2d预处理配置 Initialize ai2d preprocessing configuration
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top,bottom,left,right = self.get_padding_param()
            # 设置填充参数 Set padding parameters
            self.ai2d.pad([0,0,0,0,top,bottom,left,right], 0, [0,0,0])
            # 设置缩放方法 Set resize method
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            # 构建预处理图形 Build preprocessing graph
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                           [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        """
        后处理函数 Postprocessing function
        将模型输出转换为检测框 Convert model output to detection boxes
        """
        with ScopedTiming("postprocess",self.debug_mode > 0):
            # 转换图像格式从CHW到HWC Convert image format from CHW to HWC
            hwc_array = self.chw2hwc(self.cur_img)
            # 使用aicube处理OCR检测结果 Process OCR detection results using aicube
            # 返回格式：[[crop_array_nhwc,[p1_x,p1_y,p2_x,p2_y,p3_x,p3_y,p4_x,p4_y]],...]
            # Return format: [[crop_array_nhwc,[p1_x,p1_y,p2_x,p2_y,p3_x,p3_y,p4_x,p4_y]],...]
            det_boxes = aicube.ocr_post_process(results[0][:,:,:,0].reshape(-1), 
                                              hwc_array.reshape(-1),
                                              self.model_input_size,
                                              self.rgb888p_size, 
                                              self.mask_threshold, 
                                              self.box_threshold)
            return det_boxes

    def get_padding_param(self):
        """
        计算padding参数 Calculate padding parameters
        返回上下左右padding的像素数 Return pixels to pad for top, bottom, left and right
        """
        # 计算目标尺寸和输入尺寸 Calculate target and input dimensions
        dst_w = self.model_input_size[0]
        dst_h = self.model_input_size[1]
        input_width = self.rgb888p_size[0]
        input_high = self.rgb888p_size[1]
        
        # 计算缩放比例 Calculate scaling ratio
        ratio_w = dst_w / input_width
        ratio_h = dst_h / input_high
        ratio = ratio_w if ratio_w < ratio_h else ratio_h
        
        # 计算新的尺寸 Calculate new dimensions
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
        将CHW格式转换为HWC格式 Convert CHW format to HWC format
        """
        # 保存原始形状 Save original shape
        ori_shape = (features.shape[0], features.shape[1], features.shape[2])
        # 重构并转置数组 Reshape and transpose array
        c_hw_ = features.reshape((ori_shape[0], ori_shape[1] * ori_shape[2]))
        hw_c_ = c_hw_.transpose()
        new_array = hw_c_.copy()
        # 重构为HWC格式 Reshape to HWC format
        hwc_array = new_array.reshape((ori_shape[1], ori_shape[2], ori_shape[0]))
        # 释放临时变量 Release temporary variables
        del c_hw_
        del hw_c_
        del new_array
        return hwc_array

class OCRRecognitionApp(AIBase):
    """
    OCR识别类，用于识别检测到的文本内容
    OCR recognition class for recognizing detected text content
    """
    def __init__(self,kmodel_path,model_input_size,dict_path,rgb888p_size=[1920,1080],display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 Initialization function
        
        参数 Parameters:
        kmodel_path: 模型路径 Model path
        model_input_size: 模型输入尺寸 Model input size
        dict_path: 字典文件路径 Dictionary file path
        rgb888p_size: 输入图像尺寸 Input image size
        display_size: 显示尺寸 Display size
        debug_mode: 调试模式 Debug mode
        """
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.dict_path = dict_path
        # 设置图像尺寸，宽度16字节对齐 Set image size, width aligned to 16 bytes
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode = debug_mode
        self.dict_word = None
        # 加载字典文件 Load dictionary file
        self.read_dict()
        # 初始化AI2D图像处理器 Initialize AI2D image processor
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.RGB_packed,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,input_image_size=None,input_np=None):
        """
        配置预处理参数 Configure preprocessing parameters
        支持pad和resize操作 Support pad and resize operations
        """
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            # 获取padding参数 Get padding parameters
            top,bottom,left,right = self.get_padding_param(ai2d_input_size,self.model_input_size)
            # 设置padding和resize参数 Set padding and resize parameters
            self.ai2d.pad([0,0,0,0,top,bottom,left,right], 0, [0,0,0])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            # 构建处理流程 Build processing pipeline
            self.ai2d.build([input_np.shape[0],input_np.shape[1],input_np.shape[2],input_np.shape[3]],
                           [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        """
        后处理函数：将模型输出转换为文本 
        Postprocessing: convert model output to text
        """
        with ScopedTiming("postprocess",self.debug_mode > 0):
            # 获取预测结果的最大值索引 Get indices of maximum values from predictions
            preds = np.argmax(results[0], axis=2).reshape((-1))
            output_txt = ""
            for i in range(len(preds)):
                # 处理预测结果：去重并转换为文本
                # Process predictions: remove duplicates and convert to text
                if preds[i] != (len(self.dict_word) - 1) and (not (i > 0 and preds[i - 1] == preds[i])):
                    output_txt = output_txt + self.dict_word[preds[i]]
            return output_txt

    def get_padding_param(self,src_size,dst_size):
        """
        计算填充参数 Calculate padding parameters
        输入源尺寸和目标尺寸，返回需要填充的像素数
        Input source size and target size, return pixels needed for padding
        """
        dst_w = dst_size[0]
        dst_h = dst_size[1]
        input_width = src_size[0]
        input_high = src_size[1]
        
        # 计算宽高缩放比例 Calculate width and height scaling ratios
        ratio_w = dst_w / input_width
        ratio_h = dst_h / input_high
        ratio = ratio_w if ratio_w < ratio_h else ratio_h
        
        # 计算缩放后的新尺寸 Calculate new dimensions after scaling
        new_w = (int)(ratio * input_width)
        new_h = (int)(ratio * input_high)
        
        # 计算需要填充的像素数 Calculate pixels needed for padding
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        top = (int)(round(0))
        bottom = (int)(round(dh * 2 + 0.1))
        left = (int)(round(0))
        right = (int)(round(dw * 2 - 0.1))
        return top, bottom, left, right

    def read_dict(self):
        """
        读取字典文件 Read dictionary file
        将字典内容加载到内存中 Load dictionary content into memory
        """
        if self.dict_path != "":
            with open(self.dict_path, 'r') as file:
                line_one = file.read(100000)
                line_list = line_one.split("\r\n")
            # 构建字典映射 Build dictionary mapping
            self.dict_word = {num: char.replace("\r", "").replace("\n", "") for num, char in enumerate(line_list)}

class OCRDetRec:
    """
    OCR检测和识别的集成类 Integrated class for OCR detection and recognition
    将检测和识别功能组合在一起 Combines detection and recognition functions
    """
    def __init__(self,ocr_det_kmodel,ocr_rec_kmodel,det_input_size,rec_input_size,dict_path,
                 mask_threshold=0.25,box_threshold=0.3,rgb888p_size=[1920,1080],
                 display_size=[1920,1080],debug_mode=0):
        """
        初始化函数 Initialization function
        
        参数 Parameters:
        ocr_det_kmodel: 检测模型路径 Detection model path
        ocr_rec_kmodel: 识别模型路径 Recognition model path
        det_input_size: 检测模型输入尺寸 Detection model input size
        rec_input_size: 识别模型输入尺寸 Recognition model input size
        dict_path: 字典路径 Dictionary path
        mask_threshold: 掩码阈值 Mask threshold
        box_threshold: 框阈值 Box threshold
        rgb888p_size: 输入图像尺寸 Input image size
        display_size: 显示尺寸 Display size
        debug_mode: 调试模式 Debug mode
        """
        self.ocr_det_kmodel = ocr_det_kmodel
        self.ocr_rec_kmodel = ocr_rec_kmodel
        self.det_input_size = det_input_size
        self.rec_input_size = rec_input_size
        self.dict_path = dict_path
        self.mask_threshold = mask_threshold
        self.box_threshold = box_threshold
        # 设置图像尺寸，宽度16字节对齐 Set image size, width aligned to 16 bytes
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode = debug_mode
        
        # 初始化检测和识别模型 Initialize detection and recognition models
        self.ocr_det = OCRDetectionApp(self.ocr_det_kmodel,
                                     model_input_size=self.det_input_size,
                                     mask_threshold=self.mask_threshold,
                                     box_threshold=self.box_threshold,
                                     rgb888p_size=self.rgb888p_size,
                                     display_size=self.display_size,
                                     debug_mode=0)
        self.ocr_rec = OCRRecognitionApp(self.ocr_rec_kmodel,
                                        model_input_size=self.rec_input_size,
                                        dict_path=self.dict_path,
                                        rgb888p_size=self.rgb888p_size,
                                        display_size=self.display_size)
        self.ocr_det.config_preprocess()

    def run(self, input_np):
        """
        运行OCR检测和识别 Run OCR detection and recognition
        先检测文本位置，再识别文本内容 First detect text location, then recognize text content
        
        参数/Parameters:
            input_np: 输入图像/Input image
            
        返回/Returns:
            boxes: 检测到的文本框/Detected text boxes 
            ocr_res: OCR识别结果/OCR recognition results
        """
        try:
            # 执行文本检测 Perform text detection
            det_res = self.ocr_det.run(input_np)
            boxes = []
            ocr_res = []

            # 限制最大处理的文本区域数量为4个 Limit max text regions to 4
            max_regions = 4
            if len(det_res) > max_regions:
                det_res = det_res[:max_regions]
            
            # 对每个检测到的文本区域进行识别 Recognize each detected text region
            for det in det_res:
                try:
                    # 配置识别模型预处理 Configure recognition model preprocessing
                    self.ocr_rec.config_preprocess(input_image_size=[det[0].shape[2], det[0].shape[1]], 
                                                input_np=det[0])
                    # 执行文本识别 Perform text recognition
                    ocr_str = self.ocr_rec.run(det[0])
                    ocr_res.append(ocr_str)
                    boxes.append(det[1])
                    gc.collect()  # 进行垃圾回收 Perform garbage collection

                except Exception as e:
                    print(f"Text recognition error: {e}")
                    continue

            return boxes, ocr_res

        except Exception as e:
            print(f"Text detection run error: {e}")
            return [], []

    def draw_result(self,pl,det_res,rec_res):
        """
        绘制OCR结果 Draw OCR results
        在图像上绘制检测框和识别文本 Draw detection boxes and recognized text on image
        """
        pl.osd_img.clear()
        if det_res:
            # 遍历所有检测结果 Traverse all detection results
            for j in range(len(det_res)):
                # 绘制四边形检测框 Draw quadrilateral detection box
                for i in range(4):
                    # 坐标转换 Coordinate conversion
                    x1 = det_res[j][(i * 2)] / self.rgb888p_size[0] * self.display_size[0]
                    y1 = det_res[j][(i * 2 + 1)] / self.rgb888p_size[1] * self.display_size[1]
                    x2 = det_res[j][((i + 1) * 2) % 8] / self.rgb888p_size[0] * self.display_size[0]
                    y2 = det_res[j][((i + 1) * 2 + 1) % 8] / self.rgb888p_size[1] * self.display_size[1]
                    # 绘制线段 Draw line segment
                    pl.osd_img.draw_line((int(x1), int(y1), int(x2), int(y2)), color=(255, 0, 0, 255),thickness=5)
                # 绘制识别文本 Draw recognized text
                pl.osd_img.draw_string_advanced(int(x1),int(y1),32,rec_res[j],color=(0,0,255))
                uart.send(f"${rec_res[j]}#")

class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.ocr = None
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
        gc.collect()
        display_mode = self.pl.display_mode
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()

        # 配置模型和参数路径 Configure model and parameter paths
        ocr_det_kmodel_path = "/sdcard/kmodel/ocr_det_int16.kmodel"
        ocr_rec_kmodel_path = "/sdcard/kmodel/ocr_rec_int16.kmodel"
        dict_path = "/sdcard/utils/dict.txt"
        
        # 设置参数 Set parameters
        # rgb888p_size = [640,360]
        ocr_det_input_size = [640,640]
        ocr_rec_input_size = [512,32]
        mask_threshold = 0.25
        box_threshold = 0.3

        # 初始化OCR模型 Initialize OCR model
        self.ocr = OCRDetRec(ocr_det_kmodel_path,ocr_rec_kmodel_path,
                    det_input_size=ocr_det_input_size,
                    rec_input_size=ocr_rec_input_size,
                    dict_path=dict_path,
                    mask_threshold=mask_threshold,
                    box_threshold=box_threshold,
                    rgb888p_size=rgb888p_size,
                    display_size=display_size)

        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        pass
                        sleep_ms(10)
                        break
            img = self.pl.get_frame()                     # 获取图像帧 Get image frame
            det_res,rec_res = self.ocr.run(img)          # 执行OCR Run OCR
            self.ocr.draw_result(self.pl,det_res,rec_res)     # 绘制结果 Draw results
            self.pl.show_image()                         # 显示图像 Show image
            gc.collect()                           # 垃圾回收 Garbage collection                             # 退出程序 Exit program
            sleep_us(1)