@echo off
chcp 65001 >nul
echo ========================================
echo   琥珀冒险 - 远程连接服务器
echo ========================================
echo.

set SERVER_IP=117.72.177.240
set SERVER_USER=root
set SERVER_PORT=22

echo 连接到 %SERVER_USER@%SERVER_IP%...
echo.

ssh -p %SERVER_PORT% %SERVER_USER@%SERVER_IP%
