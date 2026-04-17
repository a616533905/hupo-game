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

echo "[1/7] 检查依赖..."
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

echo "[2/7] 安装 Python 依赖..."
if command -v pip3 &> /dev/null; then
    pip3 install psutil --break-system-packages 2>/dev/null || pip3 install psutil
elif command -v pip &> /dev/null; then
    pip install psutil --break-system-packages 2>/dev/null || pip install psutil
else
    echo "尝试使用 apt 安装 psutil..."
    apt-get install -y python3-psutil
fi

echo "[3/7] 创建安装目录..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs

echo "[4/7] 复制文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp -r $SCRIPT_DIR/* $INSTALL_DIR/
else
    echo "  已在安装目录，跳过复制"
fi

echo "[5/7] 安装 Systemd 服务..."
cp $INSTALL_DIR/hupo-bridge.service /etc/systemd/system/
cp $INSTALL_DIR/hupo-voice.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hupo-bridge
systemctl enable hupo-voice

echo "[6/7] 设置权限..."
chmod +x $INSTALL_DIR/start.sh
chmod +x $INSTALL_DIR/stop.sh
chmod +x $INSTALL_DIR/install.sh
chmod +x $INSTALL_DIR/status.sh
chmod +x $INSTALL_DIR/cron/health_check.sh
chmod 644 /etc/systemd/system/hupo-bridge.service
chmod 644 /etc/systemd/system/hupo-voice.service

echo "[7/7] 配置定时任务 (Cron)..."
CRON_DIR="$INSTALL_DIR/cron"
CRON_HEALTH="*/5 * * * * $CRON_DIR/health_check.sh >> $INSTALL_DIR/logs/health_check.log 2>&1"
CRON_AUDIT="0 3 * * * cd $INSTALL_DIR && /usr/bin/python3 $CRON_DIR/log_auditor.py 24 >> $INSTALL_DIR/logs/audit_cron.log 2>&1"

if ! crontab -l 2>/dev/null | grep -q "health_check.sh"; then
    (crontab -l 2>/dev/null; echo "$CRON_HEALTH") | crontab -
    echo "  已添加健康检查任务 (每5分钟)"
else
    echo "  健康检查任务已存在"
fi

if ! crontab -l 2>/dev/null | grep -q "log_auditor.py"; then
    (crontab -l 2>/dev/null; echo "$CRON_AUDIT") | crontab -
    echo "  已添加日志审计任务 (每天凌晨3点)"
else
    echo "  日志审计任务已存在"
fi

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
echo "  方式1 (推荐): systemctl start hupo-bridge hupo-voice"
echo "  方式2 (脚本): cd $INSTALL_DIR && ./start.sh"
echo ""
echo "【健康检查】"
echo "  自动检查: 每5分钟 (Cron)"
echo "  手动检查: ./health_check.sh"
echo "  检查日志: logs/health_check.log"
echo ""
echo "【常用命令】"
echo "  启动服务: systemctl start hupo-bridge hupo-voice"
echo "  停止服务: systemctl stop hupo-bridge hupo-voice"
echo "  查看状态: ./status.sh"
echo "  查看日志: journalctl -u hupo-bridge -f"
echo ""
echo "========================================"
