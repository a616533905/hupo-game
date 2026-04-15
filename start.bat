@echo off
setlocal enabledelayedexpansion
title Game Server Startup

set USE_HTTPS=0
set SELECTED_MODE=

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="--https" (
    set USE_HTTPS=1
    set SELECTED_MODE=HTTPS
    shift
    goto :parse_args
)
if /i "%~1"=="-s" (
    set USE_HTTPS=1
    set SELECTED_MODE=HTTPS
    shift
    goto :parse_args
)
if /i "%~1"=="--http" (
    set USE_HTTPS=0
    set SELECTED_MODE=HTTP
    shift
    goto :parse_args
)
if /i "%~1"=="-h" (
    set USE_HTTPS=0
    set SELECTED_MODE=HTTP
    shift
    goto :parse_args
)
echo Unknown option: %~1
echo Usage: %0 [--https^|-s] [--http^|-h]
exit /b 1

:done_args

echo ========================================
echo   Hupo Game Server Startup Script
echo ========================================
echo.

cd /d "%~dp0"

echo [1/6] Loading configuration...
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty api_port"') do set API_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty voice_port"') do set VOICE_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty access_token"') do set ACCESS_TOKEN=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty ssl_cert_file"') do set SSL_CERT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty ssl_key_file"') do set SSL_KEY=%%a

if "%API_PORT%"=="" set API_PORT=8080
if "%VOICE_PORT%"=="" set VOICE_PORT=85
if "%ACCESS_TOKEN%"=="" set ACCESS_TOKEN=hupo_secret_token_2024

if "%SELECTED_MODE%"=="" (
    echo ========================================
    echo   Select server mode:
    echo ========================================
    echo   [1] HTTP only      - No SSL, simpler setup
    echo   [2] HTTPS          - Secure, requires certificate
    echo ========================================
    echo.
    choice /c:12 /m:"Select mode (1 or 2)"
    if errorlevel 2 (
        set USE_HTTPS=1
        set SELECTED_MODE=HTTPS
    ) else (
        set USE_HTTPS=0
        set SELECTED_MODE=HTTP
    )
)

echo.
echo   API Port: %API_PORT%
echo   Voice Port: %VOICE_PORT%
echo   Mode: %SELECTED_MODE%
echo.

echo [2/6] Checking ports...
if "%USE_HTTPS%"=="1" (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":80 " ^| findstr "LISTENING"') do (
        echo   Closing port 80 PID: %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%API_PORT% " ^| findstr "LISTENING"') do (
    echo   Closing port %API_PORT% PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%VOICE_PORT% " ^| findstr "LISTENING"') do (
    echo   Closing port %VOICE_PORT% PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo   Ports cleared
echo.

echo [3/6] Checking SSL certificates...
if "%USE_HTTPS%"=="1" (
    if exist "%SSL_CERT%" (
        echo   Certificate exists: %SSL_CERT%
    ) else (
        echo   Generating self-signed SSL certificate...
        for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
            set LAN_IP=%%a
            goto :got_ip
        )
        :got_ip
        set LAN_IP=!LAN_IP: =!
        echo   Local IP: !LAN_IP!

        echo [req] > openssl.cnf
        echo distinguished_name = req_distinguished_name >> openssl.cnf
        echo prompt = no >> openssl.cnf
        echo [req_distinguished_name] >> openssl.cnf
        echo CN = !LAN_IP! >> openssl.cnf

        openssl req -x509 -newkey rsa:2048 -keyout "%SSL_KEY%" -out "%SSL_CERT%" -days 365 -nodes -subj "/CN=!LAN_IP!" -config openssl.cnf >nul 2>&1
        if errorlevel 1 (
            echo   Error: Certificate generation failed
            set USE_HTTPS=0
            set SELECTED_MODE=HTTP
        ) else (
            echo   Certificate generated: %SSL_CERT%
            del openssl.cnf 2>nul
        )
    )
) else (
    echo   HTTPS disabled, skipping SSL certificates
)
echo.

echo [4/6] Starting AI Bridge (port %API_PORT%)...
if "%USE_HTTPS%"=="1" (
    start "AI Bridge" cmd /k "set SSL_CERT_FILE=%SSL_CERT%&& set SSL_KEY_FILE=%SSL_KEY%&& set USE_HTTPS=1&& set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"
) else (
    start "AI Bridge" cmd /k "set USE_HTTPS=0&& set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"
)

echo [5/6] Starting voice proxy (port %VOICE_PORT%)...
start "Voice Proxy" cmd /k "set VOICE_PORT=%VOICE_PORT%&& node voice-proxy.js"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Server Started Successfully
echo ========================================
echo.

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set LAN_IP=%%a
    goto :show_ip
)
:show_ip
set LAN_IP=!LAN_IP: =!

if "%USE_HTTPS%"=="1" (
    echo   Local:         https://localhost:%API_PORT%
    echo   Network:       https://!LAN_IP!:%API_PORT%
    echo   ^(First visit: accept self-signed certificate^)
    echo.
    echo   HTTP port 80 redirects to HTTPS
) else (
    echo   Local:         http://localhost:%API_PORT%
    echo   Network:       http://!LAN_IP!:%API_PORT%
)
echo.
echo   Voice Port: %VOICE_PORT%
echo   Token:      ?token=%ACCESS_TOKEN%
echo.
echo ========================================
echo.

if "%USE_HTTPS%"=="1" (
    echo Note: First visit may show self-signed certificate warning
    echo       Accept on mobile to enable HTTPS
) else (
    echo Note: Make sure firewall allows these ports
    echo       Use local IP address for mobile access
)
echo.

timeout /t 10 /nobreak >nul
