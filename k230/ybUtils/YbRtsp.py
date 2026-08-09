# Description: This example demonstrates how to stream video and audio to the network using the RTSP server.
#
# Note: You will need an SD card to run this example.
#
# You can run the rtsp server to stream video and audio to the network
import network
import os
import time
import _thread
import gc
import sys
import random
import ujson
import utime
import ulab.numpy as np
import nncase_runtime as nn
import aidemo
import image
import multimedia as mm
from time import sleep
from media.vencoder import *
from media.sensor import *
from media.media import *
from media.display import *
from libs.PipeLine import PipeLine, ScopedTiming
from libs.AIBase import AIBase
from libs.AI2D import Ai2d

def Connect_WIFI(ID,PASSWORD):
    sta=network.WLAN(0)
    if(not sta.isconnected()):
        # sta连接ap
        sta.connect(ID,PASSWORD)
    # 查看是否连接
    return sta.isconnected()

class FaceDetectionApp(AIBase):
    def __init__(self, kmodel_path, model_input_size, anchors, confidence_threshold=0.5, nms_threshold=0.2, rgb888p_size=[224,224], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)  # 调用基类的构造函数
        self.kmodel_path = kmodel_path  # 模型文件路径
        self.model_input_size = model_input_size  # 模型输入分辨率
        self.confidence_threshold = confidence_threshold  # 置信度阈值
        self.nms_threshold = nms_threshold  # NMS（非极大值抑制）阈值
        self.anchors = anchors  # 锚点数据，用于目标检测
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]  # sensor给到AI的图像分辨率，并对宽度进行16的对齐
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]  # 显示分辨率，并对宽度进行16的对齐
        self.debug_mode = debug_mode  # 是否开启调试模式
        self.ai2d = Ai2d(debug_mode)  # 实例化Ai2d，用于实现模型预处理
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)  # 设置Ai2d的输入输出格式和类型

    # 配置预处理操作，这里使用了pad和resize，Ai2d支持crop/shift/pad/resize/affine，具体代码请打开/sdcard/app/libs/AI2D.py查看
    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):  # 计时器，如果debug_mode大于0则开启
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size  # 初始化ai2d预处理配置，默认为sensor给到AI的尺寸，可以通过设置input_image_size自行修改输入尺寸
            top, bottom, left, right = self.get_padding_param()  # 获取padding参数
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [104, 117, 123])  # 填充边缘
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)  # 缩放图像
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])  # 构建预处理流程

    # 自定义当前任务的后处理，results是模型输出array列表，这里使用了aidemo库的face_det_post_process接口
    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            post_ret = aidemo.face_det_post_process(self.confidence_threshold, self.nms_threshold, self.model_input_size[1], self.anchors, self.rgb888p_size, results)
            if len(post_ret) == 0:
                return post_ret
            else:
                return post_ret[0]

    # 绘制检测结果到画面上
    def draw_result(self,img,dets):
        if dets:
            for det in dets:
                # 将检测框的坐标转换为显示分辨率下的坐标
                x, y, w, h = map(lambda x: int(round(x, 0)), det[:4])
                x = x * self.display_size[0] // self.rgb888p_size[0]
                y = y * self.display_size[1] // self.rgb888p_size[1]
                w = w * self.display_size[0] // self.rgb888p_size[0]
                h = h * self.display_size[1] // self.rgb888p_size[1]
                img.draw_rectangle(x, y, w, h)  # 绘制矩形框

    # 获取padding参数
    def get_padding_param(self):
        dst_w = self.model_input_size[0]  # 模型输入宽度
        dst_h = self.model_input_size[1]  # 模型输入高度
        ratio_w = dst_w / self.rgb888p_size[0]  # 宽度缩放比例
        ratio_h = dst_h / self.rgb888p_size[1]  # 高度缩放比例
        ratio = min(ratio_w, ratio_h)  # 取较小的缩放比例
        new_w = int(ratio * self.rgb888p_size[0])  # 新宽度
        new_h = int(ratio * self.rgb888p_size[1])  # 新高度
        dw = (dst_w - new_w) / 2  # 宽度差
        dh = (dst_h - new_h) / 2  # 高度差
        top = int(round(0))
        bottom = int(round(dh * 2 + 0.1))
        left = int(round(0))
        right = int(round(dw * 2 - 0.1))
        return top, bottom, left, right

