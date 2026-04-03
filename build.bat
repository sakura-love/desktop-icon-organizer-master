@echo off
chcp 65001 >nul
echo ========================================
echo   Desktop Icon Organizer - Build Script
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/2] Building...
python -m PyInstaller --clean --noconfirm build.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo   Build completed!
    echo   Output: %cd%\dist
    echo ========================================
    dir /b dist
) else (
    echo.
    echo [ERROR] Build failed, please check error messages
)

pause
