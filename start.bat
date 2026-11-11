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
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Install / update dependencies (silent)
echo [*] Checking dependencies...
python -m pip install -r requirements.txt --user --quiet --disable-pip-version-check
python -m pip install pywebview --user --quiet --disable-pip-version-check

:: 3. Launch everything via the Python launcher
::    - server starts in a background thread
::    - customizer opens as a native desktop popup window
echo.
echo [*] Launching Spotify OBS Overlay...
echo [*] OBS Source URL: http://localhost:8888/overlay
echo.
python launcher.py

echo.
echo Overlay stopped.
pause
