@echo off
title Install JARVIS Dependencies
cd /d "%~dp0"

echo ===================================================
echo     Installing Dependencies for JARVIS
echo ===================================================
echo.

if exist ".venv\Scripts\activate.bat" (
    echo Using virtual environment...
    call .venv\Scripts\activate.bat
)

python -m pip install -r requirements.txt

echo.
echo Dependencies installed successfully.
pause
