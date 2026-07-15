# 追踪颜色（绿色） By: 中科浩电 - 周一 3月 22 2021

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
# 绿色追踪
threshold = [24, 87, -89, -26, -49, 41]
Frame_Cnt = 0
fCnt_tmp = [0, 0]
count = 0
rangefinder = 0

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


def UART_Send(FormType, Loaction0, Location1, range_finder=0):
    global Frame_Cnt
    global fCnt_tmp
    Frame_Head = [170, 170]
    Frame_End = [85, 85]
    fFormType_tmp = [FormType]
    Frame_Cnt += 1

    if Frame_Cnt > 65534:
        FrameCnt = 0

    fHead = bytes(Frame_Head)

    fCnt_tmp[0] = range_finder & 0xFF
    fCnt_tmp[1] = range_finder >> 8
    # if(range_finder != 0):
    #     fCnt_tmp[1] = range_finder
    fCnt = bytes(fCnt_tmp)

    fFormType = bytes(fFormType_tmp)
    fLoaction0 = bytes(ExceptionVar(Loaction0))
    fLoaction1 = bytes(ExceptionVar(Location1))
    fEnd = bytes(Frame_End)
    FrameBuffe = fHead + fCnt + fFormType + fLoaction0 + fLoaction1 + fEnd
    return FrameBuffe


# main函数区
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QQVGA)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)  # must be turned off for color tracking
sensor.set_auto_whitebal(False)  # must be turned off for color tracking
clock = time.clock()
uart = UART(3, 115200)
uart_Rangefinder = UART(1, 115200)

while(True):
    clock.tick()
    img = sensor.snapshot()
    blobs = img.find_blobs([threshold], pixels_threshold=100,
                           area_threshold=100, merge=True, margin=10)
    if blobs:
        green_led.on()
        for blob in blobs:
            img.draw_rectangle(blob.rect())
            img.draw_cross(blob.cx(), blob.cy())
            P0 = blob.cx()
            P1 = blob.cy()
            Type = 200
            print(Type, P0, P1)
            # uart.write(UART_Send(Type, P0, P1, rangefinder))

    else:
        # print("no find blobs")
        green_led.off()
        Type = 0xFF
        P0 = -1
        P1 = -1

    uart.write(UART_Send(Type, P0, P1, rangefinder))

    if (count % 2 == 0):
        if (uart_Rangefinder.any()):
            p = uart_Rangefinder.readline()
            # print(bytes(p))
            rangefinder = get_rangefinder(p)
            print(rangefinder)
    count += 1
    # print(clock.fps())
