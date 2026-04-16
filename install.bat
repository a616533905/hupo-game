@echo off
chcp 65001 >nul
echo ========================================
echo   Hupo Game - Installation Script (Windows)
echo ========================================
echo.

set INSTALL_DIR=%~dp0

echo [1/4] Checking dependencies...

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python not found, please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Node.js not found, please install Node.js 18+
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

echo [2/4] Installing Python dependencies (psutil)...
python -c "import psutil" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo   psutil already installed, skipping
) else (
    echo   Installing psutil...
    pip install psutil
    if %ERRORLEVEL% neq 0 (
        echo   Warning: psutil installation failed, please run manually: pip install psutil
    )
)

echo [3/4] Creating log directory...
if not exist "%INSTALL_DIR%logs" mkdir "%INSTALL_DIR%logs"

echo [4/4] Setting firewall rules...
netsh advfirewall firewall show rule name="Hupo Game HTTP" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    netsh advfirewall firewall add rule name="Hupo Game HTTP" dir=in action=allow protocol=tcp localport=80
    netsh advfirewall firewall add rule name="Hupo Game HTTPS" dir=in action=allow protocol=tcp localport=443
    netsh advfirewall firewall add rule name="Hupo Game Voice" dir=in action=allow protocol=tcp localport=85
    echo Firewall rules added
) else (
    echo Firewall rules already exist
)

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Config file: %INSTALL_DIR%config.json
echo Log directory: %INSTALL_DIR%logs\
echo.
echo [Port Configuration]
echo   HTTP Port: 80
echo   HTTPS Port: 443
echo   Voice Port: 85
echo.
echo [Start Server]
echo   Double-click start.bat or run: start.bat
echo.
echo [HTTPS Configuration]
echo   Start with HTTPS mode: start.bat --https
echo   Or interactive selection: start.bat
echo.
echo ========================================
pause
