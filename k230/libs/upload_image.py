import os
import gc
try:
    import urequests as requests
except ImportError:
    import requests

# MicroPython兼容的路径处理
def basename(path):
    """获取文件名，兼容MicroPython"""
    if hasattr(os, 'path') and hasattr(os.path, 'basename'):
        return os.path.basename(path)
    else:
        # MicroPython兼容实现
        if '/' in path:
            return path.split('/')[-1]
        elif '\\' in path:
            return path.split('\\')[-1]
        else:
            return path

def get_upload_policy(api_key, model_name):
    """获取文件上传凭证"""
    # 手动构建URL参数，因为urequests不支持params参数
    url = f"https://dashscope.aliyuncs.com/api/v1/uploads?action=getPolicy&model={model_name}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to get upload policy: {response.text}")
    
    json_data = response.json()
    return json_data['data']

def upload_file_to_oss(policy_data, file_path):
    """将文件上传到临时存储OSS"""
    file_name = basename(file_path)
    key = f"{policy_data['upload_dir']}/{file_name}"
    
    # 在文件读取前进行垃圾回收
    gc.collect()
    
    # 读取文件数据
    with open(file_path, 'rb') as file_content:
        file_data = file_content.read()
    
    # 文件读取后进行垃圾回收
    gc.collect()
    
    # 构建multipart/form-data格式的数据
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    # 构建表单数据
    form_data = []
    
    # 添加各个字段
    fields = {
        'OSSAccessKeyId': policy_data['oss_access_key_id'],
        'Signature': policy_data['signature'],
        'policy': policy_data['policy'],
        'x-oss-object-acl': policy_data['x_oss_object_acl'],
        'x-oss-forbid-overwrite': policy_data['x_oss_forbid_overwrite'],
        'key': key,
        'success_action_status': '200'
    }
    
    for field_name, field_value in fields.items():
        form_data.append(f'--{boundary}')
        form_data.append(f'Content-Disposition: form-data; name="{field_name}"')
        form_data.append('')
        form_data.append(str(field_value))
    
    # 添加文件数据
    form_data.append(f'--{boundary}')
    form_data.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"')
    form_data.append('Content-Type: application/octet-stream')
    form_data.append('')
    
    # 将文本部分转换为字节
    text_part = '\r\n'.join(form_data) + '\r\n'
    text_bytes = text_part.encode('utf-8')
    
    # 构建完整的请求体
    end_boundary = f'\r\n--{boundary}--\r\n'.encode('utf-8')
    body = text_bytes + file_data + end_boundary
    
    # 使用优化后的头部（移除Content-Length，避免-104错误）
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    }
    
    # 上传前进行垃圾回收
    gc.collect()
    
    response = requests.post(policy_data['upload_host'], data=body, headers=headers)
    
    # 上传后进行垃圾回收
    gc.collect()
    
    if response.status_code != 200:
        raise Exception(f"Failed to upload file: {response.text}")
    
    return f"oss://{key}"

def upload_image_to_dashscope(api_key, image_path, model_name):
    """
    上传到DashScope临时存储
    
    参数:
        api_key (str): DashScope API密钥
        image_path (str): 文件路径
    
    返回:
        str: 临时URL，格式为 oss://bucket/path/filename
    
    异常:
        Exception: 当上传失败时抛出异常
    """
    try:
        # 检查文件是否存在
        with open(image_path, 'rb') as f:
            pass  # 只是检查文件是否可读
    
        
        # 1. 获取上传凭证
        policy_data = get_upload_policy(api_key, model_name)
        
        # 2. 上传文件到OSS
        oss_url = upload_file_to_oss(policy_data, image_path)
        
        return oss_url
        
    except Exception as e:
        raise Exception(f"上传失败: {str(e)}")