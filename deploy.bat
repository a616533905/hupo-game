@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   琥珀冒险 - 推送更新到服务器
echo ========================================
echo.

if not exist "server.ini" (
    echo 错误: server.ini 配置文件不存在
    echo 请创建 server.ini 文件
    pause
    exit /b 1
)

for /f "tokens=1,2 delims== " %%a in ('findstr /i "host" server.ini') do set "SERVER_IP=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "user" server.ini') do set "SERVER_USER=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "port" server.ini') do set "SERVER_PORT=%%b"
for /f "tokens=1,2 delims== " %%a in ('findstr /i "dir" server.ini') do set "SERVER_DIR=%%b"

echo [1/3] 检查 Git 状态...
git status --porcelain >nul 2>&1
if not errorlevel 1 (
    echo   无未提交的更改
) else (
    echo   有未提交的更改，正在提交...
    git add -A
    for /f "tokens=*" %%a in ('date /t') do set DATETIME=%%a
    git commit -m "更新: %DATETIME%"
)

echo.
echo [2/3] 推送到 GitHub...
git push -u origin main
if errorlevel 1 (
    echo   错误: GitHub 推送失败
    pause
    exit /b 1
)
echo   推送成功

echo.
echo [3/3] 在服务器上执行更新...
ssh -p %SERVER_PORT% %SERVER_USER%@%SERVER_IP% "cd %SERVER_DIR% && git pull origin main"

if errorlevel 1 (
    echo.
    echo ========================================
    echo   警告: 服务器更新可能失败，请检查连接
    echo ========================================
    pause
) else (
    echo.
    echo ========================================
    echo   推送完成！
    echo ========================================
    pause
)
