# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 单文件打包配置
生成单个可执行文件，内嵌字体资源
"""

import os

base_dir = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=[],
    datas=[
        ('PingFang SC.ttf', '.'),
        ('app.ico', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'pytest', 'IPython', 'jupyter', 'notebook',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DesktopIconOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # 可改为 True 启用压缩（减小体积但启动更慢）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)
