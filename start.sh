#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 游戏服务器启动脚本"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/5] 读取配置文件..."
if [ -f "config.json" ]; then
    API_PORT=$(grep -o '"api_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    VOICE_PORT=$(grep -o '"voice_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    ACCESS_TOKEN=$(grep -o '"access_token"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
    SSL_CERT=$(grep -o '"ssl_cert_file"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
    SSL_KEY=$(grep -o '"ssl_key_file"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
fi

API_PORT=${API_PORT:-80}
VOICE_PORT=${VOICE_PORT:-85}
ACCESS_TOKEN=${ACCESS_TOKEN:-hupo_secret_token_2024}

echo "  API端口: $API_PORT"
echo "  语音端口: $VOICE_PORT"
echo ""

cleanup_port() {
    local port=$1
    local service=$2
    echo "  检查端口 $port ($service)..."

    pid=$(lsof -t -i:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "    发现端口 $port 被占用，PID: $pid"
        proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "未知进程")
        echo "    进程名: $proc_name"
        echo "    正在关闭..."
        kill -9 $pid 2>/dev/null
        sleep 1
        if lsof -t -i:$port 2>/dev/null > /dev/null; then
            echo "    警告: 端口 $port 仍然被占用"
        else
            echo "    已关闭"
        fi
    else
        echo "    端口 $port 空闲"
    fi
}

echo "[2/5] 清理端口..."
cleanup_port $API_PORT "AI Bridge"
cleanup_port $VOICE_PORT "Voice Proxy"

echo "[3/5] 检查SSL证书..."
generate_ssl_certs() {
    local cert_file="$1"
    local key_file="$2"
    local common_name="$3"

    if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
        echo "  证书已存在: $cert_file"
        return 0
    fi

    echo "  正在生成自签名SSL证书..."
    if command -v openssl &> /dev/null; then
        openssl req -x509 -newkey rsa:2048 -keyout "$key_file" -out "$cert_file" \
            -days 365 -nodes -subj "/CN=$common_name" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  证书已生成: $cert_file"
            return 0
        fi
    fi
    echo "  警告: 无法生成证书，SSL功能将不可用"
    return 1
}

if [ -n "$SSL_CERT" ] && [ -n "$SSL_KEY" ]; then
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -n "$IP" ]; then
        generate_ssl_certs "$SSL_CERT" "$SSL_KEY" "$IP" || true
    fi
else
    echo "  未配置SSL证书，跳过"
fi

echo "[4/5] 启动 AI Bridge (端口 $API_PORT, 含Web服务)..."
SSL_CERT_FILE="$SSL_CERT" SSL_KEY_FILE="$SSL_KEY" API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py &
API_PID=$!
echo "API Server PID: $API_PID"

echo "[5/5] 启动语音代理 (端口 $VOICE_PORT)..."
VOICE_PORT=$VOICE_PORT node voice-proxy.js &
VOICE_PID=$!
echo "Voice Server PID: $VOICE_PID"

sleep 3

echo ""
echo "========================================"
echo "  所有服务已启动！"
echo "========================================"
echo ""
echo "  本地访问:  https://localhost:$API_PORT"

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$IP" ]; then
    echo "  局域网访问: https://$IP:$API_PORT"
    echo "  (首次访问需在浏览器中信任自签名证书)"
fi

echo ""
echo "  API端口: $API_PORT (HTTPS)"
echo "  语音端口: $VOICE_PORT"
echo ""
echo "  Token访问: https://localhost:$API_PORT/?token=$ACCESS_TOKEN"
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
