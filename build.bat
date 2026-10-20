@echo off
setlocal
cd /d "%~dp0"
title Password Manager - Build

echo ================================================================
echo              Password Manager - Build (onefile EXE)
echo ================================================================
echo.

set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

echo Using: %PYTHON%
"%PYTHON%" --version
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ and try again.
    pause
    exit /b 1
)

if not exist "assets\icon.ico" (
    echo Generating icon...
    "%PYTHON%" tools\make_icon.py
    if errorlevel 1 (
        echo ERROR: Failed to generate icon.
        pause
        exit /b 1
    )
)

echo.
echo Installing dependencies...
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Building EXE...
"%PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --noconsole ^
    --name PasswordManager ^
    --icon "assets\icon.ico" ^
    --add-data "static;static" ^
    --add-data "assets;assets" ^
    --collect-submodules uvicorn ^
    run.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo.
if exist "dist\PasswordManager.exe" (
    echo ================================================================
    echo Build complete: dist\PasswordManager.exe
    echo ================================================================
    echo Frontend and icons are embedded in the EXE.
    echo The app starts without a console and shows a tray icon.
    echo passwords.json and password_manager.log are created next to the EXE.
) else (
    echo ERROR: dist\PasswordManager.exe was not created.
)
echo.
pause
