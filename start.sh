#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "config.json" ]; then
    python3 -c "import json; c=json.load(open('config.json')); c['runtime_mode']='server'; json.dump(c,open('config.json','w'),indent=4)" 2>/dev/null
fi

RUN_DAEMON=1

USE_HTTPS=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --https|-s)
            USE_HTTPS=1
            shift
            ;;
        --http|-h)
            USE_HTTPS=0
            shift
            ;;
        --foreground|-f)
            RUN_DAEMON=0
            shift
            ;;
        --daemon|-d)
            RUN_DAEMON=1
            shift
            ;;
        *)
            echo "未知选项: $1"
            echo "用法: $0 [--https|-s] [--http|-h] [--foreground|-f]"
            echo "  --https, -s    启用 HTTPS"
            echo "  --http,  -h    仅使用 HTTP"
            echo "  --foreground, -f   前台运行（覆盖守护进程模式）"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "  琥珀冒险 - 服务器启动脚本"
echo "========================================"
echo ""

echo "[1/6] 加载配置..."
RUNTIME_MODE=$(grep -o '"runtime_mode"[[:space:]]*:[[:space:]]*"[^"]*"' config.json 2>/dev/null | sed 's/.*:.*"\([^"]*\)"/\1/')
if [ -z "$RUNTIME_MODE" ]; then RUNTIME_MODE="local"; fi

get_env_config() {
    local key=$1
    python3 -c "import json; c=json.load(open('config.json')); env=c.get('runtime_mode','local'); print(c.get('environments',{}).get(env,{}).get('server',{}).get('$key',''))" 2>/dev/null
}

HTTP_PORT=$(get_env_config "http_port")
HTTPS_PORT=$(get_env_config "https_port")
VOICE_PORT=$(get_env_config "voice_port")
ACCESS_TOKEN=$(python3 -c "import json; c=json.load(open('config.json')); env=c.get('runtime_mode','local'); print(c.get('environments',{}).get(env,{}).get('access_token',''))" 2>/dev/null)
SSL_CERT=$(get_env_config "ssl_cert_file")
SSL_KEY=$(get_env_config "ssl_key_file")

HTTP_PORT=${HTTP_PORT:-80}
HTTPS_PORT=${HTTPS_PORT:-443}
VOICE_PORT=${VOICE_PORT:-85}
ACCESS_TOKEN=${ACCESS_TOKEN:-hupo_secret_token_2024}

