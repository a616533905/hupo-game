#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nanobot Web Bridge - 支持多种AI提供者的配置化桥接"""

import json
import os
import sys
import http.client
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import threading
import time
import mimetypes
import logging
import signal
from datetime import datetime
from urllib.parse import urlparse, parse_qs

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, f'bridge_{datetime.now().strftime("%Y%m%d")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

DEBUG_LOG_FILE = os.path.join(LOG_DIR, f'api_debug_{datetime.now().strftime("%Y%m%d")}.log')
debug_logger = logging.getLogger('api_debug')
debug_logger.setLevel(logging.DEBUG)
debug_logger.propagate = False
debug_handler = logging.FileHandler(DEBUG_LOG_FILE, encoding='utf-8')
debug_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
debug_logger.addHandler(debug_handler)

SENSITIVE_PATTERNS = [
    'api_key', 'apikey', 'access_token', 'token', 'password', 'secret', 
    'credential', 'auth', 'private_key', 'session_id'
]

def sanitize_log_message(message):
    if not isinstance(message, str):
        message = str(message)
    
    import re
    
    for pattern in SENSITIVE_PATTERNS:
        regex = rf'({pattern}["\s:=]+)(["\']?)([^"\'\s,}}\]]+)(["\']?)'
        message = re.sub(regex, r'\1\2***REDACTED***\4', message, flags=re.IGNORECASE)
    
    message = re.sub(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer ***REDACTED***', message)
    message = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***EMAIL***', message)
    
    return message

class SanitizingLogger:
    def __init__(self, logger):
        self.logger = logger
    
    def info(self, msg, *args, **kwargs):
        self.logger.info(sanitize_log_message(msg), *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(sanitize_log_message(msg), *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self.logger.error(sanitize_log_message(msg), *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(sanitize_log_message(msg), *args, **kwargs)
    
    def __getattr__(self, name):
        return getattr(self.logger, name)

logger = SanitizingLogger(logger)

CONFIG_FILE = "config.json"
WAF_RULES_FILE = "waf_rules.json"
WAF_RULES_EXAMPLE = "waf_rules.example.json"
ERROR_CODES_FILE = "error_codes.json"
WEB_ROOT = os.path.dirname(os.path.abspath(__file__))

def load_waf_rules():
    waf_path = os.path.join(WEB_ROOT, WAF_RULES_FILE)
    waf_example_path = os.path.join(WEB_ROOT, WAF_RULES_EXAMPLE)
    
    if os.path.exists(waf_path):
        try:
            with open(waf_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"WAF规则加载失败: {e}")
    
    if os.path.exists(waf_example_path):
        try:
            with open(waf_example_path, 'r', encoding='utf-8') as f:
                logger.info(f"使用默认WAF规则: {WAF_RULES_EXAMPLE}")
                return json.load(f)
        except Exception as e:
            logger.warning(f"默认WAF规则加载失败: {e}")
    
    return None

def load_error_codes():
    error_path = os.path.join(WEB_ROOT, ERROR_CODES_FILE)
    
    if os.path.exists(error_path):
        try:
            with open(error_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"错误码配置加载失败: {e}")
    
    return None

WAF_RULES = load_waf_rules()
ERROR_CODES = load_error_codes()

import psutil
import threading

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 100
RATE_LIMIT_CHAT_MAX = 30
RATE_LIMIT_CHAT_WINDOW = 60
MAX_CONTENT_LENGTH = 10 * 1024 * 1024
HTTP_TIMEOUT = 30
rate_limit_data = {}
chat_rate_limit_data = {}
rate_limit_lock = threading.Lock()

WAF_BLACKLIST_DURATION = WAF_RULES.get('blacklist_duration', 3600) if WAF_RULES else 3600
WAF_BLACKLIST = {}
WAF_BLACKLIST_LOCK = threading.Lock()

LOGIN_FAIL_TRACKER = {}
LOGIN_FAIL_LOCK = threading.Lock()
LOGIN_FAIL_TEMP_BAN = 86400
LOGIN_FAIL_PERM_THRESHOLD = 10

def record_login_failure(client_ip, fail_type="web"):
    with LOGIN_FAIL_LOCK:
        if client_ip not in LOGIN_FAIL_TRACKER:
            LOGIN_FAIL_TRACKER[client_ip] = {'count': 0, 'first_fail': time.time(), 'type': fail_type}
        
        LOGIN_FAIL_TRACKER[client_ip]['count'] += 1
        LOGIN_FAIL_TRACKER[client_ip]['last_fail'] = time.time()
        count = LOGIN_FAIL_TRACKER[client_ip]['count']
        
        logger.warning(f"[LOGIN_FAIL] IP={client_ip}, Type={fail_type}, Count={count}")
        
        if count >= LOGIN_FAIL_PERM_THRESHOLD:
            with WAF_BLACKLIST_LOCK:
                WAF_BLACKLIST[client_ip] = time.time() + (LOGIN_FAIL_TEMP_BAN * 365)
            logger.warning(f"[LOGIN_BAN] IP={client_ip} 永久封禁 - 登录失败累计{count}次")
            return 'permanent'
        elif count >= 5:
            with WAF_BLACKLIST_LOCK:
                WAF_BLACKLIST[client_ip] = time.time() + LOGIN_FAIL_TEMP_BAN
            logger.warning(f"[LOGIN_BAN] IP={client_ip} 临时封禁1天 - 登录失败累计{count}次")
            return 'temp'
        
        return 'recorded'

def check_login_banned(client_ip):
    with WAF_BLACKLIST_LOCK:
        if client_ip in WAF_BLACKLIST:
            if time.time() < WAF_BLACKLIST[client_ip]:
                return True
            else:
                del WAF_BLACKLIST[client_ip]
    return False

def waf_check_request(client_ip, path, headers):
    with WAF_BLACKLIST_LOCK:
        if client_ip in WAF_BLACKLIST:
            if time.time() < WAF_BLACKLIST[client_ip]:
                return True, "IP in blacklist"
            else:
                del WAF_BLACKLIST[client_ip]
    
    path_lower = path.lower()
    attack_patterns = WAF_RULES.get('attack_patterns', []) if WAF_RULES else []
    for item in attack_patterns:
        pattern = item['pattern'] if isinstance(item, dict) else item
        if pattern.lower() in path_lower:
            with WAF_BLACKLIST_LOCK:
                WAF_BLACKLIST[client_ip] = time.time() + WAF_BLACKLIST_DURATION
            category = item.get('category', 'unknown') if isinstance(item, dict) else 'unknown'
            logger.warning(f"[WAF] 检测到攻击: IP={client_ip}, Category={category}, Pattern={pattern}, Path={path[:100]}")
            return True, f"Attack pattern detected: {pattern}"
    
    user_agent = headers.get('User-Agent', '').lower()
    scanner_signatures = WAF_RULES.get('scanner_signatures', []) if WAF_RULES else []
    for item in scanner_signatures:
        pattern = item['pattern'] if isinstance(item, dict) else item
        if pattern.lower() in user_agent:
            with WAF_BLACKLIST_LOCK:
                WAF_BLACKLIST[client_ip] = time.time() + WAF_BLACKLIST_DURATION
            logger.warning(f"[WAF] 检测到扫描器: IP={client_ip}, Agent={user_agent[:50]}")
            return True, f"Scanner detected: {pattern}"
    
    return False, None

def waf_is_blacklisted(client_ip):
    with WAF_BLACKLIST_LOCK:
        if client_ip in WAF_BLACKLIST:
            if time.time() < WAF_BLACKLIST[client_ip]:
                return True
            else:
                del WAF_BLACKLIST[client_ip]
    return False

MAX_CONCURRENT_AI_REQUESTS = 10
ai_request_semaphore = threading.Semaphore(MAX_CONCURRENT_AI_REQUESTS)
ai_request_queue = []
ai_queue_lock = threading.Lock()

HTTP_POOL_SIZE = 20
http_pool_lock = threading.Lock()
http_pool_minimax = []
http_pool_minimax_tts = []
http_pool_openrouter = []
http_pool_last_cleanup = time.time()

def is_connection_valid(conn):
    if conn is None:
        return False
    try:
        if hasattr(conn, 'sock') and conn.sock is None:
            return False
        return True
    except Exception as e:
        logger.debug(f"Connection check failed: {str(e)}")
        return False

def cleanup_connection_pools():
    global http_pool_last_cleanup
    with http_pool_lock:
        for pool in [http_pool_minimax, http_pool_minimax_tts, http_pool_openrouter]:
            valid = []
            for conn in pool:
                if conn is not None and is_connection_valid(conn):
                    valid.append(conn)
                else:
                    try:
                        if conn:
                            conn.close()
                    except Exception as e:
                        logger.debug(f"Connection close failed: {str(e)}")
            pool.clear()
            pool.extend(valid)
        http_pool_last_cleanup = time.time()

def get_http_connection(host, pool_list, timeout=HTTP_TIMEOUT):
    global http_pool_last_cleanup
    if time.time() - http_pool_last_cleanup > 300:
        cleanup_connection_pools()
    
    with http_pool_lock:
        valid_connections = [c for c in pool_list if is_connection_valid(c)]
        pool_list.clear()
        pool_list.extend(valid_connections)
        
        for i, conn in enumerate(pool_list):
            if conn and conn.host == host:
                pool_list[i] = None
                return conn
        
        return http.client.HTTPSConnection(host, timeout=timeout)

def return_http_connection(conn, pool_list):
    if conn:
        with http_pool_lock:
            if len(pool_list) < HTTP_POOL_SIZE:
                try:
                    pool_list.append(conn)
                except Exception as e:
                    logger.debug(f"Failed to return connection to pool: {str(e)}")
                    try:
                        conn.close()
                    except Exception as e2:
                        logger.debug(f"Connection close failed: {str(e2)}")
            else:
                try:
                    conn.close()
                except Exception as e:
                    logger.debug(f"Connection close failed: {str(e)}")

prometheus_metrics = {
    'requests_total': 0,
    'requests_success': 0,
    'requests_error': 0,
    'chat_requests': 0,
    'tts_requests': 0,
    'start_time': time.time()
}
metrics_lock = threading.Lock()

def increment_metric(key, value=1):
    with metrics_lock:
        prometheus_metrics[key] += value

def check_rate_limit(client_ip):
    """检查请求频率限制"""
    now = time.time()
    with rate_limit_lock:
        if client_ip not in rate_limit_data:
            rate_limit_data[client_ip] = []
        
        rate_limit_data[client_ip] = [t for t in rate_limit_data[client_ip] if now - t < RATE_LIMIT_WINDOW]
        
        if len(rate_limit_data[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        
        rate_limit_data[client_ip].append(now)
        return True

def check_chat_rate_limit(client_ip):
    """检查 /chat 接口的请求频率限制（更严格）"""
    now = time.time()
    with rate_limit_lock:
        if client_ip not in chat_rate_limit_data:
            chat_rate_limit_data[client_ip] = []
        
        chat_rate_limit_data[client_ip] = [t for t in chat_rate_limit_data[client_ip] if now - t < RATE_LIMIT_CHAT_WINDOW]
        
        if len(chat_rate_limit_data[client_ip]) >= RATE_LIMIT_CHAT_MAX:
            return False
        
        chat_rate_limit_data[client_ip].append(now)
        return True

def cleanup_rate_limit_data():
    """定期清理过期的频率限制数据"""
    while True:
        time.sleep(300)
        now = time.time()
        with rate_limit_lock:
            ips_to_remove = []
            for ip in rate_limit_data:
                rate_limit_data[ip] = [t for t in rate_limit_data[ip] if now - t < RATE_LIMIT_WINDOW]
                if not rate_limit_data[ip]:
                    ips_to_remove.append(ip)
            for ip in ips_to_remove:
                del rate_limit_data[ip]
            
            chat_ips_to_remove = []
            for ip in chat_rate_limit_data:
                chat_rate_limit_data[ip] = [t for t in chat_rate_limit_data[ip] if now - t < RATE_LIMIT_CHAT_WINDOW]
                if not chat_rate_limit_data[ip]:
                    chat_ips_to_remove.append(ip)
            for ip in chat_ips_to_remove:
                del chat_rate_limit_data[ip]
            
            if ips_to_remove or chat_ips_to_remove:
                logger.debug(f"清理了 {len(ips_to_remove)} 个通用频率限制记录, {len(chat_ips_to_remove)} 个聊天频率限制记录")

cleanup_thread = threading.Thread(target=cleanup_rate_limit_data, daemon=True)
cleanup_thread.start()

def get_system_stats():
    """获取系统状态"""
    with metrics_lock:
        uptime = time.time() - prometheus_metrics['start_time']
    return {
        'cpu_percent': psutil.cpu_percent(interval=0.1),
        'memory_percent': psutil.virtual_memory().percent,
        'memory_used': psutil.virtual_memory().used,
        'memory_total': psutil.virtual_memory().total,
        'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent,
        'uptime': uptime
    }

def format_prometheus_metrics():
    """格式化Prometheus指标"""
    stats = get_system_stats()
    with metrics_lock:
        metrics = f"""# HELP hupo_requests_total Total number of requests
# TYPE hupo_requests_total counter
hupo_requests_total {prometheus_metrics['requests_total']}

# HELP hupo_requests_success Total successful requests
# TYPE hupo_requests_success counter
hupo_requests_success {prometheus_metrics['requests_success']}

# HELP hupo_requests_error Total failed requests
# TYPE hupo_requests_error counter
hupo_requests_error {prometheus_metrics['requests_error']}

# HELP hupo_chat_requests Total chat API requests
# TYPE hupo_chat_requests counter
hupo_chat_requests {prometheus_metrics['chat_requests']}

# HELP hupo_tts_requests Total TTS API requests
# TYPE hupo_tts_requests counter
hupo_tts_requests {prometheus_metrics['tts_requests']}

# HELP hupo_cpu_percent CPU usage percentage
# TYPE hupo_cpu_percent gauge
hupo_cpu_percent {stats['cpu_percent']}

# HELP hupo_memory_percent Memory usage percentage
# TYPE hupo_memory_percent gauge
hupo_memory_percent {stats['memory_percent']}

# HELP hupo_uptime_seconds Server uptime in seconds
# TYPE hupo_uptime_seconds gauge
hupo_uptime_seconds {stats['uptime']}
"""
    return metrics

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
if(window.location.search.indexOf('error=1')!==-1){
    document.getElementById('errorMsg').style.display='block';
}
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

REQUIRED_CONFIG_FIELDS = {
    'active_provider': str,
}

PROVIDER_CONFIG_FIELDS = {
    'minimax': ['api_key', 'group_id'],
    'openrouter': ['api_key'],
    'ollama': ['api_base'],
    'baidu': ['api_key', 'secret_key'],
}

def validate_config(cfg):
    """验证配置文件格式和必需字段"""
    errors = []
    warnings = []
    
    for field, expected_type in REQUIRED_CONFIG_FIELDS.items():
        if field not in cfg:
            errors.append(f"缺少必需字段: {field}")
        elif not isinstance(cfg[field], expected_type) and cfg[field] is not None:
            if expected_type == int and isinstance(cfg[field], str) and cfg[field].isdigit():
                pass
            else:
                errors.append(f"字段 '{field}' 类型错误: 期望 {expected_type.__name__}, 实际 {type(cfg[field]).__name__}")
    
    active_provider = cfg.get('active_provider', 'minimax')
    if active_provider in PROVIDER_CONFIG_FIELDS:
        provider_cfg = cfg.get(active_provider, {})
        for field in PROVIDER_CONFIG_FIELDS[active_provider]:
            if field not in provider_cfg or not provider_cfg[field]:
                if active_provider == 'ollama' and field == 'api_base':
                    warnings.append(f"提供者 '{active_provider}' 缺少配置: {field} (将使用默认值)")
                elif active_provider != 'ollama':
                    warnings.append(f"提供者 '{active_provider}' 缺少配置: {field}")
    
    if 'server' in cfg:
        server_cfg = cfg['server']
        if 'http_port' in server_cfg and not isinstance(server_cfg['http_port'], int):
            errors.append("server.http_port 必须是整数")
        if 'https_port' in server_cfg and not isinstance(server_cfg['https_port'], int):
            errors.append("server.https_port 必须是整数")
        if 'voice_port' in server_cfg and not isinstance(server_cfg['voice_port'], int):
            errors.append("server.voice_port 必须是整数")
    else:
        warnings.append("缺少 server 配置，将使用默认端口")
    
    return errors, warnings

def load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"配置文件不存在: {CONFIG_FILE}")
        return {}
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        logger.info(f"配置文件加载成功: {CONFIG_FILE}")
        
        if 'environments' in cfg:
            runtime_mode = cfg.get('runtime_mode', 'local')
            env_cfg = cfg.get('environments', {}).get(runtime_mode, {})
            for key in ['server', 'access_token', 'token_required', 'active_provider', 'audit']:
                if key in env_cfg and key not in cfg:
                    cfg[key] = env_cfg[key]
            logger.info(f"使用环境配置: {runtime_mode}")
        
        errors, warnings = validate_config(cfg)
        
        for warning in warnings:
            logger.warning(f"配置警告: {warning}")
        
        if errors:
            for error in errors:
                logger.error(f"配置错误: {error}")
            logger.warning("配置验证失败，使用默认值")
        else:
            logger.info("配置验证通过")
        
        return cfg
    except json.JSONDecodeError as e:
        logger.error(f"配置文件JSON格式错误: {e}")
        return {}
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
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
            logger.info(f"从环境变量覆盖配置: {provider}.{key}")

    return config

config = get_config()

server_config = config.get('server', {})

HTTPS_DOMAIN = os.environ.get('HTTPS_DOMAIN', config.get('https_domain', ''))
SSL_CERT_FILE = os.environ.get('SSL_CERT_FILE', server_config.get('ssl_cert_file', ''))
SSL_KEY_FILE = os.environ.get('SSL_KEY_FILE', server_config.get('ssl_key_file', ''))
USE_HTTPS_ENV = os.environ.get('USE_HTTPS', '')
if USE_HTTPS_ENV.lower() in ('1', 'true', 'yes'):
    USE_HTTPS = bool(SSL_CERT_FILE and SSL_KEY_FILE)
elif USE_HTTPS_ENV.lower() in ('0', 'false', 'no'):
    USE_HTTPS = False
else:
    USE_HTTPS = bool(SSL_CERT_FILE and SSL_KEY_FILE)

if USE_HTTPS:
    PORT = int(os.environ.get('API_PORT')) if os.environ.get('API_PORT') else server_config.get('https_port', 443)
else:
    PORT = int(os.environ.get('API_PORT')) if os.environ.get('API_PORT') else server_config.get('http_port', 80)

def get_provider_config(provider_name):
    """获取指定提供者的配置"""
    return config.get(provider_name, {})

conversation_history = []
conversation_lock = threading.Lock()
MAX_HISTORY_LENGTH = 100

def cleanup_conversation_history():
    global conversation_history
    with conversation_lock:
        if len(conversation_history) > MAX_HISTORY_LENGTH:
            conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]
            logger.info(f"清理对话历史，保留最近{MAX_HISTORY_LENGTH}条")

def get_minimax_error_msg(status_code):
    if ERROR_CODES and 'minimax' in ERROR_CODES:
        error_map = ERROR_CODES['minimax']
        key = str(status_code) if isinstance(status_code, str) else status_code
        if str(key) in error_map:
            return error_map[str(key)]
        if key in error_map:
            return error_map[key]
    default_map = {
        1000: "服务暂时繁忙，请稍后重试",
        1001: "请求超时，请稍后重试",
        1002: "请求频率超限，请稍后重试",
        1004: "API未授权，请检查API密钥是否正确",
        1008: "账户余额不足，请及时充值",
    }
    if status_code in default_map:
        return default_map[status_code]
    if isinstance(status_code, int) and 1000 <= status_code <= 9999:
        return f"服务暂时异常，请稍后重试"
    return None

def call_minimax_chat(message, model_override=None):
    """调用 MiniMax API (带并发控制和连接池)"""
    global conversation_history
    cleanup_conversation_history()
    
    provider_config = get_provider_config('minimax')
    api_key = provider_config.get('api_key', '')
    group_id = provider_config.get('group_id', '')
    model = model_override or provider_config.get('model', 'MiniMax-M2.7')

    if not api_key or not group_id:
        logger.error("MiniMax API未配置")
        return "错误: MiniMax API未配置（请在config.json中设置api_key和group_id）"

    logger.info(f"调用MiniMax API, model={model}, message_length={len(message)}")
    debug_logger.debug(f"[MiniMax] 请求内容: {message[:500]}{'...' if len(message) > 500 else ''}")
    with conversation_lock:
        conversation_history.append({"role": "user", "content": message})

        if len(conversation_history) > MAX_HISTORY_LENGTH:
            conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]

        data = {
            "model": model,
            "messages": conversation_history.copy(),
            "temperature": 0.7
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    path = f"/v1/text/chatcompletion_v2?GroupId={group_id}"

    acquired = ai_request_semaphore.acquire(blocking=True, timeout=30)
    if not acquired:
        logger.warning("AI 请求队列已满，请稍后重试")
        return "系统繁忙，请稍后重试"

    max_retries = 2
    for retry in range(max_retries + 1):
        conn = None
        conn_returned = False
        try:
            conn = get_http_connection("api.minimax.chat", http_pool_minimax)
            conn.request("POST", path, json.dumps(data), headers)
            response = conn.getresponse()
            status_code = response.status
            result = response.read().decode('utf-8')
            result_json = json.loads(result)

            if "choices" in result_json and len(result_json["choices"]) > 0:
                assistant_message = result_json["choices"][0]["message"]["content"]
                with conversation_lock:
                    conversation_history.append({"role": "assistant", "content": assistant_message})
                logger.info(f"MiniMax API调用成功, response_length={len(assistant_message)}")
                debug_logger.debug(f"[MiniMax] 返回内容: {assistant_message[:500]}{'...' if len(assistant_message) > 500 else ''}")
                return_http_connection(conn, http_pool_minimax)
                conn_returned = True
                return assistant_message
            else:
                base_resp = result_json.get('base_resp', {})
                status_code_resp = base_resp.get('status_code', 'N/A')
                status_msg = base_resp.get('status_msg', '未知错误')
                error_msg = result_json.get('error', {}).get('message', '')
                logger.error(f"MiniMax API错误: HTTP {status_code}, status_code={status_code_resp}, status_msg={status_msg}, error={error_msg}, response={result[:500]}")
                user_msg = get_minimax_error_msg(status_code_resp)
                if user_msg:
                    return user_msg
                return f"MiniMax API服务暂时异常，请稍后重试"
        except json.JSONDecodeError as e:
            logger.error(f"MiniMax API响应解析失败: HTTP {status_code}, response={result[:500] if 'result' in dir() else 'N/A'}")
            return f"响应解析失败: {str(e)}"
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError) as e:
            if retry < max_retries:
                logger.warning(f"MiniMax连接断开，第{retry+1}次重试...")
                time.sleep(0.5)
                continue
            logger.error(f"MiniMax API请求失败(重试后): {str(e)}")
            return "网络连接不稳定，请稍后重试"
        except Exception as e:
            logger.error(f"MiniMax API请求失败: {str(e)}")
            return f"请求失败: {str(e)}"
        finally:
            ai_request_semaphore.release()
            if conn and not conn_returned:
                try:
                    conn.close()
                except Exception as e:
                    logger.debug(f"Connection close failed: {str(e)}")
    return "网络连接不稳定，请稍后重试"

def call_minimax_tts(text, voice_id="female-tianmei"):
    """调用 MiniMax TTS API 进行语音合成"""
    import base64
    provider_config = get_provider_config('minimax')
    api_key = provider_config.get('api_key', '')
    group_id = provider_config.get('group_id', '')

    if not api_key or not group_id:
        return None, "错误: MiniMax API未配置"

    conn = http.client.HTTPSConnection("api.minimaxi.com", timeout=HTTP_TIMEOUT)

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
        status_code = response.status
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
            base_resp = result_json.get('base_resp', {})
            status_code_resp = base_resp.get('status_code', 'N/A')
            error_msg = base_resp.get('status_msg', result_json.get('error', '未知错误'))
            logger.error(f"MiniMax TTS错误: HTTP {status_code}, status_code={status_code_resp}, status_msg={error_msg}, response={result[:500]}")
            if 'token plan not support' in error_msg:
                return None, "当前Token套餐不支持语音功能，请升级到Plus或更高套餐"
            user_msg = get_minimax_error_msg(status_code_resp)
            if user_msg:
                return None, user_msg
            return None, "语音合成失败，请稍后重试"
    except json.JSONDecodeError as e:
        logger.error(f"MiniMax TTS响应解析失败: HTTP {status_code}, response={result[:500] if 'result' in dir() else 'N/A'}")
        return None, f"TTS响应解析失败: {str(e)}"
    except Exception as e:
        logger.error(f"MiniMax TTS请求失败: {str(e)}")
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

    conn = http.client.HTTPSConnection("api.minimax.chat", timeout=HTTP_TIMEOUT)

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
        status_code = response.status
        result = response.read().decode('utf-8')
        result_json = json.loads(result)
        
        if "text" in result_json:
            debug_logger.debug(f"[MiniMax ASR] 识别结果: {result_json['text']}")
            return result_json["text"], None
        else:
            base_resp = result_json.get('base_resp', {})
            status_code_resp = base_resp.get('status_code', 'N/A')
            error_msg = base_resp.get('status_msg', '未知错误')
            logger.error(f"MiniMax ASR错误: HTTP {status_code}, status_code={status_code_resp}, status_msg={error_msg}, response={result[:500]}")
            user_msg = get_minimax_error_msg(status_code_resp)
            if user_msg:
                return None, user_msg
            return None, "语音识别失败，请稍后重试"
    except json.JSONDecodeError as e:
        logger.error(f"MiniMax ASR响应解析失败: HTTP {status_code}, response={result[:500] if 'result' in dir() else 'N/A'}")
        return None, f"ASR响应解析失败: {str(e)}"
    except Exception as e:
        logger.error(f"MiniMax ASR请求失败: {str(e)}")
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
    except Exception as e:
        logger.debug(f"Ollama service check failed: {str(e)}")
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
                logger.info("Ollama 服务已启动")
                return True
        return False
    except Exception as e:
        logger.error(f"启动 Ollama 服务失败: {e}")
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
        logger.error(f"加载模型失败: {e}")
        return False

def call_ollama_api(message, model_override=None, host_override=None):
    """调用 Ollama API (本地) - 兼容 OpenAI 格式和原生 Ollama 格式"""
    global conversation_history
    cleanup_conversation_history()

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

    logger.info(f"调用Ollama API, model={model}, host={host}:{port}")

    if not check_ollama_running(host, port):
        logger.warning("Ollama 服务未运行，正在启动...")
        if not start_ollama_service():
            logger.error("无法启动 Ollama 服务")
            return "Ollama错误: 无法启动 Ollama 服务，请手动运行 'ollama serve'"
    
    ensure_ollama_model(model, host, port)

    with conversation_lock:
        conversation_history.append({"role": "user", "content": message})

        if len(conversation_history) > MAX_HISTORY_LENGTH:
            conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]

        use_https = parsed.scheme == 'https'
        conn_class = http.client.HTTPSConnection if use_https else http.client.HTTPConnection

        data_openai = {
            "model": model,
            "messages": conversation_history.copy(),
            "temperature": 0.7
        }
        data_native = {
            "model": model,
            "messages": conversation_history.copy(),
            "stream": False
        }

    headers = {"Content-Type": "application/json"}

    def try_openai_api():
        conn = conn_class(host, port, timeout=HTTP_TIMEOUT)
        try:
            conn.request("POST", "/v1/chat/completions", json.dumps(data_openai), headers)
            response = conn.getresponse()
            result = response.read().decode('utf-8')
            result_json = json.loads(result)
            if "choices" in result_json and len(result_json["choices"]) > 0:
                return result_json["choices"][0]["message"]["content"]
            logger.warning(f"OpenAI API 无有效响应: {result[:200]}")
            return None
        except Exception as e:
            logger.warning(f"OpenAI API 错误: {e}")
            return None
        finally:
            conn.close()

    def try_native_api():
        conn = conn_class(host, port, timeout=HTTP_TIMEOUT)
        try:
            conn.request("POST", "/api/chat", json.dumps(data_native), headers)
            response = conn.getresponse()
            result = response.read().decode('utf-8')
            result_json = json.loads(result)
            if "message" in result_json:
                return result_json["message"].get("content", "")
            logger.warning(f"Native API 无有效响应: {result[:200]}")
            return None
        except Exception as e:
            logger.warning(f"Native API 错误: {e}")
            return None
        finally:
            conn.close()

    try:
        result = try_openai_api()
        if result:
            with conversation_lock:
                conversation_history.append({"role": "assistant", "content": result})
            logger.info(f"Ollama API调用成功(OpenAI格式), response_length={len(result)}")
            return result

        result = try_native_api()
        if result:
            with conversation_lock:
                conversation_history.append({"role": "assistant", "content": result})
            logger.info(f"Ollama API调用成功(Native格式), response_length={len(result)}")
            return result

        logger.error(f"Ollama无法获取响应, model={model}")
        return "Ollama错误: 无法获取响应，请检查模型是否已下载 (ollama pull " + model + ")"
    except Exception as e:
        logger.error(f"Ollama请求失败: {str(e)}")
        return f"Ollama请求失败: {str(e)}"

def get_openrouter_error_msg(status_code):
    if ERROR_CODES and 'openrouter' in ERROR_CODES:
        error_map = ERROR_CODES['openrouter']
        key = str(status_code) if isinstance(status_code, str) else status_code
        if str(key) in error_map:
            return error_map[str(key)]
        if key in error_map:
            return error_map[key]
    default_map = {
        400: "请求参数错误，请检查输入内容",
        401: "API密钥无效，请检查密钥是否正确",
        402: "账户余额不足，请充值后重试",
        403: "输入内容被标记为违规，无法处理",
        408: "请求超时，请稍后重试",
        429: "请求频率超限，请稍后重试",
        502: "AI模型服务暂不可用，请稍后重试",
        503: "当前无可用模型提供商，请稍后重试",
    }
    if status_code in default_map:
        return default_map[status_code]
    return None

def call_openrouter_api(message, model_override=None):
    """调用 OpenRouter API (带并发控制和连接池)"""
    global conversation_history
    cleanup_conversation_history()

    provider_config = get_provider_config('openrouter')
    api_key = provider_config.get('api_key', '')
    config_model = provider_config.get('model', 'openrouter/auto')
    if model_override and '/' in model_override and not model_override.startswith('MiniMax'):
        model = model_override
    else:
        model = config_model

    if not api_key:
        return "错误: OpenRouter API未配置（请在config.json中设置api_key）"

    logger.info(f"调用OpenRouter API, model={model}, message_length={len(message)}")
    debug_logger.debug(f"[OpenRouter] 请求内容: {message[:500]}{'...' if len(message) > 500 else ''}")
    with conversation_lock:
        conversation_history.append({"role": "user", "content": message})

        if len(conversation_history) > MAX_HISTORY_LENGTH:
            conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]

        data = {
            "model": model,
            "messages": conversation_history.copy(),
            "temperature": 0.7
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://localhost",
        "X-Title": "HupoGame"
    }

    acquired = ai_request_semaphore.acquire(blocking=True, timeout=30)
    if not acquired:
        logger.warning("AI 请求队列已满，请稍后重试")
        return "系统繁忙，请稍后重试"

    max_retries = 2
    for retry in range(max_retries + 1):
        conn = None
        conn_returned = False
        try:
            conn = get_http_connection("openrouter.ai", http_pool_openrouter)
            conn.request("POST", "/api/v1/chat/completions", json.dumps(data), headers)
            response = conn.getresponse()
            status_code = response.status
            result = response.read().decode('utf-8')
            result_json = json.loads(result)

            if "choices" in result_json and len(result_json["choices"]) > 0:
                assistant_message = result_json["choices"][0]["message"]["content"]
                with conversation_lock:
                    conversation_history.append({"role": "assistant", "content": assistant_message})
                logger.info(f"OpenRouter API调用成功, response_length={len(assistant_message)}")
                debug_logger.debug(f"[OpenRouter] 返回内容: {assistant_message[:500]}{'...' if len(assistant_message) > 500 else ''}")
                return_http_connection(conn, http_pool_openrouter)
                conn_returned = True
                return assistant_message
            else:
                error_info = result_json.get('error', {})
                error_msg = error_info.get('message', '未知错误')
                error_code = error_info.get('code', 'N/A')
                error_type = error_info.get('type', 'N/A')
                logger.error(f"OpenRouter API错误: HTTP {status_code}, code={error_code}, type={error_type}, message={error_msg}, response={result[:500]}")
                user_msg = get_openrouter_error_msg(status_code)
                if user_msg:
                    return user_msg
                return "AI服务暂时异常，请稍后重试"
        except json.JSONDecodeError as e:
            logger.error(f"OpenRouter API响应解析失败: HTTP {status_code}, response={result[:500] if 'result' in dir() else 'N/A'}")
            return f"响应解析失败: {str(e)}"
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError) as e:
            if retry < max_retries:
                logger.warning(f"OpenRouter连接断开，第{retry+1}次重试...")
                time.sleep(0.5)
                continue
            logger.error(f"OpenRouter请求失败(重试后): {str(e)}")
            return "网络连接不稳定，请稍后重试"
        except Exception as e:
            logger.error(f"OpenRouter请求失败: {str(e)}")
            return f"OpenRouter请求失败: {str(e)}"
        finally:
            ai_request_semaphore.release()
            if conn and not conn_returned:
                try:
                    conn.close()
                except Exception as e:
                    logger.debug(f"Connection close failed: {str(e)}")
    return "网络连接不稳定，请稍后重试"

