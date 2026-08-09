from machine import SPI
from machine import FPIOA
import time

class YbRGB:
    def __init__(self, num_leds=1):
        self._fpioa = FPIOA()
        self._fpioa.set_function(16, FPIOA.QSPI0_D0)

        self._spi = SPI(1, baudrate=2500000, polarity=0, phase=0)
        self._num_leds = num_leds
        self._buf = bytearray(num_leds * 3)

    def set_led(self, index, r, g, b):
        if 0 <= index < self._num_leds:
            self._buf[index*3] = g
            self._buf[index*3 + 1] = r
            self._buf[index*3 + 2] = b

    def set_all(self, r, g, b):
        for i in range(self._num_leds):
            self.set_led(i, r, g, b)

    def show(self):
        timing_buf = bytearray(len(self._buf) * 8 * 3)
        pos = 0
        for color in self._buf:
            for bit in range(7, -1, -1):
                if color & (1 << bit):
                    timing_buf[pos] = 0b11100000
                    timing_buf[pos + 1] = 0b00000000
                    timing_buf[pos + 2] = 0b00000000
                else:
                    timing_buf[pos] = 0b10000000
                    timing_buf[pos + 1] = 0b00000000
                    timing_buf[pos + 2] = 0b00000000
                pos += 3
        
        # 发送Reset码
        reset_buf = bytearray(1)
        reset_buf[0] = 0
        self._spi.write(reset_buf)
        time.sleep_us(300)

        # 分批发送数据，每次最多发送1024字节
        chunk_size = 1024
        for i in range(0, len(timing_buf), chunk_size):
            chunk = timing_buf[i:min(i+chunk_size, len(timing_buf))]
            self._spi.write(chunk)
            time.sleep_us(10)  # 每个数据块之间添加短暂延时

    def show_rgb(self, rgb):
        self.set_all(rgb[0], rgb[1], rgb[2])
        self.show()