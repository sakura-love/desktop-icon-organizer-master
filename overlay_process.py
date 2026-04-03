"""
独立叠加层进程
作为独立进程运行，在桌面显示半透明边框叠加层。
主程序退出后此进程继续运行，仅通过控制文件接收关闭指令。

通信方式：
- .overlay_layout.json: 布局数据（由主程序写入）
- .overlay_control.json: 控制指令 {"command": "stop"}（由主程序写入）
"""

import ctypes
import json
import os
import sys
import time
import traceback

from PIL import Image

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 延迟导入，避免影响启动速度
layout_engine = None
desktop_overlay = None


def _init_modules():
    global layout_engine, desktop_overlay
    if layout_engine is None:
        from layout_engine import DesktopLayout, CategoryLayout, Cell
        layout_engine = DesktopLayout, CategoryLayout, Cell
    if desktop_overlay is None:
        import desktop_overlay as _mod
        desktop_overlay = _mod


# ===================== Win32 常量 =====================
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WM_CLOSE = 0x0010

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ULW_ALPHA = 0x00000002

# ===================== Win32 结构体 =====================

class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_longlong),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                 ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

# ===================== Win32 DLL =====================

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

user32.CreateWindowExW.restype = ctypes.c_void_p
user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p,
    ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
user32.UpdateLayeredWindow.restype = ctypes.c_int
user32.UpdateLayeredWindow.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    ctypes.c_void_p, ctypes.POINTER(POINT), ctypes.c_uint, ctypes.POINTER(BLENDFUNCTION),
    ctypes.c_uint,
]
user32.SetWindowPos.restype = ctypes.c_int
user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.GetDC.restype = ctypes.c_void_p
user32.GetDC.argtypes = [ctypes.c_void_p]
user32.ReleaseDC.restype = ctypes.c_int
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.restype = ctypes.c_long
user32.DestroyWindow.restype = ctypes.c_int
user32.DestroyWindow.argtypes = [ctypes.c_void_p]
user32.PostMessageW.restype = ctypes.c_int
user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
user32.PeekMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
user32.TranslateMessage.restype = ctypes.c_int
user32.DispatchMessageW.restype = ctypes.c_long
user32.IsWindowVisible.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
user32.GetWindowRect.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
user32.SystemParametersInfoW.restype = ctypes.c_int
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.CreateDIBSection.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.DeleteObject.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.restype = ctypes.c_int
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
kernel32.GetModuleHandleW.restype = ctypes.c_void_p
kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.RtlMoveMemory.restype = None
kernel32.RtlMoveMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
kernel32.GetLastError.restype = ctypes.c_uint
kernel32.GetLastError.argtypes = []


def _get_last_error():
    return kernel32.GetLastError()


def get_workarea_offset():
    rect = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top


def _rgba_to_bgra(img):
    r, g, b, a = img.split()
    bgra_img = Image.merge("RGBA", (b, g, r, a))
    return bgra_img.tobytes()


def _rebuild_layout(data):
    """从序列化数据重建 DesktopLayout 对象"""
    _init_modules()
    DesktopLayout, CategoryLayout, Cell = layout_engine

    cats = []
    for c in data["categories"]:
        cats.append(CategoryLayout(
            category=c["category"],
            icons=[],  # 渲染不需要 icons
            start_x=0, end_x=0, columns=0,
            column_width=c["column_width"],
            row_height=0, padding_left=0, padding_right=0,
        ))
    cells = []
    for c in data["cells"]:
        cells.append(Cell(
            grid_x=0, grid_y=0,
            pixel_x=c["pixel_x"], pixel_y=c["pixel_y"],
            icon=None, category=c["category"],
            is_header=c.get("is_header", False), header_text="",
        ))
    return DesktopLayout(
        total_width=data["total_width"],
        total_height=data["total_height"],
        cell_width=0,
        cell_height=data["cell_height"],
        category_layouts=cats,
        cells=cells,
    )


