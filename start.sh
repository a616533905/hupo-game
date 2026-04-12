#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 游戏服务器启动脚本"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/4] 读取配置文件..."
if [ -f "config.json" ]; then
    API_PORT=$(grep -o '"api_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    VOICE_PORT=$(grep -o '"voice_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    ACCESS_TOKEN=$(grep -o '"access_token"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
fi

API_PORT=${API_PORT:-80}
VOICE_PORT=${VOICE_PORT:-85}
ACCESS_TOKEN=${ACCESS_TOKEN:-hupo_secret_token_2024}

echo "  API端口: $API_PORT"
echo "  语音端口: $VOICE_PORT"
echo ""

echo "[2/4] 清理端口..."
pkill -f "nanobot_bridge.py" 2>/dev/null
pkill -f "voice-proxy.js" 2>/dev/null
sleep 2

echo "[3/4] 启动 AI Bridge (端口 $API_PORT, 含Web服务)..."
API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py &
API_PID=$!
echo "API Server PID: $API_PID"

echo "[4/4] 启动语音代理 (端口 $VOICE_PORT)..."
VOICE_PORT=$VOICE_PORT node voice-proxy.js &
VOICE_PID=$!
echo "Voice Server PID: $VOICE_PID"

sleep 3

echo ""
echo "========================================"
echo "  所有服务已启动！"
echo "========================================"
echo ""
echo "  本地访问:  http://localhost:$API_PORT"

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$IP" ]; then
    echo "  局域网访问: http://$IP:$API_PORT"
fi

echo ""
echo "  API端口: $API_PORT (集成Web服务)"
echo "  语音端口: $VOICE_PORT"
echo ""
echo "  Token访问: http://localhost:$API_PORT/?token=$ACCESS_TOKEN"
echo ""
echo "========================================"
echo ""
echo "提示: 请确保防火墙允许这些端口访问"
echo "      手机访问时请使用局域网IP地址"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

trap "kill $API_PID $VOICE_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
