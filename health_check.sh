#!/bin/bash
# ========================================
#   琥珀冒险 - 健康检查脚本
# ========================================
# 检查服务健康状态，自动恢复异常服务

CONFIG_FILE="/root/hupo-game/config.json"
LOG_DIR="/root/hupo-game/logs"
ALERT_LOG="$LOG_DIR/health_check.log"

mkdir -p "$LOG_DIR"

log_alert() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$ALERT_LOG"
}

check_port() {
    local port=$1
    local service=$2
    if ! netstat -tlnp 2>/dev/null | grep -q ":$port "; then
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

restart_service() {
    local service=$1
    log_alert "[恢复] 重启服务: $service"
    systemctl restart "$service" 2>&1 >> "$ALERT_LOG"
    sleep 3
    if systemctl is-active --quiet "$service"; then
        log_alert "[成功] $service 重启成功"
    else
        log_alert "[失败] $service 重启失败"
    fi
}

BRIDGE_OK=true
VOICE_OK=true

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
