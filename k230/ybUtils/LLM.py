try:
    import YbRequests as requests
except Exception:    
    import ybUtils.YbRequests as requests

import time
import json  # 添加json模块导入

class LLM:
    """大语言模型API封装类"""

    # 模型类型
    MODEL_TYPE_SPARK = "spark"
    MODEL_TYPE_OPENROUTER = "openrouter"

    # Spark可用模型列表
    SPARK_MODELS = {
        "LITE": "lite",
        "PRO": "generalv3",
        "PRO_128K": "pro-128k",
        "MAX": "generalv3.5",
        "MAX_32K": "max-32k",
        "ULTRA_4": "4.0Ultra"
    }

    # API端点
    API_URLS = {
        MODEL_TYPE_SPARK: "https://spark-api-open.xf-yun.com/v1/chat/completions",
        MODEL_TYPE_OPENROUTER: "https://openrouter.ai/api/v1/chat/completions"
    }

    def __init__(self, api_key, model_type=MODEL_TYPE_SPARK):
        """
        初始化大语言模型API客户端

        参数:
            api_key: API密钥
            model_type: 模型类型("spark"/"openrouter")
        """
        print(f"[DEBUG] 初始化LLM - API密钥: {api_key[:5]}..., 模型类型: {model_type}")
        self.api_key = api_key
        self.model_type = model_type
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        print(f"[DEBUG] 初始化完成，请求头: {self.headers}")

    def _prepare_request_data(self, model, messages, **kwargs):
        """准备请求数据"""
        print(f"[DEBUG] 准备请求数据 - 模型: {model}")
        print(f"[DEBUG] 消息内容: {messages}")
        
        # 构建基本请求数据
        data = {
            "model": model,
            "messages": messages
        }

        # 添加可选参数
        optional_params = [
            "user", "temperature", "top_p", "top_k", "stream",
            "max_tokens", "presence_penalty", "frequency_penalty",
            "tools", "response_format", "tool_calls_switch", "tool_choice"
        ]

        for param in optional_params:
            if param in kwargs and kwargs[param] is not None:
                data[param] = kwargs[param]
                print(f"[DEBUG] 添加参数 {param}: {kwargs[param]}")

        print(f"[DEBUG] 完整请求数据: {data}")
        return data

    def _parse_non_stream_response(self, response):
        
        print(f"[DEBUG] 解析非流式响应 - 状态码: {response.status_code}")
        if response.status_code != 200:
            try:
                error_data = response.json
                print(f"[DEBUG] 错误响应数据: {error_data}")
                if "error" in error_data:
                    return {
                        "error": error_data["error"]
                    }
            except:
                error_msg = f"HTTP错误: {response.status_code}, {response.text}"
                print(f"[DEBUG] 解析错误响应失败: {error_msg}")
                return {
                    "error": {
                        "message": error_msg,
                        "type": "http_error",
                        "code": response.status_code
                    }
                }
        try:
            result = response.json
            # print(f"[DEBUG] 成功解析响应: {result}")
            return result
        except Exception as e:
            error_msg = f"解析响应失败: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            return {"error": {"message": error_msg, "type": "parse_error"}}

    def _process_stream_response(self, response, callback=None):
        return
        # """处理流式响应"""
        # print(f"[DEBUG] 处理流式响应 - 状态码: {response.status_code}")
        # if response.status_code != 200:
        #     error_msg = f"HTTP错误: {response.status_code}, {response.text}"
        #     print(f"[DEBUG] 流式响应错误: {error_msg}")
        #     if callback:
        #         callback({"error": error_msg})
        #         return None
        #     else:
        #         return {"error": error_msg}

        # full_content = ""
        # content = response.text
        # print(f"[DEBUG] 原始流式响应内容: {content[:100]}...")
        # lines = content.split('\n')
        # print(f"[DEBUG] 响应行数: {len(lines)}")

        # for line in lines:
        #     line = line.strip()
        #     if not line:
        #         continue

        #     print(f"[DEBUG] 处理行: {line[:50]}...")
        #     if line.startswith('data:'):
        #         data = line[5:].strip()

        #         if data == '[DONE]':
        #             print("[DEBUG] 流式响应结束")
        #             if callback:
        #                 callback({"done": True})
        #             break

        #         try:
        #             try:
        #                 print(f"[DEBUG] 尝试解析JSON数据")
        #                 chunk_data = json.loads(data)
        #             except:
        #                 print(f"[DEBUG] 使用requests.json解析")
        #                 chunk_data = requests.json.loads(data)

        #             print(f"[DEBUG] 解析的数据块: {chunk_data}")
        #             if callback:
        #                 print(f"[DEBUG] 调用回调函数")
        #                 callback(chunk_data)
        #                 time.sleep(0.5)
        #             else:
        #                 if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
        #                     delta = chunk_data["choices"][0].get("delta", {})
        #                     if "content" in delta:
        #                         content_piece = delta["content"]
        #                         print(f"[DEBUG] 内容片段: {content_piece}")
        #                         full_content += content_piece
        #         except Exception as e:
        #             error_msg = f"解析错误: {str(e)}, 原始数据: {data}"
        #             print(f"[DEBUG] 解析出错: {error_msg}")
        #             if callback:
        #                 callback({"error": error_msg})
        #             else:
        #                 return {"error": error_msg}

        # print(f"[DEBUG] 流式处理完成，完整内容长度: {len(full_content)}")
        # if callback is None:
        #     return {"content": full_content}


    def chat(self, messages, model=None, stream=False, stream_callback=None, **kwargs):
        print(f"[DEBUG] 开始聊天请求 - 模型: {model}, 流式: {stream}")
        # 设置默认model
        if model is None:
            print("[DEBUG] 错误: 未指定模型")
            return {"error": {"message": "未指定模型 No model settigs", "type": "model_error"}}
        data = self._prepare_request_data(model, messages, stream=stream, **kwargs)
        try:
            print(f"[DEBUG] 发送请求到: {self.API_URLS[self.model_type]}")
            response = requests.post(
                url=self.API_URLS[self.model_type],
                headers=self.headers,
                json_data=data
            )
            print(f"[DEBUG] 收到响应 - 状态码: {response.status_code}")

            if stream:
                print("[DEBUG] 处理流式响应")
                return self._process_stream_response(response, stream_callback)
            else:
                print(f"[DEBUG] 尝试解析JSON响应")
                print("[DEBUG] 处理非流式响应")
                return self._parse_non_stream_response(response)
            
        except Exception as e:
            error_msg = f"请求错误: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            return {"error": {"message": error_msg, "type": "request_error"}}

