@echo off
title HALO - Lone Worker Safety System
color 0B

echo.
echo  ================================================
echo     HALO - Hazard Analytics ^& Live Oversight
echo     AI-Powered Lone Worker Safety System
echo  ================================================
echo.

:: Navigate to project directory
cd /d "%~dp0"

:: Check if venv exists
if not exist ".venv\Scripts\python.exe" (
    echo  [ERROR] Virtual environment not found!
    echo  Run: python -m venv .venv
    echo  Then: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Activate venv and launch
echo  Starting all HALO services...
echo  (Press Ctrl+C to stop everything)
echo.

.venv\Scripts\python.exe launch.py --monitor

pause
