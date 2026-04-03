"""
桌面图标整理工具 - 主程序
Windows 11 风格 GUI，支持图标分类、布局预览、拖拽排列、备份还原
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import sys

from desktop_scanner import (
    DesktopIcon,
    DesktopInfo,
    get_desktop_info,
    scan_all_icons,
    apply_icon_positions,
)
from icon_classifier import (
    CATEGORIES,
    CATEGORY_COLORS,
    classify_all_icons,
    classify_icon,
    load_custom_categories,
    save_classification_cache,
)
from layout_engine import (
    DesktopLayout,
    calculate_layout,
    layout_to_icon_list,
)
from backup_manager import (
    backup_current_layout,
    save_layout,
    load_layout,
    load_backup,
    list_backups,
    list_layouts,
    delete_backup,
    delete_layout,
    get_latest_backup,
)
from desktop_overlay import (
    show_desktop_overlay,
    hide_desktop_overlay,
    is_overlay_running,
    is_autostart_enabled,
    enable_autostart,
    disable_autostart,
    save_persistent_layout,
    has_persistent_layout,
    clear_persistent_layout,
)
from preview_canvas import DragDropPreviewCanvas


# ===================== 主题配置 =====================

# Windows 11 风格颜色
COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_medium": "#16213e",
    "bg_light": "#0f3460",
    "accent": "#e94560",
    "accent2": "#3a86ff",
    "text_primary": "#ffffff",
    "text_secondary": "#a0a0b0",
    "border": "#333355",
    "card": "#1e1e3a",
    "card_hover": "#252550",
    "success": "#00c853",
    "warning": "#ff8f00",
    "danger": "#ff1744",
    "header": "#0d1b3e",
}

FONT_FAMILY = "Microsoft YaHei UI"


class ScrollableFrame(ctk.CTkScrollableFrame):
    """可滚动框架"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)


class ToolButton(ctk.CTkButton):
    """工具栏按钮"""

    def __init__(
        self,
        master,
        text="",
        icon_text="",
        width=100,
        height=36,
        command=None,
        **kwargs,
    ):
        super().__init__(
            master,
            text=f"{icon_text}  {text}" if icon_text else text,
            width=width,
            height=height,
            corner_radius=8,
            command=command,
            font=(FONT_FAMILY, 12),
            fg_color=COLORS["card"],
            hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )


class ActionButton(ctk.CTkButton):
    """主要操作按钮"""

    def __init__(self, master, text="", command=None, color="accent", **kwargs):
        color_map = {
            "accent": COLORS["accent"],
            "accent2": COLORS["accent2"],
            "success": COLORS["success"],
            "warning": COLORS["warning"],
            "danger": COLORS["danger"],
        }
        super().__init__(
            master,
            text=text,
            command=command,
            corner_radius=10,
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=color_map.get(color, COLORS["accent"]),
            hover_color=color_map.get(color, COLORS["accent"]),
            text_color="#ffffff",
            height=40,
            **kwargs,
        )


class CategoryCard(ctk.CTkButton):
    """类别卡片（紧凑型单行按钮）"""

    def __init__(self, master, category_name, icon_count, color, **kwargs):
        super().__init__(
            master,
            text=f"  {category_name}   {icon_count}",
            height=28,
            corner_radius=6,
            fg_color=COLORS["card"],
            hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"],
            font=(FONT_FAMILY, 11),
            anchor="w",
            **kwargs,
        )

        self.category_name = category_name
        self.color = color
        self._icon_count = icon_count
        self.selected = False

        # 颜色指示条通过左侧 border 模拟
        self.configure(border_width=0)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.configure(fg_color=COLORS["bg_light"])
        else:
            self.configure(fg_color=COLORS["card"])

    def update_count(self, count: int):
        self._icon_count = count
        self.configure(text=f"  {self.category_name}   {count}")


