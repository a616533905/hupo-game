@echo off
chcp 65001 >nul
echo ========================================
echo   琥珀冒险 - 服务状态 (Windows)
echo ========================================
echo.

echo 【进程状态】
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /I "python" >nul
if %ERRORLEVEL% equ 0 (
    echo   Bridge: 运行中
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" ^| findstr /I "python"') do echo     PID: %%a
) else (
    echo   Bridge: 未运行
)

tasklist /FI "IMAGENAME eq node.exe" 2>nul | findstr /I "node" >nul
if %ERRORLEVEL% equ 0 (
    echo   Voice: 运行中
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" ^| findstr /I "node"') do echo     PID: %%a
) else (
    echo   Voice: 未运行
)
echo.

echo 【端口监听】
netstat -ano | findstr ":80 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   端口 80: 已监听
) else (
    echo   端口 80: 未监听
)

netstat -ano | findstr ":85 " | findstr "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   端口 85: 已监听
) else (
    echo   端口 85: 未监听
)
echo.

echo 【系统资源】
for /f "skip=1" %%a in ('wmic cpu get loadpercentage') do (
    if not "%%a"=="" echo   CPU使用率: %%a%%
    goto :cpu_done
)
:cpu_done
for /f "skip=1 tokens=2,3" %%a in ('wmic OS get TotalVisibleMemorySize^,FreePhysicalMemory /value') do (
    set /a used=%%a-%%b
    set /a percent=used*100/%%a
    echo   内存使用: !percent!%%
    goto :mem_done
)
:mem_done
echo.

echo 【请求统计】
curl -s http://127.0.0.1:80/health >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%a in ('curl -s http://127.0.0.1:80/health ^| powershell -Command "$input | ConvertFrom-Json | Select-Object -ExpandProperty requests_total"') do echo   总请求: %%a
    for /f "tokens=*" %%a in ('curl -s http://127.0.0.1:80/health ^| powershell -Command "$input | ConvertFrom-Json | Select-Object -ExpandProperty uptime"') do echo   运行时间: %%a 秒
) else (
    echo   无法获取（服务未启动）
)
echo.

echo ========================================
pause
