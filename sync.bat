@echo off
chcp 65001 >nul

if not exist "server.ini" (
    echo 错误: server.ini 配置文件不存在
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "^host" server.ini') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^user" server.ini') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^port" server.ini') do set "SERVER_PORT=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^password" server.ini') do set "SERVER_PASS=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^dir" server.ini') do set "SERVER_DIR=%%b"

if not defined SERVER_PORT set SERVER_PORT=22
if not defined SERVER_DIR set SERVER_DIR=/root/hupo-game

if not defined SERVER_PASS (
    echo 错误: 无法读取 password
    pause
    exit /b 1
)

echo ========================================
echo   琥珀冒险 - 同步到服务器
echo ========================================
echo.

echo 服务器: %SERVER_USER%@%SERVER_IP%:%SERVER_PORT%
echo 目录: %SERVER_DIR%
echo.

echo %SERVER_PASS% | plink -batch -P %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "cd %SERVER_DIR% && git pull origin main"
pause