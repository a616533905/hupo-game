#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 安装脚本"
echo "========================================"
echo ""

INSTALL_DIR="/root/hupo-game"

if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 权限运行此脚本"
    echo "sudo ./install.sh"
    exit 1
fi

echo "[1/10] 检查依赖..."
if ! command -v python3 &> /dev/null; then
    echo "正在安装 Python3..."
    apt-get update
    apt-get install -y python3 python3-pip python3-psutil
fi

if ! command -v node &> /dev/null; then
    echo "正在安装 Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

echo "[2/10] 安装 Python 依赖..."
if command -v pip3 &> /dev/null; then
    pip3 install psutil --break-system-packages 2>/dev/null || pip3 install psutil
elif command -v pip &> /dev/null; then
    pip install psutil --break-system-packages 2>/dev/null || pip install psutil
else
    echo "尝试使用 apt 安装 psutil..."
    apt-get install -y python3-psutil
fi

echo "[3/10] 创建安装目录..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs
mkdir -p $INSTALL_DIR/data

echo "[4/10] 复制文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp -r $SCRIPT_DIR/* $INSTALL_DIR/
else
    echo "  已在安装目录，跳过复制"
fi

echo "[5/10] 安装 Systemd 服务..."
cp $INSTALL_DIR/hupo-bridge.service /etc/systemd/system/
cp $INSTALL_DIR/hupo-voice.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hupo-bridge
systemctl enable hupo-voice

echo "[6/10] 设置权限..."
chmod +x $INSTALL_DIR/start.sh
chmod +x $INSTALL_DIR/stop.sh
chmod +x $INSTALL_DIR/install.sh
chmod +x $INSTALL_DIR/uninstall.sh
chmod +x $INSTALL_DIR/status.sh
chmod +x $INSTALL_DIR/cron/health_check.sh
chmod +x $INSTALL_DIR/cron/log_auditor.py
chmod 644 /etc/systemd/system/hupo-bridge.service
chmod 644 /etc/systemd/system/hupo-voice.service

echo ""
echo "  配置日志轮转..."
if [ -f "$INSTALL_DIR/logrotate.conf" ]; then
    cp $INSTALL_DIR/logrotate.conf /etc/logrotate.d/hupo-game
    chmod 644 /etc/logrotate.d/hupo-game
    echo "  已安装 logrotate 配置"
else
    echo "  logrotate.conf 不存在，跳过"
fi

echo "[7/10] 初始化 SOAR 数据文件..."
if [ ! -f "$INSTALL_DIR/data/blacklist.json" ]; then
    python3 -c "import json; json.dump({'permanent':[]}, open('$INSTALL_DIR/data/blacklist.json','w'))"
    echo "  已创建 blacklist.json"
else
    echo "  blacklist.json 已存在，跳过"
fi
if [ ! -f "$INSTALL_DIR/data/temp_ban.json" ]; then
    python3 -c "import json; json.dump({}, open('$INSTALL_DIR/data/temp_ban.json','w'))"
    echo "  已创建 temp_ban.json"
else
    echo "  temp_ban.json 已存在，跳过"
fi
if [ ! -f "$INSTALL_DIR/data/attack_count.json" ]; then
    python3 -c "import json; json.dump({}, open('$INSTALL_DIR/data/attack_count.json','w'))"
    echo "  已创建 attack_count.json"
else
    echo "  attack_count.json 已存在，跳过"
fi
if [ ! -f "$INSTALL_DIR/data/alerts.json" ]; then
    python3 -c "import json; json.dump({'active':{}, 'escalation_count':{}}, open('$INSTALL_DIR/data/alerts.json','w'))"
    echo "  已创建 alerts.json"
else
    echo "  alerts.json 已存在，跳过"
fi
if [ ! -f "$INSTALL_DIR/data/alert_history.json" ]; then
    python3 -c "import json; json.dump([], open('$INSTALL_DIR/data/alert_history.json','w'))"
    echo "  已创建 alert_history.json"
else
    echo "  alert_history.json 已存在，跳过"
fi

