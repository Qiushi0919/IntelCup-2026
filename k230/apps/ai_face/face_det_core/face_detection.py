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
import _thread

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH

# Initialize touch sensor on pin 0
# 在引脚0上初始化触摸传感器
tp = TOUCH(0)
from libs.YbProtocol import YbProtocol

uart = None
pto = YbProtocol()

class FaceDetectionApp(AIBase):
    def __init__(self, kmodel_path, model_input_size, anchors, confidence_threshold=0.5, nms_threshold=0.2, rgb888p_size=[224,224], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.anchors = anchors
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right = self.get_padding_param()
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [104, 117, 123])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],
                          [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            start_time = time.time_ns()
            post_ret = aidemo.face_det_post_process(self.confidence_threshold, 
                                                  self.nms_threshold,
                                                  self.model_input_size[1], 
                                                  self.anchors,
                                                  self.rgb888p_size,
                                                  results)
            end_time = time.time_ns()
            return post_ret[0] if post_ret else post_ret

    def draw_result(self, pl, dets):
        with ScopedTiming("display_draw", self.debug_mode > 0):
            if dets:
                pl.osd_img.clear()
                for det in dets:
                    x, y, w, h = map(lambda x: int(round(x, 0)), det[:4])
                    x = x * self.display_size[0] // self.rgb888p_size[0]
                    y = y * self.display_size[1] // self.rgb888p_size[1]
                    w = w * self.display_size[0] // self.rgb888p_size[0]
                    h = h * self.display_size[1] // self.rgb888p_size[1]
                    pl.osd_img.draw_rectangle(x, y, w, h, color=(255, 255, 0, 255), thickness=2)
                    pto_data = pto.get_face_detect_data(x, y, w, h)
                    uart.send(pto_data)
                    print(pto_data)
            else:
                pl.osd_img.clear()

    def get_padding_param(self):
        dst_w = self.model_input_size[0]
        dst_h = self.model_input_size[1]
        ratio_w = dst_w / self.rgb888p_size[0]
        ratio_h = dst_h / self.rgb888p_size[1]
        ratio = min(ratio_w, ratio_h)
        new_w = int(ratio * self.rgb888p_size[0])
        new_h = int(ratio * self.rgb888p_size[1])
        dw = (dst_w - new_w) / 2
        dh = (dst_h - new_h) / 2
        return (int(round(0)),
                int(round(dh * 2 + 0.1)),
                int(round(0)),
                int(round(dw * 2 - 0.1)))

    def run(self, img):
        return super().run(img)
        
    def deinit(self):
        super().deinit()


class YAHBOOM_DEMO:
    def __init__(self, pl, _uart = None):
        global uart
        self.pl = pl
        self.face_det = None
        uart = _uart
        
    def exce_demo(self, loading_text="Loading ..."):
        display_mode = self.pl.display_mode
        rgb888p_size = self.pl.rgb888p_size
        display_size = self.pl.display_size
        self.pl.osd_img.clear()
        self.pl.osd_img.draw_string_advanced(display_size[0]//2 - 40, 220, 40, loading_text, color=(255,255,0,0))
        self.pl.show_image()
        kmodel_path = "/sdcard/kmodel/face_detection_320.kmodel"
        confidence_threshold = 0.5
        nms_threshold = 0.2
        anchor_len = 4200
        det_dim = 4
        anchors_path = "/sdcard/utils/prior_data_320.bin"
        anchors = np.fromfile(anchors_path, dtype=np.float)
        anchors = anchors.reshape((anchor_len, det_dim))

        self.face_det = FaceDetectionApp(kmodel_path, 
                                model_input_size=[320, 320], 
                                anchors=anchors,
                                confidence_threshold=confidence_threshold,
                                nms_threshold=nms_threshold,
                                rgb888p_size=rgb888p_size,
                                display_size=display_size,
                                debug_mode=0)
        self.face_det.config_preprocess()

        frame_count = 0
        start_time = time.time()
        
        while True:
            point = tp.read(1)
            if len(point):
                pt = point[0]
                if pt.event == TOUCH.EVENT_DOWN:
                    if pt.x<100 and pt.y<100:
                        self.exit_demo()
                        time.sleep_ms(10)
                        break
            img = self.pl.get_frame()
            res = self.face_det.run(img)
            self.face_det.draw_result(self.pl, res)
            self.pl.show_image()
            gc.collect()
            frame_count += 1
            if frame_count % 10 == 0:
                current_time = time.time()
                elapsed_time = current_time - start_time
                fps = 10 / elapsed_time if elapsed_time > 0 else 0
                start_time = current_time
            time.sleep_us(5)

    def exit_demo(self):
        pass
        return
        try:
            self.face_det.deinit()
            self.face_det = None  # 确保引用被清除
        except Exception as e:
            pass
        finally:
            return