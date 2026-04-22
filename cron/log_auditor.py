#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志审计与安全响应系统 (SOAR)
功能：
1. 日志审计分析
2. 攻击检测与IP封禁
3. 防火墙规则管理
4. 自动解封过期IP
"""

import json
import os
import sys
import subprocess
import http.client
import re
import time
from datetime import datetime, timedelta
from collections import Counter

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
WAF_RULES_FILE = os.path.join(PROJECT_DIR, "waf_rules.json")
ERROR_CODES_FILE = os.path.join(PROJECT_DIR, "error_codes.json")
LOG_DIR = os.path.join(PROJECT_DIR, 'logs')
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

SOAR_CONFIG = {
    'max_attack_count': 10,
    'temp_ban_hours': 24,
    'ssh_fail_threshold': 5,
    'web_attack_threshold': 3,
    'scan_threshold': 20,
    'ddos_threshold': 100,
}

ATTACK_PATTERNS = [
    r'eval-stdin',
    r'\.php',
    r'\.env',
    r'\.git',
    r'redirect\?',
    r'redirect\.php',
    r'shell',
    r'cmd=',
    r'exec=',
    r'whoami',
    r'passwd',
    r'/etc/',
    r'union.*select',
    r'<script',
    r'javascript:',
]

VOICE_ERROR_PATTERNS = {
    'voice_error': [
        (r'PCM转换失败', '音频格式转换失败'),
        (r'ffmpeg启动失败', 'FFmpeg 启动失败'),
        (r'音频转换失败', '音频处理错误'),
        (r'识别失败', '语音识别失败'),
        (r'Token错误', '百度 Token 获取失败'),
        (r'SSL证书加载失败', 'SSL 证书加载失败'),
    ],
    'voice_network': [
        (r'HTTP 5\d{2}', '语音服务 5xx 错误'),
        (r'HTTP 4\d{2}', '语音服务 4xx 错误'),
        (r'Connection refused', '语音服务连接被拒绝'),
        (r'TimeoutError', '语音服务超时'),
    ],
}

SYSTEM_THRESHOLDS = {
    'cpu_warning': 80,
    'cpu_critical': 95,
    'memory_warning': 80,
    'memory_critical': 95,
    'disk_warning': 80,
    'disk_critical': 90,
    'log_size_mb': 100,
    'log_retention_days': 30,
}

SERVICE_CONFIG = {
    'nanobot_bridge': {
        'name': 'AI Bridge 服务',
        'port': 80,
        'check_url': '/health',
        'restart_cmd': 'systemctl restart nanobot',
    },
    'voice_proxy': {
        'name': '语音代理服务',
        'port': 85,
        'check_url': '/voice/config',
        'restart_cmd': 'systemctl restart voice-proxy',
    },
}

ALERT_LEVELS = {
    'info': 0,
    'warning': 1,
    'error': 2,
    'critical': 3,
}

ERROR_PATTERNS = {
    'http_error': [
        (r'HTTP 5\d{2}', 'HTTP 5xx 服务器错误'),
        (r'HTTP 4\d{2}', 'HTTP 4xx 客户端错误'),
        (r'Connection refused', '连接被拒绝'),
        (r'Connection timeout', '连接超时'),
        (r'Connection reset', '连接重置'),
        (r'Socket error', 'Socket 错误'),
    ],
    'api_error': [
        (r'API.*失败', 'API 调用失败'),
        (r'API.*错误', 'API 错误'),
        (r'rate limit', 'API 频率限制'),
        (r'quota exceeded', 'API 配额超限'),
        (r'invalid.*key', 'API Key 无效'),
        (r'unauthorized', '未授权访问'),
    ],
    'code_bug': [
        (r'Traceback', 'Python 异常堆栈'),
        (r'Exception:', 'Python 异常'),
        (r'Error:', '代码错误'),
        (r'KeyError', '字典键错误'),
        (r'IndexError', '索引越界'),
        (r'TypeError', '类型错误'),
        (r'ValueError', '值错误'),
        (r'AttributeError', '属性错误'),
        (r'ImportError', '导入错误'),
        (r'ModuleNotFoundError', '模块未找到'),
        (r'FileNotFoundError', '文件未找到'),
        (r'PermissionError', '权限错误'),
        (r'JSONDecodeError', 'JSON 解析错误'),
        (r'UnicodeDecodeError', '编码错误'),
        (r'OSError', '系统错误'),
        (r'MemoryError', '内存不足'),
        (r'RecursionError', '递归过深'),
        (r'TimeoutError', '超时错误'),
    ],
    'ssl_error': [
        (r'SSL.*error', 'SSL 错误'),
        (r'certificate.*error', '证书错误'),
        (r'handshake.*fail', 'SSL 握手失败'),
    ],
    'system_error': [
        (r'Out of memory', '内存不足'),
        (r'Disk full', '磁盘空间不足'),
        (r'Too many open files', '文件描述符耗尽'),
        (r'Resource temporarily unavailable', '资源暂时不可用'),
    ],
}

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json_file(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default

def save_json_file(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def is_private_ip(ip):
    if not ip:
        return False
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    try:
        first = int(parts[0])
        second = int(parts[1])
        if first == 10:
            return True
        if first == 172 and 16 <= second <= 31:
            return True
        if first == 192 and second == 168:
            return True
        if ip.startswith('127.'):
            return True
        return False
    except:
        return False

class AlertManager:
    def __init__(self):
        self.alert_file = os.path.join(DATA_DIR, 'alerts.json')
        self.alert_history_file = os.path.join(DATA_DIR, 'alert_history.json')
        ensure_data_dir()
    
    def _load_alerts(self):
        return load_json_file(self.alert_file, {'active': {}, 'escalation_count': {}})
    
    def _save_alerts(self, data):
        save_json_file(self.alert_file, data)
    
    def _load_history(self):
        return load_json_file(self.alert_history_file, [])
    
    def _save_history(self, data):
        save_json_file(self.alert_history_file, data[-1000:])
    
    def create_alert(self, alert_type, level, message, details=None):
        alerts = self._load_alerts()
        alert_key = f"{alert_type}:{message[:50]}"
        now = time.time()
        
        if alert_key in alerts['active']:
            alerts['active'][alert_key]['count'] += 1
            alerts['active'][alert_key]['last_seen'] = now
        else:
            alerts['active'][alert_key] = {
                'type': alert_type,
                'level': level,
                'message': message,
                'details': details,
                'count': 1,
                'first_seen': now,
                'last_seen': now,
            }
        
        escalation_count = alerts.get('escalation_count', {}).get(alert_key, 0)
        if escalation_count > 0:
            if level == 'warning':
                level = 'error'
            elif level == 'error':
                level = 'critical'
        
        self._save_alerts(alerts)
        
        history = self._load_history()
        history.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': alert_type,
            'level': level,
            'message': message,
        })
        self._save_history(history)
        
        return alerts['active'][alert_key]
    
    def escalate_alert(self, alert_type, message):
        alerts = self._load_alerts()
        alert_key = f"{alert_type}:{message[:50]}"
        
        if 'escalation_count' not in alerts:
            alerts['escalation_count'] = {}
        
        alerts['escalation_count'][alert_key] = alerts['escalation_count'].get(alert_key, 0) + 1
        self._save_alerts(alerts)
    
    def resolve_alert(self, alert_type, message):
        alerts = self._load_alerts()
        alert_key = f"{alert_type}:{message[:50]}"
        
        if alert_key in alerts['active']:
            del alerts['active'][alert_key]
        
        if 'escalation_count' in alerts and alert_key in alerts['escalation_count']:
            del alerts['escalation_count'][alert_key]
        
        self._save_alerts(alerts)
    
    def get_active_alerts(self, level=None):
        alerts = self._load_alerts()
        active = alerts.get('active', {})
        
        if level:
            return {k: v for k, v in active.items() if v['level'] == level}
        return active
    
    def get_alert_summary(self):
        alerts = self._load_alerts()
        active = alerts.get('active', {})
        
        summary = {
            'total': len(active),
            'by_level': {'info': 0, 'warning': 0, 'error': 0, 'critical': 0},
            'top_issues': [],
        }
        
        for alert in active.values():
            summary['by_level'][alert['level']] += 1
        
        sorted_alerts = sorted(active.values(), key=lambda x: x['count'], reverse=True)
        summary['top_issues'] = [(a['type'], a['message'], a['count']) for a in sorted_alerts[:5]]
        
        return summary

class SystemMonitor:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.stats_file = os.path.join(DATA_DIR, 'system_stats.json')
        ensure_data_dir()
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout.strip()
        except:
            return False, ''
    
    def get_cpu_usage(self):
        success, output = self._run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        if success and output:
            try:
                return float(output)
            except:
                pass
        return 0
    
    def get_memory_usage(self):
        success, output = self._run_cmd("free | grep Mem | awk '{print int($3/$2 * 100)}'")
        if success and output:
            try:
                return int(output)
            except:
                pass
        return 0
    
    def get_disk_usage(self):
        success, output = self._run_cmd("df -h / | tail -1 | awk '{print $5}' | tr -d '%'")
        if success and output:
            try:
                return int(output)
            except:
                pass
        return 0
    
    def get_load_average(self):
        success, output = self._run_cmd("cat /proc/loadavg | awk '{print $1, $2, $3}'")
        if success and output:
            try:
                loads = [float(x) for x in output.split()]
                return loads
            except:
                pass
        return [0, 0, 0]
    
    def check_system_health(self):
        stats = {
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'disk': self.get_disk_usage(),
            'load': self.get_load_average(),
            'alerts': [],
        }
        
        if stats['cpu'] >= SYSTEM_THRESHOLDS['cpu_critical']:
            alert = self.alert_manager.create_alert(
                'system', 'critical',
                f"CPU 使用率过高: {stats['cpu']}%",
                {'cpu': stats['cpu']}
            )
            stats['alerts'].append(alert)
        elif stats['cpu'] >= SYSTEM_THRESHOLDS['cpu_warning']:
            alert = self.alert_manager.create_alert(
                'system', 'warning',
                f"CPU 使用率较高: {stats['cpu']}%",
                {'cpu': stats['cpu']}
            )
            stats['alerts'].append(alert)
        
        if stats['memory'] >= SYSTEM_THRESHOLDS['memory_critical']:
            alert = self.alert_manager.create_alert(
                'system', 'critical',
                f"内存使用率过高: {stats['memory']}%",
                {'memory': stats['memory']}
            )
            stats['alerts'].append(alert)
        elif stats['memory'] >= SYSTEM_THRESHOLDS['memory_warning']:
            alert = self.alert_manager.create_alert(
                'system', 'warning',
                f"内存使用率较高: {stats['memory']}%",
                {'memory': stats['memory']}
            )
            stats['alerts'].append(alert)
        
        if stats['disk'] >= SYSTEM_THRESHOLDS['disk_critical']:
            alert = self.alert_manager.create_alert(
                'system', 'critical',
                f"磁盘使用率过高: {stats['disk']}%",
                {'disk': stats['disk']}
            )
            stats['alerts'].append(alert)
        elif stats['disk'] >= SYSTEM_THRESHOLDS['disk_warning']:
            alert = self.alert_manager.create_alert(
                'system', 'warning',
                f"磁盘使用率较高: {stats['disk']}%",
                {'disk': stats['disk']}
            )
            stats['alerts'].append(alert)
        
        self._save_stats(stats)
        return stats
    
    def _save_stats(self, stats):
        history = load_json_file(self.stats_file, [])
        history.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **stats
        })
        save_json_file(self.stats_file, history[-1440:])

class ServiceHealthChecker:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.status_file = os.path.join(DATA_DIR, 'service_status.json')
        ensure_data_dir()
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except:
            return False, '', ''
    
    def check_http_service(self, service_name, port, path='/'):
        try:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            conn.request('GET', path)
            response = conn.getresponse()
            conn.close()
            return response.status < 500, response.status
        except Exception as e:
            return False, str(e)
    
    def check_service(self, service_id):
        config = SERVICE_CONFIG.get(service_id, {})
        service_name = config.get('name', service_id)
        
        status = {
            'service': service_id,
            'name': service_name,
            'healthy': True,
            'status_code': None,
            'error': None,
            'restart_attempted': False,
        }
        
        if 'check_url' in config:
            healthy, code = self.check_http_service(
                service_id, config['port'], config['check_url']
            )
            status['healthy'] = healthy
            status['status_code'] = code
        
        if 'check_cmd' in config:
            success, stdout, stderr = self._run_cmd(config['check_cmd'])
            status['healthy'] = success
            if not success:
                status['error'] = stderr[:200] if stderr else '检查命令失败'
        
        if not status['healthy']:
            alert = self.alert_manager.create_alert(
                'service', 'error',
                f"服务异常: {service_name}",
                {'service': service_id, 'error': status.get('error', status.get('status_code'))}
            )
            status['alert'] = alert
        
        return status
    
    def check_all_services(self):
        results = {}
        for service_id in SERVICE_CONFIG:
            results[service_id] = self.check_service(service_id)
        
        self._save_status(results)
        return results
    
    def _save_status(self, status):
        history = load_json_file(self.status_file, [])
        history.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **status
        })
        save_json_file(self.status_file, history[-1440:])
    
    def restart_service(self, service_id):
        config = SERVICE_CONFIG.get(service_id, {})
        restart_cmd = config.get('restart_cmd')
        
        if not restart_cmd:
            return False, "未配置重启命令"
        
        success, stdout, stderr = self._run_cmd(restart_cmd)
        if success:
            self.alert_manager.resolve_alert('service', f"服务异常: {config.get('name', service_id)}")
            return True, "重启成功"
        return False, stderr[:200] if stderr else "重启失败"

class SSLCertificateChecker:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.config = load_config()
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout.strip()
        except:
            return False, ''
    
    def check_certificate(self, cert_path):
        if not os.path.exists(cert_path):
            self.alert_manager.create_alert(
                'ssl', 'critical',
                f"SSL证书文件不存在: {cert_path}",
                {'path': cert_path}
            )
            return None
        
        success, output = self._run_cmd(
            f"openssl x509 -in {cert_path} -noout -enddate 2>/dev/null | cut -d= -f2"
        )
        
        if not success or not output:
            return None
        
        try:
            from datetime import datetime as dt
            expiry_date = dt.strptime(output.strip(), '%b %d %H:%M:%S %Y %Z')
            days_left = (expiry_date - dt.now()).days
            
            status = {
                'path': cert_path,
                'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                'days_left': days_left,
                'valid': days_left > 0,
            }
            
            if days_left <= 0:
                self.alert_manager.create_alert(
                    'ssl', 'critical',
                    f"SSL证书已过期: {cert_path}",
                    {'days_left': days_left, 'expiry': status['expiry_date']}
                )
            elif days_left <= 7:
                self.alert_manager.create_alert(
                    'ssl', 'critical',
                    f"SSL证书即将过期({days_left}天): {cert_path}",
                    {'days_left': days_left, 'expiry': status['expiry_date']}
                )
            elif days_left <= 30:
                self.alert_manager.create_alert(
                    'ssl', 'warning',
                    f"SSL证书将在{days_left}天后过期: {cert_path}",
                    {'days_left': days_left, 'expiry': status['expiry_date']}
                )
            
            return status
        except Exception as e:
            return None
    
    def check_all_certificates(self):
        results = {}
        
        ssl_cert = self.config.get('server', {}).get('ssl_cert_file', '')
        ssl_cert = ssl_cert or self.config.get('ssl_cert_file', '')
        
        if ssl_cert:
            results['main'] = self.check_certificate(ssl_cert)
        
        return results

class LogCleaner:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout.strip()
        except:
            return False, ''
    
    def get_log_size(self, log_dir):
        total_size = 0
        if os.path.exists(log_dir):
            for root, dirs, files in os.walk(log_dir):
                for f in files:
                    if f.endswith('.log'):
                        fp = os.path.join(root, f)
                        total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)
    
    def get_old_logs(self, log_dir, days=30):
        old_logs = []
        cutoff = time.time() - days * 86400
        
        if os.path.exists(log_dir):
            for root, dirs, files in os.walk(log_dir):
                for f in files:
                    if f.endswith('.log'):
                        fp = os.path.join(root, f)
                        if os.path.getmtime(fp) < cutoff:
                            old_logs.append(fp)
        return old_logs
    
    def clean_old_logs(self, days=None):
        if days is None:
            days = SYSTEM_THRESHOLDS['log_retention_days']
        
        old_logs = self.get_old_logs(LOG_DIR, days)
        cleaned_size = 0
        
        for log_file in old_logs:
            try:
                size = os.path.getsize(log_file)
                os.remove(log_file)
                cleaned_size += size
            except:
                pass
        
        if cleaned_size > 0:
            self.alert_manager.create_alert(
                'maintenance', 'info',
                f"清理了 {len(old_logs)} 个旧日志文件，释放 {cleaned_size / (1024*1024):.1f}MB",
                {'files': len(old_logs), 'size_mb': cleaned_size / (1024*1024)}
            )
        
        return len(old_logs), cleaned_size
    
    def check_and_clean(self):
        log_size_mb = self.get_log_size(LOG_DIR)
        
        if log_size_mb > SYSTEM_THRESHOLDS['log_size_mb']:
            self.alert_manager.create_alert(
                'maintenance', 'warning',
                f"日志目录过大: {log_size_mb:.1f}MB",
                {'size_mb': log_size_mb}
            )
            
            days = SYSTEM_THRESHOLDS['log_retention_days']
            while log_size_mb > SYSTEM_THRESHOLDS['log_size_mb'] and days > 7:
                count, size = self.clean_old_logs(days)
                log_size_mb = self.get_log_size(LOG_DIR)
                days -= 7
        
        return log_size_mb

class VoiceLogAnalyzer:
    def __init__(self):
        self.voice_log_dir = LOG_DIR
    
    def get_latest_voice_log(self):
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(self.voice_log_dir, f'voice_{today}.log')
        if os.path.exists(log_file):
            return log_file
        
        log_files = [f for f in os.listdir(self.voice_log_dir) if f.startswith('voice_') and f.endswith('.log')]
        if log_files:
            log_files.sort(reverse=True)
            return os.path.join(self.voice_log_dir, log_files[0])
        
        return None
    
    def analyze_voice_logs(self, log_file, hours=24):
        stats = {
            'total_lines': 0,
            'errors': [],
            'voice_errors': {'voice_error': [], 'voice_network': []},
            'recognition_success': 0,
            'recognition_failed': 0,
            'token_requests': 0,
            'token_failures': 0,
        }
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if not os.path.exists(log_file):
            return stats
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stats['total_lines'] += 1
                
                try:
                    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if time_match:
                        line_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                        if line_time < cutoff_time:
                            continue
                except:
                    pass
                
                if '[ERROR]' in line:
                    stats['errors'].append(line.strip())
                
                for category, patterns in VOICE_ERROR_PATTERNS.items():
                    for pattern, desc in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            stats['voice_errors'][category].append({
                                'line': line.strip()[:200],
                                'desc': desc,
                            })
                            break
                
                if '识别结果' in line and 'success' in line.lower():
                    stats['recognition_success'] += 1
                elif '识别失败' in line or '识别错误' in line:
                    stats['recognition_failed'] += 1
                
                if 'Token响应' in line:
                    stats['token_requests'] += 1
                elif 'Token错误' in line:
                    stats['token_failures'] += 1
        
        return stats

class APIHealthChecker:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.config = load_config()
        self.status_file = os.path.join(DATA_DIR, 'api_status.json')
        ensure_data_dir()
    
    def check_minimax_api(self):
        provider_config = self.config.get('minimax', {})
        api_key = provider_config.get('api_key', '')
        group_id = provider_config.get('group_id', '')
        
        if not api_key or not group_id:
            return {'available': False, 'error': '未配置'}
        
        try:
            conn = http.client.HTTPSConnection("api.minimax.chat", timeout=10)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            data = {
                "model": "MiniMax-M2.7",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            path = f"/v1/text/chatcompletion_v2?GroupId={group_id}"
            
            conn.request("POST", path, json.dumps(data), headers)
            response = conn.getresponse()
            result = response.read().decode('utf-8')
            conn.close()
            
            result_json = json.loads(result)
            if "choices" in result_json:
                return {'available': True, 'latency': 0}
            else:
                error_msg = result_json.get('base_resp', {}).get('status_msg', '未知错误')
                return {'available': False, 'error': error_msg}
        except Exception as e:
            return {'available': False, 'error': str(e)[:100]}
    
    def check_baidu_api(self):
        baidu_config = self.config.get('baidu', {})
        api_key = baidu_config.get('api_key', '')
        secret_key = baidu_config.get('secret_key', '')
        
        if not api_key or not secret_key:
            return {'available': False, 'error': '未配置'}
        
        try:
            token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
            conn = http.client.HTTPSConnection("aip.baidubce.com", timeout=10)
            conn.request("GET", token_url.split("aip.baidubce.com")[1])
            response = conn.getresponse()
            result = response.read().decode('utf-8')
            conn.close()
            
            result_json = json.loads(result)
            if 'access_token' in result_json:
                return {'available': True}
            else:
                return {'available': False, 'error': result_json.get('error_description', '获取Token失败')}
        except Exception as e:
            return {'available': False, 'error': str(e)[:100]}
    
    def check_openrouter_api(self):
        provider_config = self.config.get('openrouter', {})
        api_key = provider_config.get('api_key', '')
        
        if not api_key:
            return {'available': False, 'error': '未配置'}
        
        try:
            conn = http.client.HTTPSConnection("openrouter.ai", timeout=10)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            conn.request("GET", "/api/v1/models", headers=headers)
            response = conn.getresponse()
            conn.close()
            
            if response.status == 200:
                return {'available': True}
            else:
                return {'available': False, 'error': f'HTTP {response.status}'}
        except Exception as e:
            return {'available': False, 'error': str(e)[:100]}
    
    def check_all_apis(self):
        results = {
            'minimax': self.check_minimax_api(),
            'baidu': self.check_baidu_api(),
            'openrouter': self.check_openrouter_api(),
        }
        
        for api_name, status in results.items():
            if not status['available']:
                self.alert_manager.create_alert(
                    'api', 'error',
                    f"API 不可用: {api_name}",
                    {'error': status.get('error', '未知')}
                )
        
        self._save_status(results)
        return results
    
    def _save_status(self, status):
        history = load_json_file(self.status_file, [])
        history.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **status
        })
        save_json_file(self.status_file, history[-1440:])

class ProcessMonitor:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.process_config = {
            'nanobot_bridge': {
                'name': 'AI Bridge 进程',
                'pattern': 'nanobot_bridge.py',
                'restart_cmd': 'systemctl restart hupo-bridge',
            },
            'voice_proxy': {
                'name': '语音代理进程',
                'pattern': 'voice-proxy.js',
                'restart_cmd': 'systemctl restart hupo-voice',
            },
        }
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout.strip()
        except:
            return False, ''
    
    def check_process(self, process_id):
        config = self.process_config.get(process_id, {})
        pattern = config.get('pattern', '')
        
        success, output = self._run_cmd(f"pgrep -f '{pattern}'")
        running = success and output
        
        status = {
            'process': process_id,
            'name': config.get('name', process_id),
            'running': running,
            'pid': output.split('\n')[0] if running else None,
        }
        
        if not running:
            self.alert_manager.create_alert(
                'process', 'critical',
                f"进程未运行: {config.get('name', process_id)}",
                {'process': process_id}
            )
        
        return status
    
    def check_all_processes(self):
        results = {}
        for process_id in self.process_config:
            results[process_id] = self.check_process(process_id)
        return results
    
    def restart_process(self, process_id):
        config = self.process_config.get(process_id, {})
        restart_cmd = config.get('restart_cmd')
        
        if not restart_cmd:
            return False, "未配置重启命令"
        
        success, output = self._run_cmd(restart_cmd)
        if success:
            self.alert_manager.resolve_alert('process', f"进程未运行: {config.get('name', process_id)}")
            return True, "重启成功"
        return False, "重启失败"

class PortMonitor:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.port_config = {
            80: {'name': 'HTTP 端口', 'service': 'nanobot_bridge'},
            443: {'name': 'HTTPS 端口', 'service': 'nanobot_bridge'},
            85: {'name': '语音代理端口', 'service': 'voice_proxy'},
        }
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout.strip()
        except:
            return False, ''
    
    def check_port(self, port):
        success, output = self._run_cmd(f"netstat -tlnp 2>/dev/null | grep ':{port} ' || ss -tlnp 2>/dev/null | grep ':{port} '")
        listening = bool(output.strip())
        
        config = self.port_config.get(port, {})
        status = {
            'port': port,
            'name': config.get('name', f'端口 {port}'),
            'listening': listening,
        }
        
        if not listening:
            self.alert_manager.create_alert(
                'port', 'critical',
                f"端口未监听: {config.get('name', f'端口 {port}')}",
                {'port': port}
            )
        
        return status
    
    def check_all_ports(self):
        results = {}
        for port in self.port_config:
            results[port] = self.check_port(port)
        return results

class ConfigAuditor:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.config_files = [
            CONFIG_FILE,
            os.path.join(PROJECT_DIR, 'nanobot_bridge.py'),
            os.path.join(PROJECT_DIR, 'voice-proxy.js'),
            os.path.join(PROJECT_DIR, 'index.html'),
        ]
        self.checksum_file = os.path.join(DATA_DIR, 'config_checksums.json')
        ensure_data_dir()
    
    def _get_file_checksum(self, filepath):
        if not os.path.exists(filepath):
            return None
        try:
            import hashlib
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None
    
    def _load_checksums(self):
        return load_json_file(self.checksum_file, {})
    
    def _save_checksums(self, data):
        save_json_file(self.checksum_file, data)
    
    def init_checksums(self):
        checksums = {}
        for filepath in self.config_files:
            checksum = self._get_file_checksum(filepath)
            if checksum:
                checksums[filepath] = {
                    'checksum': checksum,
                    'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
        self._save_checksums(checksums)
        return checksums
    
    def check_config_integrity(self):
        stored_checksums = self._load_checksums()
        results = {
            'checked': 0,
            'modified': [],
            'new_files': [],
            'missing': [],
        }
        
        for filepath in self.config_files:
            current_checksum = self._get_file_checksum(filepath)
            
            if not current_checksum:
                results['missing'].append(filepath)
                continue
            
            results['checked'] += 1
            
            if filepath not in stored_checksums:
                results['new_files'].append(filepath)
                continue
            
            if stored_checksums[filepath]['checksum'] != current_checksum:
                results['modified'].append(filepath)
                self.alert_manager.create_alert(
                    'config', 'warning',
                    f"配置文件被修改: {os.path.basename(filepath)}",
                    {'file': filepath}
                )
        
        if results['modified']:
            self._update_checksums()
        
        return results
    
    def _update_checksums(self):
        checksums = self._load_checksums()
        for filepath in self.config_files:
            checksum = self._get_file_checksum(filepath)
            if checksum:
                checksums[filepath] = {
                    'checksum': checksum,
                    'last_checked': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
        self._save_checksums(checksums)

class AlertNotifier:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.config = load_config()
        self.notification_file = os.path.join(DATA_DIR, 'notifications.json')
        ensure_data_dir()
    
    def _load_notifications(self):
        return load_json_file(self.notification_file, {'sent': {}, 'cooldown': {}})
    
    def _save_notifications(self, data):
        save_json_file(self.notification_file, data)
    
    def send_webhook(self, webhook_url, message):
        if not webhook_url:
            return False, "未配置 Webhook URL"
        
        try:
            import urllib.request
            data = json.dumps({"content": message}).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200, "发送成功"
        except Exception as e:
            return False, str(e)[:100]
    
    def notify_critical_alerts(self, webhook_url=None):
        alerts = self.alert_manager.get_active_alerts('critical')
        if not alerts:
            return []
        
        notifications = self._load_notifications()
        now = time.time()
        cooldown_seconds = 3600
        sent_notifications = []
        
        for alert_key, alert in alerts.items():
            if alert_key in notifications['cooldown']:
                if now - notifications['cooldown'][alert_key] < cooldown_seconds:
                    continue
            
            message = f"🚨 **严重告警**\n\n**类型**: {alert['type']}\n**消息**: {alert['message']}\n**次数**: {alert['count']}\n**时间**: {datetime.fromtimestamp(alert['last_seen']).strftime('%Y-%m-%d %H:%M:%S')}"
            
            if webhook_url:
                success, _ = self.send_webhook(webhook_url, message)
                if success:
                    notifications['cooldown'][alert_key] = now
                    sent_notifications.append(alert_key)
        
        self._save_notifications(notifications)
        return sent_notifications
    
    def notify_error_alerts(self, webhook_url=None):
        alerts = self.alert_manager.get_active_alerts('error')
        if not alerts:
            return []
        
        notifications = self._load_notifications()
        now = time.time()
        cooldown_seconds = 7200
        sent_notifications = []
        
        error_count = len(alerts)
        if error_count > 5:
            message = f"⚠️ **错误告警汇总**\n\n活跃错误告警: {error_count} 个\n\n"
            for alert_key, alert in list(alerts.items())[:5]:
                message += f"- [{alert['type']}] {alert['message']} ({alert['count']}次)\n"
            
            if webhook_url:
                success, _ = self.send_webhook(webhook_url, message)
                if success:
                    sent_notifications.append('error_summary')
        
        self._save_notifications(notifications)
        return sent_notifications

class AutoRecovery:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.process_monitor = ProcessMonitor(alert_manager)
        self.port_monitor = PortMonitor(alert_manager)
        self.service_checker = ServiceHealthChecker(alert_manager)
        self.recovery_file = os.path.join(DATA_DIR, 'recovery_log.json')
        ensure_data_dir()
    
    def _log_recovery(self, action, result):
        history = load_json_file(self.recovery_file, [])
        history.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': action,
            'result': result,
        })
        save_json_file(self.recovery_file, history[-100:])
    
    def check_and_recover(self):
        results = {
            'processes_checked': 0,
            'ports_checked': 0,
            'recoveries_attempted': 0,
            'recoveries_successful': 0,
            'actions': [],
        }
        
        process_status = self.process_monitor.check_all_processes()
        results['processes_checked'] = len(process_status)
        
        for process_id, status in process_status.items():
            if not status['running']:
                results['recoveries_attempted'] += 1
                success, msg = self.process_monitor.restart_process(process_id)
                action = f"重启进程 {status['name']}: {'成功' if success else '失败'}"
                results['actions'].append(action)
                self._log_recovery(f"restart_process:{process_id}", {'success': success, 'msg': msg})
                if success:
                    results['recoveries_successful'] += 1
        
        port_status = self.port_monitor.check_all_ports()
        results['ports_checked'] = len(port_status)
        
        for port, status in port_status.items():
            if not status['listening']:
                service_config = self.port_monitor.port_config.get(port, {})
                service_id = service_config.get('service')
                if service_id:
                    results['recoveries_attempted'] += 1
                    success, msg = self.service_checker.restart_service(service_id)
                    action = f"重启服务 {status['name']}: {'成功' if success else '失败'}"
                    results['actions'].append(action)
                    self._log_recovery(f"restart_service:{service_id}", {'success': success, 'msg': msg})
                    if success:
                        results['recoveries_successful'] += 1
        
        return results

class CronJobChecker:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.expected_crons = [
            {'pattern': 'log_auditor.py', 'name': '日志审计'},
            {'pattern': 'health_check.sh', 'name': '健康检查'},
        ]
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout.strip()
        except:
            return False, ''
    
    def check_cron_jobs(self):
        results = {
            'total_jobs': 0,
            'expected_found': [],
            'expected_missing': [],
        }
        
        success, output = self._run_cmd("crontab -l 2>/dev/null")
        if not success:
            return results
        
        cron_lines = output.split('\n')
        results['total_jobs'] = len([l for l in cron_lines if l.strip() and not l.startswith('#')])
        
        for expected in self.expected_crons:
            found = any(expected['pattern'] in line for line in cron_lines)
            if found:
                results['expected_found'].append(expected['name'])
            else:
                results['expected_missing'].append(expected['name'])
                self.alert_manager.create_alert(
                    'cron', 'warning',
                    f"定时任务缺失: {expected['name']}",
                    {'pattern': expected['pattern']}
                )
        
        return results

class FirewallManager:
    def __init__(self):
        self.blacklist_file = os.path.join(DATA_DIR, 'blacklist.json')
        self.temp_ban_file = os.path.join(DATA_DIR, 'temp_ban.json')
        self.attack_count_file = os.path.join(DATA_DIR, 'attack_count.json')
        self.soar_log_file = os.path.join(LOG_DIR, 'soar.log')
        ensure_data_dir()
    
    def _log(self, msg):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {msg}\n"
        print(log_line.strip())
        with open(self.soar_log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout.strip()
        except Exception as e:
            return False, str(e)
    
    def get_attack_count(self, ip):
        data = load_json_file(self.attack_count_file, {})
        return data.get(ip, 0)
    
    def increment_attack_count(self, ip):
        data = load_json_file(self.attack_count_file, {})
        data[ip] = data.get(ip, 0) + 1
        save_json_file(self.attack_count_file, data)
        return data[ip]
    
    def is_permanent_banned(self, ip):
        data = load_json_file(self.blacklist_file, {'permanent': []})
        return ip in data.get('permanent', [])
    
    def is_temp_banned(self, ip):
        data = load_json_file(self.temp_ban_file, {})
        if ip in data:
            if time.time() < data[ip]:
                return True
            else:
                del data[ip]
                save_json_file(self.temp_ban_file, data)
        return False
    
    def add_to_firewall(self, ip, reason=""):
        success, _ = self._run_cmd(f"iptables -C INPUT -s {ip} -j DROP 2>/dev/null")
        if success:
            return False
        success, _ = self._run_cmd(f"iptables -I INPUT -s {ip} -j DROP")
        if success:
            self._log(f"[BAN] IP {ip} 已加入防火墙黑名单 - {reason}")
            return True
        return False
    
    def remove_from_firewall(self, ip):
        success, _ = self._run_cmd(f"iptables -D INPUT -s {ip} -j DROP 2>/dev/null")
        if success:
            self._log(f"[UNBAN] IP {ip} 已从防火墙移除")
            return True
        return False
    
    def permanent_ban(self, ip, reason=""):
        data = load_json_file(self.blacklist_file, {'permanent': []})
        if ip not in data['permanent']:
            data['permanent'].append(ip)
            save_json_file(self.blacklist_file, data)
        
        temp_data = load_json_file(self.temp_ban_file, {})
        if ip in temp_data:
            del temp_data[ip]
            save_json_file(self.temp_ban_file, temp_data)
        
        self.add_to_firewall(ip, f"永久封禁 - {reason}")
        self._log(f"[PERMANENT] IP {ip} 永久封禁 - {reason}")
    
    def temp_ban(self, ip, reason=""):
        ban_until = time.time() + SOAR_CONFIG['temp_ban_hours'] * 3600
        
        data = load_json_file(self.temp_ban_file, {})
        data[ip] = ban_until
        save_json_file(self.temp_ban_file, data)
        
        ban_time_str = datetime.fromtimestamp(ban_until).strftime('%Y-%m-%d %H:%M:%S')
        self.add_to_firewall(ip, f"临时封禁({SOAR_CONFIG['temp_ban_hours']}小时) - {reason}")
        self._log(f"[TEMP] IP {ip} 临时封禁至 {ban_time_str} - {reason}")
    
    def unban_expired(self):
        now = time.time()
        data = load_json_file(self.temp_ban_file, {})
        expired_ips = [ip for ip, ban_time in data.items() if now > ban_time]
        
        for ip in expired_ips:
            del data[ip]
            self.remove_from_firewall(ip)
            self._log(f"[EXPIRED] IP {ip} 临时封禁已过期，自动解封")
        
        if expired_ips:
            save_json_file(self.temp_ban_file, data)
    
    def restore_rules(self):
        blacklist = load_json_file(self.blacklist_file, {'permanent': []})
        for ip in blacklist.get('permanent', []):
            self.add_to_firewall(ip, "恢复永久封禁")
        
        temp_data = load_json_file(self.temp_ban_file, {})
        now = time.time()
        for ip, ban_time in temp_data.items():
            if now < ban_time:
                self.add_to_firewall(ip, "恢复临时封禁")
            else:
                del temp_data[ip]
        save_json_file(self.temp_ban_file, temp_data)
    
    def get_status(self):
        blacklist = load_json_file(self.blacklist_file, {'permanent': []})
        temp_data = load_json_file(self.temp_ban_file, {})
        attack_data = load_json_file(self.attack_count_file, {})
        
        now = time.time()
        active_temp = {ip: t for ip, t in temp_data.items() if now < t}
        
        return {
            'permanent_count': len(blacklist.get('permanent', [])),
            'temp_count': len(active_temp),
            'total_attacks': sum(attack_data.values()),
            'permanent_ips': blacklist.get('permanent', []),
            'temp_ips': active_temp,
            'attack_stats': attack_data
        }

class WAFRuleLearner:
    def __init__(self):
        self.waf_rules_file = WAF_RULES_FILE
        self.learned_patterns_file = os.path.join(DATA_DIR, 'learned_patterns.json')
        ensure_data_dir()
    
    def load_waf_rules(self):
        return load_json_file(self.waf_rules_file, {'attack_patterns': [], 'scanner_signatures': []})
    
    def save_waf_rules(self, rules):
        with open(self.waf_rules_file, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
    
    def load_learned_patterns(self):
        return load_json_file(self.learned_patterns_file, {'patterns': [], 'last_updated': None})
    
    def save_learned_patterns(self, data):
        data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_json_file(self.learned_patterns_file, data)
    
    def extract_path_patterns(self, log_file, hours=24):
        patterns = Counter()
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        suspicious_keywords = [
            'php', 'asp', 'aspx', 'jsp', 'cgi', 'pl', 'py', 'sh',
            'admin', 'manager', 'config', 'backup', 'dump', 'sql',
            'shell', 'cmd', 'exec', 'eval', 'system', 'passthru',
            'upload', 'download', 'file', 'path', 'dir', 'ls',
            'passwd', 'shadow', 'hosts', 'proc', 'etc',
            'git', 'svn', 'env', 'log', 'tmp', 'temp',
            'wp-', 'xmlrpc', 'cgi-bin', 'phpmyadmin', 'adminer',
            'vendor', 'node_modules', 'composer', 'package',
            'debug', 'test', 'dev', 'staging', 'beta',
            'api/v1', 'api/v2', 'graphql', 'swagger', 'openapi',
            'oauth', 'token', 'auth', 'login', 'signin',
            'redirect', 'callback', 'webhook', 'hook',
            'ajax', 'json', 'xml', 'rpc', 'soap',
        ]
        
        if not os.path.exists(log_file):
            return patterns
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                try:
                    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if time_match:
                        line_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                        if line_time < cutoff_time:
                            continue
                except:
                    pass
                
                if 'GET ' in line or 'POST ' in line:
                    match = re.search(r'(GET|POST)\s+([^\s]+)', line)
                    if match:
                        path = match.group(2)
                        path_lower = path.lower()
                        
                        for keyword in suspicious_keywords:
                            if keyword in path_lower:
                                path_parts = re.split(r'[/\\?&=]', path)
                                for part in path_parts:
                                    if len(part) > 2 and part not in ['http', 'https', 'www', 'index', 'html', 'js', 'css', 'json']:
                                        part_lower = part.lower()
                                        if any(kw in part_lower for kw in suspicious_keywords):
                                            patterns[part_lower] += 1
                                break
        
        return patterns
    
    def categorize_pattern(self, pattern):
        pattern_lower = pattern.lower()
        
        if any(kw in pattern_lower for kw in ['php', 'asp', 'jsp', 'cgi', 'pl', 'py']):
            return 'rce'
        elif any(kw in pattern_lower for kw in ['admin', 'manager', 'login', 'dashboard']):
            return 'admin'
        elif any(kw in pattern_lower for kw in ['config', 'env', 'ini', 'conf', 'yaml', 'yml']):
            return 'sensitive'
        elif any(kw in pattern_lower for kw in ['backup', 'dump', 'sql', 'db', 'database']):
            return 'sensitive'
        elif any(kw in pattern_lower for kw in ['shell', 'cmd', 'exec', 'eval', 'system']):
            return 'rce'
        elif any(kw in pattern_lower for kw in ['passwd', 'shadow', 'etc', 'proc']):
            return 'lfi'
        elif any(kw in pattern_lower for kw in ['git', 'svn', 'cvs']):
            return 'sensitive'
        elif any(kw in pattern_lower for kw in ['wp-', 'wordpress', 'joomla', 'drupal']):
            return 'cms'
        elif any(kw in pattern_lower for kw in ['phpmyadmin', 'adminer', 'pma']):
            return 'admin'
        elif any(kw in pattern_lower for kw in ['api', 'graphql', 'swagger', 'rpc']):
            return 'probe'
        else:
            return 'probe'
    
    def learn_new_patterns(self, min_occurrences=3):
        log_file = get_latest_log_file()
        if not log_file:
            return [], "未找到日志文件"
        
        patterns = self.extract_path_patterns(log_file)
        waf_rules = self.load_waf_rules()
        existing_patterns = {p['pattern'].lower() if isinstance(p, dict) else p.lower() 
                           for p in waf_rules.get('attack_patterns', [])}
        
        learned = self.load_learned_patterns()
        already_learned = {p['pattern'] for p in learned.get('patterns', [])}
        
        new_patterns = []
        for pattern, count in patterns.most_common(100):
            if count >= min_occurrences:
                pattern_lower = pattern.lower()
                if pattern_lower not in existing_patterns and pattern_lower not in already_learned:
                    if len(pattern) > 2 and not pattern.isdigit():
                        category = self.categorize_pattern(pattern)
                        new_patterns.append({
                            'pattern': pattern,
                            'category': category,
                            'count': count,
                            'description': f'自动学习: 发现{count}次访问'
                        })
        
        return new_patterns, None
    
    def update_waf_rules(self, auto_apply=False, min_confidence=5):
        new_patterns, error = self.learn_new_patterns(min_occurrences=min_confidence)
        
        if error:
            return {'success': False, 'error': error, 'new_patterns': 0}
        
        if not new_patterns:
            return {'success': True, 'new_patterns': 0, 'message': '未发现新的攻击模式'}
        
        waf_rules = self.load_waf_rules()
        
        if auto_apply:
            for p in new_patterns:
                waf_rules['attack_patterns'].append({
                    'pattern': p['pattern'],
                    'category': p['category'],
                    'description': p['description']
                })
            
            self.save_waf_rules(waf_rules)
            
            learned = self.load_learned_patterns()
            for p in new_patterns:
                learned['patterns'].append({
                    'pattern': p['pattern'],
                    'category': p['category'],
                    'learned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            self.save_learned_patterns(learned)
            
            return {
                'success': True,
                'new_patterns': len(new_patterns),
                'patterns': new_patterns,
                'message': f'已自动添加 {len(new_patterns)} 条新规则到 WAF'
            }
        else:
            return {
                'success': True,
                'new_patterns': len(new_patterns),
                'patterns': new_patterns,
                'message': f'发现 {len(new_patterns)} 条潜在新规则，需要手动确认'
            }
    
    def get_learning_stats(self):
        learned = self.load_learned_patterns()
        waf_rules = self.load_waf_rules()
        
        return {
            'total_waf_rules': len(waf_rules.get('attack_patterns', [])),
            'total_scanner_rules': len(waf_rules.get('scanner_signatures', [])),
            'learned_patterns_count': len(learned.get('patterns', [])),
            'last_learning': learned.get('last_updated', '从未'),
            'recent_patterns': learned.get('patterns', [])[-10:]
        }

class AttackDetector:
    def __init__(self, firewall):
        self.firewall = firewall
        self.ssh_log = '/var/log/auth.log'
        self.nginx_access_log = '/var/log/nginx/access.log'
    
    def detect_ssh_brute_force(self):
        self._log_audit("检测SSH暴力破解...")
        if not os.path.exists(self.ssh_log):
            return []
        
        ssh_threshold = SOAR_CONFIG['ssh_fail_threshold']
        try:
            result = subprocess.run(
                f"tail -n 1000 {self.ssh_log} 2>/dev/null | "
                f"grep -iE 'failed password|invalid user|authentication failure' | "
                f"grep -oE '([0-9]{{1,3}}\\.){{3}}[0-9]{{1,3}}' | "
                f"sort | uniq -c | awk '$1 >= {ssh_threshold} {{print $2}}'",
                shell=True, capture_output=True, text=True, timeout=30
            )
            suspicious_ips = result.stdout.strip().split('\n')
            suspicious_ips = [ip for ip in suspicious_ips if ip and not is_private_ip(ip)]
            
            banned = []
            for ip in suspicious_ips:
                if self.firewall.is_permanent_banned(ip):
                    continue
                
                count = self.firewall.increment_attack_count(ip)
                self._log_detected("SSH暴力破解", ip, count)
                
                if count >= SOAR_CONFIG['max_attack_count']:
                    self.firewall.permanent_ban(ip, f"SSH暴力破解累计{count}次")
                elif not self.firewall.is_temp_banned(ip):
                    self.firewall.temp_ban(ip, "SSH暴力破解")
                banned.append(ip)
            
            return banned
        except Exception as e:
            self._log_audit(f"SSH检测失败: {e}")
            return []
    
    def detect_web_attacks(self):
        self._log_audit("检测Web攻击...")
        if not os.path.exists(self.nginx_access_log):
            return []
        
        attack_patterns = '|'.join([
            'union.*select', 'select.*from', 'insert.*into', 'drop.*table',
            '<script', 'javascript:', 'onerror=', 'onload=', 'alert\\(',
            '\\.\\./', '\\.\\.\\\\\\', '%2e%2e', '%252e',
            '/etc/passwd', '/etc/shadow', '/proc/',
            'cmd\\.exe', 'powershell', 'wget', 'curl.*\\|',
            'eval\\(', 'base64_decode', 'exec\\(', 'system\\('
        ])
        
        web_threshold = SOAR_CONFIG['web_attack_threshold']
        try:
            result = subprocess.run(
                f"tail -n 5000 {self.nginx_access_log} 2>/dev/null | "
                f"grep -iE '{attack_patterns}' | "
                f"grep -oE '([0-9]{{1,3}}\\.){{3}}[0-9]{{1,3}}' | "
                f"sort | uniq -c | awk '$1 >= {web_threshold} {{print $2}}'",
                shell=True, capture_output=True, text=True, timeout=30
            )
            suspicious_ips = result.stdout.strip().split('\n')
            suspicious_ips = [ip for ip in suspicious_ips if ip and not is_private_ip(ip)]
            
            banned = []
            for ip in suspicious_ips:
                if self.firewall.is_permanent_banned(ip):
                    continue
                
                count = self.firewall.increment_attack_count(ip)
                self._log_detected("Web攻击", ip, count)
                
                if count >= SOAR_CONFIG['max_attack_count']:
                    self.firewall.permanent_ban(ip, f"Web攻击累计{count}次")
                elif not self.firewall.is_temp_banned(ip):
                    self.firewall.temp_ban(ip, "Web攻击")
                banned.append(ip)
            
            return banned
        except Exception as e:
            self._log_audit(f"Web攻击检测失败: {e}")
            return []
    
    def detect_scanner_attacks(self):
        self._log_audit("检测扫描器攻击...")
        if not os.path.exists(self.nginx_access_log):
            return []
        
        scan_threshold = SOAR_CONFIG['scan_threshold']
        try:
            result = subprocess.run(
                f"tail -n 5000 {self.nginx_access_log} 2>/dev/null | "
                f'grep \'" 404 \' | '
                f"grep -oE '([0-9]{{1,3}}\\.){{3}}[0-9]{{1,3}}' | "
                f"sort | uniq -c | awk '$1 >= {scan_threshold} {{print $2}}'",
                shell=True, capture_output=True, text=True, timeout=30
            )
            suspicious_ips = result.stdout.strip().split('\n')
            suspicious_ips = [ip for ip in suspicious_ips if ip and not is_private_ip(ip)]
            
            banned = []
            for ip in suspicious_ips:
                if self.firewall.is_permanent_banned(ip):
                    continue
                
                count = self.firewall.increment_attack_count(ip)
                self._log_detected("扫描器攻击", ip, count)
                
                if count >= SOAR_CONFIG['max_attack_count']:
                    self.firewall.permanent_ban(ip, f"扫描器攻击累计{count}次")
                elif not self.firewall.is_temp_banned(ip):
                    self.firewall.temp_ban(ip, "扫描器攻击")
                banned.append(ip)
            
            return banned
        except Exception as e:
            self._log_audit(f"扫描器检测失败: {e}")
            return []
    
    def detect_ddos(self):
        self._log_audit("检测DDoS攻击...")
        if not os.path.exists(self.nginx_access_log):
            return []
        
        time_prefix = datetime.now().strftime('%d/%b/%Y:%H:%M')
        ddos_threshold = SOAR_CONFIG['ddos_threshold']
        
        try:
            result = subprocess.run(
                f"tail -n 10000 {self.nginx_access_log} 2>/dev/null | "
                f"grep '{time_prefix}' | "
                f"grep -oE '([0-9]{{1,3}}\\.){{3}}[0-9]{{1,3}}' | "
                f"sort | uniq -c | awk '$1 >= {ddos_threshold} {{print $2}}'",
                shell=True, capture_output=True, text=True, timeout=30
            )
            suspicious_ips = result.stdout.strip().split('\n')
            suspicious_ips = [ip for ip in suspicious_ips if ip and not is_private_ip(ip)]
            
            banned = []
            for ip in suspicious_ips:
                if self.firewall.is_permanent_banned(ip):
                    continue
                
                count = self.firewall.increment_attack_count(ip)
                self._log_detected("DDoS攻击", ip, count)
                
                if count >= SOAR_CONFIG['max_attack_count']:
                    self.firewall.permanent_ban(ip, f"DDoS攻击累计{count}次")
                elif not self.firewall.is_temp_banned(ip):
                    self.firewall.temp_ban(ip, "DDoS攻击")
                banned.append(ip)
            
            return banned
        except Exception as e:
            self._log_audit(f"DDoS检测失败: {e}")
            return []
    
    def _log_audit(self, msg):
        print(f"[AUDIT] {msg}")
    
    def _log_detected(self, attack_type, ip, count):
        print(f"[DETECTED] {attack_type} - IP: {ip}, 累计攻击次数: {count}")

def format_tracebacks(tracebacks):
    result = []
    for t in tracebacks:
        result.append('```')
        result.append(t)
        result.append('```')
    return chr(10).join(result)

def get_latest_log_file():
    today = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(LOG_DIR, f'bridge_{today}.log')
    if os.path.exists(log_file):
        return log_file
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    log_file = os.path.join(LOG_DIR, f'bridge_{yesterday}.log')
    if os.path.exists(log_file):
        return log_file
    
    log_files = [f for f in os.listdir(LOG_DIR) if f.startswith('bridge_') and f.endswith('.log')]
    if log_files:
        log_files.sort(reverse=True)
        return os.path.join(LOG_DIR, log_files[0])
    
    return None

def extract_ip(line):
    match = re.search(r'\[([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\]', line)
    return match.group(1) if match else None

def analyze_logs(log_file, hours=24):
    stats = {
        'total_lines': 0,
        'errors': [],
        'attacks': [],
        'ip_stats': Counter(),
        'chat_requests': 0,
        'suspicious_ips': set(),
        'rate_limit_hits': 0,
        'empty_requests': 0,
        'error_categories': {
            'http_error': [],
            'api_error': [],
            'code_bug': [],
            'ssl_error': [],
            'system_error': [],
        },
        'error_summary': Counter(),
        'tracebacks': [],
    }
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        in_traceback = False
        current_traceback = []
        
        for line in f:
            stats['total_lines'] += 1
            
            try:
                time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if time_match:
                    line_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                    if line_time < cutoff_time:
                        continue
            except:
                pass
            
            ip = extract_ip(line)
            if ip:
                stats['ip_stats'][ip] += 1
            
            if '[ERROR]' in line:
                stats['errors'].append(line.strip())
            
            if 'Traceback' in line:
                in_traceback = True
                current_traceback = [line.strip()]
            elif in_traceback:
                current_traceback.append(line.strip())
                if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                    in_traceback = False
                    if len(current_traceback) > 1:
                        stats['tracebacks'].append('\n'.join(current_traceback[-10:]))
                    current_traceback = []
            
            for category, patterns in ERROR_PATTERNS.items():
                for pattern, desc in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        stats['error_categories'][category].append({
                            'line': line.strip()[:200],
                            'desc': desc,
                            'ip': ip
                        })
                        stats['error_summary'][desc] += 1
                        break
            
            if 'POST /chat' in line:
                stats['chat_requests'] += 1
            
            if '请求频率超限' in line:
                stats['rate_limit_hits'] += 1
            
            if '空请求体' in line:
                stats['empty_requests'] += 1
            
            for pattern in ATTACK_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    stats['attacks'].append({
                        'ip': ip,
                        'pattern': pattern,
                        'line': line.strip()
                    })
                    if ip:
                        stats['suspicious_ips'].add(ip)
                    break
    
    return stats

def call_minimax_for_analysis(config, stats):
    provider_config = config.get('minimax', {})
    api_key = provider_config.get('api_key', '')
    group_id = provider_config.get('group_id', '')
    
    if not api_key or not group_id:
        return None, "MiniMax API 未配置"
    
    error_category_summary = []
    for cat, errors in stats['error_categories'].items():
        if errors:
            error_category_summary.append(f"- {cat}: {len(errors)} 个")
    
    error_summary_text = '\n'.join([f'- {desc}: {count} 次' for desc, count in stats['error_summary'].most_common(10)]) if stats['error_summary'] else '无'
    
    prompt = f"""你是一个专业的服务器安全和代码质量审计专家。请分析以下服务器日志统计数据，生成一份简洁的中文审计报告。

