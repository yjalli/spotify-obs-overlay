@echo off
setlocal enabledelayedexpansion
title Spotify Now Playing OBS Overlay Studio
cd /d "%~dp0"

echo ========================================================
echo       Spotify Now Playing OBS Overlay Studio
echo ========================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not found in PATH!
    echo Please install Python from https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Install dependencies
echo [*] Checking dependencies...
python -m pip install -r requirements.txt --user --quiet --disable-pip-version-check

:: 3. Launch overlay and control panel
echo.
echo [*] Launching Spotify OBS Overlay Studio...
echo [*] OBS Browser Source URL: http://localhost:8888/overlay
echo.
python launcher.py

echo.
echo ========================================================
echo Overlay session ended.
echo ========================================================
pause
