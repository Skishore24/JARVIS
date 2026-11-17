@echo off
title JARVIS AI Assistant Setup
echo ===================================================
echo     JARVIS AI Desktop Assistant - Setup Script
echo ===================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Checking Python environment...
python --version

:: 2. Check or create virtual environment
if not exist ".venv" (
    echo [2/4] Creating virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [2/4] Virtual environment exists.
)

:: 3. Activate venv and install dependencies
echo [3/4] Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

:: 4. Verify Ollama
echo [4/4] Verifying Ollama installation...
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama is not installed or not in PATH.
    echo Please download and install Ollama from https://ollama.ai/
) else (
    echo Ollama detected. Checking model llama3.2:3b...
    ollama list | findstr "llama3.2:3b" >nul
    if %errorlevel% neq 0 (
        echo Pulling recommended model llama3.2:3b...
        ollama pull llama3.2:3b
    ) else (
        echo Model llama3.2:3b is ready.
    )
)

echo.
echo ===================================================
echo   JARVIS Setup Complete! Run start_jarvis.bat to launch.
echo ===================================================
pause
