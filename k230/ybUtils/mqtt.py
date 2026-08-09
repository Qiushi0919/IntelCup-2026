"""
MicroPython MQTT Client library
实现了MQTT协议的基本功能,支持QoS 0和QoS 1
"""

import usocket as socket
import ustruct as struct
from ubinascii import hexlify

class MQTTException(Exception):
    """MQTT异常类"""
    pass

class MQTTClient:
    """MQTT客户端实现类"""
    
    def __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0,
                 ssl=False, ssl_params={}):
        """
        初始化MQTT客户端
        Args:
            client_id: 客户端ID
            server: MQTT服务器地址
            port: 服务器端口,默认1883(普通连接)或8883(SSL连接)
            user: 用户名
            password: 密码  
            keepalive: 保活时间(秒)
            ssl: 是否使用SSL连接
            ssl_params: SSL参数
        """
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.socket = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.packet_id = 0
        self.callback = None
        self.username = user
        self.password = password
        self.keepalive = keepalive
        # Last Will 相关设置
        self.lw_topic = None
        self.lw_message = None 
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, string):
        """发送MQTT字符串,先发送长度,再发送内容"""
        self.socket.write(struct.pack("!H", len(string)))
        self.socket.write(string)

    def _recv_len(self):
        """接收MQTT消息长度字段(变长编码)"""
        multiplier = 1
        value = 0
        while 1:
            byte = self.socket.read(1)[0]
            value += (byte & 0x7f) * multiplier
            if not byte & 0x80:
                return value
            multiplier *= 128

    def set_callback(self, callback):
        """设置收到消息的回调函数"""
        self.callback = callback

    def set_last_will(self, topic, msg, retain=False, qos=0):
        """
        设置Last Will消息
        Args:
            topic: 主题
            msg: 消息内容
            retain: 是否保留消息
            qos: 服务质量(0或1)
        """
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_message = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True):
        """
        连接到MQTT服务器
        Args:
            clean_session: 是否清理会话
        Returns:
            布尔值,表示服务器是否有之前的会话数据
        """
        self.socket = socket.socket()
        server_address = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.socket.connect(server_address)
        
        if self.ssl:
            import ussl
            self.socket = ussl.wrap_socket(self.socket, **self.ssl_params)

        # 构造连接请求报文
        header = bytearray(b"\x10\0\0\0\0\0")  # 固定报头
        payload = bytearray(b"\x04MQTT\x04\x02\0\0")  # 可变报头

        # 计算剩余长度
        remaining_length = 10 + 2 + len(self.client_id)
        
        # 添加用户名密码长度
        if self.username is not None:
            remaining_length += 2 + len(self.username) + 2 + len(self.password)
            payload[6] |= 0xC0
            
        # 添加keepalive
        if self.keepalive:
            assert self.keepalive < 65536
            payload[7] |= self.keepalive >> 8
            payload[8] |= self.keepalive & 0x00FF
            
        # 添加遗嘱消息长度
        if self.lw_topic:
            remaining_length += 2 + len(self.lw_topic) + 2 + len(self.lw_message)
            payload[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            payload[6] |= self.lw_retain << 5

        # 编码剩余长度
        i = 1
        while remaining_length > 0x7f:
            header[i] = (remaining_length & 0x7f) | 0x80
            remaining_length >>= 7
            i += 1
        header[i] = remaining_length

        # 发送连接请求
        self.socket.write(header, i + 2)
        self.socket.write(payload)
        self._send_str(self.client_id)
        
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_message)
        if self.username is not None:
            self._send_str(self.username)
            self._send_str(self.password)

        # 处理服务器响应
        response = self.socket.read(4)
        assert response[0] == 0x20 and response[1] == 0x02
        if response[3] != 0:
            raise MQTTException(response[3])
        return response[2] & 1

    def disconnect(self):
        """断开与服务器的连接"""
        self.socket.write(b"\xe0\0")
        self.socket.close()

    def ping(self):
        """发送PING请求"""
        self.socket.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        """
        发布消息
        Args:
            topic: 主题
            msg: 消息内容
            retain: 是否保留消息
            qos: 服务质量(0或1)
        """
        packet = bytearray(b"\x30\0\0\0")
        packet[0] |= qos << 1 | retain
        
        # 计算剩余长度
        length = 2 + len(topic) + len(msg)
        if qos > 0:
            length += 2
        assert length < 2097152
        
        # 编码剩余长度
        i = 1
        while length > 0x7f:
            packet[i] = (length & 0x7f) | 0x80
            length >>= 7
            i += 1
        packet[i] = length

        self.socket.write(packet, i + 1)
        self._send_str(topic)
        
        if qos > 0:
            self.packet_id += 1
            pid = self.packet_id
            struct.pack_into("!H", packet, 0, pid)
            self.socket.write(packet, 2)
            
        self.socket.write(msg)

        # 处理QoS 1的响应
        if qos == 1:
            while 1:
                operation = self.wait_msg()
                if operation == 0x40:
                    size = self.socket.read(1)
                    assert size == b"\x02"
                    received_pid = self.socket.read(2)
                    received_pid = received_pid[0] << 8 | received_pid[1]
                    if pid == received_pid:
                        return
        elif qos == 2:
            assert 0  # QoS 2暂不支持

    def subscribe(self, topic, qos=0):
        """
        订阅主题
        Args:
            topic: 主题
            qos: 服务质量(0或1)
        """
        assert self.callback is not None, "Subscribe callback is not set"
        packet = bytearray(b"\x82\0\0\0")
        self.packet_id += 1
        struct.pack_into("!BH", packet, 1, 2 + 2 + len(topic) + 1, self.packet_id)
        
        self.socket.write(packet)
        self._send_str(topic)
        self.socket.write(qos.to_bytes(1, "little"))
        
        while 1:
            operation = self.wait_msg()
            if operation == 0x90:
                response = self.socket.read(4)
                assert response[1] == packet[2] and response[2] == packet[3]
                if response[3] == 0x80:
                    raise MQTTException(response[3])
                return

    def wait_msg(self):
        """
        等待并处理一个MQTT消息
        Returns:
            消息类型或None
        """
        res = self.socket.read(1)
        self.socket.setblocking(True)
        
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            size = self.socket.read(1)[0]
            assert size == 0
            return None
            
        operation = res[0]
        if operation & 0xf0 != 0x30:
            return operation
            
        # 处理PUBLISH消息
        size = self._recv_len()
        topic_length = self.socket.read(2)
        topic_length = (topic_length[0] << 8) | topic_length[1]
        topic = self.socket.read(topic_length)
        size -= topic_length + 2
        
        if operation & 6:
            pid = self.socket.read(2)
            pid = pid[0] << 8 | pid[1]
            size -= 2

        msg = self.socket.read(size)
        self.callback(topic, msg)
        
        if operation & 6 == 2:  # QoS 1
            packet = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", packet, 2, pid)
            self.socket.write(packet)
        elif operation & 6 == 4:  # QoS 2
            assert 0

    def check_msg(self):
        """
        非阻塞地检查是否有新消息
        Returns:
            有消息时返回消息类型,否则返回None
        """
        self.socket.setblocking(False)
        return self.wait_msg()