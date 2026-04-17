#!/bin/bash

SERVER_IP="117.72.177.240"
SERVER_USER="root"
SERVER_PORT="22"
SERVER_DIR="/root/hupo-game"
GIT_REMOTE="https://github.com/a616533905/hupo-game.git"

echo "========================================"
echo "  琥珀冒险 - 推送更新到服务器"
echo "========================================"
echo ""

echo "[1/3] 检查 Git 状态..."
cd "$(dirname "$0")"

if [ -n "$(git status --porcelain)" ]; then
    echo "  有未提交的更改，正在提交..."
    git add -A
    git commit -m "更新: $(date '+%Y-%m-%d %H:%M:%S')"
else
    echo "  无未提交的更改"
fi

echo "[2/3] 推送到 GitHub..."
git push -u origin main
if [ $? -ne 0 ]; then
    echo "  错误: GitHub 推送失败"
    exit 1
fi
echo "  推送成功"

echo "[3/3] 在服务器上执行更新..."
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP << 'ENDSSH'
    cd /root/hupo-game
    echo "  正在拉取最新代码..."
    git pull origin main
    echo "  更新完成"
ENDSSH

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  推送完成！"
    echo "========================================"
else
    echo ""
    echo "========================================"
    echo "  警告: 服务器更新可能失败，请检查连接"
    echo "========================================"
fi