## 基础统计信息

- 总日志行数: {stats['total_lines']}
- 聊天请求次数: {stats['chat_requests']}
- 错误数量: {len(stats['errors'])}
- 攻击尝试次数: {len(stats['attacks'])}
- 频率限制触发: {stats['rate_limit_hits']}
- 空请求体: {stats['empty_requests']}
- 可疑IP数量: {len(stats['suspicious_ips'])}

## 错误分类统计
{chr(10).join(error_category_summary) if error_category_summary else '无错误'}

## 错误类型详情
{error_summary_text}

## Top 10 访问IP
{chr(10).join([f'- {ip}: {count} 次' for ip, count in stats['ip_stats'].most_common(10)])}

## HTTP/连接错误 (最近5条)
{chr(10).join([f'- [{e["ip"]}] {e["desc"]}: {e["line"][:80]}...' for e in stats['error_categories']['http_error'][-5:]]) if stats['error_categories']['http_error'] else '无'}

## API 错误 (最近5条)
{chr(10).join([f'- {e["desc"]}: {e["line"][:80]}...' for e in stats['error_categories']['api_error'][-5:]]) if stats['error_categories']['api_error'] else '无'}

## 代码 Bug (最近5条)
{chr(10).join([f'- {e["desc"]}: {e["line"][:80]}...' for e in stats['error_categories']['code_bug'][-5:]]) if stats['error_categories']['code_bug'] else '无'}

