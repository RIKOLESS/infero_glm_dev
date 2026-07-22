@echo off
chcp 65001 >nul
title INFERO GLM-5.2 Server

echo ==========================================
echo   INFERO db backend (GLM-5.2)
echo ==========================================
echo.

REM Load .env if present (very simple KEY=VALUE parser).
if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
    )
    echo [env] Loaded .env
)

REM Show effective mode so the operator sees it up front.
if not defined WEATHER_MODE set WEATHER_MODE=auto
echo [mode] WEATHER_MODE=%WEATHER_MODE%
if "%WEATHER_MODE%"=="demo" (
    echo        Running in DEMO mode — no luwang backend or token required.
) else if "%WEATHER_MODE%"=="live" (
    echo        Running in LIVE mode — LUWANG_TOKEN must be valid.
) else (
    echo        Running in AUTO mode — will fall back to demo samples on live failure.
)

if not defined GLM_API_KEY if not defined GLM_AUTH_HEADER (
    echo.
    echo [warn] Neither GLM_API_KEY nor GLM_AUTH_HEADER is set.
    echo        The chat endpoint will return 401 until you configure one.
    echo        See .env.example.
)

echo.
echo [1] Cleaning up old broken server processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM py.exe /T 2>nul

echo [2] Launching browser at http://127.0.0.1:8000/src/ ...
start "" http://127.0.0.1:8000/src/

echo [3] Starting Python backend via `py`...
echo ------------------------------------------
py start_glm.py
echo ------------------------------------------
echo.
echo [error] If you see this line, the server exited unexpectedly.
pause
