#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 安装脚本"
echo "========================================"
echo ""

INSTALL_DIR="/root/hupo-game"

if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 权限运行此脚本"
    echo "sudo ./install.sh"
    exit 1
fi

echo "[1/6] 检查依赖..."
if ! command -v python3 &> /dev/null; then
    echo "正在安装 Python3..."
    apt-get update
    apt-get install -y python3 python3-pip python3-psutil
fi

if ! command -v node &> /dev/null; then
    echo "正在安装 Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

echo "[2/6] 安装 Python 依赖..."
if command -v pip3 &> /dev/null; then
    pip3 install psutil --break-system-packages 2>/dev/null || pip3 install psutil
elif command -v pip &> /dev/null; then
    pip install psutil --break-system-packages 2>/dev/null || pip install psutil
else
    echo "尝试使用 apt 安装 psutil..."
    apt-get install -y python3-psutil
fi

echo "[3/6] 创建安装目录..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs

echo "[4/6] 复制文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp -r $SCRIPT_DIR/* $INSTALL_DIR/
else
    echo "  已在安装目录，跳过复制"
fi

echo "[5/6] 安装 Systemd 服务..."
cp $INSTALL_DIR/hupo-bridge.service /etc/systemd/system/
cp $INSTALL_DIR/hupo-voice.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hupo-bridge
systemctl enable hupo-voice

echo "[6/6] 设置权限..."
chmod +x $INSTALL_DIR/start.sh
chmod +x $INSTALL_DIR/stop.sh
chmod +x $INSTALL_DIR/install.sh
chmod +x $INSTALL_DIR/status.sh
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
echo "【端口配置】"
echo "  HTTP端口: 80"
echo "  HTTPS端口: 443"
echo "  Voice端口: 85"
echo ""
echo "【启动方式】"
echo "  方式1 (推荐): cd $INSTALL_DIR && ./start.sh"
echo "  方式2 (后台): systemctl start hupo-bridge && systemctl start hupo-voice"
echo ""
echo "【HTTPS配置】"
echo "  启动时选择 HTTPS 模式: ./start.sh --https"
echo "  或交互选择: ./start.sh"
echo ""
echo "【常用命令】"
echo "  启动服务: ./start.sh"
echo "  停止服务: ./stop.sh"
echo "  强制停止: ./stop.sh --force"
echo "  查看状态: ./status.sh"
echo "  查看日志: ./status.sh --logs"
echo ""
echo "========================================"
