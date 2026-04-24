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

for /f "tokens=2" %%a in ('wmic process where "commandline like '%%nanobot_bridge.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    if %FORCE_STOP% equ 1 (
        taskkill /F /PID %%a >nul 2>&1
    ) else (
        taskkill /PID %%a >nul 2>&1
    )
    echo   AI Bridge stopped (PID: %%a)
)

for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST 2^>nul ^| findstr "PID:"') do (
    wmic process where "processid=%%a and commandline like '%%nanobot_bridge.py%%'" get processid 2>nul | findstr /r "[0-9]" >nul
    if !ERRORLEVEL! equ 0 (
        if %FORCE_STOP% equ 1 (
            taskkill /F /PID %%a >nul 2>&1
        ) else (
            taskkill /PID %%a >nul 2>&1
        )
        echo   AI Bridge stopped (PID: %%a)
    )
)

echo.

echo [2/3] Stopping Voice Proxy (Node.js)...

for /f "tokens=2" %%a in ('wmic process where "commandline like '%%voice-proxy.js%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    if %FORCE_STOP% equ 1 (
        taskkill /F /PID %%a >nul 2>&1
    ) else (
        taskkill /PID %%a >nul 2>&1
    )
    echo   Voice Proxy stopped (PID: %%a)
)

for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" /FO LIST 2^>nul ^| findstr "PID:"') do (
    wmic process where "processid=%%a and commandline like '%%voice-proxy.js%%'" get processid 2>nul | findstr /r "[0-9]" >nul
    if !ERRORLEVEL! equ 0 (
        if %FORCE_STOP% equ 1 (
            taskkill /F /PID %%a >nul 2>&1
        ) else (
            taskkill /PID %%a >nul 2>&1
        )
        echo   Voice Proxy stopped (PID: %%a)
    )
)

echo.

echo [3/3] Waiting for ports to release...

set WAIT_COUNT=0
:wait_ports
set PORTS_IN_USE=0

netstat -ano | findstr ":80 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 set PORTS_IN_USE=1

netstat -ano | findstr ":443 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 set PORTS_IN_USE=1

netstat -ano | findstr ":85 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 set PORTS_IN_USE=1

if %PORTS_IN_USE% equ 1 (
    set /a WAIT_COUNT+=1
    if !WAIT_COUNT! lss 10 (
        timeout /t 1 /nobreak >nul
        goto :wait_ports
    ) else (
        echo   Warning: Ports still in use after 10 seconds
    )
) else (
    echo   All ports released
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