def _create_layered_window(bgra_data, width, height, ox, oy):
    """创建分层窗口"""
    hwnd = user32.CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        "Static", "",
        WS_POPUP | WS_VISIBLE,
        ox, oy, width, height,
        None, None, kernel32.GetModuleHandleW(None), None,
    )
    if not hwnd:
        raise RuntimeError(f"CreateWindowExW 失败, 错误码: {_get_last_error()}")

    hdc_screen = user32.GetDC(None)
    if not hdc_screen:
        user32.DestroyWindow(hwnd)
        raise RuntimeError("GetDC(NULL) 失败")

    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    if not hdc_mem:
        user32.ReleaseDC(None, hdc_screen)
        user32.DestroyWindow(hwnd)
        raise RuntimeError("CreateCompatibleDC 失败")

    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    header.biHeight = -height
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = 0

    pbits = ctypes.c_void_p()
    hbitmap = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(header), 0, ctypes.byref(pbits), None, 0)
    if not hbitmap:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        user32.DestroyWindow(hwnd)
        raise RuntimeError(f"CreateDIBSection 失败, 错误码: {_get_last_error()}")

    expected_size = width * height * 4
    if len(bgra_data) != expected_size:
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        user32.DestroyWindow(hwnd)
        raise RuntimeError(f"BGRA 数据大小不匹配: 期望 {expected_size}, 实际 {len(bgra_data)}")

    kernel32.RtlMoveMemory(pbits, bgra_data, expected_size)
    old_bmp = gdi32.SelectObject(hdc_mem, hbitmap)

    blend = BLENDFUNCTION()
    blend.BlendOp = 0
    blend.BlendFlags = 0
    blend.SourceConstantAlpha = 255
    blend.AlphaFormat = 1

    size = SIZE()
    size.cx = width
    size.cy = height
    pt_src = POINT()

    result = user32.UpdateLayeredWindow(
        hwnd, hdc_screen, None, ctypes.byref(size),
        hdc_mem, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA,
    )
    if not result:
        err = _get_last_error()
        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        user32.DestroyWindow(hwnd)
        raise RuntimeError(f"UpdateLayeredWindow 失败, 错误码: {err}")

    gdi32.SelectObject(hdc_mem, old_bmp)
    gdi32.DeleteObject(hbitmap)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_screen)

    # 设置 Z-order：放在 Progman 之上
    progman = user32.FindWindowW("Progman", "Program Manager")
    if progman:
        user32.SetWindowPos(hwnd, progman, 0, 0, 0, 0,
                           SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    # 添加点击穿透
    style = user32.GetWindowLongW(hwnd, -20)
    user32.SetWindowLongW(hwnd, -20, style | WS_EX_TRANSPARENT)

    return hwnd


def _run_overlay(hwnd, control_file, pid_file):
    """运行消息循环，定期检查控制文件（非阻塞），同时更新心跳文件"""
    msg = MSG()
    check_counter = 0
    heartbeat_counter = 0

    while True:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE
            if msg.message == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return None
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        check_counter += 1
        heartbeat_counter += 1

        # 每50次循环(~0.5秒)写入心跳PID文件
        if heartbeat_counter >= 50:
            heartbeat_counter = 0
            try:
                with open(pid_file, "w") as f:
                    f.write(str(os.getpid()))
            except Exception:
                pass

        if check_counter >= 100:
            check_counter = 0
            if os.path.exists(control_file):
                try:
                    with open(control_file, "r", encoding="utf-8") as f:
                        cmd = json.load(f)
                    if cmd.get("command") == "stop":
                        user32.PostMessageW(hwnd, WM_CLOSE, None, None)
                        return None
                    elif cmd.get("command") == "update":
                        try:
                            os.remove(control_file)
                        except Exception:
                            pass
                        return "update"
                except (json.JSONDecodeError, IOError):
                    pass

        time.sleep(0.01)


def main():
    """叠加层主函数"""
    # 检查是否是开机自启动模式
    autostart_mode = "--autostart" in sys.argv

    # PyInstaller 打包模式：控制文件放在 exe 所在目录
    # 开发模式：控制文件放在脚本所在目录
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    layout_file = os.path.join(base_dir, ".overlay_layout.json")
    persistent_layout_file = os.path.join(base_dir, "overlay_layout_persistent.json")
    control_file = os.path.join(base_dir, ".overlay_control.json")
    pid_file = os.path.join(base_dir, ".overlay_pid")
    icon_positions_file = os.path.join(base_dir, "icon_positions.json")

    # 开机自启动模式：使用持久化布局文件
    if autostart_mode:
        layout_file = persistent_layout_file
        print("[Overlay] 开机自启动模式，加载持久化布局")

    if not os.path.exists(layout_file):
        print(f"[Overlay] 布局文件不存在: {layout_file}，退出")
        sys.exit(1)

    with open(layout_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    dpi_scale = data.get("dpi_scale", 1.0)

    # 开机自启动模式：恢复图标位置
    if autostart_mode and data.get("icon_positions"):
        print("[Overlay] 正在恢复图标位置...")
        _restore_icon_positions(data["icon_positions"])

    # 重建 DesktopLayout 对象，复用 desktop_overlay 的渲染逻辑
    layout = _rebuild_layout(data)

    # 导入并调用渲染函数（确保与主程序完全一致的渲染效果）
    _init_modules()
    img = desktop_overlay._render_overlay(layout, dpi_scale)
    if img is None:
        print("[Overlay] 渲染失败，退出")
        sys.exit(1)

    # 调试保存
    try:
        img.save(os.path.join(base_dir, "overlay_debug.png"))
    except Exception:
        pass

    w, h = img.size
    bgra_data = _rgba_to_bgra(img)
    ox, oy = get_workarea_offset()

    print(f"[Overlay] 创建窗口: {w}x{h}, 偏移: ({ox}, {oy})")
    hwnd = _create_layered_window(bgra_data, w, h, ox, oy)
    print(f"[Overlay] 窗口创建成功: hwnd={hwnd:#x}")

    # 主循环：等待更新或停止
    while True:
        result = _run_overlay(hwnd, control_file, pid_file)
        if result == "update":
            # 更新时优先从临时布局文件读取
            temp_layout_file = os.path.join(base_dir, ".overlay_layout.json")
            update_file = temp_layout_file if os.path.exists(temp_layout_file) else layout_file

            if not os.path.exists(update_file):
                print("[Overlay] 布局文件已删除，退出")
                break
            try:
                with open(update_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                dpi_scale = data.get("dpi_scale", 1.0)
                layout = _rebuild_layout(data)
                img = desktop_overlay._render_overlay(layout, dpi_scale)
                if img:
                    bgra_data = _rgba_to_bgra(img)
                    ox, oy = get_workarea_offset()
                    hdc_screen = user32.GetDC(None)
                    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                    header = BITMAPINFOHEADER()
                    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                    header.biWidth = img.size[0]
                    header.biHeight = -img.size[1]
                    header.biPlanes = 1
                    header.biBitCount = 32
                    header.biCompression = 0
                    pbits = ctypes.c_void_p()
                    hbitmap = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(header), 0, ctypes.byref(pbits), None, 0)
                    if hbitmap:
                        kernel32.RtlMoveMemory(pbits, bgra_data, img.size[0] * img.size[1] * 4)
                        old_bmp = gdi32.SelectObject(hdc_mem, hbitmap)
                        blend = BLENDFUNCTION()
                        blend.BlendOp = 0
                        blend.BlendFlags = 0
                        blend.SourceConstantAlpha = 255
                        blend.AlphaFormat = 1
                        size = SIZE()
                        size.cx = img.size[0]
                        size.cy = img.size[1]
                        pt_src = POINT()
                        user32.UpdateLayeredWindow(hwnd, hdc_screen, None, ctypes.byref(size),
                                                   hdc_mem, ctypes.byref(pt_src), 0,
                                                   ctypes.byref(blend), ULW_ALPHA)
                        gdi32.SelectObject(hdc_mem, old_bmp)
                        gdi32.DeleteObject(hbitmap)
                    gdi32.DeleteDC(hdc_mem)
                    user32.ReleaseDC(None, hdc_screen)
                    print("[Overlay] 布局已更新")
            except Exception as e:
                print(f"[Overlay] 更新失败: {e}")
        else:
            break

    # 清理临时文件（不清理持久化布局文件）
    for fp in [pid_file, control_file]:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except Exception:
            pass
    # 只清理临时布局文件，不清理持久化布局
    temp_layout = os.path.join(base_dir, ".overlay_layout.json")
    try:
        if os.path.exists(temp_layout):
            os.remove(temp_layout)
    except Exception:
        pass
    print("[Overlay] 进程退出")


def _restore_icon_positions(positions: list):
    """恢复图标位置"""
    try:
        # 延迟导入避免循环依赖
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from desktop_scanner import find_desktop_listview, set_icon_position, scan_all_icons

        # 扫描当前桌面获取索引映射
        current_icons = scan_all_icons(extract_images=False)
        name_to_index = {icon.name: icon.index for icon in current_icons}

        hwnd = find_desktop_listview()
        if not hwnd:
            print("[Overlay] 无法找到桌面窗口")
            return

        restored = 0
        for pos in positions:
            name = pos.get("name")
            x, y = pos.get("x"), pos.get("y")
            if name in name_to_index:
                set_icon_position(hwnd, name_to_index[name], x, y)
                restored += 1

        print(f"[Overlay] 已恢复 {restored} 个图标位置")
    except Exception as e:
        print(f"[Overlay] 恢复图标位置失败: {e}")


if __name__ == "__main__":
    main()
