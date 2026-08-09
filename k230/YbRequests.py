# YbRequests.py 修改版本，修复HTTPS问题并支持文件上传
import usocket as socket
import ussl as ssl
import gc, os
import time

try:
    import ujson as json
except:
    import json

# 在Response类中添加保存二进制内容到文件的方法
class Response:
    def __init__(self, status_code, headers, content):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self._text = None
        self._json = None
    
    # 清理多余的换行符和空格
    def clean_data(self, data):
        dt = b''.join(line for line in data.splitlines() if line.strip())
        return dt
    
    @property
    def text(self):
        self.content = self.clean_data(self.content)
        gc.collect()
        # if self._text is None:
        #     try:
        #         self._text = self.content.decode('utf-8')
        #     except UnicodeDecodeError as e:
        #         self._text = self.content.decode('utf-8', errors='replace')
        #         print("error on decode: ", e)
        return self.content
    
    def parse_json_from_bytes(self, byte_data):
        # 找到JSON开始位置
        start_index = -1
        for i in range(len(byte_data)):
            if byte_data[i] == ord('{'):
                start_index = i
                break
        
        if start_index == -1:
            return None
        
        # 找到匹配的JSON结束位置
        open_braces = 0
        end_index = -1
        for i in range(start_index, len(byte_data)):
            if byte_data[i] == ord('{'):
                open_braces += 1
            elif byte_data[i] == ord('}'):
                open_braces -= 1
                if open_braces == 0:
                    end_index = i + 1  # 包含最后的 }
                    break
        
        if end_index == -1:
            return None
        
        # 只取出有效的JSON部分
        json_bytes = byte_data[start_index:end_index]
        try:
            return json.loads(json_bytes)
        except Exception as e:
            print("JSON解析失败:", e)
            return None
        
    def save_content_to_file(self, file_path):
        """
        将响应内容保存为文件
        
        参数:
        - file_path: 保存的文件路径
        
        返回:
        - bool: 保存是否成功
        """
        try:
            print(f"正在保存文件到: {file_path}")
            with open(file_path, 'wb') as f:
                print("正在写入文件...")
                f.write(self.content)
            print(f"文件已保存到: {file_path}")
            return True
        except Exception as e:
            print(f"保存文件失败: {e}")
            return False
        
    @property
    def json(self):
        if self._json is None:
            try:
                self._json = self.parse_json_from_bytes(self.text)
            except Exception as e:
                print("JSON解析失败, 检查内容格式: ", e)
                print("响应内容: ", self.text)
                raise
        return self._json
    
    def clean_response(self, raw_text):
        start_index = raw_text.find('{')
        if start_index == -1:
            return raw_text
        
        json_text = raw_text[start_index:]
        end_index = json_text.rfind('}')
        if end_index == -1:
            return json_text
        
        cleaned_json = json_text[:end_index + 1]
        return cleaned_json

def parse_url(url):
    scheme = 'http'
    if '://' in url:
        scheme, url = url.split('://', 1)

    hostname = url
    path = '/'
    port = 80 if scheme == 'http' else 443

    if '/' in url:
        hostname, path = url.split('/', 1)
        path = '/' + path

    if ':' in hostname:
        hostname, port = hostname.split(':')
        port = int(port)

    query = ''
    if '?' in path:
        path, query = path.split('?', 1)

    return {
        'scheme': scheme,
        'hostname': hostname,
        'port': port,
        'path': path,
        'query': query
    }