## Python 异常堆栈 (最近2个)
{format_tracebacks(stats['tracebacks'][-2:]) if stats['tracebacks'] else '无'}

## 攻击尝试 (最近5条)
{chr(10).join([f'- [{a["ip"]}] {a["pattern"]}: {a["line"][:80]}...' for a in stats['attacks'][-5:]]) if stats['attacks'] else '无攻击尝试'}

## 可疑IP列表
{', '.join(stats['suspicious_ips']) if stats['suspicious_ips'] else '无'}

请生成一份包含以下内容的审计报告：
1. 📊 总体评估（安全/警告/危险）
2. 🐛 代码质量分析（是否有 Bug 需要修复）
3. 🔌 API/连接问题分析
4. 🔒 安全风险评估
5. 💡 建议采取的措施

报告要简洁明了，适合通过消息推送发送。重点关注代码 Bug 和需要立即修复的问题。"""

    conn = http.client.HTTPSConnection("api.minimax.chat", timeout=60)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    path = f"/v1/text/chatcompletion_v2?GroupId={group_id}"
    
    try:
        conn.request("POST", path, json.dumps(data), headers)
        response = conn.getresponse()
        result = response.read().decode('utf-8')
        result_json = json.loads(result)
        
        if "choices" in result_json and len(result_json["choices"]) > 0:
            return result_json["choices"][0]["message"]["content"], None
        else:
            error_msg = result_json.get('base_resp', {}).get('status_msg', '未知错误')
            return None, f"API错误: {error_msg}"
    except Exception as e:
        return None, f"请求失败: {str(e)}"
    finally:
        conn.close()

def generate_local_report(stats, soar_status=None):
    report = f"""📊 琥珀冒险 - 日志审计报告
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 基础统计
- 总日志行数: {stats['total_lines']:,}
- 聊天请求: {stats['chat_requests']}
- 错误数量: {len(stats['errors'])}
- 攻击尝试: {len(stats['attacks'])}

