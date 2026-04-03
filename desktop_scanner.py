"""
桌面图标扫描模块
负责获取桌面图标信息（名称、位置、图像）以及移动图标位置
注意：桌面 ListView 在 explorer.exe 进程中，需要跨进程通信
"""

import ctypes
import ctypes.wintypes as wintypes
from dataclasses import dataclass
from typing import List, Optional, Tuple
import os
from PIL import Image


# ---- 声明进程 DPI 感知（必须在所有 Win32 调用之前） ----
# DPI_AWARENESS_PER_MONITOR_AWARE = 2
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


@dataclass
class DesktopIcon:
    """桌面图标数据"""
    index: int
    name: str
    x: int
    y: int
    target_path: str = ""
    image: Optional[Image.Image] = None
    category: str = "其他"


@dataclass
class DesktopInfo:
    """桌面环境信息"""
    physical_width: int    # 物理分辨率宽度（像素）
    physical_height: int   # 物理分辨率高度（像素）
    workarea_width: int    # 工作区宽度（物理像素，去掉任务栏）
    workarea_height: int   # 工作区高度（物理像素，去掉任务栏）
    dpi_scale: float       # DPI 缩放比例（如 1.0, 1.25, 1.5, 2.0 等）


# Windows 消息常量
LVM_GETITEMCOUNT = 0x1004
LVM_GETITEMTEXTW = 0x102D
LVM_GETITEMPOSITION = 0x1010
LVM_SETITEMPOSITION = 0x100F
LVM_SETITEMPOSITION32 = 0x1031
LVM_GETIMAGELIST = 0x1002
LVSIL_NORMAL = 0

# 进程操作常量
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
MEM_COMMIT = 0x00001000
MEM_RESERVE = 0x00002000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

# SHGetFileInfo 常量
SHGFI_ICON = 0x000000100
SHGFI_LARGEICON = 0x000000000


class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HANDLE),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", ctypes.c_wchar * 260),
        ("szTypeName", ctypes.c_wchar * 80),
    ]


class RemoteMemory:
    """跨进程内存操作"""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.process_id = wintypes.DWORD()
        self.process_handle = None
        self.allocations = []

        # 获取窗口所属进程
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(self.process_id))
        self.process_handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE,
            False,
            self.process_id,
        )

    def allocate(self, size: int) -> int:
        """在目标进程中分配内存"""
        addr = ctypes.windll.kernel32.VirtualAllocEx(
            self.process_handle, 0, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
        )
        if not addr:
            raise RuntimeError(f"VirtualAllocEx 失败: {ctypes.GetLastError()}")
        self.allocations.append(addr)
        return addr

    def write(self, addr: int, data: bytes):
        """写入数据到目标进程内存"""
        written = ctypes.c_size_t()
        ctypes.windll.kernel32.WriteProcessMemory(
            self.process_handle, addr, data, len(data), ctypes.byref(written)
        )

    def read(self, addr: int, size: int) -> bytes:
        """从目标进程内存读取数据"""
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t()
        ctypes.windll.kernel32.ReadProcessMemory(
            self.process_handle, addr, buf, size, ctypes.byref(read)
        )
        return buf.raw[:read.value]

    def read_unicode(self, addr: int, max_chars: int = 260) -> str:
        """从目标进程内存读取 Unicode 字符串"""
        data = self.read(addr, max_chars * 2)
        # 找到 null terminator
        null_idx = data.find(b'\x00\x00')
        if null_idx >= 0:
            data = data[:null_idx + 2] if null_idx % 2 == 0 else data[:null_idx + 1]
        return data.decode('utf-16-le', errors='replace').rstrip('\x00')

    def free_all(self):
        """释放所有分配的内存"""
        for addr in self.allocations:
            ctypes.windll.kernel32.VirtualFreeEx(
                self.process_handle, addr, 0, MEM_RELEASE
            )
        self.allocations.clear()

    def close(self):
        """关闭进程句柄"""
        if self.process_handle:
            ctypes.windll.kernel32.CloseHandle(self.process_handle)
            self.process_handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.free_all()
        self.close()


