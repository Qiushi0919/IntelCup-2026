# 追踪颜色（黄色） By: 中科浩电 - 周一 3月 22 2021

import sensor
import image
import time
import network
import usocket
import sys
import sensor
import image
import time
import network
import usocket
import sys
import math
from pyb import UART
from pyb import LED

# 变量分配区
# 黄色追踪
threshold = [43, 63, -17, 15, 21, 67]
Frame_Cnt = 0
fCnt_tmp = [0, 0]
count = 0
rangefinder = 0
area_tmp = [0, 0]
area = 0
# 局部函数定义区

red_led = LED(1)
green_led = LED(2)
blue_led = LED(3)
ir_led = LED(4)


def get_rangefinder(uart_line):
    try:
        if (len(uart_line) < 8):
            return 0xFF
        if(uart_line[0] != 0x59):
            return 0xFF
        if(uart_line[1] != 0x59):
            return 0xFF
        if(uart_line[2] != None and uart_line[3] != None):
            return uart_line[3] * 256 | uart_line[2]
    except:
        return 20
        pass


def ExceptionVar(var):
    data = []
    data.append(0)
    data.append(0)

    if var == -1:
        data[0] = 0
        data[1] = 0
    else:
        data[0] = var & 0xFF
        data[1] = var >> 8
    return data

# 串口3 P4 P5 = TX RX
# 串口1 P1 P2 = TX RX


def UART_Send(FormType, Loaction0, Location1, range_finder=0, frame_type=0, area=0, prame2=0, prame3=0, prame4=0):
    global Frame_Cnt
    global fCnt_tmp
    Frame_Head = [170, 170]
    Frame_End = [85, 85]
    fFormType_tmp = [FormType]
    Frame_Cnt += 1
    prame = bytes(0)

    if Frame_Cnt > 65534:
        FrameCnt = 0

    fHead = bytes(Frame_Head)

    # 计算距离值
    fCnt_tmp[0] = range_finder & 0xFF
    fCnt_tmp[1] = range_finder >> 8
    fCnt = bytes(fCnt_tmp)

    # 计算区域值
    area_tmp[0] = area & 0xFF
    area_tmp[1] = area >> 8
    area = bytes(area_tmp)

    fFormType = bytes(fFormType_tmp)
    fLoaction0 = bytes(ExceptionVar(Loaction0))
    fLoaction1 = bytes(ExceptionVar(Location1))
    fEnd = bytes(Frame_End)

    if frame_type == 0:
        FrameBuffe = fHead + fCnt + fFormType + fLoaction0 + fLoaction1 + fEnd
    elif frame_type == 1:
        FrameBuffe = fHead + fCnt + fFormType + fLoaction0 + \
            fLoaction1 + area + prame + prame + prame + fEnd
        pass
    return FrameBuffe


# main函数区
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)  # must be turned off for color tracking
sensor.set_auto_whitebal(False)  # must be turned off for color tracking
clock = time.clock()
uart = UART(3, 115200)
uart_Rangefinder = UART(1, 115200)


# 注意，请插入SD卡后再将此变量（save_snapshot）设置为真
# 设置为真后，该逻辑会自动拍照位于图像中间的黄色物体，并且通过检测距离值拍照二维码
save_snapshot = True
is_snapshot = False
snapshot_count = 0

auto_snapshot_qrcode = False
while(True):
    img = sensor.snapshot()
    blobs = img.find_blobs([threshold], pixels_threshold=100,
                           area_threshold=100, merge=True, margin=10)
    if blobs:
        green_led.on()
        red_led.off()
        p = []
        p.append(blobs[0])
        for blob in p:
            img.draw_rectangle(blob.rect())
            img.draw_cross(blob.cx(), blob.cy())
            P0 = blob.cx()
            P1 = blob.cy()
            if save_snapshot:

                if P0 < 214:
                    is_snapshot = True
                    print("start shot")
                else:
                    is_snapshot = False
            area = blob.area()
            Type = 201
    else:
        green_led.off()
        red_led.on()
        Type = 0xFF
        P0 = -1
        P1 = -1

    uart.write(UART_Send(Type, P0, P1, rangefinder, area=area, frame_type=1))

    if (count % 2 == 0):
        # 获取距离值
        if (uart_Rangefinder.any()):
            p = uart_Rangefinder.readline()
            # print(bytes(p))
            rangefinder = get_rangefinder(p)
            print(rangefinder)

        # 对黄色物体进行拍照，
        if is_snapshot:
            snapshot_count += 1
            print("save" + str(count) + ".jpg")

            # 拍照请取消以下语句的注释
            # img.save(str(count) + ".jpg")

            # 拍摄4张图片
            if snapshot_count > 3:
                save_snapshot = False
                is_snapshot = False
                # auto_snapshot_qrcode = True
                snapshot_count = 0
                break

    count += 1
    if count > 100:
        pass
        # break
    # print(clock.fps())


sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.VGA)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)  # must be turned off for color tracking
sensor.set_auto_whitebal(False)  # must be turned off for color tracking

# 自动拍照，请开启vga_snapshot
vga_count = 0
vga_snapshot = False
while(True):
    img = sensor.snapshot()

    count += 1
    if (count % 5 == 0):
        # 获取距离值
        if (uart_Rangefinder.any()):
            p = uart_Rangefinder.readline()
            # print(bytes(p))
            rangefinder = get_rangefinder(p)
            print(rangefinder)

        # 判断离杆的距离，来获取二维码的拍照时间
        if rangefinder < 100 and vga_snapshot:
            img.save(str(count) + ".jpg")
            vga_count += 1

            if vga_count > 5:
                vga_snapshot = False
                pass
            pass


