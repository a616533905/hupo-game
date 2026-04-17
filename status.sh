#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 服务状态"
echo "========================================"
echo ""

SHOW_LOGS=0
if [[ "$1" == "--logs" ]] || [[ "$1" == "-l" ]]; then
    SHOW_LOGS=1
fi

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
BRIDGE_PID=$(pgrep -f "nanobot_bridge.py" 2>/dev/null | head -1)
if [ -n "$BRIDGE_PID" ]; then
    echo "  AI Bridge: 运行中 (PID: $BRIDGE_PID)"
else
    echo "  AI Bridge: 未运行"
fi

VOICE_PID=$(pgrep -f "voice-proxy.js" 2>/dev/null | head -1)
if [ -n "$VOICE_PID" ]; then
    echo "  Voice Proxy: 运行中 (PID: $VOICE_PID)"
else
    echo "  Voice Proxy: 未运行"
fi
echo ""

echo "【系统资源】"
echo "  CPU使用率: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "  内存使用: $(free -m | awk 'NR==2{printf "%.1f%% (%dMB/%dMB)", $3*100/$2, $3, $2}')"
echo "  磁盘使用: $(df -h / | awk 'NR==2{print $5 " (" $3 "/" $2 ")"}')"
echo ""

echo "【进程信息】"
if [ -n "$BRIDGE_PID" ]; then
    UPTIME=$(ps -o etime= -p $BRIDGE_PID 2>/dev/null | tr -d ' ')
    echo "  Bridge PID: $BRIDGE_PID (运行时间: $UPTIME)"
else
    echo "  Bridge PID: 未运行"
fi

if [ -n "$VOICE_PID" ]; then
    echo "  Voice PID: $VOICE_PID"
else
    echo "  Voice PID: 未运行"
fi
echo ""

echo "【端口监听】"
if command -v netstat &> /dev/null; then
    netstat -tlnp 2>/dev/null | grep -E ":($HTTP_PORT|$VOICE_PORT)\s" | awk '{print "  " $4}' || echo "  无端口监听"
elif command -v ss &> /dev/null; then
    ss -tlnp 2>/dev/null | grep -E ":($HTTP_PORT|$VOICE_PORT)\s" | awk '{print "  " $4}' || echo "  无端口监听"
else
    echo "  无法检查端口"
fi
echo ""

echo "【最近错误日志】"
LOG_DIR="/root/hupo-game/logs"
if [ -d "$LOG_DIR" ]; then
    echo "  --- Bridge 错误 (最近10条) ---"
    BRIDGE_ERRORS=$(grep '\[ERROR\]' "$LOG_DIR"/bridge_*.log 2>/dev/null | tail -10)
    if [ -n "$BRIDGE_ERRORS" ]; then
        echo "$BRIDGE_ERRORS" | while read line; do echo "    $line"; done
    else
        echo "    无错误"
    fi
    echo ""
    echo "  --- Voice 错误 (最近10条) ---"
    VOICE_ERRORS=$(grep '\[ERROR\]' "$LOG_DIR"/voice_*.log 2>/dev/null | tail -10)
    if [ -n "$VOICE_ERRORS" ]; then
        echo "$VOICE_ERRORS" | while read line; do echo "    $line"; done
    else
        echo "    无错误"
    fi
else
    echo "  日志目录不存在"
fi
echo ""

echo "【请求统计】"
if command -v curl &> /dev/null; then
    STATS=$(curl -s http://127.0.0.1:$HTTP_PORT/health 2>/dev/null)
    if [ -n "$STATS" ]; then
        TOTAL=$(echo $STATS | python3 -c "import sys,json; print(json.load(sys.stdin).get('requests_total','N/A'))" 2>/dev/null || echo 'N/A')
        UPTIME_HRS=$(echo $STATS | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d.get('uptime',0)/3600,1))" 2>/dev/null || echo 'N/A')
        echo "  总请求: $TOTAL"
        echo "  运行时间: ${UPTIME_HRS} 小时"
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

if [ $SHOW_LOGS -eq 1 ]; then
    echo "========================================"
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
else
    echo "========================================"
    echo ""
    echo "提示: 使用 ./status.sh --logs 或 ./status.sh -l 查看完整日志"
    echo ""
    echo "停止服务: ./stop.sh"
    echo "强制停止: ./stop.sh --force"
    echo ""
    echo "========================================"
fi
