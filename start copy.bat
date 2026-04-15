@echo off
setlocal enabledelayedexpansion
title Game Server Startup

echo ========================================
echo   琥珀冒险 - 游戏服务器启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] 读取配置文件...
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty api_port"') do set API_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty voice_port"') do set VOICE_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty access_token"') do set ACCESS_TOKEN=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty ssl_cert_file"') do set SSL_CERT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty ssl_key_file"') do set SSL_KEY=%%a

if "%API_PORT%"=="" set API_PORT=80
if "%VOICE_PORT%"=="" set VOICE_PORT=85
if "%ACCESS_TOKEN%"=="" set ACCESS_TOKEN=hupo_secret_token_2024

echo   API端口: %API_PORT%
echo   语音端口: %VOICE_PORT%
if "%SSL_CERT%" neq "" (
    echo   SSL证书: %SSL_CERT%
) else (
    echo   SSL证书: 未配置
)
echo.

echo [2/5] 清理端口...
echo   检查端口 %API_PORT% (AI Bridge)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%API_PORT% " ^| findstr "LISTENING" ^| findstr /v "0.0.0.0" ^| findstr /v ":::"') do (
    echo     发现端口 %API_PORT% 被占用，PID: %%a
    for /f "tokens=1" %%b in ('wmic process where ProcessId=%%a get Name 2^|findstr ".exe"') do set PROC_NAME=%%b
    echo     进程名: !PROC_NAME!
    echo     正在关闭...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo     端口 %API_PORT% 已清理

echo   检查端口 %VOICE_PORT% (Voice Proxy)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%VOICE_PORT% " ^| findstr "LISTENING" ^| findstr /v "0.0.0.0" ^| findstr /v ":::"') do (
    echo     发现端口 %VOICE_PORT% 被占用，PID: %%a
    for /f "tokens=1" %%b in ('wmic process where ProcessId=%%a get Name 2^|findstr ".exe"') do set PROC_NAME=%%b
    echo     进程名: !PROC_NAME!
    echo     正在关闭...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo     端口 %VOICE_PORT% 已清理

timeout /t 2 /nobreak >nul

echo [3/5] 检查SSL证书...
if "%SSL_CERT%" neq "" (
    if exist "%SSL_CERT%" (
        echo   证书已存在: %SSL_CERT%
    ) else (
        echo   正在生成自签名SSL证书...
        for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do set LAN_IP=%%a
        echo   服务器IP: !LAN_IP!

        echo [req] > openssl.cnf
        echo distinguished_name = req_distinguished_name >> openssl.cnf
        echo prompt = no >> openssl.cnf
        echo [req_distinguished_name] >> openssl.cnf
        echo CN = !LAN_IP! >> openssl.cnf

        openssl req -x509 -newkey rsa:2048 -keyout "%SSL_KEY%" -out "%SSL_CERT%" -days 365 -nodes -subj "/CN=!LAN_IP!" -config openssl.cnf >nul 2>&1
        if errorlevel 1 (
            echo   警告: 证书生成失败，SSL功能将不可用
        ) else (
            echo   证书已生成: %SSL_CERT%
            del openssl.cnf 2>nul
        )
    )
) else (
    echo   未配置SSL证书，跳过
)
echo.

echo [4/5] 启动 AI Bridge (端口 %API_PORT%, 含Web服务)...
if "%SSL_CERT%" neq "" (
    start "AI Bridge" cmd /k "set SSL_CERT_FILE=%SSL_CERT%&& set SSL_KEY_FILE=%SSL_KEY%&& set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"
) else (
    start "AI Bridge" cmd /k "set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"
)

echo [5/5] 启动语音代理 (端口 %VOICE_PORT%)...
start "Voice Proxy" cmd /k "set VOICE_PORT=%VOICE_PORT%&& node voice-proxy.js"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   所有服务已启动！
echo ========================================
echo.
if "%SSL_CERT%" neq "" (
    echo   本地访问:  https://localhost:%API_PORT%
) else (
    echo   本地访问:  http://localhost:%API_PORT%
)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :show_ip
)
:show_ip
if "%SSL_CERT%" neq "" (
    echo   局域网访问: https:%IP%:%API_PORT%
    echo   ^(首次访问需在浏览器中信任自签名证书^)
) else (
    echo   局域网访问: http:%IP%:%API_PORT%
)
echo.
if "%SSL_CERT%" neq "" (
    echo   API端口: %API_PORT% (HTTPS)
) else (
    echo   API端口: %API_PORT% (HTTP)
)
echo   语音端口: %VOICE_PORT%
echo.
if "%SSL_CERT%" neq "" (
    echo   Token访问: https://localhost:%API_PORT%/?token=%ACCESS_TOKEN%
) else (
    echo   Token访问: http://localhost:%API_PORT%/?token=%ACCESS_TOKEN%
)
echo.
echo ========================================
echo.
if "%SSL_CERT%" neq "" (
    echo 提示: 首次访问需在浏览器中信任自签名证书
    echo       手机访问时请用HTTPS并信任证书
) else (
    echo 提示: 请确保防火墙允许这些端口访问
    echo       手机访问时请使用局域网IP地址
)
echo.

timeout /t 10 /nobreak >nul
