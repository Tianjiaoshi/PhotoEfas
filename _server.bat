@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title PhotoEfas

echo.
echo   ========================================
echo   PhotoEfas - Image Watermark System
echo   SM2 + RSA Hybrid Encryption
echo   ========================================
echo.
echo   URL:    http://localhost:5000
echo   Admin:  admin / admin123
echo.
echo   Close this window to stop the service
echo   ========================================
echo.

venv\Scripts\python run.py

echo.
echo Service stopped.
pause
