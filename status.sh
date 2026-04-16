#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 服务状态"
echo "========================================"
echo ""

CONFIG_FILE="/root/hupo-game/config.json"

load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        HTTP_PORT=$(grep -o '"http_port"[[:space:]]*:[[:space:]]*[0-9]*' "$CONFIG_FILE" | grep -o '[0-9]*$' | head -1)
        VOICE_PORT=$(grep -o '"voice_port"[[:space:]]*:[[:space:]]*[0-9]*' "$CONFIG_FILE" | grep -o '[0-9]*$' | head -1)
    fi
    HTTP_PORT=${HTTP_PORT:-80}
    VOICE_PORT=${VOICE_PORT:-85}
}

load_config

echo "【服务状态】"
systemctl is-active hupo-bridge > /dev/null 2>&1 && echo "  hupo-bridge: 运行中" || echo "  hupo-bridge: 未运行"
systemctl is-active hupo-voice > /dev/null 2>&1 && echo "  hupo-voice: 运行中" || echo "  hupo-voice: 未运行"
echo ""

echo "【系统资源】"
echo "  CPU使用率: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "  内存使用: $(free -m | awk 'NR==2{printf "%.1f%% (%dMB/%dMB)", $3*100/$2, $3, $2}')"
echo "  磁盘使用: $(df -h / | awk 'NR==2{print $5 " (" $3 "/" $2 ")"}')"
echo ""

echo "【进程信息】"
BRIDGE_PID=$(pgrep -f "nanobot_bridge.py" | head -1)
if [ -n "$BRIDGE_PID" ]; then
    UPTIME=$(ps -o etime= -p $BRIDGE_PID | tr -d ' ')
    echo "  Bridge PID: $BRIDGE_PID (运行时间: $UPTIME)"
else
    echo "  Bridge PID: 未运行"
fi

VOICE_PID=$(pgrep -f "voice-proxy.js" | head -1)
if [ -n "$VOICE_PID" ]; then
    echo "  Voice PID: $VOICE_PID"
else
    echo "  Voice PID: 未运行"
fi
echo ""

echo "【端口监听】"
netstat -tlnp 2>/dev/null | grep -E ":($HTTP_PORT|$VOICE_PORT)\s" | awk '{print "  " $4}' || ss -tlnp | grep -E ":($HTTP_PORT|$VOICE_PORT)\s" | awk '{print "  " $4}'
echo ""

echo "【最近错误日志】"
LOG_DIR="/root/hupo-game/logs"
if [ -d "$LOG_DIR" ]; then
    echo "  --- Bridge 错误 (最近10条) ---"
    grep '\[ERROR\]' "$LOG_DIR"/bridge_*.log 2>/dev/null | tail -10 | while read line; do echo "    $line"; done
    echo ""
    echo "  --- Voice 错误 (最近10条) ---"
    grep '\[ERROR\]' "$LOG_DIR"/voice_*.log 2>/dev/null | tail -10 | while read line; do echo "    $line"; done
else
    echo "  日志目录不存在"
fi
echo ""

echo "【请求统计】"
if command -v curl &> /dev/null; then
    STATS=$(curl -s http://127.0.0.1:$HTTP_PORT/health 2>/dev/null)
    if [ -n "$STATS" ]; then
        echo "  总请求: $(echo $STATS | python3 -c "import sys,json; print(json.load(sys.stdin).get('requests_total','N/A'))" 2>/dev/null || echo 'N/A')"
        echo "  运行时间: $(echo $STATS | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d.get('uptime',0)/3600,1), '小时')" 2>/dev/null || echo 'N/A')"
    else
        echo "  无法获取（服务未启动）"
    fi
else
    echo "  需要 curl 命令"
fi
echo ""

echo "【配置信息】"
echo "  HTTP端口: $HTTP_PORT"
echo "  Voice端口: $VOICE_PORT"
echo ""

echo "========================================"
echo ""
read -p "按回车键查看完整日志..."
echo ""

echo "【Bridge 完整日志 (最近30行)】"
if [ -f "$LOG_DIR"/bridge_*.log ]; then
    tail -30 "$LOG_DIR"/bridge_*.log 2>/dev/null | head -30
else
    echo "  未找到 Bridge 日志"
fi
echo ""

echo "【Voice 完整日志 (最近30行)】"
if [ -f "$LOG_DIR"/voice_*.log ]; then
    tail -30 "$LOG_DIR"/voice_*.log 2>/dev/null | head -30
else
    echo "  未找到 Voice 日志"
fi
echo ""

echo "========================================"
