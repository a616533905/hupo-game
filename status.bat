@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ========================================
echo   Hupo Game - Service Status (Windows)
echo ========================================
echo.

echo [Process Status]
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /I "python" >nul
if %ERRORLEVEL% equ 0 (
    echo   Bridge: Running
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" ^| findstr /I "python"') do echo     PID: %%a
) else (
    echo   Bridge: Not running
)

tasklist /FI "IMAGENAME eq node.exe" 2>nul | findstr /I "node" >nul
if %ERRORLEVEL% equ 0 (
    echo   Voice: Running
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" ^| findstr /I "node"') do echo     PID: %%a
) else (
    echo   Voice: Not running
)
echo.

echo [Port Listening]
netstat -ano | findstr ":80 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Port 80: Listening
) else (
    echo   Port 80: Not listening
)

netstat -ano | findstr ":443 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Port 443: Listening
) else (
    echo   Port 443: Not listening
)

netstat -ano | findstr ":85 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Port 85: Listening
) else (
    echo   Port 85: Not listening
)
echo.

echo [System Resources]
for /f "skip=1" %%a in ('wmic cpu get loadpercentage') do (
    if not "%%a"=="" echo   CPU Usage: %%a%%
    goto :cpu_done
)
:cpu_done
for /f "skip=1 tokens=2,3" %%a in ('wmic OS get TotalVisibleMemorySize^,FreePhysicalMemory /value') do (
    set /a used=%%a-%%b
    set /a percent=used*100/%%a
    echo   Memory Usage: !percent!%%
    goto :mem_done
)
:mem_done
echo.

echo [Request Statistics]
curl -s http://127.0.0.1:80/health >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%a in ('curl -s http://127.0.0.1:80/health ^| powershell -Command "$input | ConvertFrom-Json | Select-Object -ExpandProperty requests_total"') do echo   Total Requests: %%a
    for /f "tokens=*" %%a in ('curl -s http://127.0.0.1:80/health ^| powershell -Command "$input | ConvertFrom-Json | Select-Object -ExpandProperty uptime"') do echo   Uptime: %%a seconds
) else (
    echo   Unable to retrieve (service not running)
)
echo.

echo ========================================
pause