def find_desktop_listview() -> Optional[int]:
    """查找桌面 ListView 窗口句柄"""
    hwnd_progrman = ctypes.windll.user32.FindWindowW("Progman", "Program Manager")
    if not hwnd_progrman:
        return None

    # 直接查找（大多数情况下有效）
    hwnd_shell = ctypes.windll.user32.FindWindowExW(hwnd_progrman, 0, "SHELLDLL_DefView", None)
    hwnd_lv = None
    if hwnd_shell:
        hwnd_lv = ctypes.windll.user32.FindWindowExW(hwnd_shell, 0, "SysListView32", None)

    if hwnd_lv:
        return hwnd_lv

    # 备用方案：枚举所有 WorkerW 子窗口
    def enum_child(hwnd, lparam):
        nonlocal hwnd_lv
        cls = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, cls, 256)
        if cls.value == "SHELLDLL_DefView":
            lv = ctypes.windll.user32.FindWindowExW(hwnd, 0, "SysListView32", None)
            if lv:
                hwnd_lv = lv
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    ctypes.windll.user32.EnumChildWindows(hwnd_progrman, WNDENUMPROC(enum_child), 0)
    return hwnd_lv


def get_icon_count(hwnd: int) -> int:
    """获取桌面图标数量"""
    return ctypes.windll.user32.SendMessageW(hwnd, LVM_GETITEMCOUNT, 0, 0)


def get_icon_text(hwnd: int, index: int, remote: RemoteMemory) -> str:
    """获取指定索引的图标文本（跨进程）"""
    TEXT_BUF_SIZE = 260

    # 构造 LVITEMW 结构体
    class LVITEM(ctypes.Structure):
        _fields_ = [
            ("mask", wintypes.UINT),
            ("iItem", wintypes.INT),
            ("iSubItem", wintypes.INT),
            ("state", wintypes.UINT),
            ("stateMask", wintypes.UINT),
            ("pszText", ctypes.c_void_p),
            ("cchTextMax", wintypes.INT),
            ("iImage", wintypes.INT),
            ("lParam", wintypes.LPARAM),
        ]

    # 在目标进程中分配内存
    remote_item_addr = remote.allocate(ctypes.sizeof(LVITEM))
    # 分配较大缓冲区，兼容 ANSI 和 Unicode
    remote_text_addr = remote.allocate(TEXT_BUF_SIZE * 4)

    # 构造 LVITEM
    item = LVITEM()
    item.mask = 0x0001  # LVIF_TEXT
    item.iItem = index
    item.iSubItem = 0
    item.pszText = remote_text_addr
    item.cchTextMax = TEXT_BUF_SIZE

    # 写入结构体到目标进程
    remote.write(remote_item_addr, bytes(item))

    # 发送 LVM_GETITEMTEXTW
    result = ctypes.windll.user32.SendMessageW(
        hwnd, LVM_GETITEMTEXTW, index, remote_item_addr
    )

    if result > 0:
        # 桌面 ListView 返回 ANSI 编码文本（系统代码页，如 cp936/GBK）
        raw = remote.read(remote_text_addr, result)

        # 使用 Windows 系统代码页解码
        try:
            text = raw.decode('mbcs', errors='replace')
        except Exception:
            # 回退到 GBK
            text = raw.decode('gbk', errors='replace')

        return text.rstrip('\x00')

    return ""


def get_icon_position(hwnd: int, index: int, remote: RemoteMemory) -> Tuple[int, int]:
    """获取指定索引的图标位置（跨进程）"""
    # POINT 结构: x(4) + y(4) = 8 bytes
    POINT_SIZE = 8

    remote_point_addr = remote.allocate(POINT_SIZE)
    ctypes.windll.user32.SendMessageW(
        hwnd, LVM_GETITEMPOSITION, index, remote_point_addr
    )

    data = remote.read(remote_point_addr, POINT_SIZE)
    x = int.from_bytes(data[0:4], 'little', signed=True)
    y = int.from_bytes(data[4:8], 'little', signed=True)
    return x, y


