@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Game Server Startup

echo ========================================
echo   琥珀冒险 - 游戏服务器启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] 读取配置文件...
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty api_port"') do set API_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty server | Select-Object -ExpandProperty voice_port"') do set VOICE_PORT=%%a
for /f "tokens=*" %%a in ('powershell -Command "Get-Content config.json | ConvertFrom-Json | Select-Object -ExpandProperty access_token"') do set ACCESS_TOKEN=%%a

if "%API_PORT%"=="" set API_PORT=80
if "%VOICE_PORT%"=="" set VOICE_PORT=85
if "%ACCESS_TOKEN%"=="" set ACCESS_TOKEN=hupo_secret_token_2024

echo   API端口: %API_PORT%
echo   语音端口: %VOICE_PORT%
echo.

echo [2/4] 清理端口...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%API_PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%VOICE_PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

timeout /t 2 /nobreak >nul

echo [3/4] 启动 AI Bridge (端口 %API_PORT%, 含Web服务)...
start "AI Bridge" cmd /k "set API_PORT=%API_PORT%&& set VOICE_PORT=%VOICE_PORT%&& python nanobot_bridge.py"

echo [4/4] 启动语音代理 (端口 %VOICE_PORT%)...
start "Voice Proxy" cmd /k "set VOICE_PORT=%VOICE_PORT%&& node voice-proxy.js"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   所有服务已启动！
echo ========================================
echo.
echo   本地访问:  http://localhost:%API_PORT%
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :show_ip
)
:show_ip
echo   局域网访问: http:%IP%:%API_PORT%
echo.
echo   API端口: %API_PORT% (集成Web服务)
echo   语音端口: %VOICE_PORT%
echo.
echo   Token访问: http://localhost:%API_PORT%/?token=%ACCESS_TOKEN%
echo.
echo ========================================
echo.
echo 提示: 请确保防火墙允许这些端口访问
echo       手机访问时请使用局域网IP地址
echo.

timeout /t 10 /nobreak >nul
