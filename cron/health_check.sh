#!/bin/bash
# ========================================
#   琥珀冒险 - 健康检查脚本
# ========================================
# 检查服务健康状态，自动恢复异常服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_DIR/config.json"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data"
ALERT_LOG="$LOG_DIR/health_check.log"
MAX_LOG_SIZE=10485760
MAX_LOG_FILES=5

mkdir -p "$LOG_DIR"

rotate_log() {
    if [ -f "$ALERT_LOG" ]; then
        local size=$(stat -f%z "$ALERT_LOG" 2>/dev/null || stat -c%s "$ALERT_LOG" 2>/dev/null || echo 0)
        if [ "$size" -gt "$MAX_LOG_SIZE" ]; then
            for i in $(seq $((MAX_LOG_FILES-1)) -1 1); do
                if [ -f "${ALERT_LOG}.$i" ]; then
                    mv "${ALERT_LOG}.$i" "${ALERT_LOG}.$((i+1))"
                fi
            done
            mv "$ALERT_LOG" "${ALERT_LOG}.1"
        fi
    fi
}

rotate_log

log_alert() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$ALERT_LOG"
}

check_port() {
    local port=$1
    local service=$2
    if ! netstat -tlnp 2>/dev/null | grep -q ":$port " && ! ss -tlnp 2>/dev/null | grep -q ":$port "; then
        log_alert "[警告] $service 端口 $port 未监听"
        return 1
    fi
    return 0
}

check_process() {
    local name=$1
    if ! pgrep -f "$name" > /dev/null; then
        log_alert "[警告] 进程 $name 未运行"
        return 1
    fi
    return 0
}

check_disk_space() {
    local usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    if [ "$usage" -gt 90 ]; then
        log_alert "[严重] 磁盘空间不足: ${usage}%"
        return 1
    elif [ "$usage" -gt 80 ]; then
        log_alert "[警告] 磁盘空间紧张: ${usage}%"
    fi
    return 0
}

check_memory() {
    local mem_free=$(free -m | grep Mem | awk '{print $7}')
    if [ "$mem_free" -lt 100 ]; then
        log_alert "[严重] 内存不足: 可用 ${mem_free}MB"
        return 1
    elif [ "$mem_free" -lt 500 ]; then
        log_alert "[警告] 内存紧张: 可用 ${mem_free}MB"
    fi
    return 0
}

check_minimax_api() {
    if [ ! -f "$CONFIG_FILE" ]; then
        return 0
    fi
    
    local api_key=$(grep -o '"api_key"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | head -1 | sed 's/.*: *"\([^"]*\)".*/\1/')
    local group_id=$(grep -o '"group_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | head -1 | sed 's/.*: *"\([^"]*\)".*/\1/')
    
    if [ -z "$api_key" ] || [ -z "$group_id" ]; then
        return 0
    fi
    
    local response=$(curl -s -w "\n%{http_code}" -X POST "https://api.minimax.chat/v1/text/chatcompletion_v2?GroupId=$group_id" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $api_key" \
        -d '{"model":"MiniMax-M2.7","messages":[{"role":"user","content":"hi"}],"temperature":0.7}' \
        --connect-timeout 10 \
        --max-time 15 2>/dev/null)
    
    local http_code=$(echo "$response" | tail -1)
    local body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        if echo "$body" | grep -q '"choices"'; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [正常] MiniMax API 响应正常" >> "$ALERT_LOG"
            return 0
        else
            log_alert "[警告] MiniMax API 返回异常: $(echo "$body" | head -c 200)"
            return 1
        fi
    else
        log_alert "[警告] MiniMax API HTTP错误: $http_code"
        return 1
    fi
}

check_openrouter_api() {
    if [ ! -f "$CONFIG_FILE" ]; then
        return 0
    fi
    
    local api_key=$(grep -A 20 '"openrouter"' "$CONFIG_FILE" | grep -o '"api_key"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*: *"\([^"]*\)".*/\1/')
    
    if [ -z "$api_key" ]; then
        return 0
    fi
    
    local response=$(curl -s -w "\n%{http_code}" -X POST "https://openrouter.ai/api/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $api_key" \
        -H "HTTP-Referer: https://localhost" \
        -d '{"model":"openrouter/auto","messages":[{"role":"user","content":"hi"}],"temperature":0.7}' \
        --connect-timeout 10 \
        --max-time 15 2>/dev/null)
    
    local http_code=$(echo "$response" | tail -1)
    local body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        if echo "$body" | grep -q '"choices"'; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [正常] OpenRouter API 响应正常" >> "$ALERT_LOG"
            return 0
        else
            log_alert "[警告] OpenRouter API 返回异常: $(echo "$body" | head -c 200)"
            return 1
        fi
    else
        log_alert "[警告] OpenRouter API HTTP错误: $http_code"
        return 1
    fi
}

restart_service() {
    local service=$1
    log_alert "[恢复] 重启服务: $service"
    cd "$PROJECT_DIR" && ./stop.sh --wait --max-wait=15 2>&1 >> "$ALERT_LOG"
    sleep 2
    cd "$PROJECT_DIR" && ./start.sh 2>&1 >> "$ALERT_LOG"
    sleep 3
    if pgrep -f "$service" > /dev/null; then
        log_alert "[成功] $service 重启成功"
        return 0
    else
        log_alert "[失败] $service 重启失败"
        return 1
    fi
}

BRIDGE_OK=true
VOICE_OK=true

check_disk_space
check_memory

CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_HOUR" = "00" ] || [ "$CURRENT_HOUR" = "06" ] || [ "$CURRENT_HOUR" = "12" ] || [ "$CURRENT_HOUR" = "18" ]; then
    CURRENT_MIN=$(date +%M)
    if [ "$CURRENT_MIN" -lt 5 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [检查] 开始 API 健康检查..." >> "$ALERT_LOG"
        check_minimax_api
        check_openrouter_api
    fi
fi

if ! check_port 443 "AI Bridge"; then
    BRIDGE_OK=false
fi

if ! check_port 85 "Voice Proxy"; then
    VOICE_OK=false
fi

if ! check_process "nanobot_bridge.py"; then
    BRIDGE_OK=false
fi

if ! check_process "voice-proxy.js"; then
    VOICE_OK=false
fi

if [ "$BRIDGE_OK" = false ]; then
    log_alert "[异常] AI Bridge 服务异常，尝试重启..."
    restart_service "hupo-bridge"
fi

if [ "$VOICE_OK" = false ]; then
    log_alert "[异常] Voice Proxy 服务异常，尝试重启..."
    restart_service "hupo-voice"
fi

if [ "$BRIDGE_OK" = true ] && [ "$VOICE_OK" = true ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [正常] 所有服务运行正常" >> "$ALERT_LOG"
fi

exit 0
