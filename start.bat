@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo   PhotoEfas - Environment Setup
echo ========================================

if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Cannot create venv. Please install Python 3.10+
        pause
        exit /b 1
    )
)

echo [2/3] Installing dependencies...
venv\Scripts\pip install -q -r requirements.txt 2>nul

echo [3/3] Initializing database...
venv\Scripts\python init_db.py
echo.

echo Starting service in new window...
start "PhotoEfas" cmd /k "_server.bat"
