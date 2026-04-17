@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   琥珀冒险 - 远程连接服务器
echo ========================================
echo.

if not exist "server.ini" (
    echo 错误: server.ini 配置文件不存在
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "^host" server.ini') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^user" server.ini') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^port" server.ini') do set "SERVER_PORT=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^password" server.ini') do set "SERVER_PASS=%%b"

if not defined SERVER_IP (
    echo 错误: 无法读取 host
    pause
    exit /b 1
)
if not defined SERVER_USER (
    echo 错误: 无法读取 user
    pause
    exit /b 1
)
if not defined SERVER_PORT set SERVER_PORT=22
if not defined SERVER_PASS (
    echo 错误: 无法读取 password
    pause
    exit /b 1
)

echo 连接到 %SERVER_USER%@%SERVER_IP%:%SERVER_PORT%...
echo.

echo %SERVER_PASS% | plink -P %SERVER_PORT% %SERVER_USER%@%SERVER_IP% -pw %SERVER_PASS%