🐛 错误分类
"""
    
    for cat, errors in stats['error_categories'].items():
        if errors:
            report += f"- {cat}: {len(errors)} 个\n"
    
    if stats['error_summary']:
        report += "\n❌ 错误类型统计:\n"
        for desc, count in stats['error_summary'].most_common(5):
            report += f"  - {desc}: {count} 次\n"
    
    report += f"""
🚨 安全状态
- 频率限制触发: {stats['rate_limit_hits']}
- 空请求体: {stats['empty_requests']}
- 可疑IP: {len(stats['suspicious_ips'])}

"""
    
    if soar_status:
        report += f"""🛡️ SOAR 安全响应
- 永久封禁IP: {soar_status['permanent_count']}
- 临时封禁IP: {soar_status['temp_count']}
- 累计攻击次数: {soar_status['total_attacks']}

"""
    
    if stats['suspicious_ips']:
        report += f"⚠️ 可疑IP: {', '.join(list(stats['suspicious_ips'])[:10])}\n\n"
    
    if stats['error_categories']['code_bug']:
        report += "🐛 代码 Bug:\n"
        for bug in stats['error_categories']['code_bug'][-3:]:
            report += f"  - {bug['desc']}: {bug['line'][:80]}...\n"
        report += "\n"
    
    if stats['error_categories']['api_error']:
        report += "🔌 API 错误:\n"
        for err in stats['error_categories']['api_error'][-3:]:
            report += f"  - {err['desc']}: {err['line'][:80]}...\n"
        report += "\n"
    
    if stats['error_categories']['http_error']:
        report += "🌐 HTTP/连接错误:\n"
        for err in stats['error_categories']['http_error'][-3:]:
            report += f"  - [{err['ip']}] {err['desc']}\n"
        report += "\n"
    
    if stats['attacks']:
        report += "🔴 攻击尝试:\n"
        for attack in stats['attacks'][-5:]:
            report += f"  - [{attack['ip']}] {attack['pattern']}\n"
        report += "\n"
    
    if stats['tracebacks']:
        report += "📚 Python 异常:\n"
        for tb in stats['tracebacks'][-1:]:
            report += f"```\n{tb[:300]}...\n```\n"
    
    return report

def send_webhook_notification(webhook_url, report):
    import urllib.request
    
    data = json.dumps({"content": report}).encode('utf-8')
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"Webhook 发送失败: {e}")
        return False

def run_soar_mode(mode='audit'):
    alert_manager = AlertManager()
    firewall = FirewallManager()
    detector = AttackDetector(firewall)
    system_monitor = SystemMonitor(alert_manager)
    service_checker = ServiceHealthChecker(alert_manager)
    ssl_checker = SSLCertificateChecker(alert_manager)
    log_cleaner = LogCleaner(alert_manager)
    voice_analyzer = VoiceLogAnalyzer()
    api_checker = APIHealthChecker(alert_manager)
    process_monitor = ProcessMonitor(alert_manager)
    port_monitor = PortMonitor(alert_manager)
    config_auditor = ConfigAuditor(alert_manager)
    alert_notifier = AlertNotifier(alert_manager)
    auto_recovery = AutoRecovery(alert_manager)
    cron_checker = CronJobChecker(alert_manager)
    
    if mode == 'restore':
        log("恢复防火墙规则...")
        firewall.restore_rules()
        log("规则恢复完成")
        return
    
    if mode == 'status':
        status = firewall.get_status()
        alert_summary = alert_manager.get_alert_summary()
        system_stats = system_monitor.check_system_health()
        process_status = process_monitor.check_all_processes()
        port_status = port_monitor.check_all_ports()
        
        print("=" * 60)
        print("       SOAR 安全状态报告")
        print("=" * 60)
        print(f"\n🛡️ 防火墙状态:")
        print(f"  - 永久封禁IP数量: {status['permanent_count']}")
        print(f"  - 临时封禁IP数量: {status['temp_count']}")
        print(f"  - 累计攻击次数: {status['total_attacks']}")
        
        success, output = firewall._run_cmd("iptables -L INPUT -n | grep DROP | wc -l")
        print(f"  - 防火墙规则数量: {output if success else 'N/A'}")
        
        print(f"\n💻 系统状态:")
        print(f"  - CPU: {system_stats['cpu']:.1f}%")
        print(f"  - 内存: {system_stats['memory']}%")
        print(f"  - 磁盘: {system_stats['disk']}%")
        print(f"  - 负载: {', '.join([str(x) for x in system_stats['load']])}")
        
        print(f"\n🔧 进程状态:")
        for pid, pstatus in process_status.items():
            status_icon = "✅" if pstatus['running'] else "❌"
            pid_info = f" (PID: {pstatus['pid']})" if pstatus['pid'] else ""
            print(f"  - {status_icon} {pstatus['name']}{pid_info}")
        
        print(f"\n🌐 端口状态:")
        for port, pstatus in port_status.items():
            status_icon = "✅" if pstatus['listening'] else "❌"
            print(f"  - {status_icon} {pstatus['name']}")
        
        print(f"\n🚨 告警状态:")
        print(f"  - 活跃告警: {alert_summary['total']}")
        print(f"  - Critical: {alert_summary['by_level']['critical']}")
        print(f"  - Error: {alert_summary['by_level']['error']}")
        print(f"  - Warning: {alert_summary['by_level']['warning']}")
        
        print(f"\n📋 最近告警:")
        for alert_type, msg, count in alert_summary['top_issues']:
            print(f"  - [{alert_type}] {msg} ({count}次)")
        
        print("\n📜 最近SOAR日志:")
        if os.path.exists(firewall.soar_log_file):
            with open(firewall.soar_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-10:]
                for line in lines:
                    print("  " + line.rstrip())
        print("\n" + "=" * 60)
        return
    
    if mode == 'health':
        log("========== 健康检查开始 ==========")
        
        system_stats = system_monitor.check_system_health()
        log(f"系统状态: CPU {system_stats['cpu']:.1f}%, 内存 {system_stats['memory']}%, 磁盘 {system_stats['disk']}%")
        
        process_status = process_monitor.check_all_processes()
        for pid, pstatus in process_status.items():
            if pstatus['running']:
                log(f"✅ {pstatus['name']}: 运行中 (PID: {pstatus['pid']})")
            else:
                log(f"❌ {pstatus['name']}: 未运行")
        
        port_status = port_monitor.check_all_ports()
        for port, pstatus in port_status.items():
            if pstatus['listening']:
                log(f"✅ {pstatus['name']}: 监听中")
            else:
                log(f"❌ {pstatus['name']}: 未监听")
        
        service_status = service_checker.check_all_services()
        for service_id, status in service_status.items():
            if status['healthy']:
                log(f"✅ {status['name']}: 正常")
            else:
                log(f"❌ {status['name']}: 异常 - {status.get('error', status.get('status_code'))}")
        
        api_status = api_checker.check_all_apis()
        for api_name, status in api_status.items():
            if status['available']:
                log(f"✅ API {api_name}: 可用")
            else:
                log(f"❌ API {api_name}: 不可用 - {status.get('error', '未知')}")
        
        ssl_status = ssl_checker.check_all_certificates()
        for cert_name, cert_info in ssl_status.items():
            if cert_info:
                if cert_info['valid']:
                    log(f"✅ SSL证书({cert_name}): 有效，剩余 {cert_info['days_left']} 天")
                else:
                    log(f"❌ SSL证书({cert_name}): 已过期")
        
        config_status = config_auditor.check_config_integrity()
        if config_status['modified']:
            log(f"⚠️ 配置文件被修改: {', '.join([os.path.basename(f) for f in config_status['modified']])}")
        else:
            log(f"✅ 配置文件完整性: 正常")
        
        cron_status = cron_checker.check_cron_jobs()
        if cron_status['expected_missing']:
            log(f"⚠️ 定时任务缺失: {', '.join(cron_status['expected_missing'])}")
        
        log_size = log_cleaner.check_and_clean()
        log(f"日志目录大小: {log_size:.1f}MB")
        
        log("========== 健康检查完成 ==========")
        return
    
    if mode == 'restart':
        if len(sys.argv) < 3:
            print("用法: python log_auditor.py restart <service_id>")
            print(f"可用服务: {', '.join(SERVICE_CONFIG.keys())}")
            return
        
        service_id = sys.argv[2]
        success, msg = service_checker.restart_service(service_id)
        if success:
            log(f"✅ 服务 {service_id} 重启成功")
        else:
            log(f"❌ 服务 {service_id} 重启失败: {msg}")
        return
    
    if mode == 'recover':
        log("========== 自动恢复开始 ==========")
        recovery_results = auto_recovery.check_and_recover()
        log(f"检查进程: {recovery_results['processes_checked']} 个")
        log(f"检查端口: {recovery_results['ports_checked']} 个")
        log(f"恢复尝试: {recovery_results['recoveries_attempted']} 次")
        log(f"恢复成功: {recovery_results['recoveries_successful']} 次")
        for action in recovery_results['actions']:
            log(f"  - {action}")
        log("========== 自动恢复完成 ==========")
        return
    
    if mode == 'notify':
        webhook_url = None
        if len(sys.argv) > 2:
            webhook_url = sys.argv[2]
        
        log("========== 发送告警通知 ==========")
        critical_sent = alert_notifier.notify_critical_alerts(webhook_url)
        error_sent = alert_notifier.notify_error_alerts(webhook_url)
        log(f"严重告警通知: {len(critical_sent)} 条")
        log(f"错误告警通知: {len(error_sent)} 条")
        return
    
    if mode == 'init':
        log("========== 初始化审计基线 ==========")
        config_auditor.init_checksums()
        log("配置文件校验和已初始化")
        return
    
    if mode == 'learn':
        log("========== WAF 规则学习 ==========")
        waf_learner = WAFRuleLearner()
        
        auto_apply = False
        min_confidence = 5
        if len(sys.argv) > 2:
            if sys.argv[2] == 'auto':
                auto_apply = True
            elif sys.argv[2].isdigit():
                min_confidence = int(sys.argv[2])
        
        log(f"分析日志中的攻击模式 (最小置信度: {min_confidence})...")
        result = waf_learner.update_waf_rules(auto_apply=auto_apply, min_confidence=min_confidence)
        
        if result['success']:
            log(f"✅ {result['message']}")
            if result.get('patterns'):
                log(f"\n发现的新模式:")
                for p in result['patterns'][:10]:
                    log(f"  - [{p['category']}] {p['pattern']} ({p['count']}次)")
        else:
            log(f"❌ 学习失败: {result.get('error', '未知错误')}")
        
        stats = waf_learner.get_learning_stats()
        log(f"\n📊 WAF 规则统计:")
        log(f"  - 总攻击规则: {stats['total_waf_rules']}")
        log(f"  - 总扫描器规则: {stats['total_scanner_rules']}")
        log(f"  - 已学习规则: {stats['learned_patterns_count']}")
        log(f"  - 上次学习: {stats['last_learning']}")
        log("========== WAF 规则学习完成 ==========")
        return
    
    if mode == 'waf-status':
        waf_learner = WAFRuleLearner()
        stats = waf_learner.get_learning_stats()
        
        print("=" * 60)
        print("       WAF 规则学习状态")
        print("=" * 60)
        print(f"\n📊 规则统计:")
        print(f"  - 总攻击规则: {stats['total_waf_rules']}")
        print(f"  - 总扫描器规则: {stats['total_scanner_rules']}")
        print(f"  - 已学习规则: {stats['learned_patterns_count']}")
        print(f"  - 上次学习: {stats['last_learning']}")
        
        if stats['recent_patterns']:
            print(f"\n📚 最近学习的规则:")
            for p in stats['recent_patterns']:
                print(f"  - [{p['category']}] {p['pattern']} ({p.get('learned_at', 'N/A')})")
        print("\n" + "=" * 60)
        return
    
    log("========== SOAR 安全审计开始 ==========")
    
    firewall.unban_expired()
    
    ssh_banned = detector.detect_ssh_brute_force()
    web_banned = detector.detect_web_attacks()
    scan_banned = detector.detect_scanner_attacks()
    ddos_banned = detector.detect_ddos()
    
    system_stats = system_monitor.check_system_health()
    log(f"系统监控: CPU {system_stats['cpu']:.1f}%, 内存 {system_stats['memory']}%, 磁盘 {system_stats['disk']}%")
    
    process_status = process_monitor.check_all_processes()
    dead_processes = [p for p in process_status.values() if not p['running']]
    if dead_processes:
        log(f"⚠️ 发现 {len(dead_processes)} 个进程未运行")
    
    port_status = port_monitor.check_all_ports()
    dead_ports = [p for p in port_status.values() if not p['listening']]
    if dead_ports:
        log(f"⚠️ 发现 {len(dead_ports)} 个端口未监听")
    
    service_status = service_checker.check_all_services()
    unhealthy_services = [s for s in service_status.values() if not s['healthy']]
    if unhealthy_services:
        log(f"⚠️ 发现 {len(unhealthy_services)} 个服务异常")
    
    api_status = api_checker.check_all_apis()
    unavailable_apis = [name for name, status in api_status.items() if not status['available']]
    if unavailable_apis:
        log(f"⚠️ API 不可用: {', '.join(unavailable_apis)}")
    
    ssl_status = ssl_checker.check_all_certificates()
    for cert_name, cert_info in ssl_status.items():
        if cert_info and cert_info['days_left'] <= 30:
            log(f"⚠️ SSL证书({cert_name})将在 {cert_info['days_left']} 天后过期")
    
    config_status = config_auditor.check_config_integrity()
    if config_status['modified']:
        log(f"⚠️ 配置文件被修改: {', '.join([os.path.basename(f) for f in config_status['modified']])}")

    voice_log = voice_analyzer.get_latest_voice_log()
    if voice_log:
        voice_stats = voice_analyzer.analyze_voice_logs(voice_log)
        if voice_stats['errors']:
            log(f"语音服务: 发现 {len(voice_stats['errors'])} 个错误")
    
    cron_status = cron_checker.check_cron_jobs()
    if cron_status['expected_missing']:
        log(f"⚠️ 定时任务缺失: {', '.join(cron_status['expected_missing'])}")
    
    waf_learner = WAFRuleLearner()
    log("学习新的攻击模式...")
    waf_result = waf_learner.update_waf_rules(auto_apply=True, min_confidence=5)
    if waf_result['success'] and waf_result['new_patterns'] > 0:
        log(f"✅ WAF规则学习: 新增 {waf_result['new_patterns']} 条规则")
        for p in waf_result.get('patterns', [])[:5]:
            log(f"  - [{p['category']}] {p['pattern']}")
    elif waf_result['success']:
        log("WAF规则学习: 未发现新的攻击模式")
    else:
        log(f"⚠️ WAF规则学习失败: {waf_result.get('error', '未知错误')}")
    
    log_size = log_cleaner.check_and_clean()
    
    log(f"========== SOAR 安全审计完成 ==========")
    log(f"SSH暴力破解封禁: {len(ssh_banned)} 个IP")
    log(f"Web攻击封禁: {len(web_banned)} 个IP")
    log(f"扫描器封禁: {len(scan_banned)} 个IP")
    log(f"DDoS封禁: {len(ddos_banned)} 个IP")
    
    alert_summary = alert_manager.get_alert_summary()
    if alert_summary['total'] > 0:
        log(f"活跃告警: {alert_summary['total']} 个 (Critical: {alert_summary['by_level']['critical']}, Error: {alert_summary['by_level']['error']})")

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == 'soar':
            run_soar_mode('audit')
            return
        elif arg == 'restore':
            run_soar_mode('restore')
            return
        elif arg == 'status':
            run_soar_mode('status')
            return
        elif arg == 'health':
            run_soar_mode('health')
            return
        elif arg == 'restart':
            run_soar_mode('restart')
            return
        elif arg == 'recover':
            run_soar_mode('recover')
            return
        elif arg == 'notify':
            run_soar_mode('notify')
            return
        elif arg == 'init':
            run_soar_mode('init')
            return
        elif arg == 'learn':
            run_soar_mode('learn')
            return
        elif arg == 'waf-status':
            run_soar_mode('waf-status')
            return
        elif arg == 'help' or arg == '--help' or arg == '-h':
            print("=" * 60)
            print("  琥珀冒险 - 日志审计与安全响应系统 (SOAR)")
            print("=" * 60)
            print("\n用法: python log_auditor.py [命令] [参数]")
            print("\n命令:")
            print("  (无参数)    - 运行日志审计分析")
            print("  soar        - 运行完整的 SOAR 安全审计")
            print("  status      - 显示系统安全状态")
            print("  health      - 运行健康检查")
            print("  restart <服务ID> - 重启指定服务")
            print("  recover     - 自动恢复异常服务")
            print("  notify [webhook_url] - 发送告警通知")
            print("  init        - 初始化审计基线")
            print("  restore     - 恢复防火墙规则")
            print("  learn       - 学习新的攻击模式并更新WAF规则")
            print("  waf-status  - 查看WAF规则学习状态")
            print("\n可用服务ID:")
            for service_id in SERVICE_CONFIG:
                print(f"  - {service_id}")
            print("\n示例:")
            print("  python log_auditor.py          # 日志审计")
            print("  python log_auditor.py soar     # SOAR 审计")
            print("  python log_auditor.py status   # 查看状态")
            print("  python log_auditor.py health   # 健康检查")
            print("  python log_auditor.py restart nanobot_bridge  # 重启服务")
            print("  python log_auditor.py recover  # 自动恢复")
            print("  python log_auditor.py learn    # 学习新攻击模式(预览)")
            print("  python log_auditor.py learn auto  # 自动添加新规则")
            print("  python log_auditor.py learn 3  # 使用更低置信度学习")
            print("  python log_auditor.py waf-status  # 查看WAF学习状态")
            print("=" * 60)
            return
    
    print("=" * 50)
    print("  琥珀冒险 - 日志审计程序")
    print("=" * 50)
    
    config = load_config()
    
    log_file = get_latest_log_file()
    if not log_file:
        print("❌ 未找到日志文件")
        return
    
    print(f"📄 分析日志文件: {log_file}")
    
    hours = 24
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except:
            pass
    
    print(f"⏱️ 分析时间范围: 最近 {hours} 小时")
    
    stats = analyze_logs(log_file, hours)
    
    print(f"\n📊 统计结果:")
    print(f"  - 总日志行数: {stats['total_lines']:,}")
    print(f"  - 聊天请求: {stats['chat_requests']}")
    print(f"  - 错误数量: {len(stats['errors'])}")
    print(f"  - 攻击尝试: {len(stats['attacks'])}")
    print(f"  - 可疑IP: {len(stats['suspicious_ips'])}")
    
    if any(stats['error_categories'].values()):
        print(f"\n🐛 错误分类:")
        for cat, errors in stats['error_categories'].items():
            if errors:
                print(f"  - {cat}: {len(errors)} 个")
    
    if stats['error_summary']:
        print(f"\n❌ 错误类型 Top 5:")
        for desc, count in stats['error_summary'].most_common(5):
            print(f"  - {desc}: {count} 次")
    
    print("\n🤖 调用 MiniMax API 进行分析...")
    ai_report, error = call_minimax_for_analysis(config, stats)
    
    if ai_report:
        print("\n" + "=" * 50)
        print("  AI 审计报告")
        print("=" * 50)
        print(ai_report)
    else:
        print(f"\n⚠️ AI 分析失败: {error}")
        print("\n生成基础报告...")
        local_report = generate_local_report(stats)
        print(local_report)
    
    report_file = os.path.join(LOG_DIR, f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    final_report = ai_report if ai_report else generate_local_report(stats)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(final_report)
    print(f"\n💾 报告已保存: {report_file}")
    
    webhook_url = os.environ.get('AUDIT_WEBHOOK_URL', config.get('audit', {}).get('webhook_url', ''))
    if webhook_url:
        print("\n📤 发送 Webhook 通知...")
        if send_webhook_notification(webhook_url, final_report):
            print("✅ Webhook 通知发送成功")
        else:
            print("❌ Webhook 通知发送失败")
    
    print("\n✅ 审计完成")

if __name__ == "__main__":
    main()
