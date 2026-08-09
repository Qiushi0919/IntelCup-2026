import time
import math
import os
import gc
from media.sensor import *
from media.display import *
from media.media import *
from libs.YbProtocol import YbProtocol
from ybUtils.YbUart import YbUart
uart = None
# uart = YbUart(baudrate=115200)
pto = YbProtocol()

DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480

# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)

def process_qrcode(image, qr_result):
    """
    Process detected QR code and draw information on image
    处理检测到的二维码并在图像上绘制信息

    Args:
        image: Current frame image | 当前帧图像
        qr_result: QR code detection result | 二维码检测结果
    """
    if len(qr_result) > 0:
        # Draw rectangle around QR code | 在二维码周围画矩形
        image.draw_rectangle(qr_result[0].rect(), thickness=2, color=(200, 0, 0))
        # Display QR code content | 显示二维码内容
        image.draw_string_advanced(0, 0, 30, qr_result[0].payload(),
                                 color=(255, 255, 255))
        print(qr_result[0].payload())

        x, y, w, h = qr_result[0].rect()
        pto_data = pto.get_qrcode_data(x, y, w, h, qr_result[0].payload())
        uart.send(pto_data)
        print(pto_data)


class YAHBOOM_DEMO:
    def __init__(self, pl,  _uart = None):
        global uart
        self.pl = pl
        uart = _uart
    def exce_demo(self, loading_text="Loading ..."):
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
            img = self.pl.sensor.snapshot(chn=CAM_CHN_ID_1)

            # Detect QR codes | 检测二维码
            qr_codes = img.find_qrcodes()

            img.clear()
            
            # Process detection results | 处理检测结果
            process_qrcode(img, qr_codes)

            # Display result | 显示结果
            Display.show_image(img)
            time.sleep_us(1)

    def exit_demo(self):
        pass