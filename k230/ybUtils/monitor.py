import json
import socket
import network
import os
import utime as time
import machine
import uos, gc
import _thread

class WIFI_INFO:
    def __init__(self):
        self.mode = None
        self.key = None
        self.ssid = None
        self.ip = None
        self.rssi = None

wifi_info = WIFI_INFO()

def DISCONNECT_WIFI():
    print("[WIFI] Closing wifi ...")
    try:
        sta = network.WLAN(0)
        sta.disconnect()
        time.sleep(1)
        if sta.isconnected():
            print("[WIFI] wifi closeed")
            return True
    except Exception as e:
        print("[WIFI] 关闭WIFI失败")
        return False

def CONNECT_WIFI(ssid,key):
    global sta,wifi_info
    AP_SSID = 'YAHBOOM-K230'
    AP_KEY = '12345678'
    try:
        sta = None
        if (ssid is None and key is None):
            print("[Monitor] 热点创建中 / Use AP mode")
            sta = network.WLAN(network.AP_IF)
            if not sta.active():
                sta.active(True)
            sta.config(ssid=AP_SSID, key=AP_KEY)
            print("[Monitor] 5%")
            time.sleep(1)
            print("[Monitor] 15%")
            time.sleep(1)
            print("[Monitor] 50%")
            time.sleep(1)
            print("[Monitor] 90%")
            time.sleep(1)
            print("[Monitor] 99%")
            wifi_info.mode = 'ap'
            wifi_info.ssid = AP_SSID
            wifi_info.key = AP_KEY
            print("\n[Monitor] 热点已创建 / Hotspot created:")
            print(f"[Monitor] SSID: {AP_SSID}")
            print(f"[Monitor] KEY: {AP_KEY}")
        else:
            print("[WIFI] WIFI连接中.... wifi connecting...")
            sta = network.WLAN(0)
            start_time = time.ticks_ms()
            while sta.isconnected():
                sta.disconnect()
                time.sleep(1)
                if time.ticks_diff(time.ticks_ms(),start_time) > 10000:
                    print("[Monitor] 异常，无法断开WIFI")
                    break           
            sta.connect(ssid,key)
            while not sta.isconnected():
                time.sleep(1)
            print("[Monitor] WIFI连接成功 Connect success!")
            wifi_info.mode = 'sta'
            wifi_info.ssid = ssid
        while sta.ifconfig()[0] == '0.0.0.0':
            os.exitpoint()
        wifi_info.ip = sta.ifconfig()[0]
        return wifi_info.ip
    except Exception as e:
        print("Connet WIFI Error:",e)

def get_device_status():
    global sta,wifi_info
    h = gc.sys_heap()
    p = gc.sys_page()
    m = gc.sys_mmz()
    sdcard_storage = uos.statvfs('/sdcard/')
    data_storage = uos.statvfs('/data/')
    chip_id = ''.join(['%02x' % b for b in machine.chipid()])
    if wifi_info.mode == 'sta':
        wifi_info.rssi = sta.status("rssi")
    else:
        wifi_info.rssi = 'AP模式下无信号强度区分'
    return {
        "wifi_mode": wifi_info.mode,
        "wifi_ssid": wifi_info.ssid,
        "wifi_ip": wifi_info.ip,
        "wifi_signal": wifi_info.rssi,
        "device_name": "亚博智能K230",
        "chip_id": chip_id,
        "firmware_version": "1.0.0",
        "temperature": machine.temperature(),
        "cpu_usage": uos.cpu_usage(),
        "heap_memory": {
            "total": h[0],
            "available": h[2]
        },
        "page_memory": {
            "total": p[0],
            "available": p[2]
        },
        "mmz_memory": {
            "total": m[0],
            "available": m[2]
        },
        "sdcard_storage": {
            "total": sdcard_storage[0]*sdcard_storage[2],
            "available": sdcard_storage[0]*sdcard_storage[3]
        },
        "data_storage": {
            "total": data_storage[0]*data_storage[2],
            "available": data_storage[0]*data_storage[3]
        }
    }

