#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

FORCE_STOP=0
WAIT_PORTS=0
MAX_WAIT=15

for arg in "$@"; do
    case $arg in
        --force|-f)
            FORCE_STOP=1
            ;;
        --wait|-w)
            WAIT_PORTS=1
            ;;
        --max-wait=*)
            MAX_WAIT="${arg#*=}"
            ;;
    esac
done

echo "========================================"
echo "  琥珀冒险 - 停止服务"
echo "========================================"
echo ""

if [ $FORCE_STOP -eq 1 ]; then
    echo "[模式] 强制停止"
fi
echo ""

stop_process() {
    local proc_pattern=$1
    local display_name=$2
    echo "[停止] $display_name..."
    
    local pids=$(pgrep -f "$proc_pattern" 2>/dev/null)
    if [ -z "$pids" ]; then
        echo "  未运行"
        return 0
    fi
    
    for pid in $pids; do
        echo "  发现进程 PID: $pid"
        if [ $FORCE_STOP -eq 1 ]; then
            kill -9 $pid 2>/dev/null
        else
            kill $pid 2>/dev/null
        fi
    done
    
    sleep 1
    
    local remaining=$(pgrep -f "$proc_pattern" 2>/dev/null)
    if [ -n "$remaining" ]; then
        echo "  进程未响应，强制终止..."
        for pid in $remaining; do
            kill -9 $pid 2>/dev/null
        done
        sleep 1
    fi
    
    remaining=$(pgrep -f "$proc_pattern" 2>/dev/null)
    if [ -z "$remaining" ]; then
        echo "  已停止"
        return 0
    else
        echo "  警告: 可能仍在运行"
        return 1
    fi
}

wait_port_release() {
    local port=$1
    local count=0
    
    while [ $count -lt $MAX_WAIT ]; do
        if ! ss -tlnp 2>/dev/null | grep -q ":$port "; then
            return 0
        fi
        count=$((count + 1))
        sleep 1
    done
    return 1
}

stop_process "nanobot_bridge.py" "AI Bridge"
stop_process "voice-proxy.js" "Voice Proxy"

if [ $WAIT_PORTS -eq 1 ]; then
    echo ""
    echo "[等待] 端口释放..."
    
    HTTP_PORT=${HTTP_PORT:-80}
    HTTPS_PORT=${HTTPS_PORT:-443}
    VOICE_PORT=${VOICE_PORT:-85}
    
    if [ -f "config.json" ]; then
        HTTP_PORT=$(grep -o '"http_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json 2>/dev/null | grep -o '[0-9]*$' || echo "80")
        HTTPS_PORT=$(grep -o '"https_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json 2>/dev/null | grep -o '[0-9]*$' || echo "443")
        VOICE_PORT=$(grep -o '"voice_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json 2>/dev/null | grep -o '[0-9]*$' || echo "85")
    fi
    
    for port in $HTTP_PORT $HTTPS_PORT $VOICE_PORT; do
        echo -n "  端口 $port: "
        if ss -tlnp 2>/dev/null | grep -q ":$port "; then
            echo -n "等待中..."
            if wait_port_release $port; then
                echo " 已释放"
            else
                echo " 超时"
            fi
        else
            echo "空闲"
        fi
    done
fi

echo ""
echo "========================================"
echo "  停止完成"
echo "========================================"

if [ $WAIT_PORTS -eq 0 ]; then
    echo ""
    echo "用法: $0 [--force|-f] [--wait|-w] [--max-wait=N]"
    echo "  --force     强制终止进程"
    echo "  --wait      等待端口释放"
    echo "  --max-wait  最大等待秒数 (默认15)"
fi
echo ""