if [ -n "$SSL_CERT" ] && [ -n "$SSL_KEY" ] && [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
    USE_HTTPS=1
fi

if [ $USE_HTTPS -eq 1 ]; then
    API_PORT=${API_PORT:-$HTTPS_PORT}
else
    API_PORT=${API_PORT:-$HTTP_PORT}
fi

echo "  API端口: $API_PORT"
echo "  语音端口: $VOICE_PORT"
echo "  HTTPS: $([ $USE_HTTPS -eq 1 ] && echo '已启用' || echo '已禁用')"
echo ""

echo "[2/6] 停止现有服务..."
if [ -f "./stop.sh" ]; then
    ./stop.sh --wait --max-wait=10
else
    echo "  警告: stop.sh 不存在，手动停止..."
    pkill -f "nanobot_bridge.py" 2>/dev/null
    pkill -f "voice-proxy.js" 2>/dev/null
    sleep 2
fi

wait_port_release() {
    local port=$1
    local max_wait=$2
    local count=0
    echo "    等待端口 $port 释放..."
    while true; do
        if ! ss -tlnp 2>/dev/null | grep -q ":$port "; then
            echo "    端口 $port 已释放"
            return 0
        fi
        count=$((count + 1))
        if [ $count -ge $max_wait ]; then
            echo "    警告: 端口 $port 等待超时，继续启动..."
            return 0
        fi
        sleep 1
    done
}

echo "[3/6] 等待端口释放..."
if [ $USE_HTTPS -eq 1 ]; then
    wait_port_release 80 10
fi
wait_port_release $API_PORT 10
wait_port_release $VOICE_PORT 10

generate_ssl_certs() {
    local cert_file="$1"
    local key_file="$2"
    local common_name="$3"

    if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
        echo "  证书已存在: $cert_file"
        return 0
    fi

    echo "  生成自签名SSL证书..."
    if command -v openssl &> /dev/null; then
        openssl req -x509 -newkey rsa:2048 -keyout "$key_file" -out "$cert_file" \
            -days 365 -nodes -subj "/CN=$common_name" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  证书已生成: $cert_file"
            return 0
        fi
    fi
    echo "  警告: 无法生成证书，SSL将被禁用"
    return 1
}

echo "[4/6] 检查SSL证书..."
if [ $USE_HTTPS -eq 1 ]; then
    if [ -n "$SSL_CERT" ] && [ -n "$SSL_KEY" ]; then
        IP=$(hostname -I 2>/dev/null | awk '{print $1}')
        if [ -n "$IP" ]; then
            generate_ssl_certs "$SSL_CERT" "$SSL_KEY" "$IP" || true
        fi
    else
        echo "  config.json 中未配置SSL证书"
    fi
else
    echo "  HTTPS已禁用，跳过SSL证书"
fi

echo "[5/6] 启动 AI Bridge (端口 $API_PORT)..."
if [ $RUN_DAEMON -eq 1 ]; then
    LOG_DIR="logs"
    mkdir -p "$LOG_DIR"
    if [ $USE_HTTPS -eq 1 ]; then
        nohup env USE_HTTPS=1 SSL_CERT_FILE="$SSL_CERT" SSL_KEY_FILE="$SSL_KEY" API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py > "$LOG_DIR/bridge.log" 2>&1 &
    else
        nohup env USE_HTTPS=0 API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py > "$LOG_DIR/bridge.log" 2>&1 &
    fi
    API_PID=$!
    echo "  AI Bridge PID: $API_PID (后台运行)"

    echo "[6/6] 启动语音代理 (端口 $VOICE_PORT)..."
    nohup env VOICE_PORT=$VOICE_PORT node voice-proxy.js > "$LOG_DIR/voice.log" 2>&1 &
    VOICE_PID=$!
    echo "  Voice Proxy PID: $VOICE_PID (后台运行)"
else
    if [ $USE_HTTPS -eq 1 ]; then
        USE_HTTPS=1 SSL_CERT_FILE="$SSL_CERT" SSL_KEY_FILE="$SSL_KEY" API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py &
    else
        USE_HTTPS=0 API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py &
    fi
    API_PID=$!
    echo "  AI Bridge PID: $API_PID"

    echo "[6/6] 启动语音代理 (端口 $VOICE_PORT)..."
    VOICE_PORT=$VOICE_PORT node voice-proxy.js &
    VOICE_PID=$!
    echo "  Voice Proxy PID: $VOICE_PID"
fi

sleep 3

if [ $RUN_DAEMON -eq 1 ]; then
    echo ""
    echo "========================================"
    echo "  服务器已在后台运行"
    echo "========================================"
    echo ""
    echo "  日志: logs/bridge.log, logs/voice.log"
    echo ""
    echo "  停止服务:"
    echo "    ./stop.sh"
    echo ""
    echo "========================================"
    echo ""
    exit 0
fi

echo ""
echo "========================================"
echo "  服务器启动成功"
echo "========================================"
echo ""

IP=$(hostname -I 2>/dev/null | awk '{print $1}')

if [ $USE_HTTPS -eq 1 ]; then
    echo "  本地访问:    https://localhost:$API_PORT"
    if [ -n "$IP" ]; then
        echo "  局域网访问:  https://$IP:$API_PORT"
        echo "  (首次访问需接受自签名证书)"
    fi
    if [ -n "$SSL_CERT" ] && [ -f "$SSL_CERT" ]; then
        echo ""
        echo "  注意: HTTP端口80会重定向到HTTPS"
    fi
else
    echo "  本地访问:    http://localhost:$API_PORT"
    if [ -n "$IP" ]; then
        echo "  局域网访问:  http://$IP:$API_PORT"
    fi
fi

echo ""
echo "  语音端口: $VOICE_PORT"
echo "  访问令牌: ?token=$ACCESS_TOKEN"
echo ""
echo "========================================"
echo ""
echo "提示: 请确保防火墙允许这些端口"
echo "      使用局域网IP可从手机访问"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

trap "kill $API_PID $VOICE_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
