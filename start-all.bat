@echo off
chcp 65001 >nul
title INFERO db + luwang 一键启动
setlocal enableextensions enabledelayedexpansion

echo ==========================================
echo   INFERO db + luwang 一键启动
echo ==========================================
echo.

set "DB_ROOT=%~dp0"
set "DB_ROOT=%DB_ROOT:~0,-1%"
set "LUWANG_FRONT=F:\彩云\luwang\luwangfrontend"
set "VITE_CFG=%DB_ROOT%\agent-frontend\vite.config.js"

echo [check] db root       = %DB_ROOT%
echo [check] luwang front  = %LUWANG_FRONT%
echo [check] vite config   = %VITE_CFG%
echo.

if not exist "%LUWANG_FRONT%" (
    echo [error] 未找到 luwang 前端目录：%LUWANG_FRONT%
    echo         请确认路径，或按需修改 start-all.bat 中的 LUWANG_FRONT。
    pause
    exit /b 1
)
if not exist "%VITE_CFG%" (
    echo [error] 未找到 vite 配置：%VITE_CFG%
    pause
    exit /b 1
)

echo [1/5] 释放 8000 / 8080 端口占用...
for %%P in (8000 8080) do (
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r /c:":%%P *.*LISTENING"') do (
        echo        kill pid %%A ^(port %%P^)
        taskkill /F /PID %%A >nul 2>&1
    )
)
REM 兜底：清 python / node 残留进程（避免 db_backend 端口没在 LISTENING）
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM py.exe /T >nul 2>&1

echo [2/5] 启动 db 后端（新窗口）...
start "db-backend (127.0.0.1:8000)" cmd /k "cd /d "%DB_ROOT%" && py start_glm.py"

echo [3/5] 启动 luwang 前端 vite（新窗口）...
start "luwang-frontend (localhost:8080)" cmd /k "cd /d "%LUWANG_FRONT%" && npx vite --config "%VITE_CFG%""

echo [4/5] 等待 8080 就绪（最多 60 秒）...
set /a WAIT=0
:wait_loop
powershell -NoProfile -Command "if ((Test-NetConnection localhost -Port 8080 -InformationLevel Quiet -WarningAction SilentlyContinue)) { exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto ready
set /a WAIT+=1
if %WAIT% GEQ 60 (
    echo [warn] 等待超时，仍尝试打开浏览器。若失败请检查两个窗口的日志。
    goto open_browser
)
timeout /t 1 /nobreak >nul
goto wait_loop

:ready
echo        luwang 8080 已就绪（等待 %WAIT% 秒）

:open_browser
echo [5/5] 打开浏览器 http://localhost:8080 ...
start "" http://localhost:8080

echo.
echo ==========================================
echo   两个服务已在各自窗口运行：
echo     - db-backend        (127.0.0.1:8000)
echo     - luwang-frontend   (localhost:8080)
echo   关闭那两个窗口即可停止对应服务。
echo ==========================================
echo.
endlocal
exit /b 0
