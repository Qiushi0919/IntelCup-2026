from machine import PWM
from machine import FPIOA
import time


class YbBuzzer:
    
    def __init__(self):
        self._fpioa = FPIOA()
        self._pwm_num = 5
        self._pin_num = 53
        self._fpioa.set_function(self._pin_num, FPIOA.PWM0 + self._pwm_num)
        self._pwm = PWM(self._pwm_num)

    # 鸣笛一声
    # duration：持续时间
    def beep(self, duration=0.1):
        self._pwm.freq(1000)
        self._pwm.duty(50)
        time.sleep(duration if duration > 0 else 0.1)
        self._pwm.duty(0)

    # 打开蜂鸣器
    # freq:频率
    # duty:占空比
    # duration:持续时间，小于或等于0则维持状态
    def on(self, freq, duty, duration):
        self._pwm.freq(freq)
        self._pwm.duty(duty)
        if duration > 0:
            time.sleep(duration)
            self._pwm.duty(0)

    # 关闭蜂鸣器
    def off(self):
        self._pwm.duty(0)
