#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日志审计程序 - 使用 MiniMax API 分析日志并生成报告"""

import json
import os
import sys
import http.client
import re
from datetime import datetime, timedelta
from collections import Counter

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
LOG_DIR = os.path.join(PROJECT_DIR, 'logs')

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

SUSPICIOUS_IPS = {}

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

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
{chr(10).join([f'```\n{t}\n```' for t in stats['tracebacks'][-2:]]) if stats['tracebacks'] else '无'}

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

def generate_local_report(stats):
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
    
    if stats['suspicious_ips']:
        report += f"⚠️ 可疑IP: {', '.join(stats['suspicious_ips'])}\n\n"
    
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

def main():
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
