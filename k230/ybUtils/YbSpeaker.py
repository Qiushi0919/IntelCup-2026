from machine import FPIOA, Pin


class YbSpeaker:
    def __init__(self):
        self._fpioa = FPIOA()
        self._pin_num = 48
        self._fpioa.set_function(self._pin_num, FPIOA.GPIO0 + self._pin_num, ie=0, oe=1)
        self._speaker_en = Pin(self._pin_num, Pin.OUT, pull=Pin.PULL_NONE, drive=7)

    def enable(self):
        self._speaker_en.value(1)

    def disable(self):
        self._speaker_en.value(0)

    def value(self, val=-1):
        if val == 0:
            self._speaker_en.value(0)
        elif val > 0:
            self._speaker_en.value(1)
        else:
            return self._speaker_en.value()