class RtspServer:
    def __init__(self,session_name="video",port=8554,video_type = mm.multi_media_type.media_h264,enable_audio=False,sensor=None,initMediaManager=False):
        self.session_name = session_name # session name
        self.video_type = video_type  # 视频类型264/265
        self.enable_audio = enable_audio # 是否启用音频
        self.port = port   #rtsp 端口号
        self.rtspserver = mm.rtsp_server() # 实例化rtsp server
        self.venc_chn = VENC_CHN_ID_0 #venc通道
        self.start_stream = False #是否启动推流线程
        self.runthread_over = False #推流线程是否结束
        self.sensor = sensor

        self.initMediaManager = initMediaManager

    def start(self):
        # 初始化推流
        self._init_stream()
        self.rtspserver.rtspserver_init(self.port)
        # 创建session
        self.rtspserver.rtspserver_createsession(self.session_name,self.video_type,self.enable_audio)
        # 启动rtsp server
        self.rtspserver.rtspserver_start()
        self._start_stream()

        # 启动推流线程
        self.start_stream = True
        _thread.start_new_thread(self._do_rtsp_stream,())


    def stop(self):
        if (self.start_stream == False):
            return
        # 等待推流线程退出
        self.start_stream = False
        while not self.runthread_over:
            sleep(0.1)
        self.runthread_over = False

        # 停止推流
        self._stop_stream()
        self.rtspserver.rtspserver_stop()
        #self.rtspserver.rtspserver_destroysession(self.session_name)
        self.rtspserver.rtspserver_deinit()

    def get_rtsp_url(self):
        return self.rtspserver.rtspserver_getrtspurl(self.session_name)

    def _init_stream(self):
        width = 1280
        height = 720
        width = ALIGN_UP(width, 16)
        # 初始化sensor
        if self.sensor is None:
            self.sensor = Sensor()
            self.sensor.reset()
            self.sensor.set_framesize(width = width, height = height, alignment=12)
            self.sensor.set_pixformat(Sensor.YUV420SP)

            self.sensor.set_framesize(width = 1920, height = 1080, chn=CAM_CHN_ID_1)
            self.sensor.set_pixformat(PIXEL_FORMAT_RGB_888_PLANAR, chn=CAM_CHN_ID_1)
        # 实例化video encoder
        self.encoder = Encoder()
        self.encoder.SetOutBufs(self.venc_chn, 8, width, height)
        # 绑定camera和venc
        # self.link = MediaManager.link(self.sensor.bind_info()['src'], (VIDEO_ENCODE_MOD_ID, VENC_DEV_ID, self.venc_chn))
        self.link = None
        # init media manager

        Display.init(Display.ST7701, width=800, height=480, osd_num=2, to_ide=True)

        MediaManager.init()
        # 创建编码器
        chnAttr = ChnAttrStr(self.encoder.PAYLOAD_TYPE_H264, self.encoder.H264_PROFILE_MAIN, width, height)
        self.encoder.Create(self.venc_chn, chnAttr)

    def _start_stream(self):
        # 开始编码
        self.encoder.Start(self.venc_chn)
        # 启动camera
        self.sensor.run()

    def _stop_stream(self):
        # 停止camera
        self.sensor.stop()
        # 接绑定camera和venc
        del self.link
        # 停止编码
        self.encoder.Stop(self.venc_chn)
        self.encoder.Destroy(self.venc_chn)
        # 清理buffer
        MediaManager.deinit()

    def _do_rtsp_stream(self):
        try:
            streamData = StreamData()
            frame_info = k_video_frame_info()
            # 这里必须是 1280*720 和 1920*1080
            display_size=[1280,720]
            rgb888p_size = [1920, 1080]
            # ################# 填入预处理参数 ################### #

            # 设置模型路径和其他参数
            kmodel_path = "/sdcard/examples/kmodel/face_detection_320.kmodel"
            # 其它参数
            confidence_threshold = 0.5
            nms_threshold = 0.2
            anchor_len = 4200
            det_dim = 4
            anchors_path = "/sdcard/examples/utils/prior_data_320.bin"
            anchors = np.fromfile(anchors_path, dtype=np.float)
            anchors = anchors.reshape((anchor_len, det_dim))
            face_det = FaceDetectionApp(kmodel_path, model_input_size=[320, 320], anchors=anchors, confidence_threshold=confidence_threshold, nms_threshold=nms_threshold, rgb888p_size=rgb888p_size, display_size=display_size, debug_mode=0)
            face_det.config_preprocess()  # 配置预处理
            # ################################################## #

            # 通道一给AI视觉识别
            # 通道二用来推流显示
            while self.start_stream:

                # 通过两个通道获取图片
                img = self.sensor.snapshot(chn=CAM_CHN_ID_1)
                np_img = img.to_numpy_ref()
                res = face_det.run(np_img)         # 推理当前帧
                rtsp_show_img = self.sensor.snapshot(chn=CAM_CHN_ID_0)

                # 绘制AI视觉结果
                face_det.draw_result(rtsp_show_img,res)
