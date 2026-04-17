#!/bin/bash

cd "$(dirname "$0")"

USE_HTTPS=0
RUN_DAEMON=1

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
            echo "Unknown option: $1"
            echo "Usage: $0 [--https|-s] [--http|-h] [--foreground|-f]"
            echo "  --https, -s    Enable HTTPS"
            echo "  --http,  -h    Enable HTTP only"
            echo "  --foreground, -f   Run in foreground (override daemon mode)"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "  Hupo Game Server Startup Script"
echo "========================================"
echo ""

echo "[1/6] Loading configuration..."
if [ -f "config.json" ]; then
    HTTP_PORT=$(grep -o '"http_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    HTTPS_PORT=$(grep -o '"https_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    VOICE_PORT=$(grep -o '"voice_port"[[:space:]]*:[[:space:]]*[0-9]*' config.json | grep -o '[0-9]*$')
    ACCESS_TOKEN=$(grep -o '"access_token"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
    SSL_CERT=$(grep -o '"ssl_cert_file"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
    SSL_KEY=$(grep -o '"ssl_key_file"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*:.*"\([^"]*\)"/\1/')
fi

HTTP_PORT=${HTTP_PORT:-80}
HTTPS_PORT=${HTTPS_PORT:-443}
VOICE_PORT=${VOICE_PORT:-85}
ACCESS_TOKEN=${ACCESS_TOKEN:-hupo_secret_token_2024}

if [ $USE_HTTPS -eq 1 ]; then
    API_PORT=${API_PORT:-$HTTPS_PORT}
else
    API_PORT=${API_PORT:-$HTTP_PORT}
fi

echo "  API Port: $API_PORT"
echo "  Voice Port: $VOICE_PORT"
echo "  HTTPS: $([ $USE_HTTPS -eq 1 ] && echo 'Enabled' || echo 'Disabled')"
echo ""

cleanup_port() {
    local port=$1
    local service=$2
    echo "  Checking port $port ($service)..."

    pid=$(lsof -t -i:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "    Found port $port in use, PID: $pid"
        proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "Unknown")
        echo "    Process: $proc_name"
        echo "    Closing..."
        kill -9 $pid 2>/dev/null
        sleep 1
        if lsof -t -i:$port 2>/dev/null > /dev/null; then
            echo "    Warning: Port $port still in use"
        else
            echo "    Closed"
        fi
    else
        echo "    Port $port is free"
    fi
}

echo "[2/6] Clearing ports..."
if [ $USE_HTTPS -eq 1 ]; then
    cleanup_port 80 "HTTP Redirect"
fi
cleanup_port $API_PORT "AI Bridge"
cleanup_port $VOICE_PORT "Voice Proxy"

generate_ssl_certs() {
    local cert_file="$1"
    local key_file="$2"
    local common_name="$3"

    if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
        echo "  Certificate exists: $cert_file"
        return 0
    fi

    echo "  Generating self-signed SSL certificate..."
    if command -v openssl &> /dev/null; then
        openssl req -x509 -newkey rsa:2048 -keyout "$key_file" -out "$cert_file" \
            -days 365 -nodes -subj "/CN=$common_name" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  Certificate generated: $cert_file"
            return 0
        fi
    fi
    echo "  Warning: Cannot generate certificate, SSL will be disabled"
    return 1
}

echo "[3/6] Checking SSL certificates..."
if [ $USE_HTTPS -eq 1 ]; then
    if [ -n "$SSL_CERT" ] && [ -n "$SSL_KEY" ]; then
        IP=$(hostname -I 2>/dev/null | awk '{print $1}')
        if [ -n "$IP" ]; then
            generate_ssl_certs "$SSL_CERT" "$SSL_KEY" "$IP" || true
        fi
    else
        echo "  No SSL certificate configured in config.json"
    fi
else
    echo "  HTTPS disabled, skipping SSL certificates"
fi

echo "[4/6] Starting AI Bridge (port $API_PORT)..."
if [ $RUN_DAEMON -eq 1 ]; then
    LOG_DIR="logs"
    mkdir -p "$LOG_DIR"
    if [ $USE_HTTPS -eq 1 ]; then
        nohup env USE_HTTPS=1 SSL_CERT_FILE="$SSL_CERT" SSL_KEY_FILE="$SSL_KEY" API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py > "$LOG_DIR/bridge.log" 2>&1 &
    else
        nohup env USE_HTTPS=0 API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py > "$LOG_DIR/bridge.log" 2>&1 &
    fi
    API_PID=$!
    echo "  AI Bridge PID: $API_PID (background)"

    echo "[5/6] Starting voice proxy (port $VOICE_PORT)..."
    nohup env VOICE_PORT=$VOICE_PORT node voice-proxy.js > "$LOG_DIR/voice.log" 2>&1 &
    VOICE_PID=$!
    echo "  Voice Proxy PID: $VOICE_PID (background)"
else
    if [ $USE_HTTPS -eq 1 ]; then
        USE_HTTPS=1 SSL_CERT_FILE="$SSL_CERT" SSL_KEY_FILE="$SSL_KEY" API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py &
    else
        USE_HTTPS=0 API_PORT=$API_PORT VOICE_PORT=$VOICE_PORT python3 nanobot_bridge.py &
    fi
    API_PID=$!
    echo "  AI Bridge PID: $API_PID"

    echo "[5/6] Starting voice proxy (port $VOICE_PORT)..."
    VOICE_PORT=$VOICE_PORT node voice-proxy.js &
    VOICE_PID=$!
    echo "  Voice Proxy PID: $VOICE_PID"
fi

sleep 3

if [ $RUN_DAEMON -eq 1 ]; then
    echo ""
    echo "========================================"
    echo "  Server Running in Background"
    echo "========================================"
    echo ""
    echo "  Logs: logs/bridge.log, logs/voice.log"
    echo ""
    echo "  To stop:"
    echo "    kill $API_PID $VOICE_PID"
    echo ""
    echo "========================================"
    echo ""
    exit 0
fi

echo ""
echo "========================================"
echo "  Server Started Successfully"
echo "========================================"
echo ""

IP=$(hostname -I 2>/dev/null | awk '{print $1}')

if [ $USE_HTTPS -eq 1 ]; then
    echo "  Local:        https://localhost:$API_PORT"
    if [ -n "$IP" ]; then
        echo "  Network:      https://$IP:$API_PORT"
        echo "  (First visit: accept self-signed certificate)"
    fi
    if [ -n "$SSL_CERT" ] && [ -f "$SSL_CERT" ]; then
        echo ""
        echo "  Note: HTTP port 80 redirects to HTTPS"
    fi
else
    echo "  Local:        http://localhost:$API_PORT"
    if [ -n "$IP" ]; then
        echo "  Network:      http://$IP:$API_PORT"
    fi
fi

echo ""
echo "  Voice Port: $VOICE_PORT"
echo "  Token:      ?token=$ACCESS_TOKEN"
echo ""
echo "========================================"
echo ""
echo "Tip: Ensure firewall allows these ports"
echo "     Use LAN IP for mobile access"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

trap "kill $API_PID $VOICE_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