echo ""
echo "  初始化 WAF 规则配置..."
if [ ! -f "$INSTALL_DIR/waf_rules.json" ]; then
    if [ -f "$INSTALL_DIR/waf_rules.example.json" ]; then
        cp "$INSTALL_DIR/waf_rules.example.json" "$INSTALL_DIR/waf_rules.json"
        echo "  已从 waf_rules.example.json 创建 waf_rules.json"
    else
        echo "  waf_rules.example.json 不存在，跳过"
    fi
else
    echo "  waf_rules.json 已存在，跳过"
fi

if [ ! -f "$INSTALL_DIR/error_codes.json" ]; then
    if [ -f "$INSTALL_DIR/error_codes.example.json" ]; then
        cp "$INSTALL_DIR/error_codes.example.json" "$INSTALL_DIR/error_codes.json"
        echo "  已从 error_codes.example.json 创建 error_codes.json"
    else
        echo "  error_codes.example.json 不存在，跳过"
    fi
else
    echo "  error_codes.json 已存在，跳过"
fi

echo ""
echo "  初始化审计基线..."
/usr/bin/python3 $INSTALL_DIR/cron/log_auditor.py init
echo "  配置文件校验和已初始化"

echo "[8/10] 配置定时任务 (Cron)..."
CRON_DIR="$INSTALL_DIR/cron"

CRON_HEALTH="*/5 * * * * $CRON_DIR/health_check.sh >> $INSTALL_DIR/logs/health_check.log 2>&1"
CRON_AUDIT="0 3 * * * cd $INSTALL_DIR && /usr/bin/python3 $CRON_DIR/log_auditor.py 24 >> $INSTALL_DIR/logs/audit_cron.log 2>&1"
CRON_SOAR="*/5 * * * * /usr/bin/python3 $CRON_DIR/log_auditor.py soar >> $INSTALL_DIR/logs/soar.log 2>&1"
CRON_RECOVER="*/10 * * * * /usr/bin/python3 $CRON_DIR/log_auditor.py recover >> $INSTALL_DIR/logs/recover.log 2>&1"
CRON_HEALTH_FULL="0 */6 * * * /usr/bin/python3 $CRON_DIR/log_auditor.py health >> $INSTALL_DIR/logs/health_full.log 2>&1"
CRON_RESTART="0 3 * * * $INSTALL_DIR/start.sh >> $INSTALL_DIR/logs/restart.log 2>&1"

if ! crontab -l 2>/dev/null | grep -q "health_check.sh"; then
    (crontab -l 2>/dev/null; echo "$CRON_HEALTH") | crontab -
    echo "  已添加健康检查任务 (每5分钟)"
else
    echo "  健康检查任务已存在"
fi

if ! crontab -l 2>/dev/null | grep -q "log_auditor.py 24"; then
    (crontab -l 2>/dev/null; echo "$CRON_AUDIT") | crontab -
    echo "  已添加日志审计任务 (每天凌晨3点)"
else
    echo "  日志审计任务已存在"
fi

if ! crontab -l 2>/dev/null | grep -q "log_auditor.py soar"; then
    (crontab -l 2>/dev/null; echo "$CRON_SOAR") | crontab -
    echo "  已添加 SOAR 安全审计任务 (每5分钟)"
else
    echo "  SOAR 安全审计任务已存在"
fi

if ! crontab -l 2>/dev/null | grep -q "log_auditor.py recover"; then
    (crontab -l 2>/dev/null; echo "$CRON_RECOVER") | crontab -
    echo "  已添加自动恢复任务 (每10分钟)"
else
    echo "  自动恢复任务已存在"
fi

if ! crontab -l 2>/dev/null | grep -q "log_auditor.py health"; then
    (crontab -l 2>/dev/null; echo "$CRON_HEALTH_FULL") | crontab -
    echo "  已添加完整健康检查任务 (每6小时)"
else
    echo "  完整健康检查任务已存在"
fi

if ! crontab -l 2>/dev/null | grep -q "start.sh"; then
    (crontab -l 2>/dev/null; echo "$CRON_RESTART") | crontab -
    echo "  已添加服务重启任务 (每天凌晨3点)"
else
    echo "  服务重启任务已存在"
fi

echo ""
echo "  当前定时任务列表:"
crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$"

echo "[9/10] 创建 SOAR 管理命令..."
cat > /usr/local/bin/soar << 'SOAR_EOF'
#!/bin/bash
INSTALL_DIR="/root/hupo-game"
DATA_DIR="$INSTALL_DIR/data"
CRON_DIR="$INSTALL_DIR/cron"

