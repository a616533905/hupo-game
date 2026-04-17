#!/bin/bash

SERVER_IP="117.72.177.240"
SERVER_USER="root"
SERVER_PORT="22"

echo "========================================"
echo "  琥珀冒险 - 远程连接服务器"
echo "========================================"
echo ""

ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP
