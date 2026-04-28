"""
桌面叠加层模块
通过独立进程显示半透明叠加层，主程序退出后叠加层仍保持。
渲染函数 _render_overlay 供 overlay_process.py 导入复用。
"""

import json
import os
import subprocess
import sys
import time
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from layout_engine import DesktopLayout

# 控制文件路径
# PyInstaller 打包模式：控制文件放在 exe 所在目录
# 开发模式：控制文件放在脚本所在目录
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_LAYOUT_FILE = os.path.join(_BASE_DIR, ".overlay_layout.json")
_PERSISTENT_LAYOUT_FILE = os.path.join(_BASE_DIR, "overlay_layout_persistent.json")  # 持久化布局文件
_CONTROL_FILE = os.path.join(_BASE_DIR, ".overlay_control.json")
_PID_FILE = os.path.join(_BASE_DIR, ".overlay_pid")
_OVERLAY_SCRIPT = os.path.join(_BASE_DIR, "overlay_process.py")
_ICON_POSITIONS_FILE = os.path.join(_BASE_DIR, "icon_positions.json")  # 持久化图标位置

# 检测是否在 PyInstaller 打包模式下运行
_FROZEN = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# ===================== 渲染参数 =====================
BORDER_RADIUS = 16
BORDER_ALPHA = 80
LABEL_FONT_SIZE = 14
UNIFIED_COLOR = "#5A7A8B"
BOTTOM_EXTRA = 24
MARGIN_X = 4
DEFAULT_BORDER_STYLE = "rounded"
BORDER_STYLES = ["rounded", "square", "corner", "bracket"]


def hex_to_rgba(hex_color: str, alpha: int = 255):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)


def _draw_border_frame(draw, box, outline_rgba, radius: int, style: str, d: float):
    x1, y1, x2, y2 = box
    if style == "square":
        draw.rectangle([x1, y1, x2, y2], outline=outline_rgba, width=1)
        return

    if style == "corner":
        arm = max(10, int(18 * d))
        draw.line([(x1, y1 + arm), (x1, y1), (x1 + arm, y1)], fill=outline_rgba, width=2)
        draw.line([(x2 - arm, y1), (x2, y1), (x2, y1 + arm)], fill=outline_rgba, width=2)
        draw.line([(x1, y2 - arm), (x1, y2), (x1 + arm, y2)], fill=outline_rgba, width=2)
        draw.line([(x2 - arm, y2), (x2, y2), (x2, y2 - arm)], fill=outline_rgba, width=2)
        return

    if style == "bracket":
        arm = max(8, int(14 * d))
        draw.line([(x1, y1), (x1, y2)], fill=outline_rgba, width=2)
        draw.line([(x1, y1), (x1 + arm, y1)], fill=outline_rgba, width=2)
        draw.line([(x1, y2), (x1 + arm, y2)], fill=outline_rgba, width=2)
        draw.line([(x2, y1), (x2, y2)], fill=outline_rgba, width=2)
        draw.line([(x2 - arm, y1), (x2, y1)], fill=outline_rgba, width=2)
        draw.line([(x2 - arm, y2), (x2, y2)], fill=outline_rgba, width=2)
        return

    draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=radius,
        fill=None,
        outline=outline_rgba,
        width=1,
    )


def _load_font(size: int):
    # PyInstaller 打包模式：字体从临时解压目录加载
    # 开发模式：字体从项目目录加载
    if _FROZEN:
        meipass_font = os.path.join(sys._MEIPASS, "PingFang SC.ttf")
        font_paths = [
            (meipass_font, 0),
            (r"C:\Windows\Fonts\msyh.ttc", 0),
            (r"C:\Windows\Fonts\msyhbd.ttc", 0),
            (r"C:\Windows\Fonts\simhei.ttf", 0),
            (r"C:\Windows\Fonts\simsun.ttc", 0),
        ]
    else:
        project_font = os.path.join(_BASE_DIR, "PingFang SC.ttf")
        font_paths = [
            (project_font, 0),
            (r"C:\Windows\Fonts\msyh.ttc", 0),
            (r"C:\Windows\Fonts\msyhbd.ttc", 0),
            (r"C:\Windows\Fonts\simhei.ttf", 0),
            (r"C:\Windows\Fonts\simsun.ttc", 0),
        ]
    for path, index in font_paths:
        if not os.path.exists(path):
            continue
        try:
            font = ImageFont.truetype(path, size, index=index)
            print(f"[Font] 已加载字体: {path}")
            return font
        except Exception:
            try:
                font = ImageFont.truetype(path, size)
                print(f"[Font] 已加载字体(无index): {path}")
                return font
            except Exception:
                continue
    print(f"[Font] 警告: 所有字体加载失败，使用默认字体")
    return ImageFont.load_default()


def _render_overlay(layout: DesktopLayout, dpi_scale: float, border_style: str = DEFAULT_BORDER_STYLE):
    """渲染叠加层图像（供主进程和 overlay_process.py 共用）"""
    if not layout.category_layouts:
        return None

    width = layout.total_width
    height = layout.total_height
    if width <= 0 or height <= 0:
        return None

    # 预先计算最大 y2，确保画布足够大（留额外缓冲区避免边缘裁剪）
    max_needed_y = height
    for cat_layout in layout.category_layouts:
        icon_cells = [c for c in layout.cells
                      if c.category == cat_layout.category and not c.is_header]
        if not icon_cells:
            continue
        max_py = max(c.pixel_y + layout.cell_height for c in icon_cells)
        needed_y = max_py + BOTTOM_EXTRA + 4  # +4 像素缓冲区
        max_needed_y = max(max_needed_y, needed_y)
    height = max_needed_y

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    txt_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_layer)

    d = dpi_scale
    actual_font_size = int(LABEL_FONT_SIZE * dpi_scale)
    font = _load_font(actual_font_size)
    actual_radius = int(BORDER_RADIUS * d)
    outline_rgba = hex_to_rgba(UNIFIED_COLOR, BORDER_ALPHA)
    txt_color = (255, 255, 255, 255)

    for cat_layout in layout.category_layouts:
        icon_cells = [c for c in layout.cells
                      if c.category == cat_layout.category and not c.is_header]
        if not icon_cells:
            continue

        min_px = min(c.pixel_x for c in icon_cells)
        max_px = max(c.pixel_x + cat_layout.column_width for c in icon_cells)
        x1 = min_px - MARGIN_X
        x2 = max_px + MARGIN_X

        max_py = max(c.pixel_y + layout.cell_height for c in icon_cells)
        y1 = 0
        y2 = max_py + BOTTOM_EXTRA

        x1 = max(0, x1)
        x2 = min(width, x2)
        if x2 <= x1 or y2 <= y1:
            continue

        _draw_border_frame(
            draw,
            [x1, y1, x2, y2],
            outline_rgba=outline_rgba,
            radius=actual_radius,
            style=border_style if border_style in BORDER_STYLES else DEFAULT_BORDER_STYLE,
            d=d,
        )

        # 绘制类别标签（带半透明背景条提高可读性）
        label_text = cat_layout.category
        try:
            bbox = font.getbbox(label_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except AttributeError:
            text_w, text_h = font.getsize(label_text)

        # 背景色条
        label_x = (x1 + x2 - text_w) / 2
        label_y = y1 + int(6 * d)
        pad_x = int(8 * d)
        pad_y = int(2 * d)
        bg_x1 = int(label_x) - pad_x
        bg_y1 = int(label_y) - pad_y + (bbox[1] if hasattr(font, 'getbbox') else 0)
        bg_x2 = int(label_x + text_w) + pad_x
        bg_y2 = bg_y1 + int(text_h) + pad_y * 2
        bg_rgba = hex_to_rgba(UNIFIED_COLOR, 160)
        txt_draw.rounded_rectangle(
            [bg_x1, bg_y1, bg_x2, bg_y2],
            radius=int(4 * d),
            fill=bg_rgba,
        )
        txt_draw.text((label_x, label_y), label_text, fill=txt_color, font=font)

    img = Image.alpha_composite(img, txt_layer)
    return img


def _write_layout(
    layout: DesktopLayout,
    dpi_scale: float,
    icon_positions: list = None,
    border_style: str = DEFAULT_BORDER_STYLE,
):
    """将布局数据序列化写入文件"""
    data = {
        "total_width": layout.total_width,
        "total_height": layout.total_height,
        "cell_height": layout.cell_height,
        "dpi_scale": dpi_scale,
        "border_style": border_style if border_style in BORDER_STYLES else DEFAULT_BORDER_STYLE,
        "categories": [],
        "cells": [],
        "icon_positions": icon_positions or [],
    }
    for cat in layout.category_layouts:
        data["categories"].append({
            "category": cat.category,
            "column_width": cat.column_width,
        })
    for cell in layout.cells:
        data["cells"].append({
            "pixel_x": cell.pixel_x,
            "pixel_y": cell.pixel_y,
            "category": cell.category,
            "is_header": cell.is_header,
        })
    with open(_LAYOUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _write_control(command: str):
    """写入控制指令"""
    with open(_CONTROL_FILE, "w", encoding="utf-8") as f:
        json.dump({"command": command}, f)


def _is_overlay_cmdline(cmdline) -> bool:
    if not cmdline:
        return False
    lowered = [str(arg).lower() for arg in cmdline]
    if any("overlay_process.py" in arg for arg in lowered):
        return True
    if "--overlay" in lowered:
        return True
    if "--autostart" in lowered:
        return True
    return False


def _find_overlay_processes():
    try:
        import psutil
        procs = []
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if _is_overlay_cmdline(cmdline):
                    procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs
    except ImportError:
        return []


def _find_overlay_process():
    procs = _find_overlay_processes()
    return procs[0] if procs else None


def _read_overlay_pid() -> Optional[int]:
    """Read overlay pid from heartbeat file."""
    try:
        if not os.path.exists(_PID_FILE):
            return None
        with open(_PID_FILE, "r", encoding="utf-8") as f:
            value = f.read().strip()
        pid = int(value)
        return pid if pid > 0 else None
    except Exception:
        return None


def _is_pid_running(pid: Optional[int]) -> bool:
    """Check whether a process id is still alive."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _has_overlay_process(pid_hint: Optional[int] = None) -> bool:
    if _is_pid_running(pid_hint):
        return True
    return bool(_find_overlay_processes())


def _stop_all_overlay_processes(timeout: float = 1.5):
    pid_hint = _read_overlay_pid()
    try:
        _write_control("stop")
    except Exception:
        pass

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _has_overlay_process(pid_hint):
            return
        time.sleep(0.1)

    for proc in _find_overlay_processes():
        try:
            proc.terminate()
        except Exception:
            pass

    deadline = time.time() + 1.0
    while time.time() < deadline:
        if not _has_overlay_process(pid_hint):
            return
        time.sleep(0.1)

    for proc in _find_overlay_processes():
        try:
            proc.kill()
        except Exception:
            pass


def _is_overlay_running() -> bool:
    pid = _read_overlay_pid()
    return _has_overlay_process(pid)


class DesktopOverlay:
    """桌面叠加层（独立进程）"""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._visible = False
        self._error: Optional[str] = None
        self._started_by_us = False

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    def show(
        self,
        layout: DesktopLayout,
        dpi_scale: float = 1.0,
        icon_positions: list = None,
        border_style: str = DEFAULT_BORDER_STYLE,
    ) -> bool:
        """显示叠加层"""
        self._error = None

        # 检查是否已有叠加层进程在运行
        existing_procs = _find_overlay_processes()
        if len(existing_procs) > 1:
            _stop_all_overlay_processes()
            existing_procs = _find_overlay_processes()

        existing = existing_procs[0] if existing_procs else None
        if existing:
            try:
                _write_layout(layout, dpi_scale, icon_positions, border_style)
                _write_control("update")
                self._visible = True
                self._started_by_us = False
                return True
            except Exception as e:
                self._error = f"update overlay failed: {e}"
                return False

        # 启动新进程
        try:
            _write_layout(layout, dpi_scale, icon_positions, border_style)

            # PyInstaller 打包模式：使用 --overlay 参数启动自身
            # 开发模式：使用 python overlay_process.py
            if _FROZEN:
                cmd = [sys.executable, "--overlay"]
            else:
                cmd = [sys.executable, _OVERLAY_SCRIPT]

            # 开发模式下显示窗口以便调试
            if _FROZEN:
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                creation_flags = 0  # 开发模式显示控制台窗口便于调试

            self._process = subprocess.Popen(
                cmd,
                cwd=_BASE_DIR,
                creationflags=creation_flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"} if _FROZEN else None,
            )
            self._started_by_us = True
            print(f"[Overlay] 启动命令: {cmd}")
            # 短暂等待检查进程是否立即崩溃
            try:
                self._process.wait(timeout=2.0)
                # 进程退出了，说明有错误
                stdout = self._process.stdout.read().decode("utf-8", errors="replace") if self._process.stdout else ""
                stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
                print(f"[Overlay] 进程立即退出, stdout={stdout}, stderr={stderr}")
                self._error = f"叠加层进程启动失败:\nstdout: {stdout}\nstderr: {stderr}"
                self._process = None
                return False
            except subprocess.TimeoutExpired:
                # 进程仍在运行，正常
                pass
            self._visible = True
            print(f"[Overlay] 叠加层进程已启动, PID={self._process.pid}")
            return True
        except subprocess.TimeoutExpired:
            # 进程仍在运行（正常情况）
            self._visible = True
            self._started_by_us = True
            print(f"[Overlay] 叠加层进程已启动, PID={self._process.pid}")
            return True
        except Exception as e:
            self._error = f"启动叠加层进程失败: {e}"
            return False

    def hide(self):
        """Hide overlay."""
        _stop_all_overlay_processes(timeout=2.0)
        self._process = None
        self._visible = False


# 全局实例
_overlay: Optional[DesktopOverlay] = None


def show_desktop_overlay(
    layout: DesktopLayout,
    dpi_scale: float = 1.0,
    root=None,
    icon_positions: list = None,
    border_style: str = DEFAULT_BORDER_STYLE,
):
    """显示桌面叠加层"""
    global _overlay
    if _overlay is None:
        _overlay = DesktopOverlay()

    success = _overlay.show(layout, dpi_scale, icon_positions, border_style)
    if not success:
        err_msg = _overlay.last_error or "未知错误"
        raise RuntimeError(f"显示叠加层失败:\n{err_msg}")


def is_overlay_running() -> bool:
    """检查是否有叠加层进程正在运行"""
    return _is_overlay_running()


def hide_desktop_overlay():
    """隐藏桌面叠加层"""
    global _overlay
    if _overlay:
        _overlay.hide()
    else:
        # 没有本进程的 DesktopOverlay 实例，
        # 但可能有其他进程启动的叠加层，通过控制文件通知关闭
        try:
            _stop_all_overlay_processes(timeout=2.0)
        except Exception:
            pass


# ===================== 开机自启动 =====================

import winreg

_AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "DesktopIconOrganizerOverlay"


def is_autostart_enabled() -> bool:
    """检查是否已设置开机自启动"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _AUTOSTART_NAME)
        winreg.CloseKey(key)
        return True
    except (FileNotFoundError, OSError):
        return False


def enable_autostart():
    """启用开机自启动"""
    if _FROZEN:
        exe_path = sys.executable
    else:
        # 开发模式：创建一个启动脚本
        exe_path = sys.executable

    # 构建启动命令
    if _FROZEN:
        cmd = f'"{exe_path}" --autostart'
    else:
        script_path = os.path.join(_BASE_DIR, "overlay_process.py")
        cmd = f'"{exe_path}" "{script_path}" --autostart'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print(f"[Autostart] 已启用开机自启动: {cmd}")
        return True
    except Exception as e:
        print(f"[Autostart] 启用开机自启动失败: {e}")
        return False


def disable_autostart():
    """禁用开机自启动"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(key, _AUTOSTART_NAME)
        winreg.CloseKey(key)
        print("[Autostart] 已禁用开机自启动")
        return True
    except (FileNotFoundError, OSError):
        return True
    except Exception as e:
        print(f"[Autostart] 禁用开机自启动失败: {e}")
        return False


# ===================== 布局持久化 =====================

def save_persistent_layout(
    layout: DesktopLayout,
    dpi_scale: float,
    icon_positions: list = None,
    border_style: str = DEFAULT_BORDER_STYLE,
):
    """保存布局到持久化文件（开机后自动加载）"""
    data = {
        "total_width": layout.total_width,
        "total_height": layout.total_height,
        "cell_height": layout.cell_height,
        "dpi_scale": dpi_scale,
        "border_style": border_style if border_style in BORDER_STYLES else DEFAULT_BORDER_STYLE,
        "categories": [],
        "cells": [],
        "icon_positions": icon_positions or [],
    }
    for cat in layout.category_layouts:
        data["categories"].append({
            "category": cat.category,
            "column_width": cat.column_width,
        })
    for cell in layout.cells:
        data["cells"].append({
            "pixel_x": cell.pixel_x,
            "pixel_y": cell.pixel_y,
            "category": cell.category,
            "is_header": cell.is_header,
        })
    try:
        with open(_PERSISTENT_LAYOUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[Persistence] 布局已持久化保存: {_PERSISTENT_LAYOUT_FILE}")
        return True
    except Exception as e:
        print(f"[Persistence] 保存布局失败: {e}")
        return False


def load_persistent_layout():
    """加载持久化的布局数据"""
    try:
        with open(_PERSISTENT_LAYOUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Persistence] 已加载持久化布局")
        return data
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[Persistence] 加载布局失败: {e}")
        return None


def has_persistent_layout() -> bool:
    """检查是否存在持久化布局"""
    return os.path.exists(_PERSISTENT_LAYOUT_FILE)


def clear_persistent_layout():
    """清除持久化布局"""
    for fp in [_PERSISTENT_LAYOUT_FILE, _ICON_POSITIONS_FILE]:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except Exception:
            pass
    print("[Persistence] 已清除持久化布局")
