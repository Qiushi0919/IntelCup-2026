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
Frame_Cnt = 0
fCnt_tmp = [0, 0]
count = 0
rangefinder = 0

# 局部函数定义区
red_led = LED(1)
green_led = LED(2)
blue_led = LED(3)
ir_led = LED(4)

# 拆分数据


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

# 寻找Apriltag，并且返回标记的中心位置和寻找到的图像类型，此处与飞控处要相互匹配
# AprilTag在飞控处的标记类型为100


def Find_Apriltags(img):
    X = -1
    Y = -1
    FormType = 0xff
    # 寻找AprilTag
    for tag in img.find_apriltags(families=image.TAG16H5):
        # 如果找到了，就把找到的Tag用一个矩形和十字标记起来，颜色设置为150灰度值
        img.draw_rectangle(tag.rect(), color=(150))
        img.draw_cross(tag.cx(), tag.cy(), color=(150))
        # 把中心值赋值到X和Y
        X = tag.cx()
        Y = tag.cy()
        FormType = 100
    return FormType, X, Y

# 根据得到的坐标信息，通过串口发送数据


def UART_Send(FormType, Loaction0, Location1, range_finder=0):
    global Frame_Cnt
    global fCnt_tmp
    # 帧头填充
    Frame_Head = [170, 170]
    # 帧尾填充
    Frame_End = [85, 85]
    # 写入看到的形状
    fFormType_tmp = [FormType]
    # FrameCnt自动累加，识别不同的帧
    Frame_Cnt += 1

    if Frame_Cnt > 65534:
        FrameCnt = 0

    fHead = bytes(Frame_Head)

    fCnt_tmp[0] = range_finder & 0xFF
    fCnt_tmp[1] = range_finder >> 8
    # if(range_finder != 0):
    #     fCnt_tmp[1] = range_finder
    fCnt = bytes(fCnt_tmp)
    # 拆分长帧
    fFormType = bytes(fFormType_tmp)
    fLoaction0 = bytes(ExceptionVar(Loaction0))
    fLoaction1 = bytes(ExceptionVar(Location1))
    fEnd = bytes(Frame_End)
    FrameBuffe = fHead + fCnt + fFormType + fLoaction0 + fLoaction1 + fEnd
    return FrameBuffe


# main函数区
# 复位传感器
sensor.reset()

# 设置图片格式为灰度
sensor.set_pixformat(sensor.GRAYSCALE)

# 设置像素尺寸为160x120
sensor.set_framesize(sensor.QQVGA)

# 跳过图像不稳定的前2s的图像
sensor.skip_frames(time=2000)

# 关闭自动增益和自动白平衡
sensor.set_auto_gain(False)  # must be turned off for color tracking
sensor.set_auto_whitebal(False)  # must be turned off for color tracking

# 初始化时钟和串口
clock = time.clock()
uart = UART(3, 115200)

while(True):
    # 记录FPS起点
    clock.tick()

    # 拍摄一张照片
    img = sensor.snapshot()

    # 寻找Apriltags
    (Type, P0, P1) = Find_Apriltags(img)

    # 打印寻找到的结果
    print(Type, P0, P1)

    # 组帧，发送数据
    uart.write(UART_Send(Type, P0, P1))

    # 如果寻找到了标记，则亮绿灯
    # 没有寻找到标记，则亮红灯
    if Type == 100:
        green_led.on()
        red_led.off()
    else:
        green_led.off()
        red_led.on()
        pass

    # 打印FPS信息
    print(clock.fps())
