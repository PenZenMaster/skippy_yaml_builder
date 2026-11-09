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

REM The exe finds README.md, stack_profiles\ and the sibling
REM rr_yacss_factory / cloud-stack-generator checkouts from its own folder
REM (app_paths.py), so it must run from the repo root, not dist\.
IF EXIST dist\main.exe (
    copy /y dist\main.exe syb.exe >nul
    echo.
    echo [Skippy] Build successful! Run syb.exe from the repo root.
    echo.
) ELSE (
    echo.
    echo [Skippy] Build failed. Check for errors in your code or environment.
    echo.
)

pause
