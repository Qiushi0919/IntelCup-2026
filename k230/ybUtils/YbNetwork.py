import network,os

import utime as time

import json

class WIFI_INFO:
    def __init__(self):
        self.mode = None
        self.key = None
        self.ssid = None
        self.ip = None
        self.rssi = None

class YbNetwork():
    def __init__(self):
        self.wifi_info = WIFI_INFO()
        self.sta = network.WLAN(0)

    def _disconnect_wifi(self,timeout=8000):
        try:
            self.sta = network.WLAN(0)
            self.sta.disconnect()
            time.sleep_ms(100)
            time_out_count = 0
            while self.sta.isconnected():
                print("[WIFI] 尝试断开WIFI ...", time_out_count)
                time.sleep_ms(10)
                self.sta.disconnect()
                timeout -= 1000
                time_out_count += 1
                if timeout <= 0:
                    print("[WIFI] WIFI关闭超时")
                    return False
            time.sleep_ms(100)
            while self.sta.isconnected():
                print("[WIFI] 尝试断开WIFI ...", time_out_count)
                time.sleep_ms(10)
                self.sta.disconnect()
                timeout -= 1000
                time_out_count += 1
                if timeout <= 0:
                    print("[WIFI] WIFI关闭超时")
                    return False
            time.sleep(3)
            if not self.sta.isconnected():
                print("[WIFI] WIFI已断开")
                return True
            else:
                print("[WIFI] WIFI关闭失败")
                return False
        except Exception as e:
            print("[WIFI] 关闭WIFI失败", e)
            return False

    def DISCONNECT_WIFI(self, timeout=8000):
        print("[WIFI] 关闭WIFI中")
        return self._disconnect_wifi(timeout)


    def _connect_wifi(self, ssid, key, timeout=10000):  # 添加超时参数，默认20秒
        try:
            self.sta = None
            self.sta = network.WLAN(0)
            self.sta.connect(ssid, key)
            
            # 添加超时计时
            start_time = time.ticks_ms()
            
            # 等待连接，有超时限制
            while not self.sta.isconnected():
                time.sleep_us(1)  # 使用微秒级sleep防止CPU跑满
                if time.ticks_ms() - start_time > timeout:
                    print("[WIFI] 连接超时")
                    return False  # 连接超时返回False
            
            print("[WIFI] WIFI连接成功 Connect success!")
            self.wifi_info.mode = 'sta'
            self.wifi_info.ssid = ssid
            return True
        
            # 等待获取IP，有超时限制
            ip_start_time = time.time()
            while self.sta.ifconfig()[0] == '0.0.0.0':
                time.sleep_us(1)  # 使用微秒级sleep防止CPU跑满
                if time.time() - ip_start_time > timeout:
                    print("[WIFI] 获取IP超时")
                    return False  # 获取IP超时返回False
                os.exitpoint()
                
            self.wifi_info.ip = self.sta.ifconfig()[0]
            return True  # 连接成功返回True
        except Exception as e:
            print("Connect WIFI Error:", e)
            return False  # 出现异常返回False

    def CONNECT_WIFI(self,ssid,key):
        print("[WIFI] WIFI连接中.... wifi connecting...")
        return self._connect_wifi(ssid,key)

    def SCAN_WIFI(self):
        try:
            return self.sta.scan()
        except Exception as e:
            print("Scan WIFI Error:",e)
    
    def check_wifi_exists(self, wifi_list, target_name):
        for wifi in wifi_list:
            if wifi.ssid.decode('utf-8') == target_name:
                return True
        return False

    def get_wifi_info(self):
        if self.sta.isconnected():
            info = self.sta.status("ap")
            self.wifi_info.mode = 'sta'
            self.wifi_info.ssid = info.ssid
            self.wifi_info.ip = self.sta.ifconfig()[0]
            self.wifi_info.rssi = info.rssi
            return self.wifi_info
        else:
            return None


if __name__ == "__main__":
    net = YbNetwork()
    print(net.SCAN_WIFI())
