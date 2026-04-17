#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 停止服务"
echo "========================================"
echo ""

FORCE_STOP=0
if [[ "$1" == "--force" ]]; then
    FORCE_STOP=1
    echo "[模式] 强制停止已启用"
    echo ""
fi

echo "[1/3] 停止 AI Bridge (Python)..."

BRIDGE_PID=$(pgrep -f "nanobot_bridge.py" | head -1)
if [ -n "$BRIDGE_PID" ]; then
    if [ $FORCE_STOP -eq 1 ]; then
        kill -9 $BRIDGE_PID 2>/dev/null
    else
        kill $BRIDGE_PID 2>/dev/null
    fi
    sleep 1
    if pgrep -f "nanobot_bridge.py" > /dev/null; then
        echo "  AI Bridge 停止失败"
    else
        echo "  AI Bridge 已停止"
    fi
else
    echo "  AI Bridge 未运行"
fi

echo ""

echo "[2/3] 停止 Voice Proxy (Node.js)..."

VOICE_PID=$(pgrep -f "voice-proxy.js" | head -1)
if [ -n "$VOICE_PID" ]; then
    if [ $FORCE_STOP -eq 1 ]; then
        kill -9 $VOICE_PID 2>/dev/null
    else
        kill $VOICE_PID 2>/dev/null
    fi
    sleep 1
    if pgrep -f "voice-proxy.js" > /dev/null; then
        echo "  Voice Proxy 停止失败"
    else
        echo "  Voice Proxy 已停止"
    fi
else
    echo "  Voice Proxy 未运行"
fi

echo ""

echo "[3/3] 检查端口..."

if netstat -tlnp 2>/dev/null | grep -E ":(80|443|85)\s" > /dev/null; then
    echo "  警告: 仍有服务占用端口"
    netstat -tlnp 2>/dev/null | grep -E ":(80|443|85)" | while read line; do
        echo "    $line"
    done
elif ss -tlnp 2>/dev/null | grep -E ":(80|443|85)\s" > /dev/null; then
    echo "  警告: 仍有服务占用端口"
    ss -tlnp 2>/dev/null | grep -E ":(80|443|85)" | while read line; do
        echo "    $line"
    done
else
    echo "  所有端口已释放"
fi

echo ""

echo "========================================"
echo "  服务停止完成"
echo "========================================"
echo ""
echo "如果服务仍在运行，尝试:"
echo "  ./stop.sh --force"
echo ""