def set_icon_position(hwnd: int, index: int, x: int, y: int):
    """设置指定索引的图标位置（使用32位坐标，避免16位溢出）"""
    # 使用 LVM_SETITEMPOSITION32 需要在目标进程写入 POINT 结构
    from ctypes import wintypes

    class POINT(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_long),
            ("y", ctypes.c_long),
        ]

    # 在目标进程中分配内存写入坐标
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    proc = ctypes.windll.kernel32.OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE, False, pid
    )
    if not proc:
        # 回退到16位方式
        lparam = (y & 0xFFFF) << 16 | (x & 0xFFFF)
        ctypes.windll.user32.SendMessageW(hwnd, LVM_SETITEMPOSITION, index, lparam)
        return

    remote_addr = ctypes.windll.kernel32.VirtualAllocEx(
        proc, 0, 8, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    )
    point_data = POINT(x, y)
    written = ctypes.c_size_t()
    ctypes.windll.kernel32.WriteProcessMemory(
        proc, remote_addr, bytes(point_data), 8, ctypes.byref(written)
    )
    ctypes.windll.user32.SendMessageW(hwnd, LVM_SETITEMPOSITION32, index, remote_addr)
    ctypes.windll.kernel32.VirtualFreeEx(proc, remote_addr, 0, MEM_RELEASE)
    ctypes.windll.kernel32.CloseHandle(proc)


def get_icon_image_from_path(filepath: str, size: int = 48) -> Optional[Image.Image]:
    """从文件路径获取图标图像"""
    try:
        if not filepath or not os.path.exists(filepath):
            return None

        shfi = SHFILEINFOW()
        result = ctypes.windll.shell32.SHGetFileInfoW(
            filepath, 0, ctypes.byref(shfi), ctypes.sizeof(shfi),
            SHGFI_ICON | SHGFI_LARGEICON
        )
        if result == 0 or not shfi.hIcon:
            return None

        img = _hicon_to_image(shfi.hIcon, size)
        if shfi.hIcon:
            ctypes.windll.user32.DestroyIcon(shfi.hIcon)
        return img
    except Exception:
        return None


def _hicon_to_image(hicon: int, size: int) -> Optional[Image.Image]:
    """将 HICON 转换为 PIL Image"""
    try:
        hdc = ctypes.windll.user32.GetDC(None)
        mem_dc = ctypes.windll.gdi32.CreateCompatibleDC(hdc)
        bitmap = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc, size, size)
        old_bitmap = ctypes.windll.gdi32.SelectObject(mem_dc, bitmap)

        ctypes.windll.user32.DrawIconEx(mem_dc, 0, 0, hicon, size, size, 0, None, 0x0003)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = size
        bmi.biHeight = -size
        bmi.biPlanes = 1
        bmi.biBitCount = 32

        buf_size = size * size * 4
        buf = (ctypes.c_uint8 * buf_size)()
        ctypes.windll.gdi32.GetDIBits(mem_dc, bitmap, 0, size, buf, ctypes.byref(bmi), 0)

        ctypes.windll.gdi32.SelectObject(mem_dc, old_bitmap)
        ctypes.windll.gdi32.DeleteObject(bitmap)
        ctypes.windll.gdi32.DeleteDC(mem_dc)
        ctypes.windll.user32.ReleaseDC(None, hdc)

        raw_data = bytes(buf)
        img = Image.frombytes("RGBA", (size, size), raw_data, "raw", "BGRA", size * 4, -1)
        return img
    except Exception:
        return None