# 使用示例
def simple_chat_example(api_key, prompt, model_type=LLM.MODEL_TYPE_SPARK, model=None, stream=False, chat_history=None):
    """
    简单的聊天示例,支持对话历史
    
    参数:
        api_key (str): API密钥
        prompt (str): 用户输入的提示语
        model_type (str): 模型类型，默认为Spark
        model (str): 具体使用的模型
        stream (bool): 是否使用流式响应
        chat_history (list): 对话历史记录,格式为[(content, is_user), ...]
    """
    print(f"[DEBUG] 开始聊天示例 - 模型类型: {model_type}, 模型: {model}")
    
    # 构建消息列表
    messages = []
    
    # 如果有对话历史,添加到消息列表中
    if chat_history:
        total_length = 0
        max_length = 300  # 限制总长度
        
        for content, is_user in chat_history:
            
            msg_length = len(content)
            if total_length + msg_length > max_length:
                break
                
            messages.append({
                "role": "user" if is_user else "assistant",
                "content": content
            })
            total_length += msg_length
    
    # 添加当前用户输入
    messages.append({"role": "user", "content": prompt})
    
    try:
        # 创建LLM实例并发送请求
        llm = LLM(api_key, model_type)
        response = llm.chat(messages, model=model, max_tokens=512)
        # 处理响应
        if "error" in response:
            return f"ERROR: {response['error']}"
        
        elif "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0].get("message", {}).get("content", "")
            
            # 如果回复过长,进行截断
            if len(content) >= 124:
                content = f"{content[:124]} ..... "
                
            print(f"回复: {content}")
            
            # 显示token使用情况
            if "usage" in response:
                usage = response["usage"]
                print("\n使用的token: {} (输入: {}, 输出: {})".format(
                    usage.get('total_tokens', 0),
                    usage.get('prompt_tokens', 0),
                    usage.get('completion_tokens', 0)
                ))
            
            return content
            
        else:
            return "error: 无效的响应格式"
            
    except Exception as e:
        print(f"[ERROR] 发生错误: {str(e)}")
        return "sorry, some error happened"
