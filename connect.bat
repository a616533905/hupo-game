@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   琥珀冒险 - 远程连接服务器
echo ========================================
echo.

if not exist "server.ini" (
    echo 错误: server.ini 配置文件不存在
    echo 请创建 server.ini 文件
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "host" server.ini') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "user" server.ini') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "port" server.ini') do set "SERVER_PORT=%%b"

echo 连接到 %SERVER_USER%@%SERVER_IP%...
echo.

ssh -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP%
