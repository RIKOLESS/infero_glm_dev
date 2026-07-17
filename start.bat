@echo off
chcp 65001 >nul
title INFERO GLM-5.2 Server
echo ==========================================
echo   INFERO GLM-5.2 Dedicated Server
echo ==========================================
echo.
echo [1] Cleaning up old broken servers...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM py.exe /T 2>nul

echo [2] Launching Browser...
start http://127.0.0.1:8000/src/

echo [3] Starting Python Backend with 'py' command... 
echo     Tip: set GLM_API_KEY or GLM_AUTH_HEADER before launch.
echo ------------------------------------------
py start_glm.py
echo ------------------------------------------
echo.
echo [ERROR] If you see this, the server crashed!
pause