def parse_headers(headers_str):
    headers = {}
    for line in headers_str.split('\r\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()
    return headers

def parse_response(response):
    if not response or len(response) == 0:
        print("[DEBUG] Empty response received")
        return Response(0, {}, b'')  # 返回空响应而不是None
    
    header_end = response.find(b'\r\n\r\n')
    if header_end == -1:
        print("[DEBUG] No header separator found")
        return Response(0, {}, response)  # 返回原始数据
    
    headers_data = response[:header_end].decode('utf-8')
    body = response[header_end + 4:]
    headers_lines = headers_data.split('\r\n')
    status_line = headers_lines[0]
    
    try:
        status_code = int(status_line.split()[1])
    except (IndexError, ValueError):
        print("[DEBUG] Invalid status line: {}".format(status_line))
        return Response(0, {}, response)
    
    headers = parse_headers('\r\n'.join(headers_lines[1:]))
    return Response(status_code, headers, body)

def smart_read_response(sock, is_ssl=False, timeout=30):
    """
    智能读取HTTP响应，基于Content-Length和Transfer-Encoding判断传输完成
    """
    print("[DEBUG] Starting smart response reading")
    
    # 首先读取响应头
    response = b''
    header_complete = False
    headers = {}
    max_header_attempts = 50  # 增加最大尝试次数
    attempt = 0
    
    # 读取响应头
    while not header_complete and attempt < max_header_attempts:
        try:
            data = socket_receive(sock, 1024, is_ssl)
            attempt += 1
            
            if not data:
                print("[DEBUG] No data received, attempt {}/{}".format(attempt, max_header_attempts))
                # 对于SSL连接，给更多时间
                if is_ssl:
                    time.sleep(0.1)
                else:
                    time.sleep(0.05)
                continue
            
            response += data
            print("[DEBUG] Received {} bytes in attempt {}".format(len(data), attempt))
            
            header_end = response.find(b'\r\n\r\n')
            
            if header_end != -1:
                header_complete = True
                headers_data = response[:header_end].decode('utf-8')
                headers_lines = headers_data.split('\r\n')
                
                # 解析响应头
                for line in headers_lines[1:]:  # 跳过状态行
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip().lower()] = value.strip()
                
                print("[DEBUG] Headers parsed: {}".format(headers))
                break
                
        except Exception as e:
            print("[DEBUG] Exception while reading headers: {}".format(e))
            attempt += 1
            time.sleep(0.1)
    
    if not header_complete:
        print("[DEBUG] Failed to read complete headers after {} attempts".format(attempt))
        print("[DEBUG] Falling back to legacy read method")
        # 回退到原有的读取方法
        return read_legacy_response(sock, response, is_ssl)
    
    # 检查传输编码类型
    content_length = headers.get('content-length')
    transfer_encoding = headers.get('transfer-encoding', '').lower()
    
    if transfer_encoding == 'chunked':
        print("[DEBUG] Chunked transfer encoding detected")
        return read_chunked_response(sock, response, is_ssl)
    elif content_length:
        print("[DEBUG] Content-Length detected: {}".format(content_length))
        return read_content_length_response(sock, response, int(content_length), is_ssl)
    else:
        print("[DEBUG] No specific encoding, using connection-close method")
        return read_until_close_response(sock, response, is_ssl)

def read_legacy_response(sock, initial_response, is_ssl=False, max_empty_reads=10):
    """回退到原有的响应读取方法"""
    print("[DEBUG] Using legacy response reading")
    response = initial_response
    empty_reads = 0
    
    while empty_reads < max_empty_reads:
        try:
            data = socket_receive(sock, 1024, is_ssl)
            if not data:
                empty_reads += 1
                print("[DEBUG] Legacy empty read #{}, waiting...".format(empty_reads))
                time.sleep(0.2)
                continue
            else:
                empty_reads = 0
                response += data
                print("[DEBUG] Legacy received {} bytes".format(len(data)))
        except Exception as e:
            print("[DEBUG] Legacy read exception: {}".format(e))
            break
    
    print("[DEBUG] Legacy read complete, {} empty reads".format(empty_reads))
    return response

