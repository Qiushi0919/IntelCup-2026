# Import required modules
# 导入所需模块
import time, math, os, gc

from media.sensor import *
from media.display import *
from media.media import *

# AprilTag code supports processing up to 6 tag families simultaneously
# The returned tag object will have its tag family and ID within that family
# AprilTag代码最多支持同时处理6种tag家族
# 返回的tag标记对象包含其所属家族及在该家族中的ID
from libs.YbProtocol import YbProtocol
from ybUtils.YbUart import YbUart
uart = None
pto = YbProtocol()
# Import touch sensor module
# 导入触摸传感器模块
from machine import TOUCH
tp = TOUCH(0)
# Initialize tag families bitmask
# 初始化tag家族位掩码
tag_families = 0
tag_families |= image.TAG16H5    # Comment out to disable this family / 注释掉以禁用此家族
tag_families |= image.TAG25H7    # Comment out to disable this family / 注释掉以禁用此家族
tag_families |= image.TAG25H9    # Comment out to disable this family / 注释掉以禁用此家族
tag_families |= image.TAG36H10   # Comment out to disable this family / 注释掉以禁用此家族
tag_families |= image.TAG36H11   # Comment out to disable this family (default) / 注释掉以禁用此家族(默认)
tag_families |= image.ARTOOLKIT  # Comment out to disable this family / 注释掉以禁用此家族

def family_name(tag):
    """
    Get the family name of a tag
    获取tag的家族名称

    Args:
        tag: AprilTag object / AprilTag对象
    Returns:
        str: Name of the tag family / tag家族名称
    """
    family_dict = {
        image.TAG16H5: "TAG16H5",
        image.TAG25H7: "TAG25H7",
        image.TAG25H9: "TAG25H9",
        image.TAG36H10: "TAG36H10",
        image.TAG36H11: "TAG36H11",
        image.ARTOOLKIT: "ARTOOLKIT"
    }
    return family_dict.get(tag.family())

# Main loop
# 主循环
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
            # Find and process AprilTags
            # 查找和处理AprilTags
            tags = img.find_apriltags(families=tag_families)
            img.clear()
            for tag in tags:
                # Draw rectangle and cross on detected tag
                # 在检测到的tag上绘制矩形和十字
                img.draw_rectangle(tag.rect(), color=(255, 0, 0), thickness=4)
                img.draw_cross(tag.cx(), tag.cy(), color=(255, 0, 0), thickness=5)

                # pass
                # 打印tag信息
                img.draw_string_advanced(tag.cx(), tag.cy(), 30,
                                   "Family: %s, ID: %d" % (family_name(tag), tag.id()),
                                   color=(255, 0, 0))
                print_args = (family_name(tag), tag.id(), (180 * tag.rotation()) / math.pi)
                
                x, y, w, h = tag.rect()
                pto_data = pto.get_apriltag_data(x, y, w, h, tag.id(), (180*tag.rotation())/math.pi)
                uart.send(pto_data)
                print(pto_data)
                print("Tag Family %s, Tag ID %d, rotation %f (degrees)" % print_args)

            # Display image centered on screen
            # 在屏幕中央显示图像
            Display.show_image(img)
            time.sleep_us(1)
            # pass
            # 打印帧率
    def exit_demo(self):
        pass