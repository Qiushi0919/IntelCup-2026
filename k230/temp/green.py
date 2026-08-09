import sensor, image, time
from pyb import Pin, LED ,Timer,Servo
from machine import UART
from motor import send_command,turn_off_motor, turn_on_motor, go_to_home, set_absolute_angle, set_incremental_angle,set_speed,set_zero_position,clear_overcurrent


uart_A = UART(3,115200)
uart_A.init(115200, bits=8, parity=None, stop=1)
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.skip_frames(time = 333 )
sensor.set_auto_gain(True)
sensor.set_auto_whitebal(False)
sensor.skip_frames(time = 2000)
EXPOSURE_TIME_SCALE = 1
print("Initial exposure == %d" % sensor.get_exposure_us())
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)
sensor.skip_frames(time = 1000)
current_exposure_time_in_microseconds = sensor.get_exposure_us()
print("Current Exposure == %d" % current_exposure_time_in_microseconds)
sensor.set_auto_exposure(False, \
    exposure_us = int(current_exposure_time_in_microseconds * EXPOSURE_TIME_SCALE))
pin1 = Pin('P0', Pin.IN, Pin.PULL_DOWN)
beep = Pin('P1', Pin.OUT, Pin.OUT_PP)
red_led   = LED(1)
roi2	= [0,0,320,240]
thresholds = (16, 0, -21, 47, -20, 56)
red_threshold = (73, 97, -8, 51, -120, 13)
green_threshold =(79, 100, -128, -9, -128, 127)
GRAYSCALE_THRESHOLD = (0, 250)
pan_angle=0
tilt_angle=0
TASK1_OK=0
TASK2_OK=0
TASK3_OK=0
TASK4_OK=0
top_left_OK=0
top_mid_OK=0
top_right_OK=0
right_mid_OK=0
bottom_left_OK=0
bottom_mid_OK=0
bottom_right_OK=0
left_mid_OK=0
pan_step=1
tilt_step=1
last_green_x=0
last_green_y=0
set_pan=0
set_tilt=0
TASK=0
jiaodian=0
pan_step_updown=0.18
pan_step_leftrigh=0.14
ledflag=0
red_led.off()
green_no_fine=0
beep.off()
def SERVO_task(x,y):
    set_absolute_angle(0,x)#
    set_absolute_angle(1,y)#电机id 角度

def LED_task(ledflag):
    for l in range(0, ledflag, 1):
        red_led.on()
        time.sleep_ms(200)
        red_led.off()
        time.sleep_ms(200)
def find_box_corners(edges):
    if len(edges) < 1:
        return None
    top_left = edges[0]
    top_right = edges[0]
    bottom_left = edges[0]
    bottom_right = edges[0]
    for edge in edges:
        x, y = edge
        if x + y < top_left[0] + top_left[1]:
            top_left = edge
        if x - y > top_right[0] - top_right[1]:
            top_right = edge
        if x - y < bottom_left[0] - bottom_left[1]:
            bottom_left = edge
        if x + y > bottom_right[0] + bottom_right[1]:
            bottom_right = edge
    return top_left, top_right, bottom_left, bottom_right
def pan_can_angle(pan_servo_angle):
    if pan_servo_angle<=-30:
        pan_servo_angle=-30
    if pan_servo_angle>=40:
        pan_servo_angle=40
    return pan_servo_angle
def tilt_can_angle(tilt_servo_angle):
    if tilt_servo_angle<=-40:
        tilt_servo_angle=-40
    if tilt_servo_angle>=0:
        tilt_servo_angle=0
    return tilt_servo_angle


while(True):
    if pin1.value() ==1:
        if TASK == 0:
            TASK=4
            TASK4_OK=0
            LED_task(TASK)
        else:
            TASK = 0
            time.sleep_ms(300)
        print(TASK)
    if TASK ==0:
        img = sensor.snapshot()
        SERVO_task(pan_angle,tilt_angle)
        print(TASK)
    elif TASK == 4 and (TASK4_OK ==0 or TASK4_OK ==1):
        if TASK4_OK ==0 :
            TASK4_OK=1
            SERVO_task(pan_angle+20,tilt_angle+5)
            set_pan=pan_angle+20
            set_tilt=tilt_angle+5
            time.sleep_ms(300)
        while(TASK4_OK==1):
            img = sensor.snapshot()
            red_blobs = img.find_blobs([red_threshold],roi=roi2, pixels_threshold=1, area_threshold=1, merge=True)
            green_blobs = img.find_blobs([green_threshold],roi=roi2, pixels_threshold=1, area_threshold=1, merge=True)
            if pin1.value() ==1 and TASK==4:
                time.sleep_ms(600)
                TASK4_OK=2
                TASK=0
                LED_task(TASK)
                break
            if red_blobs and green_blobs :
                green_blob = green_blobs[0]
                red_blob = red_blobs[0]
                pan_error=green_blob.cx()-red_blob.cx()
                tilt_error =green_blob.cy()-red_blob.cy()
                img.draw_cross(red_blob.cx(), red_blob.cy())
                img.draw_cross(green_blob.cx(), green_blob.cy())
                print("green_blob.cx()",green_blob.cx())
                if abs(pan_error) < 5 and abs(tilt_error) < 5:
                    beep.on()
                else:
                    beep.off()
                if pan_error>4:
                    pan_step=0.1
                    if pan_error>15:
                        pan_step=0.5
                elif pan_error<-4:
                    pan_step=-0.1
                    if pan_error<-15:
                        pan_step=-0.5
                if tilt_error>4:
                    tilt_step=-0.1
                    if tilt_error>15:
                        tilt_step=-0.5
                elif tilt_error<-4:
                    tilt_step=0.1
                    if tilt_error<-15:
                        tilt_step=0.5
                set_pan -= pan_step
                set_tilt+= tilt_step
                tilt_step=0
                pan_step=0
                last_green_x=green_blob.cx()
                last_green_y=green_blob.cy()
                SERVO_task(set_pan,set_tilt)
                time.sleep_ms(1)
                green_no_fine=0
            elif red_blobs :
                print("no green")
                beep.off()
                green_no_fine+=1
                if  green_no_fine==5:
                    set_tilt+= 1
                    set_pan=set_pan
                    SERVO_task(set_pan,set_tilt)
                    print("gogogo")