GAME_STATE = {
    'cat': {
        'name': '琥珀',
        'level': 1,
        'hp': 100,
        'hpMax': 100,
        'mp': 50,
        'mpMax': 50,
        'hunger': 80,
        'happiness': 80,
        'exp': 0,
        'expMax': 100,
        'coins': 500,
        'gems': 10,
        'attack': 10,
        'defense': 5,
        'speed': 10,
        'mood': 'happy'
    },
    'fatigue': 0,
    'intimacyLevel': 1,
    'intimacyPoints': 0
}

def execute_game_command_api(command, params=None):
    """执行游戏命令并返回结果"""
    if params is None:
        params = {}
    
    result = {"success": True, "command": command, "message": "", "state": {}}
    cat = GAME_STATE['cat']
    
    if command == "feed":
        if cat['hunger'] >= 100:
            result["message"] = "琥珀已经很饱了！"
        else:
            cat['hunger'] = min(100, cat['hunger'] + 20)
            cat['happiness'] = min(100, cat['happiness'] + 5)
            result["message"] = f"🍖 喂食成功！琥珀饱腹度+20，当前：{cat['hunger']}/100"
    
    elif command == "play":
        if GAME_STATE['fatigue'] >= 100:
            result["message"] = "琥珀太累了，需要休息！"
        else:
            cat['happiness'] = min(100, cat['happiness'] + 15)
            cat['hunger'] = max(0, cat['hunger'] - 10)
            GAME_STATE['fatigue'] = min(100, GAME_STATE['fatigue'] + 10)
            result["message"] = f"🎾 玩耍成功！琥珀快乐度+15，疲劳+10"
    
    elif command == "pet":
        cat['happiness'] = min(100, cat['happiness'] + 10)
        GAME_STATE['intimacyPoints'] += 2
        result["message"] = f"✋ 抚摸成功！琥珀快乐度+10，亲密度+2"
    
    elif command == "rest":
        GAME_STATE['fatigue'] = max(0, GAME_STATE['fatigue'] - 30)
        cat['hp'] = min(cat['hpMax'], cat['hp'] + 20)
        result["message"] = f"😴 休息成功！疲劳-30，HP+20"
    
    elif command == "heal":
        cat['hp'] = cat['hpMax']
        result["message"] = f"🏥 治疗成功！HP已恢复满"
    
    elif command == "status":
        result["message"] = f"""📊 当前状态：
等级: Lv.{cat['level']}
HP: {cat['hp']}/{cat['hpMax']}
MP: {cat['mp']}/{cat['mpMax']}
饱腹: {cat['hunger']}/100
快乐: {cat['happiness']}/100
金币: {cat['coins']}
宝石: {cat['gems']}
攻击: {cat['attack']} | 防御: {cat['defense']} | 速度: {cat['speed']}
疲劳: {GAME_STATE['fatigue']}%
亲密度: Lv.{GAME_STATE['intimacyLevel']} ({GAME_STATE['intimacyPoints']}点)"""
    
    elif command == "shop":
        result["message"] = "🏪 商店已打开！可用物品：\n- 面包 (50金币) 恢复30饱腹\n- 药水 (100金币) 恢复50HP\n- 宝石箱 (500金币) 获得10宝石"
    
    elif command == "tower":
        result["message"] = "🏰 无尽之塔已打开！当前第1层，剩余挑战次数：3"
    
    elif command == "arena":
        result["message"] = "⚔️ 竞技场已打开！当前段位：青铜"
    
    elif command == "adventure":
        result["message"] = "⛏️ 冒险地图已打开！可用区域：\n- 新手草原 (Lv.1+)\n- 幽暗森林 (Lv.5+)\n- 火焰山脉 (Lv.10+)"
    
    elif command == "sign":
        cat['coins'] += 100
        cat['gems'] += 5
        result["message"] = "🎁 签到成功！获得100金币+5宝石"
    
    elif command == "wheel":
        import random
        rewards = ["100金币", "50金币", "10宝石", "5宝石", "药水x1", "面包x2"]
        reward = random.choice(rewards)
        result["message"] = f"🎰 转盘结果：{reward}！"
    
    elif command == "save":
        result["message"] = "💾 游戏已保存！"
    
    elif command == "battle":
        enemy = params.get("enemy", "史莱姆")
        cat['exp'] += 30
        cat['coins'] += 50
        if cat['exp'] >= cat['expMax']:
            cat['level'] += 1
            cat['exp'] = 0
            cat['hpMax'] += 10
            cat['attack'] += 2
            cat['defense'] += 1
            result["message"] = f"⚔️ 战斗胜利！击败了{enemy}！升级到Lv.{cat['level']}！"
        else:
            result["message"] = f"⚔️ 战斗胜利！击败了{enemy}！获得30经验+50金币"
    
    elif command == "buy":
        item = params.get("item", "面包")
        count = params.get("count", 1)
        prices = {"面包": 50, "药水": 100, "宝石箱": 500}
        price = prices.get(item, 50) * count
        if cat['coins'] >= price:
            cat['coins'] -= price
            result["message"] = f"🛒 购买成功！{item}x{count}，花费{price}金币"
        else:
            result["message"] = f"❌ 金币不足！需要{price}金币"
    
    elif command == "use":
        item = params.get("item", "面包")
        if item == "面包":
            cat['hunger'] = min(100, cat['hunger'] + 30)
            result["message"] = f"🍞 使用{item}！饱腹+30"
        elif item == "药水":
            cat['hp'] = min(cat['hpMax'], cat['hp'] + 50)
            result["message"] = f"💊 使用{item}！HP+50"
        else:
            result["message"] = f"📦 使用{item}！"
    
    elif command == "equip":
        item = params.get("item", "铁剑")
        cat['attack'] += 5
        result["message"] = f"⚔️ 装备了{item}！攻击+5"
    
    elif command == "learn_skill":
        skill = params.get("skill", "火球术")
        result["message"] = f"⚡ 学会了技能：{skill}！"
    
    elif command == "chat":
        message = params.get("message", "")
        result["message"] = f'💬 琥珀听到了你说："{message}"\n琥珀：喵~'
    
    else:
        result["success"] = False
        result["message"] = f"❌ 未知命令：{command}"
    
    result["state"] = {
        "cat": cat,
        "fatigue": GAME_STATE['fatigue'],
        "intimacyLevel": GAME_STATE['intimacyLevel'],
        "intimacyPoints": GAME_STATE['intimacyPoints']
    }
    
    return result