def resolve_shortcut_path(shortcut_name: str) -> str:
    """解析快捷方式的目标路径"""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    public_desktop = os.path.join(
        os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop"
    )

    # 尝试各种路径
    for base in [desktop, public_desktop]:
        for ext in ["", ".lnk", ".url"]:
            test_path = os.path.join(base, f"{shortcut_name}{ext}")
            if os.path.exists(test_path):
                return _resolve_lnk(test_path)

    # 尝试直接在 Desktop 文件夹中搜索匹配的文件
    for base in [desktop, public_desktop]:
        if not os.path.isdir(base):
            continue
        name_lower = shortcut_name.lower()
        for fname in os.listdir(base):
            if fname.lower().startswith(name_lower):
                return _resolve_lnk(os.path.join(base, fname))

    return ""


def _resolve_lnk(filepath: str) -> str:
    """解析 .lnk 或 .url 文件"""
    try:
        if filepath.lower().endswith(".url"):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.lower().startswith("url="):
                        return line.strip()[4:]
            return filepath

        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(filepath)
        target = shortcut.TargetPath
        return target if target else filepath
    except Exception:
        return filepath


def get_desktop_info() -> DesktopInfo:
    """
    获取完整的桌面环境信息：物理分辨率、工作区、DPI 缩放比例
    必须在声明 DPI 感知后调用。
    返回的像素值均为物理像素。
    """
    # DPI 缩放比例
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        dpi_scale = dpi / 96.0
    except Exception:
        dpi_scale = 1.0

    # 物理分辨率（DPI 感知模式下，GetSystemMetrics 返回物理像素）
    physical_w = ctypes.windll.user32.GetSystemMetrics(0)   # SM_CXSCREEN
    physical_h = ctypes.windll.user32.GetSystemMetrics(1)   # SM_CYSCREEN

    # 工作区（去掉任务栏）—— DPI 感知模式下直接是物理像素
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    workarea_w = rect.right - rect.left
    workarea_h = rect.bottom - rect.top

    return DesktopInfo(
        physical_width=physical_w,
        physical_height=physical_h,
        workarea_width=workarea_w,
        workarea_height=workarea_h,
        dpi_scale=round(dpi_scale, 4),
    )


def get_desktop_resolution() -> Tuple[int, int]:
    """兼容旧接口：获取桌面工作区物理像素尺寸"""
    info = get_desktop_info()
    return info.workarea_width, info.workarea_height


def scan_all_icons(extract_images: bool = True) -> List[DesktopIcon]:
    """扫描桌面所有图标"""
    hwnd = find_desktop_listview()
    if not hwnd:
        raise RuntimeError("无法找到桌面 ListView 窗口")

    count = get_icon_count(hwnd)
    icons = []

    with RemoteMemory(hwnd) as remote:
        for i in range(count):
            name = get_icon_text(hwnd, i, remote)
            if not name:
                continue
            x, y = get_icon_position(hwnd, i, remote)
            target_path = resolve_shortcut_path(name)

            icon = DesktopIcon(
                index=i,
                name=name,
                x=x,
                y=y,
                target_path=target_path,
            )

            if extract_images and target_path:
                icon.image = get_icon_image_from_path(target_path)

            icons.append(icon)

    return icons


def apply_icon_positions(icon_positions: List[Tuple[int, int, int]]):
    """应用图标位置到桌面"""
    hwnd = find_desktop_listview()
    if not hwnd:
        raise RuntimeError("无法找到桌面 ListView 窗口")

    for index, x, y in icon_positions:
        set_icon_position(hwnd, index, x, y)


if __name__ == "__main__":
    print("正在扫描桌面图标...")
    icons = scan_all_icons(extract_images=False)
    for icon in icons[:10]:
        print(f"  [{icon.index}] {icon.name} ({icon.x}, {icon.y}) -> {icon.target_path}")
    if len(icons) > 10:
        print(f"  ... 还有 {len(icons) - 10} 个图标")
    print(f"共找到 {len(icons)} 个图标")
    w, h = get_desktop_resolution()
    print(f"桌面可用区域: {w}x{h}")
