#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 安装脚本"
echo "========================================"
echo ""

INSTALL_DIR="/root/hupo-game"
SERVICE_USER="root"

if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 权限运行此脚本"
    echo "sudo ./install.sh"
    exit 1
fi

echo "[1/7] 检查依赖..."
if ! command -v python3 &> /dev/null; then
    echo "正在安装 Python3..."
    apt-get update
    apt-get install -y python3 python3-pip
fi

if ! command -v node &> /dev/null; then
    echo "正在安装 Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

echo "[2/7] 安装 Python 依赖..."
pip3 install psutil --break-system-packages 2>/dev/null || pip3 install psutil

echo "[3/7] 创建安装目录..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs

echo "[4/7] 复制文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp -r $SCRIPT_DIR/* $INSTALL_DIR/

echo "[5/7] 配置日志轮转..."
cp $INSTALL_DIR/logrotate.conf /etc/logrotate.d/hupo-game

echo "[6/7] 安装 Systemd 服务..."
cp $INSTALL_DIR/hupo-bridge.service /etc/systemd/system/
cp $INSTALL_DIR/hupo-voice.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hupo-bridge
systemctl enable hupo-voice

echo "[7/7] 设置权限..."
chmod +x $INSTALL_DIR/start.sh
chmod +x $INSTALL_DIR/install.sh
chmod 644 /etc/systemd/system/hupo-bridge.service
chmod 644 /etc/systemd/system/hupo-voice.service

echo ""
echo "========================================"
echo "  安装完成！"
echo "========================================"
echo ""
echo "配置文件: $INSTALL_DIR/config.json"
echo "日志目录: $INSTALL_DIR/logs/"
echo ""
echo "启动服务:"
echo "  systemctl start hupo-bridge"
echo "  systemctl start hupo-voice"
echo ""
echo "查看状态:"
echo "  systemctl status hupo-bridge"
echo "  systemctl status hupo-voice"
echo ""
echo "查看日志:"
echo "  journalctl -u hupo-bridge -f"
echo "  tail -f $INSTALL_DIR/logs/bridge_*.log"
echo ""
echo "API端点:"
echo "  健康检查: http://localhost:80/health"
echo "  Prometheus: http://localhost:80/metrics"
echo ""
echo "========================================"