def read_chunked_response(sock, initial_response, is_ssl=False):
    """读取chunked编码的响应"""
    response = initial_response
    
    # 检查initial_response中是否已经包含了chunk数据
    # 如果包含，需要先处理这部分数据
    remaining_buffer = b''
    
    while True:
        try:
            # 读取chunk大小行
            chunk_size_line = remaining_buffer
            while b'\r\n' not in chunk_size_line:
                data = socket_receive(sock, 1, is_ssl)
                if not data:
                    print("[DEBUG] Connection closed while reading chunk size")
                    return response
                chunk_size_line += data
            
            # 分离chunk大小行和剩余数据
            parts = chunk_size_line.split(b'\r\n', 1)
            try:
                chunk_size_str = parts[0].decode('ascii').strip()
            except:
                # 如果ASCII解码失败，尝试UTF-8
                try:
                    chunk_size_str = parts[0].decode('utf-8').strip()
                except:
                    chunk_size_str = str(parts[0]).strip()
            
            remaining_buffer = parts[1] if len(parts) > 1 else b''
            
            print("[DEBUG] Raw chunk size line: '{}'".format(chunk_size_str))
            
            # 处理可能包含扩展信息的chunk大小行
            if ';' in chunk_size_str:
                chunk_size_str = chunk_size_str.split(';')[0]
            
            # 检查是否为有效的十六进制数字
            chunk_size_str = chunk_size_str.strip()
            if not chunk_size_str or not all(c in '0123456789abcdefABCDEF' for c in chunk_size_str):
                print("[DEBUG] Invalid chunk size format: '{}'".format(chunk_size_str))
                print("[DEBUG] Chunk size line bytes: {}".format(parts[0]))
                
                # 如果chunk大小格式无效，可能是数据混乱
                # 检查是否整个chunk_size_line实际上是JSON数据
                full_line = parts[0] + b'\r\n' + remaining_buffer
                try:
                    # 尝试将整行作为JSON数据处理
                    try:
                        test_str = full_line.decode('utf-8')
                    except:
                        test_str = str(full_line)
                    
                    if test_str.strip().startswith('{') or '"' in test_str:
                        print("[DEBUG] Detected JSON data in chunk size line, treating as response body")
                        response += full_line
                        # 继续读取剩余数据
                        while True:
                            try:
                                data = socket_receive(sock, 1024, is_ssl)
                                if not data:
                                    break
                                response += data
                            except:
                                break
                        break
                except:
                    pass
                
                # 如果不是JSON，尝试提取剩余数据
                response += chunk_size_line
                while True:
                    try:
                        data = socket_receive(sock, 1024, is_ssl)
                        if not data:
                            break
                        response += data
                    except:
                        break
                break
            
            try:
                chunk_size = int(chunk_size_str, 16)
            except ValueError:
                print("[DEBUG] Cannot parse chunk size: '{}'".format(chunk_size_str))
                # 将当前数据加入响应并继续读取
                response += chunk_size_line
                while True:
                    try:
                        data = socket_receive(sock, 1024, is_ssl)
                        if not data:
                            break
                        response += data
                    except:
                        break
                break
            
            print("[DEBUG] Chunk size: {} (0x{})".format(chunk_size, chunk_size_str))
            
            # 如果chunk大小为0，表示传输结束
            if chunk_size == 0:
                print("[DEBUG] Chunked transfer complete")
                # 读取最后的\r\n
                if len(remaining_buffer) >= 2:
                    remaining_buffer = remaining_buffer[2:]
                else:
                    need_bytes = 2 - len(remaining_buffer)
                    try:
                        trailing_data = socket_receive(sock, need_bytes, is_ssl)
                        remaining_buffer = remaining_buffer + trailing_data
                        remaining_buffer = remaining_buffer[2:]
                    except:
                        pass
                
                # 如果还有剩余数据，添加到响应中
                if remaining_buffer:
                    response += remaining_buffer
                
                # 继续读取可能的trailer headers
                try:
                    while True:
                        extra_data = socket_receive(sock, 1024, is_ssl)
                        if not extra_data:
                            break
                        response += extra_data
                except:
                    pass
                break
            
            # 读取chunk数据
            chunk_data = remaining_buffer
            while len(chunk_data) < chunk_size:
                remaining = chunk_size - len(chunk_data)
                data = socket_receive(sock, min(remaining, 1024), is_ssl)
                if not data:
                    print("[DEBUG] Connection closed while reading chunk data")
                    return response
                chunk_data += data
            
            # 将chunk数据添加到响应中
            response += chunk_data[:chunk_size]
            remaining_buffer = chunk_data[chunk_size:]
            
            # 读取chunk结尾的\r\n
            if len(remaining_buffer) >= 2:
                remaining_buffer = remaining_buffer[2:]
            else:
                need_bytes = 2 - len(remaining_buffer)
                try:
                    trailing_data = socket_receive(sock, need_bytes, is_ssl)
                    remaining_buffer = remaining_buffer + trailing_data
                    remaining_buffer = remaining_buffer[2:]
                except:
                    print("[DEBUG] Failed to read chunk trailer")
                    break
            
        except Exception as e:
            print("[DEBUG] Exception in chunked reading: {}".format(e))
            # 尝试读取剩余数据
            try:
                if remaining_buffer:
                    response += remaining_buffer
                while True:
                    data = socket_receive(sock, 1024, is_ssl)
                    if not data:
                        break
                    response += data
            except:
                pass
            break
    
    return response