def call_api(message, provider=None, model=None, ollama_host=None):
    """根据配置调用对应的API"""
    active_provider = provider or config.get('active_provider', 'minimax')

    if active_provider == 'ollama':
        return call_ollama_api(message, model, ollama_host)
    elif active_provider == 'openrouter':
        return call_openrouter_api(message, model)
    elif active_provider == 'minimax':
        return call_minimax_chat(message, model)
    else:
        return call_minimax_chat(message, model)

class HTTPtoHTTPSRedirectHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if HTTPS_DOMAIN:
            redirect_url = f"https://{HTTPS_DOMAIN}{self.path}"
        else:
            redirect_url = f"https://{self.headers.get('Host', 'localhost')}{self.path}"
        self.send_response(301)
        self.send_header("Location", redirect_url)
        self.send_header("Connection", "close")
        self.end_headers()

    do_POST = do_GET
    do_HEAD = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET

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
        client_ip = self.client_address[0]
        increment_metric('requests_total')
        
        if waf_is_blacklisted(client_ip):
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Forbidden')
            return
        
        blocked, reason = waf_check_request(client_ip, self.path, self.headers)
        if blocked:
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Forbidden')
            return
        
        if not check_rate_limit(client_ip):
            logger.warning(f"[{client_ip}] 请求频率超限")
            increment_metric('requests_error')
            self.send_response(429)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Too Many Requests", "message": "请求频率超限，请稍后再试"}).encode('utf-8'))
            return
        
        try:
            path_only = self.path.split('?')[0]
            if path_only == "/":
                increment_metric('chat_requests')
                
                if not check_chat_rate_limit(client_ip):
                    logger.warning(f"[{client_ip}] POST /chat - 请求频率超限")
                    increment_metric('requests_error')
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Too Many Requests", "message": "聊天请求过于频繁，请稍后再试"}).encode('utf-8'))
                    return
                
                content_length = int(self.headers.get("Content-Length", 0))
                
                if content_length == 0:
                    logger.warning(f"[{client_ip}] POST /chat - 空请求体")
                    increment_metric('requests_error')
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Bad Request", "message": "请求体不能为空"}).encode('utf-8'))
                    return
                
                if content_length > MAX_CONTENT_LENGTH:
                    logger.warning(f"[{client_ip}] POST / - 请求体过大: {content_length}")
                    self.send_response(413)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"error": "Request entity too large"}')
                    return
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    data = json.loads(body)
                    token = data.get("token", "")

                    token_required = config.get('token_required', 'no')
                    if token_required == 'yes':
                        expected_token = config.get('access_token', '')
                        if not expected_token or token != expected_token:
                            logger.warning(f"[{client_ip}] POST /chat - 认证失败")
                            ban_status = record_login_failure(client_ip, "web_token")
                            increment_metric('requests_error')
                            self.send_response(401)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            error_msg = "Unauthorized: invalid token"
                            if ban_status == 'permanent':
                                error_msg = "Unauthorized: IP has been permanently banned"
                            elif ban_status == 'temp':
                                error_msg = "Unauthorized: IP has been temporarily banned for 24 hours"
                            self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))
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

                    logger.info(f"[{client_ip}] POST /chat - provider={provider or 'default'}, msg_len={len(message)}")
                    response = call_api(message, provider, model, ollama_host)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"response": response}, ensure_ascii=False).encode('utf-8'))
                    increment_metric('requests_success')

                except Exception as e:
                    logger.error(f"[{client_ip}] POST /chat 错误: {str(e)}")
                    increment_metric('requests_error')
                    self.send_response(500)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            elif self.path == "/tts":
                increment_metric('tts_requests')
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > MAX_CONTENT_LENGTH:
                    logger.warning(f"[{client_ip}] POST /tts - 请求体过大: {content_length}")
                    self.send_response(413)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"error": "Request entity too large"}')
                    return
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    data = json.loads(body)
                    
                    token = data.get("token", "")
                    token_required = config.get('token_required', 'no')
                    if token_required == 'yes':
                        expected_token = config.get('access_token', '')
                        if not expected_token or token != expected_token:
                            logger.warning(f"[{client_ip}] POST /tts - 认证失败")
                            increment_metric('requests_error')
                            self.send_response(401)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            self.wfile.write(b'{"error": "Unauthorized: invalid token"}')
                            return
                    
                    text = data.get("text", "")
                    voice_id = data.get("voice_id", "female-tianmei")

                    if not text:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(b'{"error": "No text provided"}')
                        return

                    logger.info(f"[{client_ip}] POST /tts - voice={voice_id}, text_len={len(text)}")
                    audio_data, error = call_minimax_tts(text, voice_id)

                    if error:
                        logger.error(f"[{client_ip}] POST /tts 错误: {error}")
                        increment_metric('requests_error')
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
                    increment_metric('requests_success')

                except Exception as e:
                    logger.error(f"[{client_ip}] POST /tts 异常: {str(e)}")
                    self.send_response(500)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            elif self.path == "/asr":
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > MAX_CONTENT_LENGTH:
                    logger.warning(f"[{client_ip}] POST /asr - 请求体过大: {content_length}")
                    self.send_response(413)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'{"error": "Request entity too large"}')
                    return
                body = self.rfile.read(content_length)
                
                token_required = config.get('token_required', 'no')
                if token_required == 'yes':
                    expected_token = config.get('access_token', '')
                    auth_header = self.headers.get('Authorization', '')
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]
                    else:
                        token = ''
                    if not expected_token or token != expected_token:
                        logger.warning(f"[{client_ip}] POST /asr - 认证失败")
                        self.send_response(401)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(b'{"error": "Unauthorized: invalid token"}')
                        return

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
            elif self.path == "/api/game":
                debug_enabled = config.get('debug', {}).get('api_enabled', False)
                if not debug_enabled:
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Debug mode disabled. Set debug.api_enabled=true in config.json"}).encode('utf-8'))
                    return
                
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                
                try:
                    data = json.loads(body)
                    command = data.get("command", "")
                    params = data.get("params", {})
                    
                    if not command:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "No command provided"}).encode('utf-8'))
                        return
                    
                    logger.info(f"[{client_ip}] POST /api/game - command={command}, params={params}")
                    
                    result = execute_game_command_api(command, params)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
                    
                except Exception as e:
                    logger.error(f"[{client_ip}] POST /api/game 错误: {str(e)}")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            elif self.path == "/api/commands":
                commands = [
                    {"command": "feed", "desc": "喂食", "params": {}},
                    {"command": "play", "desc": "玩耍", "params": {}},
                    {"command": "pet", "desc": "抚摸", "params": {}},
                    {"command": "rest", "desc": "休息", "params": {}},
                    {"command": "heal", "desc": "治疗", "params": {}},
                    {"command": "status", "desc": "查看状态", "params": {}},
                    {"command": "shop", "desc": "打开商店", "params": {}},
                    {"command": "tower", "desc": "打开塔楼", "params": {}},
                    {"command": "arena", "desc": "打开竞技场", "params": {}},
                    {"command": "adventure", "desc": "打开冒险", "params": {}},
                    {"command": "sign", "desc": "签到", "params": {}},
                    {"command": "wheel", "desc": "转盘", "params": {}},
                    {"command": "save", "desc": "保存游戏", "params": {}},
                    {"command": "battle", "desc": "战斗", "params": {"enemy": "敌人名称(可选)"}},
                    {"command": "buy", "desc": "购买物品", "params": {"item": "物品ID", "count": "数量"}},
                    {"command": "use", "desc": "使用物品", "params": {"item": "物品ID"}},
                    {"command": "equip", "desc": "装备物品", "params": {"item": "装备ID"}},
                    {"command": "learn_skill", "desc": "学习技能", "params": {"skill": "技能ID"}},
                    {"command": "chat", "desc": "聊天", "params": {"message": "消息内容"}}
                ]
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"commands": commands}, ensure_ascii=False, indent=2).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

    def do_GET(self):
        client_ip = self.client_address[0]
        increment_metric('requests_total')
        
        if waf_is_blacklisted(client_ip):
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Forbidden')
            return
        
        blocked, reason = waf_check_request(client_ip, self.path, self.headers)
        if blocked:
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Forbidden')
            return
        
        if HTTPS_DOMAIN and not USE_HTTPS:
            forwarded_proto = self.headers.get('X-Forwarded-Proto', '')
            if forwarded_proto != 'https':
                https_url = f"https://{HTTPS_DOMAIN}{self.path}"
                logger.info(f"[{client_ip}] HTTP -> HTTPS 重定向: {https_url}")
                self.send_response(301)
                self.send_header("Location", https_url)
                self.end_headers()
                return
        
        try:
            if self.path == "/health":
                if client_ip not in ('127.0.0.1', '::1'):
                    self.send_response(404)
                    self.end_headers()
                    return
                stats = get_system_stats()
                with metrics_lock:
                    requests_total = prometheus_metrics['requests_total']
                health_data = {
                    "status": "ok",
                    "uptime": round(stats['uptime'], 2),
                    "cpu_percent": stats['cpu_percent'],
                    "memory_percent": stats['memory_percent'],
                    "disk_percent": stats['disk_percent'],
                    "requests_total": requests_total
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(health_data).encode('utf-8'))
                increment_metric('requests_success')
                return
            
            if self.path == "/metrics":
                if client_ip not in ('127.0.0.1', '::1'):
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.end_headers()
                self.wfile.write(format_prometheus_metrics().encode('utf-8'))
                increment_metric('requests_success')
                return
            
            if self.path == "/model":
                if client_ip not in ('127.0.0.1', '::1'):
                    self.send_response(404)
                    self.end_headers()
                    return
                active_provider = config.get('active_provider', 'minimax')
                provider_config = get_provider_config(active_provider)
                model = provider_config.get('model', 'unknown')

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"model": f"{active_provider}/{model}"}, ensure_ascii=False).encode('utf-8'))
                return

            if self.path == "/debug/api":
                debug_enabled = config.get('debug', {}).get('api_enabled', False)
                if not debug_enabled:
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Debug mode disabled"}).encode('utf-8'))
                    return
                debug_data = {
                    "config": {
                        "active_provider": config.get('active_provider', 'minimax'),
                        "token_required": config.get('token_required', 'no'),
                        "debug_enabled": debug_enabled
                    },
                    "providers": {}
                }
                for provider in ['minimax', 'openrouter', 'ollama']:
                    provider_cfg = get_provider_config(provider)
                    if provider_cfg:
                        debug_data["providers"][provider] = {
                            "model": provider_cfg.get('model', 'unknown'),
                            "api_base": provider_cfg.get('api_base', 'unknown') if provider != 'minimax' else 'api.minimax.chat'
                        }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(debug_data, ensure_ascii=False, indent=2).encode('utf-8'))
                return

            if self.path == "/debug/toggle":
                if client_ip not in ('127.0.0.1', '::1'):
                    self.send_response(403)
                    self.end_headers()
                    return
                current = config.get('debug', {}).get('api_enabled', False)
                if 'debug' not in config:
                    config['debug'] = {}
                config['debug']['api_enabled'] = not current
                try:
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"保存配置失败: {e}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"debug_enabled": config['debug']['api_enabled']}).encode('utf-8'))
                return

            if self.path == "/debug/logs":
                if client_ip not in ('127.0.0.1', '::1'):
                    self.send_response(403)
                    self.end_headers()
                    return
                log_lines = []
                try:
                    with open(DEBUG_LOG_FILE, 'r', encoding='utf-8') as f:
                        log_lines = f.readlines()[-100]
                except:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(''.join(log_lines).encode('utf-8'))
                return

            if self.path == "/config.json":
                file_path = os.path.join(WEB_ROOT, 'config.json')
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                        safe_cfg = {
                            'active_provider': cfg.get('active_provider', 'minimax'),
                            'token_required': cfg.get('token_required', 'no'),
                            'server': cfg.get('server', {}),
                            'ollama': {'api_base': cfg.get('ollama', {}).get('api_base', 'http://localhost:11434/v1')},
                        }
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps(safe_cfg, ensure_ascii=False).encode('utf-8'))
                    except Exception as e:
                        logger.error(f"读取 config.json 失败：{str(e)}")
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
                return

            if not self.check_token():
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                has_token = query.get('token', [None])[0] is not None
                cookie_header = self.headers.get('Cookie', '')
                has_cookie = 'hupo_token=' in cookie_header
                has_error = query.get('error', [None])[0] is not None
                if (has_token or has_cookie) and not has_error:
                    logger.warning(f"[{client_ip}] GET {self.path} - Token验证失败")
                    self.send_response(302)
                    self.send_header("Location", "/?error=1")
                    self.end_headers()
                else:
                    logger.info(f"[{client_ip}] GET {self.path} - 显示登录页面")
                    self.send_login_page()
                return

            parsed = urlparse(self.path)
            path = parsed.path
            
            if path == '/':
                path = '/index.html'
            
            path = path.lstrip('/')
            if '..' in path or path.startswith('/') or '\\' in path:
                logger.warning(f"[{client_ip}] GET {self.path} - 路径遍历攻击尝试")
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'Forbidden')
                return
            
            file_path = os.path.normpath(os.path.join(WEB_ROOT, path))
            
            if not file_path.startswith(WEB_ROOT):
                logger.warning(f"[{client_ip}] GET {self.path} - 路径遍历攻击尝试")
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
                    
                    logger.info(f"[{client_ip}] GET {self.path} - 成功 (200)")
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", len(content))
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("X-Frame-Options", "DENY")
                    self.send_header("X-XSS-Protection", "1; mode=block")
                    self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
                    self.end_headers()
                    self.wfile.write(content)
                except BrokenPipeError:
                    pass
                except ConnectionResetError:
                    pass
                except Exception as e:
                    logger.error(f"[{client_ip}] GET {self.path} - 文件读取错误: {str(e)}")
                    try:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(f'Internal Server Error: {str(e)}'.encode('utf-8'))
                    except Exception as e2:
                        logger.debug(f"Failed to send error response: {str(e2)}")
            else:
                logger.warning(f"[{client_ip}] GET {self.path} - 文件不存在")
                try:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not Found')
                except Exception as e:
                    logger.debug(f"Failed to send 404 response: {str(e)}")
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