case "$1" in
    status)
        /usr/bin/python3 $CRON_DIR/log_auditor.py status
        ;;
    run)
        /usr/bin/python3 $CRON_DIR/log_auditor.py soar
        ;;
    health)
        /usr/bin/python3 $CRON_DIR/log_auditor.py health
        ;;
    recover)
        /usr/bin/python3 $CRON_DIR/log_auditor.py recover
        ;;
    restore)
        /usr/bin/python3 $CRON_DIR/log_auditor.py restore
        ;;
    notify)
        /usr/bin/python3 $CRON_DIR/log_auditor.py notify "$2"
        ;;
    logs)
        tail -f $INSTALL_DIR/logs/soar.log
        ;;
    list)
        echo "=== 永久封禁IP ==="
        python3 -c "import json; data=json.load(open('$DATA_DIR/blacklist.json')); [print(ip) for ip in data.get('permanent',[])]"
        echo ""
        echo "=== 临时封禁IP ==="
        python3 -c "import json; import time; data=json.load(open('$DATA_DIR/temp_ban.json')); [print(f'{ip} -> {time.strftime(\"%Y-%m-%d %H:%M:%S\", time.localtime(t))}') for ip,t in data.items() if time.time() < t]"
        ;;
    alerts)
        echo "=== 活跃告警 ==="
        python3 -c "
import json
try:
    data = json.load(open('$DATA_DIR/alerts.json'))
    active = data.get('active', {})
    if not active:
        print('无活跃告警')
    else:
        for key, alert in active.items():
            level = alert.get('level', 'unknown')
            icon = {'critical': '🚨', 'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(level, '❓')
            print(f\"{icon} [{level.upper()}] {alert.get('type', '')}: {alert.get('message', '')} ({alert.get('count', 0)}次)\")
except Exception as e:
    print(f'读取告警失败: {e}')
"
        ;;
    unban)
        if [ -z "$2" ]; then
            echo "用法: soar unban <IP>"
            exit 1
        fi
        IP=$2
        iptables -D INPUT -s "$IP" -j DROP 2>/dev/null || true
        python3 -c "import json; data=json.load(open('$DATA_DIR/blacklist.json')); data['permanent']=[ip for ip in data.get('permanent',[]) if ip!='$IP']; json.dump(data, open('$DATA_DIR/blacklist.json','w'))"
        python3 -c "import json; data=json.load(open('$DATA_DIR/temp_ban.json')); data.pop('$IP', None); json.dump(data, open('$DATA_DIR/temp_ban.json','w'))"
        echo "IP $IP 已解封"
        ;;
    ban)
        if [ -z "$2" ]; then
            echo "用法: soar ban <IP> [reason]"
            exit 1
        fi
        IP=$2
        REASON=${3:-"手动封禁"}
        iptables -I INPUT -s "$IP" -j DROP
        python3 -c "import json; data=json.load(open('$DATA_DIR/blacklist.json')); data.setdefault('permanent',[]); data['permanent'].append('$IP'); json.dump(data, open('$DATA_DIR/blacklist.json','w'))"
        echo "IP $IP 已永久封禁 - $REASON"
        ;;
    stats)
        echo "=== 攻击统计 ==="
        python3 -c "import json; data=json.load(open('$DATA_DIR/attack_count.json')); sorted_data=sorted(data.items(), key=lambda x: x[1], reverse=True)[:20]; [print(f'{ip}: {count}次') for ip, count in sorted_data]"
        ;;
    restart)
        if [ -z "$2" ]; then
            echo "用法: soar restart <service>"
            echo "可用服务: nanobot_bridge, voice_proxy, nginx"
            exit 1
        fi
        /usr/bin/python3 $CRON_DIR/log_auditor.py restart "$2"
        ;;
    cron)
        echo "=== 定时任务状态 ==="
        crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$"
        ;;
    api)
        echo "=== API 状态检查 ==="
        python3 -c "
import sys
sys.path.insert(0, '$CRON_DIR')
from log_auditor import APIHealthChecker, AlertManager, load_config
config = load_config()
alert_mgr = AlertManager()
checker = APIHealthChecker(alert_mgr)
results = checker.check_all_apis()
for name, status in results.items():
    icon = '✅' if status['available'] else '❌'
    error = status.get('error', '') if not status['available'] else ''
    print(f'{icon} {name}: {\"可用\" if status[\"available\"] else error}')