def read_file(filename):
    # 定义文件类型与Content-Type的映射
    content_types = {
        'html': 'text/html',
        'js': 'application/javascript',
        'css': 'text/css',
        'json': 'application/json',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'ico': 'image/x-icon',
        'woff2': 'application/octet-stream',
        'woff': 'application/octet-stream',
        'ttf': 'application/octet-stream',
        'map': 'application/octet-stream'
    }

    try:
        # 获取文件扩展名
        file_ext = filename.split('.')[-1].lower()

        # 确定content_type
        content_type = content_types.get(file_ext, 'text/plain')

        # 根据文件类型决定读取模式
        if file_ext in ['png', 'jpg', 'jpeg', 'gif', 'ico','woff','woff2','ttf','map']:
            # 二进制文件使用 'rb' 模式
            with open(filename, 'rb') as file:
                content = file.read()
                return f"""\
HTTP/1.0 200 OK\r\n\
Content-Type: {content_type}\r\n\
\r\n""".encode() + content
        else:
            # 文本文件使用 'r' 模式并指定编码
            with open(filename, 'r', encoding='utf-8') as file:
                content = file.read()
                return f"""\
HTTP/1.0 200 OK\r\n\
Content-Type: {content_type}; charset=utf-8\r\n\
\r\n\
{content}""".encode('utf-8')

    except Exception as e:
        # 返回404错误响应
        return f"""\
HTTP/1.0 404 Not Found\r\n\
Content-Type: text/plain; charset=utf-8\r\n\
\r\n\
File not found: {filename}""".encode('utf-8')

def main(ssid=None,key=None,network_connected=False,micropython_optimize=True):
    global sta
    try:
        if network_connected is True:
            sta = network.WLAN(0)
            wifi_info.mode = 'sta'
            wifi_info.ssid = sta.status("ap").ssid
            wifi_info.ip = sta.ifconfig()[0]
            ip = wifi_info.ip
        else:
            ip = CONNECT_WIFI(ssid,key)
        
        print("[Monitor] 正在启动服务器 running server...")
        time.sleep(2)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(30)
        s.bind((ip, 8082))
        s.listen(30)
        time.sleep(1)
        print("[Monitor] 服务器启动成功 K230 SERVER RUNIGN ON http://%s:8082/" % (ip))
    except Exception as e:
        print("SERVER RUNING ERROR, CAUSE:", e)

    while True:
        try:
            res = s.accept()
            client_sock = res[0]
            client_addr = res[1]
            client_sock.setblocking(False)
            client_stream = client_sock if micropython_optimize else client_sock.makefile("rwb")
    
            request = b""
            while True:
                h = client_stream.read()
                if h is None or h==b'':
                    continue
                request += h
                if b"\r\n\r\n" in request:
                    if b'POST' in request and b'Content-Length: ' in request:
                        header_end = request.find(b'\r\n\r\n') + 4
                        headers = request[:header_end]
                        body_so_far = request[header_end:]
                        
                        # 提取Content-Length
                        content_length_pos = headers.find(b'Content-Length: ')
                        if content_length_pos > 0:
                            content_length_end = headers.find(b'\r\n', content_length_pos)
                            content_length = int(headers[content_length_pos + 16:content_length_end])
                            
                            # 继续读取直到获取完整body
                            while len(body_so_far) < content_length:
                                chunk = client_stream.read()
                                if chunk:
                                    body_so_far += chunk
                                os.exitpoint()
                            
                            request = headers + body_so_far
                            break
                    else:
                        break
                os.exitpoint()
                
            if b'GET /status' in request:
                status_data = get_device_status()
                response = f"""\
HTTP/1.0 200 OK\r\n\
Content-Type: application/json\r\n\
\r\n\
{json.dumps(status_data)}"""
                client_stream.write(response.encode())
            
            elif b'GET /stop-monitor' in request:
                response = f"""\
HTTP/1.0 200 OK\r\n\
Content-Type: application/json\r\n\
\r\n\
{json.dumps({"ret":"stop-monitor OK"})}"""
                client_stream.write(response.encode())
                print("[Monitor] 关闭性能监视后台 Close Monitor")
                time.sleep(1)
                client_stream.close()
                _thread.exit()
                
            elif b'GET /restart-device' in request:
                response = f"""\
HTTP/1.0 200 OK\r\n\
Content-Type: application/json\r\n\
\r\n\
{json.dumps({"ret":"restart-device OK"})}"""
                print("[Monitor] 接收到重启指令 Receive restart cmd")
                client_stream.write(response.encode())
                time.sleep(1)
                machine.reset()
            else:
                # 获取请求的路径
                requested_path = request.split(b' ')[1].decode().strip('/')
                if not requested_path:
                    requested_path = 'monitor.html'
    
                # 构建完整的文件路径
                full_path = f'/sdcard/resources/page/{requested_path}'
                content = read_file(full_path)
                client_stream.write(content)
                
            client_stream.close()
        except Exception as e:
            print(f"HTTP请求异常 {e}")
            continue

def run(ssid=None,key=None,network_connected=False):
    if(ssid is None and network_connected is False):
        print("[WARNING] 目前不支持AP模式下使用该功能，请传入一个WIFI连接信息")
        print("[WARNING] 或连接WIFI后 调用run(network_connected=True)")
        return
    _thread.start_new_thread(main,(ssid, key, network_connected))

if __name__ == "__main__":
    run("Yahboom", "WIFI PASSWORD")