#                rtsp_show_img = None

#                if(rtsp_show_img is None):
#                    rtsp_show_img = self.sensor.snapshot(chn=CAM_CHN_ID_0)
#                    rtsp_show_img.clear()
#                    rtsp_show_img.draw_string_advanced(40, 40, 32, "无画面传入", color=(255, 0, 0))


                ################ 推流，不需要修改 ################

                if (rtsp_show_img == -1):
                    continue
                frame_info.v_frame.width = rtsp_show_img.width()
                frame_info.v_frame.height = rtsp_show_img.height()
                frame_info.v_frame.pixel_format = Sensor.YUV420SP
                frame_info.pool_id = rtsp_show_img.poolid()
                frame_info.v_frame.phys_addr[0] = rtsp_show_img.phyaddr()

                if (rtsp_show_img.width() == 800 and rtsp_show_img.height() == 480):
                    frame_info.v_frame.phys_addr[1] = frame_info.v_frame.phys_addr[0] + frame_info.v_frame.width*frame_info.v_frame.height + 1024
                elif (rtsp_show_img.width() == 1920 and rtsp_show_img.height() == 1080):
                    frame_info.v_frame.phys_addr[1] = frame_info.v_frame.phys_addr[0] + frame_info.v_frame.width*frame_info.v_frame.height + 3072
                elif (rtsp_show_img.width() == 640 and rtsp_show_img.height() == 360):
                    frame_info.v_frame.phys_addr[1] = frame_info.v_frame.phys_addr[0] + frame_info.v_frame.width*frame_info.v_frame.height + 3072
                else:
                    frame_info.v_frame.phys_addr[1] = frame_info.v_frame.phys_addr[0] + frame_info.v_frame.width*frame_info.v_frame.height
                self.encoder.SendFrame(self.venc_chn, frame_info)
                self.encoder.GetStream(self.venc_chn, streamData) # 获取一帧码流

                for pack_idx in range(0, streamData.pack_cnt):
                    stream_data = bytes(uctypes.bytearray_at(streamData.data[pack_idx], streamData.data_size[pack_idx]))
#                    print("stream size: ", streamData.data_size[pack_idx], "stream type: ", streamData.stream_type[pack_idx])
                    self.rtspserver.rtspserver_sendvideodata(self.session_name,stream_data, streamData.data_size[pack_idx],1000)

                self.encoder.ReleaseStream(self.venc_chn, streamData) # 释放一帧码流

                ######################################

                gc.collect()                    # 垃圾回收
                time.sleep_us(10)
                os.exitpoint()

        except BaseException as e:
            print(f"Exception {e}")
        finally:
            self.runthread_over = True
            # 停止rtsp server
            self.stop()

        self.runthread_over = True

if __name__ == "__main__":
    print("[WIFI] 连接网络中 ...")
    isConnected = Connect_WIFI("Yahboom","WIFI PASSWORD")
#    isConnected = Connect_WIFI("Yahboom3","WIFI PASSWORD")
    if isConnected:
        print("[WIFI] 连接网络成功")
    else:
        import sys
        print("[WIFI] 连接网络失败！请检查配置")
        time.sleep_ms(10)
        sys.exit()

    print("[RTSP] 启动中 ..")
    time.sleep(1)

    # 创建rtsp server对象
    rtspserver = RtspServer()
    # 启动rtsp server
    rtspserver.start()
    # 打印rtsp url
    # print("rtsp server start:",rtspserver.get_rtsp_url())
    rtsp_address = rtspserver.get_rtsp_url()
    print("[RTSP] 启动成功, 地址:", rtsp_address)

    img2 = image.Image(800, 480, image.RGB565)
    img2.clear()
    img2.draw_string_advanced(img2.width()//5 - 5, img2.height()//2 - 30, 32, "地址: " + rtsp_address, color=(255, 255, 255))
    Display.show_image(img2)
    # 推流60s
    while True:
        time.sleep(60)
    # 停止rtsp server
    rtspserver.stop()
    print("done")
