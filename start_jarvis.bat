@echo off
title JARVIS AI Assistant
cd /d "%~dp0"

echo ===================================================
echo     Launching JARVIS AI Desktop Assistant...
echo ===================================================
echo.

:: Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Run the application
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] JARVIS closed unexpectedly (exit code: %errorlevel%).
    echo Please review logs/jarvis.log for details.
    pause
)
