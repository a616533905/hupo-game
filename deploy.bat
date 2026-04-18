@echo off
setlocal enabledelayedexpansion

if not exist "server.ini" (
    echo Error: server.ini not found
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "host" server.ini ^| findstr /v "\["') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "user" server.ini ^| findstr /v "\["') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "port" server.ini ^| findstr /v "\["') do set "SERVER_PORT=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "dir" server.ini ^| findstr /v "\["') do set "SERVER_DIR=%%b"

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

for %%f in (nanobot_bridge.py voice-proxy.js start.sh status.sh stop.sh install.sh uninstall.sh config.json config.example.json requirements.txt hupo-bridge.service hupo-voice.service logrotate.conf index.html favicon.ico README.md .gitignore) do (
    if exist "%%f" (
        echo [Copying] %%f
        scp -P %SERVER_PORT% "%%f" %SERVER_USER%@%SERVER_IP%:%SERVER_DIR%/
    ) else (
        echo [Skip] %%f - not found
    )
)

echo.
echo Copying cron directory...
if exist "cron" (
    ssh -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "mkdir -p %SERVER_DIR%/cron"
    scp -P %SERVER_PORT% -r cron/* %SERVER_USER%@%SERVER_IP%:%SERVER_DIR%/cron/
    echo [Done] cron directory copied
) else (
    echo [Skip] cron directory not found
)

echo.
echo Copying screenshots directory...
if exist "screenshots" (
    ssh -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "mkdir -p %SERVER_DIR%/screenshots"
    scp -P %SERVER_PORT% -r screenshots/* %SERVER_USER%@%SERVER_IP%:%SERVER_DIR%/screenshots/
    echo [Done] screenshots directory copied
)

echo.
echo Setting execute permissions...
ssh -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "chmod +x %SERVER_DIR%/*.sh %SERVER_DIR%/cron/*.sh %SERVER_DIR%/cron/*.py"

echo.
echo ========================================
echo   Deploy Complete!
echo ========================================
echo.
echo Next steps:
echo   1. SSH to server: ssh %SERVER_USER%@%SERVER_IP%
echo   2. Run install: cd %SERVER_DIR% ^&^& ./install.sh
echo   3. Start services: ./start.sh or systemctl start hupo-bridge hupo-voice
echo.
pause
