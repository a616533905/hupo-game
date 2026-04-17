@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Stop Hupo Game Server

echo ========================================
echo   Hupo Game - Stop Server
echo ========================================
echo.

set FORCE_STOP=0
if /i "%~1"=="--force" (
    set FORCE_STOP=1
    echo [Mode] Force stop enabled
    echo.
)

echo [1/3] Stopping AI Bridge (Python)...

tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /I "python" >nul
if %ERRORLEVEL% equ 0 (
    if %FORCE_STOP% equ 1 (
        taskkill /F /IM python.exe >nul 2>&1
    ) else (
        taskkill /IM python.exe >nul 2>&1
    )
    if %ERRORLEVEL% equ 0 (
        echo   AI Bridge stopped
    ) else (
        echo   AI Bridge already stopped or not found
    )
) else (
    echo   AI Bridge not running
)

echo.

echo [2/3] Stopping Voice Proxy (Node.js)...

tasklist /FI "IMAGENAME eq node.exe" 2>nul | findstr /I "node" >nul
if %ERRORLEVEL% equ 0 (
    if %FORCE_STOP% equ 1 (
        taskkill /F /IM node.exe >nul 2>&1
    ) else (
        taskkill /IM node.exe >nul 2>&1
    )
    if %ERRORLEVEL% equ 0 (
        echo   Voice Proxy stopped
    ) else (
        echo   Voice Proxy already stopped or not found
    )
) else (
    echo   Voice Proxy not running
)

echo.

echo [3/3] Checking ports...

netstat -ano | findstr ":80 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Warning: Port 80 still in use
)

netstat -ano | findstr ":443 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Warning: Port 443 still in use
)

netstat -ano | findstr ":85 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Warning: Port 85 still in use
)

echo.

echo ========================================
echo   Server Stop Complete
echo ========================================
echo.
echo If services are still running, try:
echo   stop.bat --force
echo.
pause