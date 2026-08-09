from machine import FPIOA, Pin
import time

class YbKey:
    def __init__(self):
        self._fpioa = FPIOA()
        self._pin_num = 61
        self._fpioa.set_function(self._pin_num, FPIOA.GPIO0 + self._pin_num, ie=1, oe=0)
        self._key = Pin(self._pin_num, Pin.IN, pull=Pin.PULL_UP, drive=7)

    def value(self):
        return self._key.value()
    
    def is_pressed(self):
        return True if self._key.value()==0 else False
