@echo off
chcp 65001 >nul
title TelyClaw
cd /d "%~dp0"

set "PY=C:\Users\ss\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
set "URL=http://127.0.0.1:8765"

echo ==================================================
echo   TelyClaw  /  X Topic Radar
echo ==================================================
echo.

REM --- 1. Find Python -------------------------------------------------
if not exist "%PY%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python not found.
        echo Expected: %PY%
        echo.
        pause
        exit /b 1
    )
    set "PY=python"
)
echo [1/3] Python OK

REM --- 2. Make sure dependencies are installed ------------------------
"%PY%" -c "import fastapi, uvicorn, requests" >nul 2>nul
if errorlevel 1 (
    echo [2/3] Installing dependencies, first run only, please wait...
    "%PY%" -m pip install -r telyclaw\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Check your network.
        echo.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Dependencies OK
)

REM --- 3. Already running? Just open the browser ----------------------
"%PY%" -c "import socket,sys; s=socket.socket(); r=s.connect_ex(('127.0.0.1',8765)); s.close(); sys.exit(0 if r==0 else 1)" >nul 2>nul
if not errorlevel 1 (
    echo [3/3] Already running. Opening browser...
    start "" "%URL%"
    echo.
    echo TelyClaw is already up at %URL%
    echo.
    pause
    exit /b 0
)

REM --- 4. Start -------------------------------------------------------
echo [3/3] Starting TelyClaw...
echo.
echo   Browser will open at: %URL%
echo   To stop: close this window, or press Ctrl + C
echo.
echo --------------------------------------------------
"%PY%" telyclaw\app.py

echo.
echo --------------------------------------------------
echo TelyClaw stopped.
pause
