@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Hupo Game - Remote Server Connect
echo ========================================
echo.

if not exist "server.ini" (
    echo Error: server.ini not found
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "^host" server.ini') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^user" server.ini') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^port" server.ini') do set "SERVER_PORT=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "^password" server.ini') do set "SERVER_PASS=%%b"

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
if not defined SERVER_PASS (
    echo Error: Cannot read password
    pause
    exit /b 1
)

echo Connecting to %SERVER_USER%@%SERVER_IP%:%SERVER_PORT%...
echo.

echo %SERVER_PASS% | plink -P %SERVER_PORT% %SERVER_USER%@%SERVER_IP% -pw %SERVER_PASS%
