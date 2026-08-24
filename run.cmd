@echo off
REM ========================================
REM Script: run.cmd
REM Description: Creates the virtual environment if it doesn't already
REM   exist, installs/updates dependencies, and launches the app.
REM   Replaces the old test.cmd, which had the same intent but never
REM   actually ran pip install or main.py -- `venv\Scripts\activate` was
REM   invoked without `call`, so control never returned to the script
REM   after activation (confirmed via a real reproduction: everything
REM   after that line was silently skipped on every run). Also renamed,
REM   since "test.cmd" launching the app rather than running the test
REM   suite was genuinely confusing.
REM ========================================

setlocal

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [Skippy] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [Skippy] Failed to create the virtual environment.
        exit /b 1
    )
)

call venv\Scripts\activate.bat

echo [Skippy] Installing/updating dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [Skippy] Failed to install dependencies.
    exit /b 1
)

echo [Skippy] Launching Skippy YAML Builder...
python main.py
