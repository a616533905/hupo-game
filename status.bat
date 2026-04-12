@echo off
chcp 65001 >nul
echo ========================================
echo   琥珀冒险 - 服务状态
echo ========================================
echo.

echo 【进程状态】
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE 2>nul | findstr /i "python" >nul
if %ERRORLEVEL% equ 0 (
    echo   Python服务: 运行中
) else (
    echo   Python服务: 未运行
)

tasklist /FI "IMAGENAME eq node.exe" /FO TABLE 2>nul | findstr /i "node" >nul
if %ERRORLEVEL% equ 0 (
    echo   Node服务: 运行中
) else (
    echo   Node服务: 未运行
)
echo.

echo 【系统资源】
for /f "skip=1" %%p in ('wmic cpu get loadpercentage') do (
    if not "%%p"=="" echo   CPU使用率: %%p%%
    goto :cpu_done
)
:cpu_done

for /f "skip=1 tokens=2,3" %%a in ('wmic OS get TotalVisibleMemorySize^,FreePhysicalMemory /value ^| findstr "="') do (
    set /a used=%%a-%%b
    set /a percent=used*100/%%a
)
echo   内存使用: %percent%%%
echo.

echo 【端口监听】
netstat -an | findstr ":80 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   端口 80: 已监听
) else (
    echo   端口 80: 未监听
)

netstat -an | findstr ":85 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   端口 85: 已监听
) else (
    echo   端口 85: 未监听
)
echo.

echo 【最近日志】
set LOG_DIR=%~dp0logs
if exist "%LOG_DIR%" (
    echo   日志目录: %LOG_DIR%
    dir /b /o-d "%LOG_DIR%\*.log" 2>nul | head -1
) else (
    echo   暂无日志文件
)
echo.

echo 【请求统计】
where curl >nul 2>nul
if %ERRORLEVEL% equ 0 (
    curl -s http://127.0.0.1:80/health >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        for /f "delims=" %%i in ('curl -s http://127.0.0.1:80/health') do set HEALTH=%%i
        echo   %HEALTH%
    ) else (
        echo   无法获取（服务未启动）
    )
) else (
    echo   需要 curl 命令
)
echo.

echo ========================================
pause
