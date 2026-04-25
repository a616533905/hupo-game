setlocal enabledelayedexpansion

echo ========================================
echo   Hupo Game - Remote Server Connect
echo ========================================
echo.

if not exist "secrets\server.ini" (
    echo Error: secrets\server.ini not found
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "host" secrets\server.ini ^| findstr /v "\["') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "user" secrets\server.ini ^| findstr /v "\["') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "port" secrets\server.ini ^| findstr /v "\["') do set "SERVER_PORT=%%b"

if not defined SERVER_IP (
    echo Error: Cannot read host
    pause
    exit /b 1
)
if not defined SERVER_USER (
    echo Error: Cannot read user
    pause
    exit /b 1
)
if not defined SERVER_PORT set SERVER_PORT=22

echo Connecting to %SERVER_USER%@%SERVER_IP%:%SERVER_PORT%...
echo.

ssh -t -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "cd /root/hupo-game; bash --login"
