@echo off
setlocal enabledelayedexpansion
title Spotify Now Playing OBS Overlay
cd /d "%~dp0"

echo ========================================================
echo       Spotify Now Playing OBS Overlay Studio
echo ========================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python (3.10 to 3.13) from https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Install / update dependencies
echo [*] Checking dependencies...
python -m pip install -r requirements.txt --user --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [*] Retrying dependency installation...
    python -m pip install fastapi uvicorn websockets pywebview "winrt-Windows.Media.Control>=3.2.1" "winrt-Windows.Storage.Streams>=3.2.1" "winrt-Windows.Foundation>=3.2.1" --user --disable-pip-version-check
)

:: 3. Launch everything via the Python launcher
::    - server starts in a background thread
::    - customizer opens as a native desktop popup window
echo.
echo [*] Launching Spotify OBS Overlay Studio...
echo [*] OBS Browser Source URL: http://localhost:8888/overlay
echo.
python launcher.py

if errorlevel 1 (
    echo.
    echo [ERROR] Overlay stopped unexpectedly.
    pause
)
