@echo off
setlocal enabledelayedexpansion

if not exist "server.ini" (
    echo Error: server.ini not found
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "^host" server.ini') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^user" server.ini') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^port" server.ini') do set "SERVER_PORT=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^dir" server.ini') do set "SERVER_DIR=%%b"

if not defined SERVER_PORT set SERVER_PORT=22
if not defined SERVER_DIR set SERVER_DIR=/root/hupo-game

echo ========================================
echo   Hupo Game - Deploy to Server
echo ========================================
echo.
echo Server: %SERVER_USER%@%SERVER_IP%:%SERVER_PORT%
echo Directory: %SERVER_DIR%
echo.

echo Deploying files...
echo.

for %%f in (nanobot_bridge.py voice-proxy.js start.sh status.sh stop.sh install.sh config.json requirements.txt hupo-bridge.service hupo-voice.service logrotate.conf) do (
    if exist "%%f" (
        echo [Copying] %%f
        scp -P %SERVER_PORT% "%%f" %SERVER_USER%@%SERVER_IP%:%SERVER_DIR%/
    ) else (
        echo [Skip] %%f - not found
    )
)

echo.
echo Setting execute permissions...
ssh -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "chmod +x %SERVER_DIR%/*.sh"

echo.
echo ========================================
echo   Deploy Complete!
echo ========================================
pause
