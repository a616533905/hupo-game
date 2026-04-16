@echo off
chcp 65001 >nul
echo ========================================
echo   琥珀冒险 - 安装脚本 (Windows)
echo ========================================
echo.

set INSTALL_DIR=%~dp0

echo [1/4] 检查依赖...

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 错误: 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 错误: 未找到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo [2/4] 安装 Python 依赖 (psutil)...
python -c "import psutil" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo   psutil 已安装，跳过
) else (
    echo   正在安装 psutil...
    pip install psutil
    if %ERRORLEVEL% neq 0 (
        echo   警告: psutil 安装失败，请手动运行: pip install psutil
    )
)

echo [3/4] 创建日志目录...
if not exist "%INSTALL_DIR%logs" mkdir "%INSTALL_DIR%logs"

echo [4/4] 设置防火墙规则...
netsh advfirewall firewall show rule name="Hupo Game HTTP" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    netsh advfirewall firewall add rule name="Hupo Game HTTP" dir=in action=allow protocol=tcp localport=80
    netsh advfirewall firewall add rule name="Hupo Game HTTPS" dir=in action=allow protocol=tcp localport=443
    netsh advfirewall firewall add rule name="Hupo Game Voice" dir=in action=allow protocol=tcp localport=85
    echo 防火墙规则已添加
) else (
    echo 防火墙规则已存在
)

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 配置文件: %INSTALL_DIR%config.json
echo 日志目录: %INSTALL_DIR%logs\
echo.
echo 【端口配置】
echo   HTTP端口: 80
echo   HTTPS端口: 443
echo   Voice端口: 85
echo.
echo 【启动方式】
echo   双击 start.bat 或运行: start.bat
echo.
echo 【HTTPS配置】
echo   启动时选择 HTTPS 模式: start.bat --https
echo   或交互选择: start.bat
echo.
echo ========================================
pause
