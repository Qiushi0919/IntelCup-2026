import time
from ybUtils.YbKey import YbKey
key = YbKey()
abort_main = 0
if key.is_pressed():
    time.sleep_ms(10)
    if key.is_pressed():
        abort_main = 1


if not abort_main:
    from ybMain.main import *
    start()