"
        ;;
    init)
        echo "初始化审计基线..."
        cd $INSTALL_DIR && /usr/bin/python3 $CRON_DIR/log_auditor.py init
        echo "完成"
        ;;
    help|--help|-h)
        echo "SOAR 安全系统管理命令"
        echo ""
        echo "用法: soar <command> [args]"
        echo ""
        echo "命令:"
        echo "  status          - 显示系统状态"
        echo "  run             - 手动运行一次安全审计"
        echo "  health          - 运行完整健康检查"
        echo "  recover         - 自动恢复异常服务"
        echo "  restore         - 恢复防火墙规则"
        echo "  notify [url]    - 发送告警通知"
        echo "  logs            - 查看实时日志"
        echo "  list            - 列出封禁IP"
        echo "  alerts          - 显示活跃告警"
        echo "  ban <IP> [reason] - 永久封禁IP"
        echo "  unban <IP>      - 解封IP"
        echo "  stats           - 显示攻击统计"
        echo "  restart <service> - 重启服务"
        echo "  cron            - 显示定时任务"
        echo "  api             - 检查API状态"
        echo "  init            - 初始化审计基线"
        ;;
    *)
        /usr/bin/python3 $CRON_DIR/log_auditor.py help
        ;;
esac
SOAR_EOF
chmod +x /usr/local/bin/soar

echo ""
echo "[10/10] 恢复防火墙规则..."
/usr/bin/python3 $INSTALL_DIR/cron/log_auditor.py restore
echo "  防火墙规则已恢复"

echo ""
echo "========================================"
echo "  安装完成！"
echo "========================================"
echo ""
echo "配置文件: $INSTALL_DIR/config.json"
echo "日志目录: $INSTALL_DIR/logs/"
echo "数据目录: $INSTALL_DIR/data/"
echo ""
echo "【端口配置】"
echo "  HTTP端口: 80"
echo "  HTTPS端口: 443"
echo "  Voice端口: 85"
echo ""
echo "【启动方式】"
echo "  方式1 (推荐): systemctl start hupo-bridge hupo-voice"
echo "  方式2 (脚本): cd $INSTALL_DIR && ./start.sh"
echo ""
echo "【定时任务】"
echo "  健康检查: 每5分钟 (health_check.sh)"
echo "  SOAR审计: 每5分钟 (log_auditor.py soar)"
echo "  自动恢复: 每10分钟 (log_auditor.py recover)"
echo "  完整检查: 每6小时 (log_auditor.py health)"
echo "  日志审计: 每天3点 (log_auditor.py 24)"
echo "  服务重启: 每天3点 (start.sh)"
echo ""
echo "【SOAR 安全系统命令】"
echo "  soar status    - 显示系统状态"
echo "  soar health    - 完整健康检查"
echo "  soar recover   - 自动恢复异常服务"
echo "  soar run       - 手动运行安全审计"
echo "  soar alerts    - 显示活跃告警"
echo "  soar list      - 列出封禁IP"
echo "  soar stats     - 显示攻击统计"
echo "  soar api       - 检查API状态"
echo "  soar ban <IP>  - 封禁IP"
echo "  soar unban <IP> - 解封IP"
echo "  soar restart <service> - 重启服务"
echo "  soar cron      - 显示定时任务"
echo "  soar notify [url] - 发送告警通知"
echo ""
echo "【联动功能】"
echo "  - 进程异常自动检测并告警"
echo "  - 端口异常自动检测并告警"
echo "  - API不可用自动检测并告警"
echo "  - SSL证书过期自动告警"
echo "  - 配置文件篡改自动告警"
echo "  - 攻击检测自动封禁IP"
echo "  - 服务异常自动尝试恢复"
echo ""
echo "【常用命令】"
echo "  启动服务: systemctl start hupo-bridge hupo-voice"
echo "  停止服务: systemctl stop hupo-bridge hupo-voice"
echo "  查看状态: ./status.sh 或 soar status"
echo "  查看日志: journalctl -u hupo-bridge -f"
echo "  查看告警: soar alerts"
echo ""
echo "========================================"