class MainApp(ctk.CTk):
    """主应用程序"""

    def __init__(self):
        super().__init__()

        self.title("桌面图标整理工具")
        self.geometry("1200x780")
        self.minsize(1000, 650)

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # 配置颜色
        self.configure(fg_color=COLORS["bg_dark"])

        # 数据状态
        self._icons: list[DesktopIcon] = []
        self._classified: dict[str, list[DesktopIcon]] = {}
        self._layout: DesktopLayout | None = None
        self._desktop_info: DesktopInfo = get_desktop_info()
        self._desktop_w = self._desktop_info.workarea_width
        self._desktop_h = self._desktop_info.workarea_height
        self._processing = False
        self._overlay_shown = False

        # 构建界面
        self._build_ui()

        # 自动扫描桌面
        self.after(500, self._auto_scan)

        # 启动后检测叠加层状态（延迟执行，避免阻塞界面初始化）
        self.after(1000, self._check_overlay_state)

        # 绑定窗口关闭事件，确保子进程退出
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_ui(self):
        """构建完整 UI"""
        # ====== 标题栏 ======
        self._build_title_bar()

        # ====== 工具栏 ======
        self._build_toolbar()

        # ====== 主内容区 ======
        self._build_main_content()

        # ====== 底部状态栏 ======
        self._build_status_bar()

    def _build_title_bar(self):
        """标题栏"""
        title_frame = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color=COLORS["header"])
        title_frame.pack(fill="x", padx=0, pady=0)
        title_frame.pack_propagate(False)

        # 左侧：标题
        left = ctk.CTkFrame(title_frame, fg_color="transparent")
        left.pack(side="left", padx=16, pady=10)

        ctk.CTkLabel(
            left,
            text="🖥  桌面图标整理工具",
            font=(FONT_FAMILY, 16, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        # 右侧：桌面信息
        right = ctk.CTkFrame(title_frame, fg_color="transparent")
        right.pack(side="right", padx=16, pady=10)

        self._desktop_info_label = ctk.CTkLabel(
            right,
            text=f"桌面: {self._desktop_info.physical_width}×{self._desktop_info.physical_height}  |  工作区: {self._desktop_w}×{self._desktop_h}  |  缩放: {int(self._desktop_info.dpi_scale * 100)}%",
            font=(FONT_FAMILY, 10),
            text_color=COLORS["text_secondary"],
        )
        self._desktop_info_label.pack(side="right")

    def _build_toolbar(self):
        """工具栏"""
        toolbar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=COLORS["bg_medium"])
        toolbar.pack(fill="x", padx=0, pady=(0, 0))
        toolbar.pack_propagate(False)

        inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        # 第一行按钮
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x")

        ToolButton(row1, text="扫描桌面", icon_text="🔍", command=self._scan_desktop, width=110).pack(side="left", padx=(0, 6))
        ToolButton(row1, text="自动分类", icon_text="📋", command=self._classify_icons, width=110).pack(side="left", padx=(0, 6))
        ToolButton(row1, text="联网分类", icon_text="🌐", command=lambda: self._classify_icons(online=True), width=120).pack(side="left", padx=(0, 6))

        # 分隔
        sep = ctk.CTkFrame(row1, width=1, fg_color=COLORS["border"])
        sep.pack(side="left", fill="y", padx=8, pady=4)

        ToolButton(row1, text="备份桌面", icon_text="💾", command=self._backup_desktop, width=110).pack(side="left", padx=(0, 6))
        ToolButton(row1, text="还原桌面", icon_text="↩️", command=self._restore_desktop, width=110).pack(side="left", padx=(0, 6))

        sep2 = ctk.CTkFrame(row1, width=1, fg_color=COLORS["border"])
        sep2.pack(side="left", fill="y", padx=8, pady=4)

        ToolButton(row1, text="保存布局", icon_text="📥", command=self._save_layout_dialog, width=110).pack(side="left", padx=(0, 6))
        ToolButton(row1, text="加载布局", icon_text="📤", command=self._load_layout_dialog, width=110).pack(side="left", padx=(0, 6))

        sep3 = ctk.CTkFrame(row1, width=1, fg_color=COLORS["border"])
        sep3.pack(side="left", fill="y", padx=8, pady=4)

        self._show_overlay_btn = ToolButton(row1, text="显示边框", icon_text="🔲", command=self._show_overlay, width=110)
        self._show_overlay_btn.pack(side="left", padx=(0, 6))

        self._hide_overlay_btn = ToolButton(row1, text="隐藏边框", icon_text="🚫", command=self._hide_overlay, width=110)
        self._hide_overlay_btn.pack(side="left", padx=(0, 6))

        # 右侧状态
        self._status_label = ctk.CTkLabel(
            row1, text="就绪",
            font=(FONT_FAMILY, 11),
            text_color=COLORS["text_secondary"],
        )
        self._status_label.pack(side="right", padx=8)

        # 进度条
        self._progress = ctk.CTkProgressBar(
            row1, width=150, height=6, corner_radius=3,
            fg_color=COLORS["border"], progress_color=COLORS["accent2"],
        )
        self._progress.pack(side="right", padx=(0, 8))
        self._progress.set(0)

    def _build_main_content(self):
        """主内容区：左侧类别 + 中间预览 + 右侧详情"""
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=0, pady=0)

        # 左侧面板 - 类别列表
        self._build_left_panel(main)

        # 中间 - 预览画布
        self._build_center_panel(main)

        # 右侧面板 - 属性详情
        self._build_right_panel(main)

    def _build_left_panel(self, parent):
        """左侧类别面板"""
        left_panel = ctk.CTkFrame(parent, width=220, corner_radius=0, fg_color=COLORS["bg_medium"])
        left_panel.pack(side="left", fill="y", padx=0, pady=0)
        left_panel.pack_propagate(False)

        # 标题
        header = ctk.CTkFrame(left_panel, height=40, corner_radius=0, fg_color=COLORS["header"])
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="  分类概览",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=8, pady=10)

        # 类别列表
        self._category_container = ctk.CTkScrollableFrame(
            left_panel, fg_color="transparent", scrollbar_button_color=COLORS["border"]
        )
        self._category_container.pack(fill="both", expand=True, padx=6, pady=6)

        self._category_cards: dict[str, CategoryCard] = {}

        # 初始化类别卡片
        for cat in CATEGORIES:
            card = CategoryCard(
                self._category_container,
                category_name=cat,
                icon_count=0,
                color=CATEGORY_COLORS.get(cat, "#666666"),
            )
            card.pack(fill="x", pady=2)
            self._category_cards[cat] = card

        # 备份管理区域（放在类别卡片下方）
        self._backup_section = ctk.CTkFrame(self._category_container, corner_radius=8, fg_color=COLORS["card"])
        self._backup_section.pack(fill="x", pady=(12, 2))

        ctk.CTkLabel(
            self._backup_section, text="备份管理",
            font=(FONT_FAMILY, 11, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 4))

        ToolButton(
            self._backup_section, text="📋 备份列表", command=self._show_backup_list, width=180, height=28,
        ).pack(fill="x", padx=6, pady=2)

        ToolButton(
            self._backup_section, text="📊 布局列表", command=self._show_layout_list, width=180, height=28,
        ).pack(fill="x", padx=6, pady=(2, 8))

        # 统计信息
        self._stats_frame = ctk.CTkFrame(left_panel, height=50, corner_radius=0, fg_color=COLORS["header"])
        self._stats_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        self._stats_frame.pack_propagate(False)

        self._stats_label = ctk.CTkLabel(
            self._stats_frame, text="共 0 个图标 · 0 个类别",
            font=(FONT_FAMILY, 10),
            text_color=COLORS["text_secondary"],
        )
        self._stats_label.pack(fill="x", padx=10, pady=15)

    def _build_center_panel(self, parent):
        """中间预览面板"""
        center_panel = ctk.CTkFrame(parent, corner_radius=0, fg_color=COLORS["bg_dark"])
        center_panel.pack(side="left", fill="both", expand=True, padx=0, pady=0)

        # 预览标题栏
        preview_header = ctk.CTkFrame(center_panel, height=40, corner_radius=0, fg_color=COLORS["header"])
        preview_header.pack(fill="x", padx=0, pady=0)
        preview_header.pack_propagate(False)

        ctk.CTkLabel(
            preview_header, text="  布局预览 (拖拽图标可交换位置)",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(side="left", padx=8, pady=10)

        # 缩放按钮
        zoom_frame = ctk.CTkFrame(preview_header, fg_color="transparent")
        zoom_frame.pack(side="right", padx=8, pady=6)

        ctk.CTkButton(
            zoom_frame, text="−", width=28, height=28, corner_radius=6,
            font=(FONT_FAMILY, 14, "bold"),
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"],
            command=self._zoom_out,
        ).pack(side="left", padx=2)

        self._zoom_label = ctk.CTkLabel(
            zoom_frame, text="100%", font=(FONT_FAMILY, 11),
            text_color=COLORS["text_secondary"], width=50,
        )
        self._zoom_label.pack(side="left", padx=4)

        ctk.CTkButton(
            zoom_frame, text="+", width=28, height=28, corner_radius=6,
            font=(FONT_FAMILY, 14, "bold"),
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"],
            command=self._zoom_in,
        ).pack(side="left", padx=2)

        # 预览画布
        self._preview_canvas = DragDropPreviewCanvas(
            center_panel,
            on_icon_dragged=self._on_icon_dragged,
            on_icon_selected=self._on_icon_selected,
            bg=COLORS["bg_dark"],
        )
        self._preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)

        self._zoom_level = 1.0

    def _build_right_panel(self, parent):
        """右侧详情面板"""
        right_panel = ctk.CTkFrame(parent, width=240, corner_radius=0, fg_color=COLORS["bg_medium"])
        right_panel.pack(side="right", fill="y", padx=0, pady=0)
        right_panel.pack_propagate(False)

        # 标题
        header = ctk.CTkFrame(right_panel, height=40, corner_radius=0, fg_color=COLORS["header"])
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="  图标详情",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=8, pady=10)

        # 详情内容
        self._detail_container = ctk.CTkScrollableFrame(
            right_panel, fg_color="transparent", scrollbar_button_color=COLORS["border"]
        )
        self._detail_container.pack(fill="both", expand=True, padx=8, pady=8)

        # 图标预览（紧凑型）
        self._icon_preview_frame = ctk.CTkFrame(self._detail_container, corner_radius=8, fg_color=COLORS["card"])
        self._icon_preview_frame.pack(fill="x", pady=(0, 4))

        self._icon_image_label = ctk.CTkLabel(
            self._icon_preview_frame, text="?",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=COLORS["text_secondary"],
            width=40, height=40,
        )
        self._icon_image_label.pack(pady=6)

        self._icon_name_label = ctk.CTkLabel(
            self._icon_preview_frame, text="未选择图标",
            font=(FONT_FAMILY, 10, "bold"),
            text_color=COLORS["text_primary"],
            wraplength=180,
        )
        self._icon_name_label.pack(pady=(0, 2))

        self._icon_path_label = ctk.CTkLabel(
            self._icon_preview_frame, text="",
            font=(FONT_FAMILY, 8),
            text_color=COLORS["text_secondary"],
            wraplength=180,
        )
        self._icon_path_label.pack(pady=(0, 6))

        # 属性区域（紧凑型）
        self._props_frame = ctk.CTkFrame(self._detail_container, corner_radius=8, fg_color=COLORS["card"])
        self._props_frame.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            self._props_frame, text="属性",
            font=(FONT_FAMILY, 10, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=8, pady=(6, 2))

        # 类别
        cat_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        cat_row.pack(fill="x", padx=8, pady=1)

        ctk.CTkLabel(cat_row, text="类别:", font=(FONT_FAMILY, 9),
                      text_color=COLORS["text_secondary"]).pack(side="left")

        self._category_value_label = ctk.CTkLabel(
            cat_row, text="—", font=(FONT_FAMILY, 9),
            text_color=COLORS["text_primary"], anchor="e",
        )
        self._category_value_label.pack(side="right")

        # 位置
        pos_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        pos_row.pack(fill="x", padx=8, pady=1)

        ctk.CTkLabel(pos_row, text="位置:", font=(FONT_FAMILY, 9),
                      text_color=COLORS["text_secondary"]).pack(side="left")

        self._position_value_label = ctk.CTkLabel(
            pos_row, text="—", font=(FONT_FAMILY, 9),
            text_color=COLORS["text_primary"], anchor="e",
        )
        self._position_value_label.pack(side="right")

        # 索引
        idx_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        idx_row.pack(fill="x", padx=8, pady=1)

        ctk.CTkLabel(idx_row, text="索引:", font=(FONT_FAMILY, 9),
                      text_color=COLORS["text_secondary"]).pack(side="left")

        self._index_value_label = ctk.CTkLabel(
            idx_row, text="—", font=(FONT_FAMILY, 9),
            text_color=COLORS["text_primary"], anchor="e",
        )
        self._index_value_label.pack(side="right")

        # 类别修改下拉框
        cat_change_row = ctk.CTkFrame(self._props_frame, fg_color="transparent")
        cat_change_row.pack(fill="x", padx=8, pady=(2, 6))

        ctk.CTkLabel(cat_change_row, text="更改类别:", font=(FONT_FAMILY, 9),
                      text_color=COLORS["text_secondary"]).pack(fill="x", pady=(0, 2))

        self._category_option = ctk.CTkOptionMenu(
            cat_change_row, values=CATEGORIES,
            font=(FONT_FAMILY, 9),
            height=24,
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["bg_light"],
            button_hover_color=COLORS["accent2"],
            dropdown_fg_color=COLORS["card"],
            text_color=COLORS["text_primary"],
        )
        self._category_option.pack(fill="x")
        self._category_option.set("其他")
        self._category_option.configure(command=self._change_icon_category)

        # ====== 操作按钮区 ======
        actions_frame = ctk.CTkFrame(self._detail_container, corner_radius=8, fg_color=COLORS["card"])
        actions_frame.pack(fill="x", pady=(0, 4))

        ActionButton(
            actions_frame, text="🚀  应用布局到桌面",
            command=self._apply_layout,
            color="accent2",
        ).pack(fill="x", padx=8, pady=(8, 3))

        ActionButton(
            actions_frame, text="🔄  重新生成布局",
            command=self._regenerate_layout,
            color="warning",
        ).pack(fill="x", padx=8, pady=(3, 8))

        # 持久化设置（紧随操作按钮）
        persist_frame = ctk.CTkFrame(self._detail_container, corner_radius=8, fg_color=COLORS["card"])
        persist_frame.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            persist_frame, text="持久化设置",
            font=(FONT_FAMILY, 10, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=8, pady=(6, 2))

        # 开机自启动开关
        autostart_row = ctk.CTkFrame(persist_frame, fg_color="transparent")
        autostart_row.pack(fill="x", padx=8, pady=2)

        ctk.CTkLabel(
            autostart_row, text="开机自启动:",
            font=(FONT_FAMILY, 9),
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        self._autostart_var = ctk.BooleanVar(value=is_autostart_enabled())
        self._autostart_switch = ctk.CTkSwitch(
            autostart_row,
            text="",
            variable=self._autostart_var,
            command=self._toggle_autostart,
            width=50,
        )
        self._autostart_switch.pack(side="right")

        ActionButton(
            persist_frame, text="💾  保存持久化布局",
            command=self._save_persistent_layout,
            color="success",
        ).pack(fill="x", padx=8, pady=(2, 2))

        ActionButton(
            persist_frame, text="🗑️  清除持久化布局",
            command=self._clear_persistent_layout,
            color="danger",
        ).pack(fill="x", padx=8, pady=(2, 6))

    def _build_status_bar(self):
        """底部状态栏"""
        status = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=COLORS["header"])
        status.pack(fill="x", side="bottom", padx=0, pady=0)
        status.pack_propagate(False)

        self._status_bar_label = ctk.CTkLabel(
            status,
            text="就绪 | 扫描桌面开始使用",
            font=(FONT_FAMILY, 10),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self._status_bar_label.pack(fill="x", padx=12, pady=6)

    # ===================== 操作方法 =====================

    def _set_status(self, text: str):
        """更新状态栏"""
        self._status_bar_label.configure(text=text)
        self._status_label.configure(text=text.split("|")[0].strip() if "|" in text else text)

    def _set_progress(self, value: float):
        """更新进度条 (0.0 - 1.0)"""
        self._progress.set(value)

    def _auto_scan(self):
        """自动扫描桌面"""
        self._scan_desktop()

    def _scan_desktop(self):
        """扫描桌面图标"""
        if self._processing:
            return

        self._processing = True
        self._set_status("正在扫描桌面图标...")

        def worker():
            try:
                icons = scan_all_icons(extract_images=True)
                self._icons = icons

                # 更新 UI（线程安全）
                self.after(0, lambda: self._on_scan_complete(icons))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"扫描失败: {e}"))
            finally:
                self.after(0, lambda: setattr(self, '_processing', False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_complete(self, icons: list[DesktopIcon]):
        """扫描完成回调"""
        self._set_status(f"扫描完成 | 共找到 {len(icons)} 个图标")
        self._set_progress(1.0)
        self._update_category_cards()
        # 初始预览：显示当前桌面布局
        if icons:
            self._preview_canvas.set_raw_icons(icons, self._desktop_w, self._desktop_h)
        else:
            self._show_empty_preview()

    def _classify_icons(self, online: bool = False):
        """分类所有图标"""
        if not self._icons:
            messagebox.showinfo("提示", "请先扫描桌面图标")
            return
        if self._processing:
            return

        self._processing = True
        mode = "联网分类" if online else "自动分类"
        self._set_status(f"正在进行{mode}...")

        def progress_cb(current, total, name, category):
            self.after(0, lambda: self._set_progress(current / total))
            self.after(0, lambda: self._set_status(f"{mode}中... {current}/{total} - {name} → {category}"))

        def worker():
            try:
                classified = classify_all_icons(
                    self._icons,
                    use_online=online,
                    progress_callback=progress_cb,
                )
                self._classified = classified
                self.after(0, lambda: self._on_classify_complete(classified))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"分类失败: {e}"))
            finally:
                self.after(0, lambda: setattr(self, '_processing', False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_classify_complete(self, classified: dict):
        """分类完成回调"""
        total_icons = sum(len(v) for v in classified.values())
        cat_count = len(classified)
        self._set_status(f"分类完成 | {total_icons} 个图标, {cat_count} 个类别")
        self._set_progress(1.0)
        self._update_category_cards()
        self._generate_and_show_layout()

    def _generate_and_show_layout(self):
        """生成布局并显示在预览中"""
        if not self._classified:
            return

        dpi_scale = self._desktop_info.dpi_scale

        # cell 尺寸需要乘以 DPI 缩放，因为 ListView 使用物理像素坐标
        from layout_engine import DEFAULT_CELL_WIDTH, DEFAULT_CELL_HEIGHT
        self._layout = calculate_layout(
            self._classified,
            self._desktop_w,
            self._desktop_h,
            cell_width=int(DEFAULT_CELL_WIDTH * dpi_scale),
            cell_height=int(DEFAULT_CELL_HEIGHT * dpi_scale),
        )
        self._preview_canvas.set_layout(self._layout, self._desktop_w, self._desktop_h)

    def _show_empty_preview(self):
        """显示空预览提示"""
        self._preview_canvas.delete("all")
        cw = self._preview_canvas.winfo_width() or 800
        ch = self._preview_canvas.winfo_height() or 600
        self._preview_canvas.create_text(
            cw / 2, ch / 2 - 20,
            text="点击「自动分类」开始整理桌面图标",
            fill=COLORS["text_secondary"],
            font=(FONT_FAMILY, 16),
        )
        self._preview_canvas.create_text(
            cw / 2, ch / 2 + 20,
            text=f"已扫描 {len(self._icons)} 个图标",
            fill=COLORS["text_secondary"],
            font=(FONT_FAMILY, 12),
        )

    def _update_category_cards(self):
        """更新左侧类别卡片"""
        total = 0
        for cat_name, card in self._category_cards.items():
            count = len(self._classified.get(cat_name, []))
            card.update_count(count)
            total += count

        active_cats = sum(1 for v in self._classified.values() if v)
        self._stats_label.configure(text=f"共 {total} 个图标 · {active_cats} 个类别")

    def _on_icon_dragged(self, src_name: str, dst_name: str | None):
        """图标拖拽交换回调"""
        if not self._layout:
            return

        src_cell = None
        dst_cell = None

        for cell in self._layout.cells:
            if cell.icon:
                if cell.icon.name == src_name:
                    src_cell = cell
                if dst_name and cell.icon.name == dst_name:
                    dst_cell = cell

        if src_cell and dst_cell:
            # 交换图标，保留 cell 的像素位置不变
            src_cell.icon, dst_cell.icon = dst_cell.icon, src_cell.icon
            if src_cell.icon:
                src_cell.category = src_cell.icon.category
            if dst_cell.icon:
                dst_cell.category = dst_cell.icon.category

            self._rebuild_classified_from_layout()
            self._update_category_cards()

        self._set_status(f"已交换: {src_name} ↔ {dst_name}")

    def _rebuild_classified_from_layout(self):
        """从布局重建分类字典"""
        self._classified = {}
        if not self._layout:
            return

        for cell in self._layout.cells:
            if cell.is_header or not cell.icon:
                continue
            cat = cell.category or "其他"
            if cat not in self._classified:
                self._classified[cat] = []
            self._classified[cat].append(cell.icon)

    def _on_icon_selected(self, icon_name: str | None):
        """图标选中回调"""
        if not icon_name:
            self._icon_name_label.configure(text="未选择图标")
            self._icon_path_label.configure(text="")
            self._category_value_label.configure(text="—")
            self._position_value_label.configure(text="—")
            self._index_value_label.configure(text="—")
            self._icon_image_label.configure(text="?", text_color=COLORS["text_secondary"])
            return

        icon = self._find_icon_by_name(icon_name)
        if not icon:
            return

        self._icon_name_label.configure(text=icon.name)

        path_text = icon.target_path if icon.target_path else "路径未知"
        if len(path_text) > 30:
            path_text = "..." + path_text[-27:]
        self._icon_path_label.configure(text=path_text)

        self._category_value_label.configure(
            text=icon.category,
            text_color=CATEGORY_COLORS.get(icon.category, COLORS["text_primary"]),
        )
        self._index_value_label.configure(text=str(icon.index))

        # 从布局中获取图标的新位置（预览中的位置）
        layout_pos = self._find_layout_position(icon_name)
        self._position_value_label.configure(text=f"({layout_pos[0]}, {layout_pos[1]})")

        # 图标预览
        if icon.image:
            ctk_image = ctk.CTkImage(light_image=icon.image, dark_image=icon.image, size=(32, 32))
            self._icon_image_label.configure(image=ctk_image, text="")
            self._icon_image_label._ctk_image = ctk_image  # 防止 GC
        else:
            initial = icon.name[0].upper() if icon.name else "?"
            self._icon_image_label.configure(text=initial, text_color=CATEGORY_COLORS.get(icon.category, COLORS["text_secondary"]))

        # 设置类别下拉框
        self._category_option.set(icon.category)

    def _find_layout_position(self, icon_name: str) -> tuple:
        """从布局中查找图标的新位置"""
        if not self._layout:
            return (0, 0)
        for cell in self._layout.cells:
            if cell.icon and cell.icon.name == icon_name:
                return (cell.pixel_x, cell.pixel_y)
        return (0, 0)

    def _find_icon_by_name(self, name: str) -> DesktopIcon | None:
        """按名称查找图标"""
        for icon in self._icons:
            if icon.name == name:
                return icon
        return None

    def _change_icon_category(self, new_category: str):
        """更改选中图标的类别"""
        if not self._selected_icon_name():
            return

        icon = self._find_icon_by_name(self._selected_icon_name())
        if not icon:
            return

        old_category = icon.category
        icon.category = new_category

        # 更新分类字典
        if old_category in self._classified:
            self._classified[old_category] = [i for i in self._classified[old_category] if i.name != icon.name]
            if not self._classified[old_category]:
                del self._classified[old_category]

        if new_category not in self._classified:
            self._classified[new_category] = []
        self._classified[new_category].append(icon)

        # 重新生成布局
        self._generate_and_show_layout()
        self._update_category_cards()

        self._set_status(f"已将「{icon.name}」从「{old_category}」移至「{new_category}」")

    def _selected_icon_name(self) -> str | None:
        """获取当前选中的图标名"""
        return self._preview_canvas._selected_icon

    def _apply_layout(self):
        """应用布局到桌面"""
        if not self._layout:
            messagebox.showinfo("提示", "没有可应用的布局")
            return

        # 确认
        result = messagebox.askyesno(
            "确认应用",
            "即将将预览布局应用到桌面。\n\n"
            "建议先备份当前桌面布局。\n\n"
            "确定要继续吗？",
        )
        if not result:
            return

        positions = layout_to_icon_list(self._layout)
        if not positions:
            messagebox.showinfo("提示", "布局中没有图标位置信息")
            return

        self._set_status("正在应用布局到桌面...")

        # 应用布局时关闭叠加层
        overlay_was_shown = self._overlay_shown
        if self._overlay_shown:
            hide_desktop_overlay()
            self._overlay_shown = False

        def worker():
            try:
                apply_icon_positions(positions)
                self.after(0, lambda: self._set_status(f"布局已应用 | 共移动 {len(positions)} 个图标"))
                # 如果叠加层之前开着，应用后重新显示
                if overlay_was_shown:
                    self.after(0, self._show_overlay_after_apply)
                self.after(0, lambda: messagebox.showinfo("成功", f"布局已成功应用到桌面！\n共移动 {len(positions)} 个图标。"))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"应用布局失败: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_overlay_after_apply(self):
        """应用布局后重新显示叠加层"""
        if self._layout:
            try:
                # 从布局中收集图标位置用于熄屏唤醒后恢复
                icon_positions = []
                for cell in self._layout.cells:
                    if cell.icon and not cell.is_header:
                        icon_positions.append({
                            "name": cell.icon.name,
                            "x": cell.pixel_x,
                            "y": cell.pixel_y,
                        })
                show_desktop_overlay(self._layout, self._desktop_info.dpi_scale, root=self, icon_positions=icon_positions)
                self._overlay_shown = True
                self._update_overlay_buttons()
            except Exception:
                self._overlay_shown = False
                self._update_overlay_buttons()

    def _regenerate_layout(self):
        """重新生成布局"""
        if not self._classified:
            messagebox.showinfo("提示", "请先分类图标")
            return

        self._generate_and_show_layout()
        self._set_status("布局已重新生成")

    def _toggle_autostart(self):
        """切换开机自启动"""
        if self._autostart_var.get():
            if enable_autostart():
                self._set_status("已启用开机自启动")
            else:
                self._autostart_var.set(False)
                messagebox.showerror("错误", "启用开机自启动失败")
        else:
            if disable_autostart():
                self._set_status("已禁用开机自启动")
            else:
                self._autostart_var.set(True)
                messagebox.showerror("错误", "禁用开机自启动失败")

    def _save_persistent_layout(self):
        """保存持久化布局（开机后自动恢复）"""
        if not self._layout:
            messagebox.showinfo("提示", "请先生成布局")
            return

        # 收集图标位置
        icon_positions = []
        for icon in self._icons:
            icon_positions.append({
                "name": icon.name,
                "x": icon.x,
                "y": icon.y,
            })

        # 保存持久化布局
        if save_persistent_layout(self._layout, self._desktop_info.dpi_scale, icon_positions):
            self._set_status("持久化布局已保存 | 开机后将自动恢复")
            messagebox.showinfo("成功", "持久化布局已保存！\n\n开机后将自动恢复叠加层和图标位置。")
        else:
            messagebox.showerror("错误", "保存持久化布局失败")

    def _clear_persistent_layout(self):
        """清除持久化布局"""
        if not has_persistent_layout():
            messagebox.showinfo("提示", "没有保存的持久化布局")
            return

        if messagebox.askyesno("确认", "确定要清除持久化布局吗？\n\n清除后开机将不再自动恢复叠加层。"):
            clear_persistent_layout()
            self._set_status("已清除持久化布局")
            messagebox.showinfo("成功", "持久化布局已清除")

    def _check_overlay_state(self):
        """启动时检测是否有叠加层进程正在运行，同步按钮状态"""
        try:
            running = is_overlay_running()
            self._overlay_shown = running
            print(f"[Main] 叠加层状态检测: running={running}")
        except Exception as e:
            print(f"[Main] 叠加层检测异常: {e}")
            self._overlay_shown = False
        self._update_overlay_buttons()

    def _update_overlay_buttons(self):
        """根据当前叠加层状态更新按钮可用性"""
        if self._overlay_shown:
            self._show_overlay_btn.configure(state="disabled", fg_color="#333355")
            self._hide_overlay_btn.configure(state="normal", fg_color=COLORS["card"])
        else:
            self._show_overlay_btn.configure(state="normal", fg_color=COLORS["card"])
            self._hide_overlay_btn.configure(state="normal", fg_color=COLORS["card"])

    def _show_overlay(self):
        """显示桌面叠加层"""
        if not self._layout:
            messagebox.showinfo("提示", "请先分类图标生成布局")
            return
        self._set_status("正在显示边框...")
        self.update_idletasks()
        try:
            # 收集图标位置用于熄屏唤醒后恢复
            icon_positions = []
            if self._icons:
                for icon in self._icons:
                    icon_positions.append({
                        "name": icon.name,
                        "x": icon.x,
                        "y": icon.y,
                    })
            show_desktop_overlay(self._layout, self._desktop_info.dpi_scale, root=self, icon_positions=icon_positions)
            self._overlay_shown = True
            self._update_overlay_buttons()
            self._set_status("桌面边框已显示")
        except Exception as e:
            self._overlay_shown = False
            self._on_error(f"显示边框失败:\n{e}")

    def _hide_overlay(self):
        """隐藏桌面叠加层"""
        hide_desktop_overlay()
        self._overlay_shown = False
        self._update_overlay_buttons()
        self._set_status("桌面边框已隐藏")

    def _backup_desktop(self):
        """备份当前桌面布局"""
        if not self._icons:
            # 即使没有扫描过也尝试备份
            self._set_status("正在备份桌面...")
            def worker():
                try:
                    icons = scan_all_icons(extract_images=False)
                    self._icons = icons
                    filepath = backup_current_layout(icons)
                    self.after(0, lambda: self._set_status(f"备份完成 | {filepath}"))
                    self.after(0, lambda: messagebox.showinfo("成功", f"桌面布局已备份！\n{filepath}"))
                except Exception as e:
                    self.after(0, lambda: self._on_error(f"备份失败: {e}"))
            threading.Thread(target=worker, daemon=True).start()
            return

        filepath = backup_current_layout(self._icons)
        self._set_status(f"备份完成 | {filepath}")
        messagebox.showinfo("成功", f"桌面布局已备份！\n{filepath}")

    def _restore_desktop(self):
        """还原桌面布局"""
        backups = list_backups()
        if not backups:
            messagebox.showinfo("提示", "没有找到备份文件")
            return

        # 创建选择对话框
        dialog = ctk.CTkToplevel(self)
        dialog.title("选择要还原的备份")
        dialog.geometry("520x420")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="选择要还原的备份（点击即可还原）",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 8))

        # 备份列表
        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        for b in backups:
            item = ctk.CTkButton(
                list_frame,
                text=f"  {b.get('name', '未命名')}  |  {b.get('icon_count', 0)} 个图标  |  {b.get('timestamp', '')[:19]}",
                font=(FONT_FAMILY, 11),
                text_color=COLORS["text_primary"],
            fg_color=COLORS["card"],
            hover_color=COLORS["accent2"],
            corner_radius=8,
            height=36,
            anchor="w",
            command=lambda fp=b["filepath"], d=dialog: (d.destroy(), self._do_restore(fp)),
            )
            item.pack(fill="x", pady=2)

        ctk.CTkButton(
            dialog, text="取消", command=dialog.destroy,
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
        ).pack(pady=12)

    def _do_restore(self, filepath: str):
        """执行还原"""
        icons_data = load_backup(filepath)
        if not icons_data:
            messagebox.showerror("错误", "无法加载备份文件")
            return

        self._set_status("正在还原桌面布局...")

        def worker():
            try:
                # 重新扫描桌面以获取最新的index映射
                current_icons = scan_all_icons(extract_images=False)

                # 建立 名称 -> 当前index 的映射
                name_to_current_index = {}
                for icon in current_icons:
                    name_to_current_index[icon.name] = icon.index

                # 根据备份中的名称匹配当前index，应用位置
                applied = 0
                hwnd = None
                for d in icons_data:
                    name = d.get("name", "")
                    x, y = d["x"], d["y"]

                    if name in name_to_current_index:
                        idx = name_to_current_index[name]
                        if hwnd is None:
                            from desktop_scanner import find_desktop_listview, set_icon_position
                            hwnd = find_desktop_listview()
                            if not hwnd:
                                raise RuntimeError("无法找到桌面 ListView 窗口")
                        set_icon_position(hwnd, idx, x, y)
                        applied += 1

                self.after(0, lambda: self._set_status(f"还原完成 | 成功还原 {applied} 个图标"))
                self.after(0, lambda: messagebox.showinfo("成功", f"桌面布局已还原！\n成功还原 {applied} 个图标。"))
            except Exception as e:
                self.after(0, lambda: self._on_error(f"还原失败: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _save_layout_dialog(self):
        """保存布局对话框"""
        if not self._classified:
            messagebox.showinfo("提示", "没有可保存的布局")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("保存布局方案")
        dialog.geometry("400x200")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="输入布局方案名称",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(20, 10))

        name_entry = ctk.CTkEntry(
            dialog, width=300, height=40,
            font=(FONT_FAMILY, 12),
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="例如：我的整理方案",
        )
        name_entry.pack(pady=8)
        name_entry.focus_set()

        def do_save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入名称", parent=dialog)
                return
            filepath = save_layout(self._icons, self._classified, name)
            dialog.destroy()
            self._set_status(f"布局已保存 | {filepath}")
            messagebox.showinfo("成功", f"布局方案「{name}」已保存！\n{filepath}")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=16)

        ctk.CTkButton(
            btn_frame, text="取消", command=dialog.destroy,
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"], corner_radius=8,
        ).pack(side="right", padx=8)

        ctk.CTkButton(
            btn_frame, text="保存", command=do_save,
            fg_color=COLORS["accent2"], corner_radius=8,
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="right", padx=8)

    def _load_layout_dialog(self):
        """加载布局对话框"""
        layouts = list_layouts()
        if not layouts:
            messagebox.showinfo("提示", "没有已保存的布局方案")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("加载布局方案")
        dialog.geometry("500x400")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="选择要加载的布局方案",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 8))

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        selected = [None]

        for l in layouts:
            item = ctk.CTkFrame(list_frame, corner_radius=8, fg_color=COLORS["card"])
            item.pack(fill="x", pady=2)

            name_text = l.get("name", "未命名")
            time_text = l.get("timestamp", "")[:19]
            cats = ", ".join(l.get("categories", [])[:4])

            ctk.CTkLabel(
                item,
                text=f"  {name_text}  |  {cats}  |  {time_text}",
                font=(FONT_FAMILY, 11),
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(fill="x", padx=8, pady=8)

            def select(fp=l["filepath"]):
                selected[0] = fp
                dialog.destroy()

            item.bind("<Button-1>", lambda e, fp=l["filepath"]: select(fp))

        def do_load():
            fp = selected[0]
            dialog.destroy()
            if not fp:
                return
            self._do_load_layout(fp)

        ctk.CTkButton(
            dialog, text="取消", command=dialog.destroy,
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"], corner_radius=8,
        ).pack(side="right", padx=16, pady=12)

        ctk.CTkButton(
            dialog, text="加载", command=do_load,
            fg_color=COLORS["accent2"], corner_radius=8,
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="right", padx=4, pady=12)

    def _do_load_layout(self, filepath: str):
        """执行加载布局"""
        data = load_layout(filepath)
        if not data:
            messagebox.showerror("错误", "无法加载布局文件")
            return

        categories = data.get("categories", {})
        icon_info = data.get("icon_info", {})

        # 根据加载的分类重建 classified 字典
        self._classified = {}
        for cat, icon_names in categories.items():
            icons_in_cat = []
            for name in icon_names:
                icon = self._find_icon_by_name(name)
                if icon:
                    info = icon_info.get(name, {})
                    icon.category = info.get("category", cat)
                    icons_in_cat.append(icon)
            if icons_in_cat:
                self._classified[cat] = icons_in_cat

        self._generate_and_show_layout()
        self._update_category_cards()
        self._set_status(f"布局已加载 | {filepath}")

    def _show_backup_list(self):
        """显示备份列表"""
        backups = list_backups()
        if not backups:
            messagebox.showinfo("备份管理", "没有备份记录")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("备份列表")
        dialog.geometry("600x450")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="备份列表",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 8))

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        for b in backups:
            item_frame = ctk.CTkFrame(list_frame, corner_radius=8, fg_color=COLORS["card"])
            item_frame.pack(fill="x", pady=2)

            info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=8, pady=6)

            ctk.CTkLabel(
                info_frame,
                text=f"{b.get('name', '未命名')}  ({b.get('icon_count', 0)} 个图标)",
                font=(FONT_FAMILY, 11, "bold"),
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(fill="x")

            ctk.CTkLabel(
                info_frame,
                text=f"  {b.get('timestamp', '')[:19]}  |  {os.path.basename(b.get('filepath', ''))}",
                font=(FONT_FAMILY, 9),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(fill="x")

            def delete_b(fp=b["filepath"], item=item_frame):
                if messagebox.askyesno("确认删除", "确定要删除此备份吗？", parent=dialog):
                    delete_backup(fp)
                    item.destroy()

            ctk.CTkButton(
                item_frame, text="删除", width=50, height=28,
                fg_color=COLORS["danger"], corner_radius=6,
                font=(FONT_FAMILY, 10),
                command=delete_b,
            ).pack(side="right", padx=8)

    def _show_layout_list(self):
        """显示布局列表"""
        layouts = list_layouts()
        if not layouts:
            messagebox.showinfo("布局管理", "没有已保存的布局方案")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("布局方案列表")
        dialog.geometry("600x450")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="布局方案列表",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 8))

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        for l in layouts:
            item_frame = ctk.CTkFrame(list_frame, corner_radius=8, fg_color=COLORS["card"])
            item_frame.pack(fill="x", pady=2)

            info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=8, pady=6)

            ctk.CTkLabel(
                info_frame,
                text=l.get("name", "未命名"),
                font=(FONT_FAMILY, 11, "bold"),
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(fill="x")

            cats = ", ".join(l.get("categories", [])[:5])
            ctk.CTkLabel(
                info_frame,
                text=f"  类别: {cats}  |  {l.get('timestamp', '')[:19]}",
                font=(FONT_FAMILY, 9),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(fill="x")

            def delete_l(fp=l["filepath"], item=item_frame):
                if messagebox.askyesno("确认删除", "确定要删除此布局方案吗？", parent=dialog):
                    delete_layout(fp)
                    item.destroy()

            def load_l(fp=l["filepath"]):
                dialog.destroy()
                self._do_load_layout(fp)

            btn_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=8)

            ctk.CTkButton(
                btn_frame, text="加载", width=50, height=28,
                fg_color=COLORS["accent2"], corner_radius=6,
                font=(FONT_FAMILY, 10),
                command=load_l,
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                btn_frame, text="删除", width=50, height=28,
                fg_color=COLORS["danger"], corner_radius=6,
                font=(FONT_FAMILY, 10),
                command=delete_l,
            ).pack(side="right", padx=2)

    def _zoom_in(self):
        """放大预览"""
        self._zoom_level = min(self._zoom_level + 0.1, 2.0)
        self._zoom_label.configure(text=f"{int(self._zoom_level * 100)}%")
        if self._layout:
            self._preview_canvas.set_layout(self._layout, self._desktop_w, self._desktop_h, self._zoom_level)

    def _zoom_out(self):
        """缩小预览"""
        self._zoom_level = max(self._zoom_level - 0.1, 0.3)
        self._zoom_label.configure(text=f"{int(self._zoom_level * 100)}%")
        if self._layout:
            self._preview_canvas.set_layout(self._layout, self._desktop_w, self._desktop_h, self._zoom_level)

    def _on_error(self, msg: str):
        """错误处理（可复制文本框）"""
        import traceback
        full_msg = msg + "\n\n" + traceback.format_exc()
        self._set_status(f"错误 | {msg}")
        self._set_progress(0)

        dialog = ctk.CTkToplevel(self)
        dialog.title("错误")
        dialog.geometry("600x350")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="发生错误（可选中复制）",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["danger"],
        ).pack(pady=(12, 4))

        text_box = ctk.CTkTextbox(
            dialog, width=560, height=220,
            font=("Consolas", 11),
            fg_color=COLORS["card"],
            text_color=COLORS["text_primary"],
            border_color=COLORS["border"],
            border_width=1,
        )
        text_box.pack(padx=16, pady=8)
        text_box.insert("1.0", full_msg)

        ctk.CTkButton(
            dialog, text="关闭", command=dialog.destroy,
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"], corner_radius=8,
        ).pack(pady=8)

    def _on_closing(self):
        """窗口关闭时保留叠加层继续运行"""
        # 叠加层保持显示，不关闭子进程
        self.destroy()


# ===================== 入口 =====================

if __name__ == "__main__":
    # 支持 --overlay 参数，用于 PyInstaller 打包后的子进程模式
    if len(sys.argv) > 1 and sys.argv[1] == "--overlay":
        import overlay_process
        overlay_process.main()
        sys.exit(0)

    # 支持 --autostart 参数，用于开机自启动显示叠加层
    if len(sys.argv) > 1 and sys.argv[1] == "--autostart":
        import overlay_process
        overlay_process.main()
        sys.exit(0)

    app = MainApp()
    app.mainloop()
