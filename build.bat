@echo off
chcp 65001 >nul
echo ========================================
echo   Desktop Icon Organizer - Build Script
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未找到，请安装 Python 3.9+ 并添加到 PATH
    pause
    exit /b 1
)

:: 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] 正在安装 PyInstaller...
    pip install pyinstaller
)

:: 安装项目依赖
echo [INFO] 正在安装项目依赖...
pip install -r requirements.txt

:: 构建
echo [INFO] 正在构建可执行文件...
pyinstaller build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] 构建失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo   构建成功！
echo   输出目录: dist\DesktopIconOrganizer\
echo   可执行文件: dist\DesktopIconOrganizer\DesktopIconOrganizer.exe
echo ========================================
echo.

pause
