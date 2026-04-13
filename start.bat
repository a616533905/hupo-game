@echo off
setlocal enabledelayedexpansion
title Game Server Startup

echo ========================================
echo   Game Server Startup Script
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Loading configuration...
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty api_port"') do set API_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty voice_port"') do set VOICE_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty access_token"') do set ACCESS_TOKEN=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty ssl_cert_file"') do set SSL_CERT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty ssl_key_file"') do set SSL_KEY=%%a

if "%API_PORT%"=="" set API_PORT=443
if "%VOICE_PORT%"=="" set VOICE_PORT=85
if "%ACCESS_TOKEN%"=="" set ACCESS_TOKEN=hupo_secret_token_2024

echo   API Port: %API_PORT%
echo   Voice Port: %VOICE_PORT%
if "%SSL_CERT%" neq "" (
    echo   SSL Cert: %SSL_CERT%
) else (
    echo   SSL Cert: Not configured
)
echo.

echo [2/5] Checking ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%API_PORT% " ^| findstr "LISTENING"') do (
    echo   Closing port %API_PORT% PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%VOICE_PORT% " ^| findstr "LISTENING"') do (
    echo   Closing port %VOICE_PORT% PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
if "%SSL_CERT%" neq "" (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":80 " ^| findstr "LISTENING"') do (
        echo   Closing port 80 PID: %%a ^(HTTP redirect^)
        taskkill /F /PID %%a >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul
echo   Ports cleared
echo.

echo [3/5] Checking SSL certificates...
if "%SSL_CERT%" neq "" (
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
            echo   Error: Certificate generation failed, SSL disabled
            set SSL_CERT=
            set SSL_KEY=
        ) else (
            echo   Certificate generated: %SSL_CERT%
            del openssl.cnf 2>nul
        )
    )
) else (
    echo   No SSL certificate configured, skipping
)
echo.

echo [4/5] Starting AI Bridge (port %API_PORT%)...
if "%SSL_CERT%" neq "" (
    start "AI Bridge" cmd /k "set SSL_CERT_FILE=%SSL_CERT%&& set SSL_KEY_FILE=%SSL_KEY%&& set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"
) else (
    start "AI Bridge" cmd /k "set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"
)

echo [5/5] Starting voice proxy (port %VOICE_PORT%)...
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

if "%SSL_CERT%" neq "" (
    echo   Local:         https://localhost:%API_PORT%
    echo   Network:       https://!LAN_IP!:%API_PORT%
    echo   ^(First visit may show certificate warning^)
    echo.
    echo   HTTP traffic will redirect to HTTPS
) else (
    echo   Local:         http://localhost:%API_PORT%
    echo   Network:       http://!LAN_IP!:%API_PORT%
)
echo.
echo   Voice Port: %VOICE_PORT%
echo   Token param: ?token=%ACCESS_TOKEN%
echo.
echo ========================================
echo.

if "%SSL_CERT%" neq "" (
    echo Note: First visit may show self-signed certificate warning
    echo       Accept on mobile to enable HTTPS
) else (
    echo Note: Make sure firewall allows these ports
    echo       Use local IP address for mobile access
)
echo.

timeout /t 10 /nobreak >nul