def read_content_length_response(sock, initial_response, content_length, is_ssl=False):
    """基于Content-Length读取响应"""
    response = initial_response
    
    # 计算已读取的body长度
    header_end = response.find(b'\r\n\r\n')
    if header_end == -1:
        return response
    
    body_received = len(response) - (header_end + 4)
    print("[DEBUG] Body already received: {}/{}".format(body_received, content_length))
    
    # 继续读取剩余数据
    while body_received < content_length:
        try:
            remaining = content_length - body_received
            chunk_size = min(remaining, 1024)
            data = socket_receive(sock, chunk_size, is_ssl)
            
            if not data:
                print("[DEBUG] Connection closed, received {}/{} bytes".format(body_received, content_length))
                break
            
            response += data
            body_received += len(data)
            print("[DEBUG] Progress: {}/{} bytes".format(body_received, content_length))
            
        except Exception as e:
            print("[DEBUG] Exception while reading content: {}".format(e))
            break
    
    print("[DEBUG] Content-Length transfer complete: {}/{} bytes".format(body_received, content_length))
    return response

def read_until_close_response(sock, initial_response, is_ssl=False, max_empty_reads=5):
    """读取直到连接关闭（改进的空读逻辑）"""
    response = initial_response
    empty_reads = 0
    consecutive_empty_reads = 0
    
    while empty_reads < max_empty_reads:
        try:
            data = socket_receive(sock, 1024, is_ssl)
            
            if not data:
                empty_reads += 1
                consecutive_empty_reads += 1
                print("[DEBUG] Empty read #{}/{}".format(empty_reads, max_empty_reads))
                
                # 如果连续空读超过3次，增加等待时间
                if consecutive_empty_reads > 3:
                    time.sleep(0.5)
                else:
                    time.sleep(0.1)
                continue
            else:
                # 收到数据，重置连续空读计数
                consecutive_empty_reads = 0
                response += data
                print("[DEBUG] Received {} bytes".format(len(data)))
                
        except Exception as e:
            print("[DEBUG] Exception in read_until_close: {}".format(e))
            break
    
    print("[DEBUG] Connection-close transfer complete, {} empty reads".format(empty_reads))
    return response

# 添加辅助函数来统一处理发送和接收
def socket_send(sock, data, is_ssl=False):
    """统一处理socket发送，区分普通socket和SSL socket"""
    if is_ssl:
        sock.write(data)
    else:
        sock.send(data)

def socket_send_with_retry(sock, data, is_ssl=False, max_retries=10):
    """改进的socket发送函数，处理EAGAIN错误"""
    sent = 0
    data_len = len(data)
    retry_count = 0
    
    while sent < data_len and retry_count < max_retries:
        try:
            if is_ssl:
                result = sock.write(data[sent:])
            else:
                result = sock.send(data[sent:])
            
            if result > 0:
                sent += result
                retry_count = 0  # 重置重试计数
            elif result == 0:
                break  # 连接关闭
                
        except OSError as e:
            if e.errno == 11:  # EAGAIN
                retry_count += 1
                print(f"[DEBUG] EAGAIN #{retry_count}, waiting...")
                time.sleep(0.05)  # 等待50ms
                gc.collect()  # 清理内存
            else:
                raise e
    
    return sent

def socket_receive(sock, chunk_size=1024, is_ssl=False):
    """改进的socket接收函数"""
    if is_ssl:
        try:
            data = sock.read(chunk_size)
            return data if data else b''
        except Exception as e:
            print("[DEBUG] SSL read exception: {}".format(e))
            # 对于SSL，有些异常可能是正常的连接结束
            return b''
    else:
        try:
            data = sock.recv(chunk_size)
            return data if data else b''
        except Exception as e:
            print("[DEBUG] Socket recv exception: {}".format(e))
            return b''

