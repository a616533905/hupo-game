#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nanobot Web Bridge - 支持多种AI提供者的配置化桥接"""

import json
import os
import sys
import http.client
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import threading
import time
import mimetypes
from urllib.parse import urlparse, parse_qs

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

CONFIG_FILE = "config.json"
WEB_ROOT = os.path.dirname(os.path.abspath(__file__))

LOGIN_PAGE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>访问验证 - 琥珀猫冒险</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:20px}
.logo{font-size:80px;margin-bottom:20px}
h1{font-size:28px;margin-bottom:10px;background:linear-gradient(135deg,#ff6b9d,#c44569);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.desc{color:rgba(255,255,255,0.7);font-size:14px;margin-bottom:30px;max-width:400px;line-height:1.6}
input{width:280px;padding:14px 20px;border-radius:12px;border:2px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;font-size:16px;text-align:center;outline:none}
input:focus{border-color:#ff6b9d}
input::placeholder{color:rgba(255,255,255,0.4)}
.btn{width:280px;padding:14px;margin-top:15px;border:none;border-radius:12px;background:linear-gradient(135deg,#ff6b9d,#c44569);color:#fff;font-size:16px;cursor:pointer}
.btn:hover{transform:scale(1.02)}
.error{color:#ff6b6b;font-size:13px;margin-top:15px;display:none}
</style>
</head>
<body>
<div class="logo">🔐</div>
<h1>访问验证</h1>
<p class="desc">此游戏需要访问令牌<br>请输入有效的访问令牌以继续</p>
<input type="password" id="tokenInput" placeholder="输入访问令牌" autocomplete="off">
<button class="btn" onclick="verifyToken()">验证并进入 🔑</button>
<p class="error" id="errorMsg">令牌无效，请重试</p>
<script>
function verifyToken(){
    var input=document.getElementById('tokenInput').value.trim();
    if(input){
        document.cookie='hupo_token='+input+';path=/;max-age=86400';
        window.location.href='index.html?token='+encodeURIComponent(input);
    }else{
        document.getElementById('errorMsg').style.display='block';
    }
}
document.getElementById('tokenInput').addEventListener('keypress',function(e){
    if(e.key==='Enter')verifyToken();
});
</script>
</body>
</html>'''

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_config():
    """获取配置，支持环境变量覆盖"""
    config = load_config()

    env_overrides = {
        ('minimax', 'api_key'): os.environ.get('MINIMAX_API_KEY', ''),
        ('minimax', 'group_id'): os.environ.get('MINIMAX_GROUP_ID', ''),
    }

    for (provider, key), value in env_overrides.items():
        if value:
            if provider not in config:
                config[provider] = {}
            config[provider][key] = value

    return config

config = get_config()

PORT = int(os.environ.get('API_PORT')) if os.environ.get('API_PORT') else config.get('port', 80)

def get_provider_config(provider_name):
    """获取指定提供者的配置"""
    return config.get(provider_name, {})

conversation_history = []

def call_minimax_api(message, model_override=None):
    """调用 MiniMax API"""
    global conversation_history

    provider_config = get_provider_config('minimax')
    api_key = provider_config.get('api_key', '')
    group_id = provider_config.get('group_id', '')
    model = model_override or provider_config.get('model', 'MiniMax-M2.7')

    if not api_key or not group_id:
        return "错误: MiniMax API未配置（请在config.json中设置api_key和group_id）"

    conversation_history.append({"role": "user", "content": message})

    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    data = {
        "model": model,
        "messages": conversation_history,
        "temperature": 0.7
    }

    conn = http.client.HTTPSConnection("api.minimax.chat")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    path = f"/v1/text/chatcompletion_v2?GroupId={group_id}"

    try:
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()
        result = response.read().decode('utf-8')
        result_json = json.loads(result)

        if "choices" in result_json and len(result_json["choices"]) > 0:
            assistant_message = result_json["choices"][0]["message"]["content"]
            conversation_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        else:
            return f"API错误: {result_json.get('base_resp', {}).get('status_msg', '未知错误')}"
    except Exception as e:
        return f"请求失败: {str(e)}"
    finally:
        conn.close()

def call_minimax_tts(text, voice_id="female-tianmei"):
    """调用 MiniMax TTS API 进行语音合成"""
    import base64
    provider_config = get_provider_config('minimax')
    api_key = provider_config.get('api_key', '')
    group_id = provider_config.get('group_id', '')

    if not api_key or not group_id:
        return None, "错误: MiniMax API未配置"

    conn = http.client.HTTPSConnection("api.minimaxi.com")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "text": text,
        "model": "speech-2.8-hd",
        "voice_setting": {
            "voice_id": voice_id,
            "speed": 1.0
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 2
        }
    }

    path = f"/v1/t2a_v2?GroupId={group_id}"

    try:
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()
        result = response.read().decode('utf-8')
        result_json = json.loads(result)
        
        if "audio" in result_json:
            audio_data = base64.b64decode(result_json["audio"])
            return audio_data, None
        elif "data" in result_json and "audio" in result_json["data"]:
            audio_data = base64.b64decode(result_json["data"]["audio"])
            return audio_data, None
        elif "file_id" in result_json:
            return None, f"异步任务已创建，file_id: {result_json['file_id']}，需要使用File API下载"
        else:
            error_msg = result_json.get('base_resp', {}).get('status_msg', result_json.get('error', '未知错误'))
            if 'token plan not support' in error_msg:
                return None, "当前Token套餐不支持语音功能，请升级到Plus或更高套餐"
            return None, f"TTS错误: {error_msg}"
    except Exception as e:
        return None, f"TTS请求失败: {str(e)}"
    finally:
        conn.close()

def call_minimax_asr(audio_data, audio_format="mp3"):
    """调用 MiniMax ASR API 进行语音识别"""
    provider_config = get_provider_config('minimax')
    api_key = provider_config.get('api_key', '')
    group_id = provider_config.get('group_id', '')

    if not api_key or not group_id:
        return None, "错误: MiniMax API未配置"

    conn = http.client.HTTPSConnection("api.minimax.chat")

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    path = f"/v1/voice_transcribe?GroupId={group_id}"

    try:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body_parts = []
        
        body_parts.append(f"--{boundary}\r\n")
        body_parts.append(f'Content-Disposition: form-data; name="file"; filename="audio.{audio_format}"\r\n')
        body_parts.append(f"Content-Type: audio/{audio_format}\r\n\r\n")
        
        body = "".join(body_parts).encode('utf-8') + audio_data + f"\r\n--{boundary}--\r\n".encode('utf-8')
        
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        
        conn.request("POST", path, body, headers)
        response = conn.getresponse()
        result = response.read().decode('utf-8')
        result_json = json.loads(result)
        
        if "text" in result_json:
            return result_json["text"], None
        else:
            return None, f"ASR错误: {result_json.get('base_resp', {}).get('status_msg', '未知错误')}"
    except Exception as e:
        return None, f"ASR请求失败: {str(e)}"
    finally:
        conn.close()

OLLAMA_STARTED = False

def check_ollama_running(host="localhost", port=11434):
    """检查 Ollama 服务是否运行"""
    try:
        conn = http.client.HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/")
        response = conn.getresponse()
        conn.close()
        return True
    except:
        return False

def start_ollama_service():
    """启动 Ollama 服务"""
    global OLLAMA_STARTED
    if OLLAMA_STARTED:
        return True
    
    try:
        if sys.platform == 'win32':
            subprocess.Popen(['ollama', 'serve'], 
                           creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(['ollama', 'serve'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        for _ in range(10):
            time.sleep(1)
            if check_ollama_running():
                OLLAMA_STARTED = True
                print("Ollama 服务已启动")
                return True
        return False
    except Exception as e:
        print(f"启动 Ollama 服务失败: {e}")
        return False

def ensure_ollama_model(model, host="localhost", port=11434):
    """确保模型已加载到内存"""
    try:
        conn = http.client.HTTPConnection(host, port, timeout=30)
        data = json.dumps({"model": model, "keep_alive": "10m"})
        conn.request("POST", "/api/generate", data, {"Content-Type": "application/json"})
        response = conn.getresponse()
        result = response.read().decode('utf-8')
        conn.close()
        return True
    except Exception as e:
        print(f"加载模型失败: {e}")
        return False

def call_ollama_api(message, model_override=None, host_override=None):
    """调用 Ollama API (本地) - 兼容 OpenAI 格式和原生 Ollama 格式"""
    global conversation_history

    provider_config = get_provider_config('ollama')
    model = model_override or provider_config.get('model', 'llama2')
    api_base = host_override or provider_config.get('api_base', 'http://localhost:11434/v1')

    from urllib.parse import urlparse
    parsed = urlparse(api_base)
    host = parsed.netloc
    port = 11434
    if ':' in host:
        parts = host.split(':')
        host = parts[0]
        port = int(parts[1])

    if not check_ollama_running(host, port):
        print("Ollama 服务未运行，正在启动...")
        if not start_ollama_service():
            return "Ollama错误: 无法启动 Ollama 服务，请手动运行 'ollama serve'"
    
    ensure_ollama_model(model, host, port)

    conversation_history.append({"role": "user", "content": message})

    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    use_https = parsed.scheme == 'https'
    conn_class = http.client.HTTPSConnection if use_https else http.client.HTTPConnection

    data_openai = {
        "model": model,
        "messages": conversation_history,
        "temperature": 0.7
    }
    data_native = {
        "model": model,
        "messages": conversation_history,
        "stream": False
    }

    headers = {"Content-Type": "application/json"}

    def try_openai_api():
        conn = conn_class(host, port)
        try:
            conn.request("POST", "/v1/chat/completions", json.dumps(data_openai), headers)
            response = conn.getresponse()
            result = response.read().decode('utf-8')
            result_json = json.loads(result)
            if "choices" in result_json and len(result_json["choices"]) > 0:
                return result_json["choices"][0]["message"]["content"]
            return None
        except Exception as e:
            print(f"OpenAI API 错误: {e}")
            return None
        finally:
            conn.close()

    def try_native_api():
        conn = conn_class(host, port)
        try:
            conn.request("POST", "/api/chat", json.dumps(data_native), headers)
            response = conn.getresponse()
            result = response.read().decode('utf-8')
            result_json = json.loads(result)
            if "message" in result_json:
                return result_json["message"].get("content", "")
            return None
        except Exception as e:
            print(f"Native API 错误: {e}")
            return None
        finally:
            conn.close()

    try:
        result = try_openai_api()
        if result:
            conversation_history.append({"role": "assistant", "content": result})
            return result

        result = try_native_api()
        if result:
            conversation_history.append({"role": "assistant", "content": result})
            return result

        return "Ollama错误: 无法获取响应，请检查模型是否已下载 (ollama pull " + model + ")"
    except Exception as e:
        return f"Ollama请求失败: {str(e)}"

def call_openrouter_api(message, model_override=None):
    """调用 OpenRouter API"""
    global conversation_history

    provider_config = get_provider_config('openrouter')
    api_key = provider_config.get('api_key', '')
    model = model_override or provider_config.get('model', 'openrouter/auto')

    if not api_key:
        return "错误: OpenRouter API未配置（请在config.json中设置api_key）"

    conversation_history.append({"role": "user", "content": message})

    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    data = {
        "model": model,
        "messages": conversation_history,
        "temperature": 0.7
    }

    conn = http.client.HTTPSConnection("openrouter.ai")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:80",
        "X-Title": "Nanobot Game"
    }

    try:
        conn.request("POST", "/api/v1/chat/completions", json.dumps(data), headers)
        response = conn.getresponse()
        result = response.read().decode('utf-8')
        result_json = json.loads(result)

        if "choices" in result_json and len(result_json["choices"]) > 0:
            assistant_message = result_json["choices"][0]["message"]["content"]
            conversation_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        else:
            return f"OpenRouter错误: {result_json.get('error', {}).get('message', '未知错误')}"
    except Exception as e:
        return f"OpenRouter请求失败: {str(e)}"
    finally:
        conn.close()

def call_api(message, provider=None, model=None, ollama_host=None):
    """根据配置调用对应的API"""
    active_provider = provider or config.get('active_provider', 'minimax')

    if active_provider == 'ollama':
        return call_ollama_api(message, model, ollama_host)
    elif active_provider == 'openrouter':
        return call_openrouter_api(message, model)
    elif active_provider == 'minimax':
        return call_minimax_api(message, model)
    else:
        return call_minimax_api(message, model)

class NanobotHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def check_token(self):
        token_required = config.get('token_required', 'no')
        if token_required != 'yes':
            return True
        
        expected_token = config.get('access_token', '')
        if not expected_token:
            return True
        
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        url_token = query.get('token', [None])[0]
        
        if url_token and url_token == expected_token:
            return True
        
        cookie_header = self.headers.get('Cookie', '')
        cookies = {}
        for cookie in cookie_header.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies[key.strip()] = value.strip()
        
        cookie_token = cookies.get('hupo_token', '')
        if cookie_token and cookie_token == expected_token:
            return True
        
        return False

    def send_login_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(LOGIN_PAGE.encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            if self.path == "/chat":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    data = json.loads(body)
                    token = data.get("token", "")

                    token_required = config.get('token_required', 'no')
                    if token_required == 'yes':
                        expected_token = config.get('access_token', '')
                        if not expected_token or token != expected_token:
                            self.send_response(401)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            self.wfile.write(b'{"error": "Unauthorized: invalid token"}')
                            return

                    message = data.get("message", "")
                    provider = data.get("provider", None)
                    model = data.get("model", None)
                    ollama_host = data.get("ollama_host", None)

                    if not message:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'{"error": "No message provided"}')
                        return

                    response = call_api(message, provider, model, ollama_host)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"response": response}, ensure_ascii=False).encode('utf-8'))

                except Exception as e:
                    self.send_response(500)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            elif self.path == "/tts":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    data = json.loads(body)
                    text = data.get("text", "")
                    voice_id = data.get("voice_id", "female-tianmei")

                    if not text:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(b'{"error": "No text provided"}')
                        return

                    audio_data, error = call_minimax_tts(text, voice_id)

                    if error:
                        self.send_response(500)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": error}, ensure_ascii=False).encode('utf-8'))
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header("Content-Length", len(audio_data))
                    self.end_headers()
                    self.wfile.write(audio_data)

                except Exception as e:
                    self.send_response(500)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            elif self.path == "/asr":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                try:
                    audio_data, error = call_minimax_asr(body, "webm")

                    if error:
                        self.send_response(500)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": error}, ensure_ascii=False).encode('utf-8'))
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"text": audio_data}, ensure_ascii=False).encode('utf-8'))

                except Exception as e:
                    self.send_response(500)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

    def do_GET(self):
        try:
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
                return
            
            if self.path == "/model":
                active_provider = config.get('active_provider', 'minimax')
                provider_config = get_provider_config(active_provider)
                model = provider_config.get('model', 'unknown')

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"model": f"{active_provider}/{model}"}, ensure_ascii=False).encode('utf-8'))
                return

            if not self.check_token():
                self.send_login_page()
                return

            parsed = urlparse(self.path)
            path = parsed.path
            
            if path == '/':
                path = '/index.html'
            
            file_path = os.path.normpath(os.path.join(WEB_ROOT, path.lstrip('/')))
            
            if not file_path.startswith(WEB_ROOT):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'Forbidden')
                return
            
            if os.path.isfile(file_path):
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = 'application/octet-stream'
                
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", len(content))
                    self.end_headers()
                    self.wfile.write(content)
                except BrokenPipeError:
                    pass
                except ConnectionResetError:
                    pass
                except Exception as e:
                    try:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(f'Internal Server Error: {str(e)}'.encode('utf-8'))
                    except:
                        pass
            else:
                try:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not Found')
                except:
                    pass
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

if __name__ == "__main__":
    print(f"AI Bridge starting on port {PORT}...")
    print(f"Config file: {CONFIG_FILE}")
    print(f"API endpoint: POST http://localhost:{PORT}/chat")
    print(f"Active provider: {config.get('active_provider', 'minimax')}")
    print()
    print("Available providers:")
    for provider in ['minimax', 'ollama', 'openrouter']:
        provider_config = get_provider_config(provider)
        api_key = provider_config.get('api_key', '')
        if api_key and api_key != 'EMPTY':
            print(f"  - {provider}: ✓ configured")
        elif provider == 'ollama':
            api_base = provider_config.get('api_base', '')
            print(f"  - {provider}: ✓ local ({api_base})")
        else:
            print(f"  - {provider}: ✗ not configured")
    print()
    print("To switch provider, change 'active_provider' in config.json")
    print("Environment variables can override config (MINIMAX_API_KEY, MINIMAX_GROUP_ID)")

    server = HTTPServer(("0.0.0.0", PORT), NanobotHandler)
    server.serve_forever()