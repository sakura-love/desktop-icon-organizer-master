@echo off
chcp 65001 >nul
echo ========================================
echo   桌面图标整理工具 - 打包脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/2] 开始打包...
pyinstaller --clean --noconfirm build.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo   打包完成！
    echo   输出目录: %cd%\dist
    echo ========================================
    dir /b dist
) else (
    echo.
    echo [错误] 打包失败，请检查错误信息
)

pause