def request(method, url, headers=None, data=None, json_data=None, file_data=None, timeout=30, max_redirects=5, chunk_size=1024):
    print("\n[DEBUG] Starting request: {} {}".format(method, url))
    parsed_url = parse_url(url)
    print("[DEBUG] Parsed URL: {}".format(parsed_url))
    
    default_headers = {
        'Host': parsed_url['hostname'],
        'User-Agent': 'MicroPython/1.0',
        'Connection': 'close'
    }

    if headers:
        print("[DEBUG] Custom headers: {}".format(headers))
        default_headers.update(headers)
    headers = default_headers
    print("[DEBUG] Final headers: {}".format(headers))
    
    is_https = parsed_url['scheme'].lower() == 'https'
    is_ssl = is_https
    
    # 处理文件上传
    if file_data and isinstance(file_data, dict):
        boundary = "---micropythonboundary"
        content_type = "multipart/form-data; boundary={}".format(boundary)
        
        # 使用分块传输编码
        # 创建socket连接
        path = parsed_url['path']
        if parsed_url['query']:
            path += '?' + parsed_url['query']
        
        print("[DEBUG] File upload path: {}".format(path))
        
        # 创建socket连接
        s = socket.socket()
        addr = socket.getaddrinfo(parsed_url['hostname'], parsed_url['port'])[0][-1]
        print("[DEBUG] Resolved address: {}".format(addr))
        s.settimeout(timeout)
        s.connect(addr)
        
        if is_https:
            print("[DEBUG] Using HTTPS connection for file upload")
            try:
                s = ssl.wrap_socket(s, server_hostname=parsed_url['hostname'])
            except Exception as e:
                print("[ERROR] SSL wrap failed: {}".format(e))
                raise
        
        try:
            # 构建请求头，使用chunked传输
            request_header = (
                "{} {} HTTP/1.1\r\n"
                "Host: {}\r\n"
                "User-Agent: MicroPython/1.0\r\n"
                "Content-Type: {}\r\n"
                "Transfer-Encoding: chunked\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).format(method, path, parsed_url['hostname'], content_type)
            
            # 发送请求头
            socket_send(s, request_header.encode(), is_https)
            
            # 开始发送分块数据
            for field_name, file_path in file_data.items():
                # 获取文件名 (替代 os.path.basename)
                file_name = file_path.split("/")[-1]
                if not file_name:
                    file_name = file_path
                
                # 构建表单字段头部
                field_header = (
                    "--{boundary}\r\n"
                    'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
                    "Content-Type: application/octet-stream\r\n\r\n"
                ).format(boundary=boundary, field_name=field_name, file_name=file_name)
                
                # 发送字段头部
                chunk_header = "{:x}\r\n".format(len(field_header)).encode()
                socket_send(s, chunk_header + field_header.encode() + b"\r\n", is_https)
                
                # 分块读取文件并发送
                with open(file_path, 'rb') as f:
                    bytes_sent = 0
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        
                        # 发送分块
                        chunk_header = "{:x}\r\n".format(len(chunk)).encode()
                        socket_send(s, chunk_header + chunk + b"\r\n", is_https)
                        
                        bytes_sent += len(chunk)
                        print("[DEBUG] Sent {} bytes of file data".format(bytes_sent))
                        gc.collect()  # 清理内存
            
            # 发送表单尾部
            form_end = "\r\n--{}--\r\n".format(boundary)
            chunk_header = "{:x}\r\n".format(len(form_end)).encode()
            socket_send(s, chunk_header + form_end.encode() + b"\r\n", is_https)
            
            # 发送结束块
            socket_send(s, b"0\r\n\r\n", is_https)
            
            # 读取响应
            response = smart_read_response(s, is_https)
            
            print("[DEBUG] Total response size: {} bytes".format(len(response)))
            resp = parse_response(response)
            if resp is None:
                print("[ERROR] Failed to parse response")
                resp = Response(0, {}, response)
            print("[DEBUG] Response status code: {}".format(resp.status_code))
            
            return resp
        except Exception as e:
            print("[ERROR] request error: {}".format(e))
        finally:
            print("[DEBUG] Closing file upload connection")
            s.close()
    else:
        # 原始的请求处理逻辑
        body = b''
        if data and isinstance(data, str):
            body = data.encode()
        elif data and isinstance(data, bytes):
            body = data
        elif data and isinstance(data, dict):
            body = '&'.join(['{}={}'.format(k, v) for k, v in data.items()]).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        elif isinstance(json_data, dict):
            body = json.dumps(json_data).encode()
            headers['Content-Type'] = 'application/json'
        else:
            body = None

        if body:
            print("[DEBUG] Body length: {}".format(len(body)))
            headers['Content-Length'] = str(len(body))

        path = parsed_url['path']
        if parsed_url['query']:
            path += '?' + parsed_url['query']
        print("[DEBUG] Full path: {}".format(path))

        # 发送请求行和头
        request_lines = ['{} {} HTTP/1.1'.format(method, path)]
        for k, v in headers.items():
            request_lines.append('{}: {}'.format(k, v))
        request_lines.extend(['', ''])
        request_data = '\r\n'.join(request_lines).encode()
        print("[DEBUG] Request data length: {}".format(len(request_data)))
        
        print("[DEBUG] Creating socket connection to {}:{}".format(parsed_url['hostname'], parsed_url['port']))
        s = socket.socket()
        addr = socket.getaddrinfo(parsed_url['hostname'], parsed_url['port'])[0][-1]
        print("[DEBUG] Resolved address: {}".format(addr))
        s.settimeout(timeout)
        s.connect(addr)

        try:
            if is_https:
                print("[DEBUG] Using HTTPS connection")
                try:
                    s = ssl.wrap_socket(s, server_hostname=parsed_url['hostname'])
                    print("[DEBUG] SSL wrap successful")
                except Exception as e:
                    print("[ERROR] SSL wrap failed: {}".format(e))
                    raise
                
                socket_send(s, request_data, is_https)

                # 处理文件分块上传
                if data and isinstance(data, str) and os.path.exists(data):
                    with open(data, 'rb') as file:
                        while True:
                            chunk = file.read(chunk_size)
                            if not chunk:
                                break
                            socket_send(s, chunk, is_https)
                elif body:
                    socket_send(s, body, is_https)
                    
                # 读取响应
                response = smart_read_response(s, is_https)
                
                print("[DEBUG] Total response size: {} bytes".format(len(response)))
                resp = parse_response(response)
                if resp is None:
                    print("[ERROR] Failed to parse response")
                    resp = Response(0, {}, response)
                print("[DEBUG] Response status code: {}".format(resp.status_code))
            else:
                print("[DEBUG] Using HTTP connection")
                socket_send(s, request_data, is_https)
                if body:
                    socket_send(s, body, is_https)
                    
                # 读取响应
                response = smart_read_response(s, is_https)

            print("[DEBUG] Total response size: {} bytes".format(len(response)))
            resp = parse_response(response)
            if resp is None:
                print("[ERROR] Failed to parse response")
                resp = Response(0, {}, response)
            
            print("[DEBUG] Response status code: {}".format(resp.status_code))
            
            if resp.status_code == 302 and 'Location' in resp.headers:
                if max_redirects > 0:
                    redirect_url = resp.headers['Location']
                    print("[DEBUG] Following redirect to: {}".format(redirect_url))
                    return request(method, redirect_url, headers=headers, data=data, 
                                json_data=json_data, file_data=file_data, timeout=timeout, 
                                max_redirects=max_redirects - 1)
                else:
                    raise Exception('Exceeded maximum number of redirects')
            return resp
        except Exception as e:
            print("[ERROR] Request failed: {}".format(e))
            raise
        finally:
            print("[DEBUG] Closing connection")
            s.close()

def get(url, **kwargs):
    return request('GET', url, **kwargs)

def post(url, **kwargs):
    return request('POST', url, **kwargs)

# 新增上传文件的便捷函数
def upload_file(url, file_field_name, file_path, headers=None, timeout=60):
    """
    上传文件到指定URL
    
    参数:
    - url: 上传目标URL
    - file_field_name: 表单字段名称
    - file_path: 文件路径
    - headers: 额外的请求头
    - timeout: 超时时间(秒)
    
    返回:
    - Response对象
    """
    return post(
        url=url,
        headers=headers,
        file_data={file_field_name: file_path},
        timeout=timeout
    )

def upload_file_optimized(url, file_field_name, file_path, headers=None, timeout=60, chunk_size=512):
    """优化的文件上传函数"""
    parsed_url = parse_url(url)
    is_https = parsed_url['scheme'].lower() == 'https'
    
    # 使用更小的chunk_size，减少内存压力
    boundary = "---micropythonboundary"
    content_type = "multipart/form-data; boundary={}".format(boundary)
    
    path = parsed_url['path']
    if parsed_url['query']:
        path += '?' + parsed_url['query']
    
    s = socket.socket()
    addr = socket.getaddrinfo(parsed_url['hostname'], parsed_url['port'])[0][-1]
    s.settimeout(timeout)
    s.connect(addr)
    
    if is_https:
        s = ssl.wrap_socket(s, server_hostname=parsed_url['hostname'])
    
    try:
        # 发送请求头
        request_header = (
            "POST {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "User-Agent: MicroPython/1.0\r\n"
            "Content-Type: {}\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(path, parsed_url['hostname'], content_type)
        
        socket_send_with_retry(s, request_header.encode(), is_https)
        
        # 发送文件数据
        file_name = file_path.split("/")[-1]
        field_header = (
            "--{boundary}\r\n"
            'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).format(boundary=boundary, field_name=file_field_name, file_name=file_name)
        
        # 分块发送字段头
        chunk_header = "{:x}\r\n".format(len(field_header)).encode()
        socket_send_with_retry(s, chunk_header + field_header.encode() + b"\r\n", is_https)
        
        # 分块读取并发送文件
        with open(file_path, 'rb') as f:
            bytes_sent = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # 发送数据块
                chunk_header = "{:x}\r\n".format(len(chunk)).encode()
                chunk_data = chunk_header + chunk + b"\r\n"
                
                sent = socket_send_with_retry(s, chunk_data, is_https)
                if sent < len(chunk_data):
                    print(f"[WARNING] Only sent {sent}/{len(chunk_data)} bytes")
                    break
                
                bytes_sent += len(chunk)
                if bytes_sent % (chunk_size * 10) == 0:  # 每发送10个块清理一次内存
                    print(f"[DEBUG] Sent {bytes_sent} bytes")
                    gc.collect()
        
        # 发送结束标记
        form_end = "\r\n--{}--\r\n".format(boundary)
        chunk_header = "{:x}\r\n".format(len(form_end)).encode()
        socket_send_with_retry(s, chunk_header + form_end.encode() + b"\r\n", is_https)
        socket_send_with_retry(s, b"0\r\n\r\n", is_https)
        
        # 接收响应
        response = b''
        recv_count = 0
        while True:
            data = socket_receive(s, 1024, is_https)
            if not data:
                recv_count += 1
                time.sleep(0.1)  # 等待100ms
                print(f"[DEBUG] Empty read on upload_file function #{recv_count}, waiting...")
            if recv_count > 6:
                break
            response += data
            gc.collect()
        
        return parse_response(response)
        
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        raise
    finally:
        s.close()

# 添加下载文件的便捷函数
def download_file(url, save_path, headers=None, timeout=60):
    """
    从URL下载文件并保存到指定路径
    
    参数:
    - url: 下载文件的URL
    - save_path: 保存文件的路径
    - headers: 额外的请求头
    - timeout: 超时时间(秒)
    
    返回:
    - bool: 下载是否成功
    """
    try:
        print(f"开始下载文件: {url}")
        response = get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            return response.save_content_to_file(save_path)
        else:
            print(f"下载失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"下载过程中发生错误: {e}")
        return False

# 添加语音对话的便捷函数
def voice_chat(url, audio_file_path, save_path, headers=None, timeout=60):
    """
    发送语音文件进行AI对话并保存返回的音频文件
    
    参数:
    - url: 语音对话API的URL
    - audio_file_path: 要上传的音频文件路径
    - save_path: 保存返回音频的路径
    - headers: 额外的请求头
    - timeout: 超时时间(秒)
    
    返回:
    - bool: 操作是否成功
    """
    try:
        print(f"开始语音对话请求: {url}")
        response = upload_file(url, 'audio', audio_file_path, headers, timeout)
        # 检查响应状态码
        if response.status_code == 200:
            # 检查Content-Type是否为音频类型
            content_type = response.headers.get('Content-Type', '')
            if 'audio/' in content_type:
                # 保存音频文件
                print("正在保存音频文件...")
                return response.save_content_to_file(save_path)
            else:
                # 可能是JSON响应，表示出错
                try:
                    error_info = response.json
                    print(f"服务器返回错误: {error_info}")
                except:
                    print(f"无法解析服务器响应")
                return False
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(response.content)
            return False
    except Exception as e:
        print(f"语音对话过程中发生错误: {e}")
        return False

def voice_to_text(url, audio_file_path, headers=None, timeout=60, max_retries=3):
    """
    发送语音文件进行语音转文字识别，添加重试机制
    
    参数:
    - url: 语音识别API的URL
    - audio_file_path: 要上传的音频文件路径
    - headers: 额外的请求头
    - timeout: 超时时间(秒)
    - max_retries: 最大重试次数
    
    返回:
    - tuple: (bool, str|dict)
      - 第一个元素表示是否成功
      - 第二个元素在成功时是识别出的文本，失败时是错误信息
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            print(f"开始语音识别请求: {url} (尝试 {retry_count + 1}/{max_retries})")
            gc.collect()  # 在重试前进行垃圾回收
            
            # response = upload_file(url, 'audio', audio_file_path, headers, timeout)
            response = upload_file_optimized(url, 'audio', audio_file_path, headers, timeout)
            
            
            if response.status_code == 200:
                try:
                    result = response.json
                    if result.get('success'):
                        recognized_text = result.get('text', '')
                        print(f"语音识别成功: {recognized_text}")
                        return True, recognized_text
                    else:
                        error_msg = result.get('message', '未知错误')
                        print(f"语音识别失败: {error_msg}")
                        return False, error_msg
                except Exception as e:
                    print(f"解析响应失败: {e}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        return False, str(e)
                    time.sleep(1)  # 等待1秒后重试
                    continue
            else:
                error_msg = f"请求失败，状态码: {response.status_code}"
                print(error_msg)
                retry_count += 1
                if retry_count >= max_retries:
                    return False, error_msg
                time.sleep(1)
                continue
                
        except Exception as e:
            error_msg = f"语音识别过程中发生错误: {e}"
            print(error_msg)
            retry_count += 1
            if retry_count >= max_retries:
                return False, error_msg
            time.sleep(1)
            continue
    
    return False, f"达到最大重试次数 ({max_retries})"

def text_to_speech(url, text, save_path, headers=None, timeout=60):
    """
    发送文本进行文字转语音并保存返回的音频文件
    
    参数:
    - url: 文字转语音API的URL (/text-to-speech)
    - text: 要转换的文本内容
    - save_path: 保存返回音频的路径
    - headers: 额外的请求头
    - timeout: 超时时间(秒)
    
    返回:
    - bool: 转换并保存是否成功
    """
    try:
        print(f"开始文字转语音请求: {url}")
        
        # 设置请求头和数据
        if not headers:
            headers = {}
        headers['Content-Type'] = 'application/json'
        
        # 发送POST请求
        response = post(
            url=url,
            headers=headers,
            json_data={'text': text},
            timeout=timeout
        )
        
        # 检查响应状态码
        if response.status_code == 200:
            # 检查Content-Type是否为音频类型
            content_type = response.headers.get('Content-Type', '')
            if 'audio/' in content_type:
                # 保存音频文件
                print("正在保存音频文件...")
                return response.save_content_to_file(save_path)
            else:
                # 可能是JSON响应，表示出错
                try:
                    error_info = response.json
                    print(f"服务器返回错误: {error_info}")
                except:
                    print(f"无法解析服务器响应")
                return False
        else:
            print(f"请求失败，状态码: {response.status_code}")
            if response.content:
                print(f"错误信息: {response.content}")
            return False
            
    except Exception as e:
        print(f"文字转语音过程中发生错误: {e}")
        return False
    
def chat(url, messages, headers=None, timeout=60):
    """
    发送文本进行AI对话
    
    参数:
    - url: AI对话API的URL (/chat)
    - messages: 消息历史数组，每个元素应该是包含 role 和 content 的字典
                例如：[
                    {"role": "system", "content": "你是一个助手"},
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！有什么我可以帮你的吗？"}
                ]
    - headers: 额外的请求头
    - timeout: 超时时间(秒)
    
    返回:
    - tuple: (bool, str|dict)
      - 第一个元素表示是否成功
      - 第二个元素在成功时是AI的回复文本，失败时是错误信息
    """
    try:
        print(f"开始AI对话请求: {url}")
        
        # 验证消息数组格式
        if not isinstance(messages, list):
            return False, "messages参数必须是一个数组"
        
        # 设置请求头和数据
        if not headers:
            headers = {}
        headers['Content-Type'] = 'application/json'
        
        # 发送POST请求
        response = post(
            url=url,
            headers=headers,
            json_data={'messages': messages},
            timeout=timeout
        )
        
        # 检查响应状态码
        if response.status_code == 200:
            try:
                result = response.json
                if result.get('success'):
                    ai_response = result.get('response', '')
                    print(f"AI对话成功: {ai_response}")
                    return True, ai_response
                else:
                    error_msg = result.get('message', '未知错误')
                    print(f"AI对话失败: {error_msg}")
                    return False, error_msg
            except Exception as e:
                print(f"解析响应失败: {e}")
                return False, str(e)
        else:
            error_msg = f"请求失败，状态码: {response.status_code}"
            print(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"AI对话过程中发生错误: {e}"
        print(error_msg)
        return False, error_msg