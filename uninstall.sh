#!/bin/bash

echo "========================================"
echo "  琥珀冒险 - 卸载脚本"
echo "========================================"
echo ""

INSTALL_DIR="/root/hupo-game"
DATA_DIR="$INSTALL_DIR/data"

if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 权限运行此脚本"
    echo "sudo ./uninstall.sh"
    exit 1
fi

read -p "确定要卸载琥珀冒险吗？(y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "取消卸载"
    exit 0
fi

echo ""
echo "[1/6] 停止服务..."
if [ -f "$INSTALL_DIR/stop.sh" ]; then
    cd "$INSTALL_DIR" && ./stop.sh --force --wait --max-wait=10 2>/dev/null || true
else
    systemctl stop hupo-bridge 2>/dev/null || true
    systemctl stop hupo-voice 2>/dev/null || true
fi

echo "[2/6] 禁用服务..."
systemctl disable hupo-bridge 2>/dev/null || true
systemctl disable hupo-voice 2>/dev/null || true

echo "[3/6] 清理防火墙规则..."
read -p "是否清理所有由SOAR添加的防火墙规则？(y/N): " clean_fw
if [ "$clean_fw" = "y" ] || [ "$clean_fw" = "Y" ]; then
    if [ -f "$DATA_DIR/blacklist.json" ]; then
        echo "  清理永久封禁IP..."
        python3 -c "
import json
try:
    with open('$DATA_DIR/blacklist.json', 'r') as f:
        data = json.load(f)
    for ip in data.get('permanent', []):
        print(ip)
except:
    pass
" | while read ip; do
            if [ -n "$ip" ]; then
                iptables -D INPUT -s "$ip" -j DROP 2>/dev/null || true
                echo "    已移除: $ip"
            fi
        done
    fi
    
    if [ -f "$DATA_DIR/temp_ban.json" ]; then
        echo "  清理临时封禁IP..."
        python3 -c "
import json
try:
    with open('$DATA_DIR/temp_ban.json', 'r') as f:
        data = json.load(f)
    for ip in data.keys():
        print(ip)
except:
    pass
" | while read ip; do
            if [ -n "$ip" ]; then
                iptables -D INPUT -s "$ip" -j DROP 2>/dev/null || true
                echo "    已移除: $ip"
            fi
        done
    fi
    echo "  防火墙规则清理完成"
fi

echo "[4/6] 清理定时任务..."
crontab -l 2>/dev/null | grep -v "health_check.sh" | grep -v "log_auditor.py" | crontab - 2>/dev/null || true
echo "  定时任务已清理"

echo "[5/6] 删除系统服务文件..."
rm -f /etc/systemd/system/hupo-bridge.service
rm -f /etc/systemd/system/hupo-voice.service
rm -f /usr/local/bin/soar
rm -f /etc/logrotate.d/hupo-game
systemctl daemon-reload
echo "  系统服务文件已删除"
echo "  logrotate 配置已删除"

echo "[6/6] 删除安装目录..."
read -p "是否删除安装目录 $INSTALL_DIR？(y/N): " delete_dir
if [ "$delete_dir" = "y" ] || [ "$delete_dir" = "Y" ]; then
    if [ -d "$DATA_DIR" ]; then
        read -p "是否备份 SOAR 数据文件（封禁列表等）？(y/N): " backup_data
        if [ "$backup_data" = "y" ] || [ "$backup_data" = "Y" ]; then
            BACKUP_DIR="/root/hupo-backup-$(date +%Y%m%d_%H%M%S)"
            mkdir -p "$BACKUP_DIR"
            cp -r "$DATA_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
            echo "  数据已备份到: $BACKUP_DIR"
        fi
    fi
    rm -rf $INSTALL_DIR
    echo "  安装目录已删除"
else
    echo "  保留安装目录: $INSTALL_DIR"
fi

echo ""
echo "========================================"
echo "  卸载完成！"
echo "========================================"
echo ""
echo "如需重新安装，请运行: ./install.sh"
echo ""
