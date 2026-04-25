@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

set FORCE_STOP=0
if /i "%~1"=="--force" set FORCE_STOP=1

echo Stopping AI Bridge...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":80 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":443 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":85 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Stopping Voice Proxy...
taskkill /F /IM node.exe /FI "WINDOWTITLE eq Voice Proxy*" >nul 2>&1

REM LINT:IGNORE W001
echo Done.
