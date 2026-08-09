from machine import UART
from machine import FPIOA


class DisabledUart:
    """Compatibility UART that deliberately performs no hardware I/O.

    Legacy AI applications receive this object so their telemetry can never be
    transmitted to the gimbal motor connected to UART1 TX.
    """

    def send(self, text):
        return 0

    def write(self, text):
        return 0

    def read(self, size=128, decode=False):
        return None

    def any(self):
        return 0

    def readline(self):
        return None

    def readinto(self, buf, nbytes=None):
        return 0

    def deinit(self):
        pass

class YbUart:
    def __init__(self, baudrate=115200):
        fpioa = FPIOA()
        fpioa.set_function(9, fpioa.UART1_TXD, ie=0, oe=1, pu=1)
        fpioa.set_function(10, fpioa.UART1_RXD, ie=1, oe=0, pu=1)
        try:
            self.uart = UART(UART.UART1, baudrate)  # 设置串口号1和波特率
        except Exception as e:
            print(e)
            print("uart init failed")

    def send(self, text):
        self.uart.write(text)

    def write(self, text):
        self.uart.write(text)

    def read(self, size=128, decode=False):
        text=self.uart.read(size) #接收128个字符
        if text != None:
            if decode:
                try:
                    text = text.decode()
                except:
                    text = text
            return text
    
    def any(self):
        return self.uart.any()
    
    def readline(self):
        return self.uart.readline()

    def readinto(self, buf, nbytes=None):
        if nbytes is None:
            return self.uart.readinto(buf)
        else:
            return self.uart.readinto(buf, nbytes)

    def deinit(self):
        self.uart.deinit()


if __name__ == "__main__":
    # 创建串口实例
    uart = YbUart(baudrate=115200)
    
    # 发送数据
    uart.send("Hello Yahboom\n")
    
    while True:
        # 读取数据
        data = uart.read()
        if data:
            print(data)
    
    # 关闭串口
    uart.deinit()