if __name__ == "__main__":
    logger.info("="*50)
    logger.info("AI Bridge 启动中...")
    logger.info("="*50)
    logger.info(f"端口: {PORT}")
    logger.info(f"配置文件: {CONFIG_FILE}")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info(f"API端点: POST http://localhost:{PORT}/chat")
    logger.info(f"当前提供者: {config.get('active_provider', 'minimax')}")
    logger.info("")
    logger.info("可用提供者:")
    for provider in ['minimax', 'ollama', 'openrouter']:
        provider_config = get_provider_config(provider)
        api_key = provider_config.get('api_key', '')
        if api_key and api_key != 'EMPTY':
            logger.info(f"  - {provider}: ✓ 已配置")
        elif provider == 'ollama':
            api_base = provider_config.get('api_base', '')
            logger.info(f"  - {provider}: ✓ 本地 ({api_base})")
        else:
            logger.info(f"  - {provider}: ✗ 未配置")
    logger.info("")
    logger.info("切换提供者请修改 config.json 中的 'active_provider'")
    logger.info("环境变量可覆盖配置 (MINIMAX_API_KEY, MINIMAX_GROUP_ID)")
    logger.info("="*50)

    class ReuseAddrHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True
        timeout = 60
        
        def server_bind(self):
            import socket
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(120)
            super().server_bind()
        
        def process_request(self, request, client_address):
            try:
                request.settimeout(60)
                super().process_request(request, client_address)
            except Exception as e:
                logger.debug(f"Request processing error: {e}")
                try:
                    request.close()
                except:
                    pass

    server = ReuseAddrHTTPServer(("0.0.0.0", PORT), NanobotHandler)
    redirect_server = None

    if USE_HTTPS:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(SSL_CERT_FILE, SSL_KEY_FILE)
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
        logger.info(f"HTTPS 已启用，证书: {SSL_CERT_FILE}")

        redirect_server = ReuseAddrHTTPServer(("0.0.0.0", 80), HTTPtoHTTPSRedirectHandler)
        redirect_server_thread = threading.Thread(target=redirect_server.serve_forever)
        redirect_server_thread.daemon = True
        redirect_server_thread.start()
        logger.info("HTTP -> HTTPS 重定向已启用 (端口 80)")

    def graceful_shutdown(signum, frame):
        logger.info("收到关闭信号，正在优雅关闭...")
        logger.info("等待当前请求完成...")
        if redirect_server:
            logger.info("关闭 HTTP 重定向服务器 (端口 80)...")
            redirect_server.shutdown()
            logger.info("HTTP 重定向服务器已关闭")
        server.shutdown()
        logger.info("主服务器已关闭")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    
    logger.info(f"服务器已启动，监听端口 {PORT} ({'HTTPS' if USE_HTTPS else 'HTTP'})")
    logger.info("按 Ctrl+C 或发送 SIGTERM 信号可优雅关闭")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        graceful_shutdown(None, None)