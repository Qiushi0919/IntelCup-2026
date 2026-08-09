# 导入必要的模块 Import required modules
import time
import gc
from media.sensor import *
from media.display import *
from media.media import *
import image


# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)
from libs.YbProtocol import YbProtocol
from ybUtils.YbUart import YbUart
uart = None
pto = YbProtocol()

# 定义条形码类型映射字典 Define barcode type mapping dictionary
BARCODE_TYPES = {
    image.EAN2: "EAN2",
    image.EAN5: "EAN5",
    image.EAN8: "EAN8",
    image.UPCE: "UPCE",
    image.ISBN10: "ISBN10",
    image.UPCA: "UPCA",
    image.EAN13: "EAN13",
    image.ISBN13: "ISBN13",
    image.I25: "I25",
    image.DATABAR: "DATABAR",
    image.DATABAR_EXP: "DATABAR_EXP",
    image.CODABAR: "CODABAR",
    image.CODE39: "CODE39",
    image.PDF417: "PDF417",
    image.CODE93: "CODE93",
    image.CODE128: "CODE128"
}

def barcode_name(code):
    """
    获取条形码类型名称
    Get barcode type name
    """
    return BARCODE_TYPES.get(code.type(), "UNKNOWN")


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


            # 查找图像中所有条形码 Find all barcodes in the image
            codes = img.find_barcodes()
            img.clear()
            for code in codes:
                # 用矩形框标记条码位置 Mark barcode position with rectangle
                img.draw_rectangle(code.rect(), thickness=2, color=(255, 255, 255))

                # 获取条码类型和内容 Get barcode type and content
                code_type = barcode_name(code)
                payload = code.payload()

                # 打印条码信息 pass
                x, y, w, h = code.rect()
                pto_data = pto.get_barcode_data(x, y, w, h, payload)
                uart.send(pto_data)
                print(pto_data)

                # 在图像中显示条码内容 Display barcode content in image

                img.draw_string_advanced(200, 10, 40, payload, color=(255, 0, 0))

            # 显示处理后的图像 Display processed image
            Display.show_image(img)

            # 执行垃圾回收 Perform garbage collection
            gc.collect()
            time.sleep_us(1)

    def exit_demo(self):
        pass