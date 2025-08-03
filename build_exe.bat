@echo off
REM ========================================
REM Batch Script: build_exe_with_icon.bat
REM Description: Builds main.py into a standalone EXE with custom icon
REM Author: Skippy the Code Slayer
REM ========================================

echo.
echo [Skippy] Building Skippy YAML Builder executable with icon...
echo.

REM Optional: Clean previous builds
rmdir /s /q build
rmdir /s /q dist
del /q main.spec

REM Build with custom icon
pyinstaller --noconfirm --onefile --windowed --icon=skippy_the_magnificient.ico main.py

IF EXIST dist\main.exe (
    echo.
    echo [Skippy] Build successful! EXE located at: dist\main.exe
    echo.
) ELSE (
    echo.
    echo [Skippy] Build failed. Check for errors in your code or environment.
    echo.
)

pause
