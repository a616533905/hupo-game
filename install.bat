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

echo [2/4] 安装 Python 依赖...
pip install psutil

echo [3/4] 创建日志目录...
if not exist "%INSTALL_DIR%logs" mkdir "%INSTALL_DIR%logs"

echo [4/4] 设置防火墙规则...
netsh advfirewall firewall show rule name="Hupo Game API" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    netsh advfirewall firewall add rule name="Hupo Game API" dir=in action=allow protocol=tcp localport=80
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
echo 启动服务:
echo   方式1: 双击 start.bat
echo   方式2: 运行 python nanobot_bridge.py
echo.
echo API端点:
echo   健康检查: http://localhost:80/health
echo   Prometheus: http://localhost:80/metrics
echo.
echo ========================================
pause
