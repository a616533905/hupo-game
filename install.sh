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

echo "[1/8] 检查依赖..."
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

echo "[2/8] 安装 Python 依赖..."
if command -v pip3 &> /dev/null; then
    pip3 install psutil --break-system-packages 2>/dev/null || pip3 install psutil
elif command -v pip &> /dev/null; then
    pip install psutil --break-system-packages 2>/dev/null || pip install psutil
else
    echo "尝试使用 apt 安装 psutil..."
    apt-get install -y python3-psutil
fi

echo "[3/8] 创建安装目录..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs

echo "[4/8] 复制文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp -r $SCRIPT_DIR/* $INSTALL_DIR/
else
    echo "  已在安装目录，跳过复制"
fi

echo "[5/8] 配置日志轮转..."
cp $INSTALL_DIR/logrotate.conf /etc/logrotate.d/hupo-game 2>/dev/null || true

echo "[6/8] 安装 Systemd 服务..."
cp $INSTALL_DIR/hupo-bridge.service /etc/systemd/system/
cp $INSTALL_DIR/hupo-voice.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hupo-bridge
systemctl enable hupo-voice

echo "[7/8] 安装 Caddy (HTTPS自动证书)..."
if ! command -v caddy &> /dev/null; then
    echo "正在安装 Caddy..."
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null || true
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
    echo "Caddy 安装完成"
else
    echo "Caddy 已安装"
fi

echo ""
echo "请输入你的域名 (例如: example.com，直接回车跳过):"
read -r DOMAIN

IS_IP=false
if [ -n "$DOMAIN" ]; then
    if [[ $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        IS_IP=true
        echo "检测到输入的是 IP 地址，无法申请 SSL 证书"
        echo "将使用 HTTP 模式运行"
    fi
fi

if [ -n "$DOMAIN" ] && [ "$IS_IP" = false ]; then
    echo "配置 Caddy for $DOMAIN..."
    cat > /etc/caddy/Caddyfile << CADDYEOF
{
    email admin@$DOMAIN
}

$DOMAIN {
    encode gzip
    reverse_proxy localhost:80
}

http://$DOMAIN {
    redir https://$DOMAIN{uri}
}
CADDYEOF
    
    sed -i 's/"api_port": 80/"api_port": 80/' $INSTALL_DIR/config.json
    sed -i 's/"web_port": 80/"web_port": 80/' $INSTALL_DIR/config.json
    sed -i 's/"http_port": 80/"http_port": 80/' $INSTALL_DIR/config.json
    sed -i 's/"https_port": 443/"https_port": 443/' $INSTALL_DIR/config.json
    
    if grep -q '"https_domain"' $INSTALL_DIR/config.json; then
        sed -i "s/\"https_domain\": \"[^\"]*\"/\"https_domain\": \"$DOMAIN\"/" $INSTALL_DIR/config.json
    else
        sed -i "s/\"https_port\": 443/\"https_port\": 443,\n    \"https_domain\": \"$DOMAIN\"/" $INSTALL_DIR/config.json
    fi
    
    if systemctl restart caddy; then
        systemctl enable caddy
        echo "Caddy 配置完成，HTTPS 已启用"
        echo "请确保域名 $DOMAIN 已解析到此服务器IP"
    else
        echo "Caddy 启动失败，可能是域名未解析到本机"
        echo "请检查: journalctl -xeu caddy.service"
        echo "将使用 HTTP 模式"
        sed -i 's/"api_port": 80/"api_port": 80/' $INSTALL_DIR/config.json
        sed -i 's/"web_port": 80/"web_port": 80/' $INSTALL_DIR/config.json
        sed -i 's/"http_port": 80/"http_port": 80/' $INSTALL_DIR/config.json
        sed -i 's/"https_port": 443/"https_port": 443/' $INSTALL_DIR/config.json
        systemctl stop caddy 2>/dev/null
        systemctl disable caddy 2>/dev/null
    fi
elif [ -n "$DOMAIN" ] && [ "$IS_IP" = true ]; then
    echo "配置 Caddy HTTP 模式 for $DOMAIN..."
    cat > /etc/caddy/Caddyfile << CADDYEOF
:80 {
    encode gzip
    reverse_proxy localhost:80
}
CADDYEOF
    
    sed -i 's/"api_port": 80/"api_port": 80/' $INSTALL_DIR/config.json
    sed -i 's/"web_port": 80/"web_port": 80/' $INSTALL_DIR/config.json
    sed -i 's/"http_port": 80/"http_port": 80/' $INSTALL_DIR/config.json
    sed -i 's/"https_port": 443/"https_port": 443/' $INSTALL_DIR/config.json
    
    if systemctl restart caddy; then
        systemctl enable caddy
        echo "Caddy HTTP 模式配置完成"
        echo "访问地址: http://$DOMAIN"
    else
        echo "Caddy 启动失败"
        sed -i 's/"api_port": 80/"api_port": 80/' $INSTALL_DIR/config.json
        sed -i 's/"web_port": 80/"web_port": 80/' $INSTALL_DIR/config.json
        sed -i 's/"http_port": 80/"http_port": 80/' $INSTALL_DIR/config.json
        sed -i 's/"https_port": 443/"https_port": 443/' $INSTALL_DIR/config.json
    fi
else
    echo "跳过域名配置，将使用 HTTP 模式"
fi

echo "[8/8] 设置权限..."
chmod +x $INSTALL_DIR/start.sh
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
echo "启动服务:"
echo "  systemctl start hupo-bridge"
echo "  systemctl start hupo-voice"
echo ""
echo "或使用启动脚本:"
echo "  cd $INSTALL_DIR && ./start.sh"
echo ""
echo "查看状态:"
echo "  ./status.sh"
echo "  systemctl status hupo-bridge"
echo ""
echo "查看日志:"
echo "  journalctl -u hupo-bridge -f"
echo "  tail -f $INSTALL_DIR/logs/bridge_*.log"
echo ""
if [ -n "$DOMAIN" ]; then
    echo "HTTPS 访问地址: https://$DOMAIN"
    echo "HTTP 会自动重定向到 HTTPS"
else
    echo "【配置信息】"
    echo "  HTTP端口: 80"
    echo "  HTTPS端口: 443"
    echo "  Voice端口: 85"
fi
echo ""
echo "========================================"
