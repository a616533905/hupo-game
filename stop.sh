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

BRIDGE_PIDS=$(pgrep -f "nanobot_bridge.py" 2>/dev/null)
if [ -n "$BRIDGE_PIDS" ]; then
    for PID in $BRIDGE_PIDS; do
        if [ $FORCE_STOP -eq 1 ]; then
            kill -9 $PID 2>/dev/null
        else
            kill $PID 2>/dev/null
        fi
        echo "  已终止进程: $PID"
    done
    sleep 1
    REMAINING=$(pgrep -f "nanobot_bridge.py" 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        echo "  AI Bridge 停止失败"
    else
        echo "  AI Bridge 已停止"
    fi
else
    echo "  AI Bridge 未运行"
fi

echo ""

echo "[2/3] 停止 Voice Proxy (Node.js)..."

VOICE_PIDS=$(pgrep -f "voice-proxy.js" 2>/dev/null)
if [ -n "$VOICE_PIDS" ]; then
    for PID in $VOICE_PIDS; do
        if [ $FORCE_STOP -eq 1 ]; then
            kill -9 $PID 2>/dev/null
        else
            kill $PID 2>/dev/null
        fi
        echo "  已终止进程: $PID"
    done
    sleep 1
    REMAINING=$(pgrep -f "voice-proxy.js" 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        echo "  Voice Proxy 停止失败"
    else
        echo "  Voice Proxy 已停止"
    fi
else
    echo "  Voice Proxy 未运行"
fi

echo ""

echo "[3/3] 检查端口..."

if command -v netstat &> /dev/null; then
    if netstat -tlnp 2>/dev/null | grep -E ":(80|443|85)\s" > /dev/null; then
        echo "  警告: 仍有服务占用端口"
        netstat -tlnp 2>/dev/null | grep -E ":(80|443|85)" | while read line; do
            echo "    $line"
        done
    else
        echo "  所有端口已释放"
    fi
elif command -v ss &> /dev/null; then
    if ss -tlnp 2>/dev/null | grep -E ":(80|443|85)\s" > /dev/null; then
        echo "  警告: 仍有服务占用端口"
        ss -tlnp 2>/dev/null | grep -E ":(80|443|85)" | while read line; do
            echo "    $line"
        done
    else
        echo "  所有端口已释放"
    fi
else
    echo "  无法检查端口（netstat/ss 均不可用）"
fi

echo ""

echo "========================================"
echo "  服务停止完成"
echo "========================================"
echo ""
echo "如果服务仍在运行，尝试:"
echo "  ./stop.sh --force"
echo ""