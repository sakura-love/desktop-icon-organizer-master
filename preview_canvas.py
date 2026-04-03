"""
预览画布模块
支持拖拽图标、竖向分区显示、缩放
"""

import tkinter as tk
from typing import Callable, List, Optional

from layout_engine import (
    GRID_MARGIN_Y,
    ICON_SIZE,
    CATEGORY_HEADER_HEIGHT,
    DesktopLayout,
    Cell,
)
from icon_classifier import CATEGORY_COLORS


class PreviewCanvas(tk.Canvas):
    """桌面布局预览画布，支持拖拽"""

    def __init__(
        self,
        parent,
        *args,
        on_icon_dragged: Optional[Callable] = None,
        on_icon_selected: Optional[Callable] = None,
        **kwargs,
    ):
        bg_color = kwargs.pop('bg', '#202020')
        super().__init__(parent, *args, bg=bg_color, highlightthickness=0, **kwargs)

        self.on_icon_dragged = on_icon_dragged
        self.on_icon_selected = on_icon_selected

        self._layout: Optional[DesktopLayout] = None
        self._raw_icons = None  # 原始扫描图标（用于初始预览）
        self._scale: float = 1.0
        self._offset_x: float = 0
        self._offset_y: float = 0
        self._desktop_w: int = 0
        self._desktop_h: int = 0
        self._user_zoom: float = 1.0

        # 拖拽状态
        self._dragging: bool = False
        self._drag_icon_name: str = ""
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._drag_ghost_ids: List[int] = []

        # 选中状态
        self._selected_icon: Optional[str] = None

        # 绑定事件
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)

        # 颜色
        self._bg_color = "#202020"
        self._grid_color = "#2a2a2a"
        self._header_bg = "#181818"
        self._cell_selected_bg = "#3d5afe"
        self._text_color = "#e0e0e0"
        self._subtext_color = "#888888"

    def set_layout(self, layout: DesktopLayout, desktop_w: int = 0, desktop_h: int = 0, zoom: float = 1.0):
        """设置分类布局并渲染"""
        self._layout = layout
        self._raw_icons = None
        if desktop_w > 0:
            self._desktop_w = desktop_w
        if desktop_h > 0:
            self._desktop_h = desktop_h
        self._user_zoom = zoom
        self._render()

    def set_raw_icons(self, icons, desktop_w: int, desktop_h: int):
        """设置原始桌面图标（未分类时显示当前桌面布局）"""
        self._raw_icons = icons
        self._raw_desktop_w = desktop_w
        self._raw_desktop_h = desktop_h
        self._layout = None
        self._render_raw()

    def _on_configure(self, event):
        """窗口大小变化时重新渲染"""
        if self._layout:
            self.after(50, self._render)
        elif self._raw_icons:
            self.after(50, self._render_raw)

    def _render_raw(self):
        """渲染原始桌面布局预览"""
        if not self._raw_icons:
            return

        self.delete("all")

        cw = self.winfo_width() or 800
        ch = self.winfo_height() or 600

        dw = self._raw_desktop_w
        dh = self._raw_desktop_h

        if dw <= 0 or dh <= 0:
            return

        scale_x = (cw - 10) / dw
        scale_y = (ch - 10) / dh
        s = min(scale_x, scale_y)

        self._scale = s
        self._offset_x = (cw - dw * s) / 2
        self._offset_y = (ch - dh * s) / 2
        offset_x, offset_y = self._offset_x, self._offset_y

        # 桌面背景
        self.create_rectangle(
            offset_x, offset_y, offset_x + dw * s, offset_y + dh * s,
            fill=self._bg_color, outline="#333333", width=1, tags="bg"
        )

        # 绘制图标
        for icon in self._raw_icons:
            ix = offset_x + icon.x * s
            iy = offset_y + icon.y * s

            # 简单的图标占位
            icon_size = int(ICON_SIZE * s)
            self.create_rectangle(
                ix, iy, ix + icon_size, iy + icon_size,
                fill="#2d2d2d", outline="#444444", width=1,
                tags=("raw_icon", f"raw_{icon.index}")
            )

            # 首字母
            font_size = max(5, int(12 * s))
            initial = icon.name[0].upper() if icon.name else "?"
            self.create_text(
                ix + icon_size / 2, iy + icon_size / 2,
                text=initial, fill="#aaaaaa",
                font=("Microsoft YaHei UI", font_size, "bold"),
                tags=("raw_icon", f"raw_{icon.index}")
            )

            # 名称
            name_size = max(5, int(8 * s))
            max_chars = max(3, int(icon_size / (name_size * 0.55)))
            display_name = icon.name
            if len(display_name) > max_chars:
                display_name = display_name[:max_chars - 1] + "…"

            self.create_text(
                ix + icon_size / 2, iy + icon_size + 2,
                text=display_name, fill="#aaaaaa",
                font=("Microsoft YaHei UI", name_size),
                anchor="n",
                tags=("raw_icon", f"raw_{icon.index}")
            )

    def _render(self):
        """渲染分类后的布局预览（以完整桌面为基准等比缩放居中）"""
        if not self._layout:
            return

        self.delete("all")

        cw = self.winfo_width() or 800
        ch = self.winfo_height() or 600

        # 以完整桌面尺寸为基准计算缩放，充分利用画布
        dw = self._desktop_w or self._layout.total_width
        dh = self._desktop_h or self._layout.total_height
        if dw <= 0 or dh <= 0:
            dw = self._layout.total_width
            dh = self._layout.total_height

        pad = 10
        scale_x = (cw - pad * 2) / dw
        scale_y = (ch - pad * 2) / dh
        self._scale = min(scale_x, scale_y) * self._user_zoom
        s = self._scale

        # 居中偏移
        self._offset_x = (cw - dw * s) / 2
        self._offset_y = (ch - dh * s) / 2
        ox, oy = self._offset_x, self._offset_y

        # 完整桌面背景
        self.create_rectangle(
            ox, oy, ox + dw * s, oy + dh * s,
            fill=self._bg_color, outline="#333333", width=1, tags="bg"
        )

        # 绘制类别标题和图标
        self._draw_category_headers(s)
        self._draw_icons(s)

    def _draw_category_headers(self, s: float):
        """绘制分类标题（竖向分区的列标题）"""
        if not self._layout:
            return

        ox, oy = self._offset_x, self._offset_y

        for cat_layout in self._layout.category_layouts:
            cat = cat_layout.category
            color = CATEGORY_COLORS.get(cat, "#666666")

            x1 = ox + cat_layout.start_x * s
            x2 = ox + cat_layout.end_x * s
            y1 = oy + GRID_MARGIN_Y * s
            y2 = oy + (GRID_MARGIN_Y + CATEGORY_HEADER_HEIGHT) * s

            self.create_rectangle(
                x1, y1, x2, y2,
                fill=self._header_bg, outline="", tags="header_bg"
            )

            self.create_rectangle(
                x1, y1, x2, y1 + 3 * s,
                fill=color, outline="", tags="header_bar"
            )

            font_size = max(7, int(10 * s))
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            self.create_text(
                cx, cy,
                text=f"{cat} ({len(cat_layout.icons)})",
                fill=color,
                font=("Microsoft YaHei UI", font_size, "bold"),
                tags="header_text",
            )

    def _draw_icons(self, s: float):
        """绘制图标"""
        if not self._layout:
            return

        ox, oy = self._offset_x, self._offset_y

        for cell in self._layout.cells:
            if cell.is_header or not cell.icon:
                continue

            col_width = self._get_cell_width(cell) * s

            cell_x = ox + cell.pixel_x * s
            cell_y = oy + cell.pixel_y * s
            cell_h = self._layout.cell_height * s

            # 选中高亮
            if cell.icon.name == self._selected_icon:
                self.create_rectangle(
                    cell_x, cell_y, cell_x + col_width, cell_y + cell_h,
                    fill=self._cell_selected_bg, outline=self._cell_selected_bg,
                    width=1, tags=("icon_bg", f"icon_{cell.icon.name}")
                )

            # 图标图像
            icon_cx = cell_x + col_width / 2
            icon_cy = cell_y + (ICON_SIZE * s) / 2 + 2 * s

            if cell.icon.image:
                try:
                    img = cell.icon.image.resize(
                        (int(ICON_SIZE * s), int(ICON_SIZE * s)),
                        resample=3,
                    )
                    self._photo = tk.PhotoImage(img)
                    self.create_image(
                        icon_cx, icon_cy,
                        image=self._photo,
                        tags=("icon_img", f"icon_{cell.icon.name}")
                    )
                except Exception:
                    self._draw_placeholder(icon_cx, icon_cy, cell, s, col_width)
            else:
                self._draw_placeholder(icon_cx, icon_cy, cell, s, col_width)

            # 图标名称标签
            label_y = cell_y + (ICON_SIZE + 6) * s
            font_size = max(6, int(8 * s))
            display_name = cell.icon.name
            max_chars = max(3, int(col_width / (font_size * 0.55)))
            if len(display_name) > max_chars:
                display_name = display_name[:max_chars - 1] + "…"

            self.create_text(
                cell_x + col_width / 2, label_y,
                text=display_name,
                fill=self._text_color,
                font=("Microsoft YaHei UI", font_size),
                anchor="n",
                tags=("icon_label", f"icon_{cell.icon.name}")
            )

    def _draw_placeholder(self, icon_cx, icon_cy, cell, s, col_width):
        """绘制图标占位符"""
        cat_color = CATEGORY_COLORS.get(cell.category, "#666666")
        icon_size = int(ICON_SIZE * s)
        self.create_rectangle(
            icon_cx - icon_size / 2, icon_cy - icon_size / 2,
            icon_cx + icon_size / 2, icon_cy + icon_size / 2,
            fill="#2d2d2d", outline=cat_color, width=1,
            tags=("icon_img", f"icon_{cell.icon.name}")
        )
        font_size = max(5, int(13 * s))
        initial = cell.icon.name[0].upper() if cell.icon.name else "?"
        self.create_text(
            icon_cx, icon_cy,
            text=initial,
            fill=cat_color,
            font=("Microsoft YaHei UI", font_size, "bold"),
            tags=("icon_img", f"icon_{cell.icon.name}")
        )

    def _get_cell_width(self, cell: Cell) -> int:
        """获取cell所在类别的实际列宽"""
        for cl in self._layout.category_layouts:
            if cl.category == cell.category:
                return cl.column_width
        return self._layout.cell_width

    def _find_icon_at(self, x: int, y: int) -> Optional[str]:
        """查找鼠标位置下的图标名称"""
        if not self._layout:
            return None

        ox, oy = self._offset_x, self._offset_y
        s = self._scale
        for cell in self._layout.cells:
            if cell.is_header or not cell.icon:
                continue
            col_w = self._get_cell_width(cell) * s
            cx1 = ox + cell.pixel_x * s
            cy1 = oy + cell.pixel_y * s
            cx2 = cx1 + col_w
            cy2 = cy1 + self._layout.cell_height * s
            if cx1 <= x <= cx2 and cy1 <= y <= cy2:
                return cell.icon.name
        return None

    def _on_press(self, event):
        """鼠标按下"""
        icon_name = self._find_icon_at(event.x, event.y)
        if icon_name:
            self._dragging = True
            self._drag_icon_name = icon_name
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            self._selected_icon = icon_name
            self._render()
            if self.on_icon_selected:
                self.on_icon_selected(icon_name)
        else:
            self._selected_icon = None
            self._dragging = False
            self._render()
            if self.on_icon_selected:
                self.on_icon_selected(None)

    def _on_motion(self, event):
        """鼠标拖动"""
        if not self._dragging or not self._layout:
            return

        for gid in self._drag_ghost_ids:
            self.delete(gid)
        self._drag_ghost_ids.clear()

        s = self._scale
        col_w = self._layout.cell_width * s
        cell_h = self._layout.cell_height * s
        gx = event.x - col_w / 2
        gy = event.y - cell_h / 2
        gid = self.create_rectangle(
            gx, gy, gx + col_w, gy + cell_h,
            fill="", outline=self._cell_selected_bg, width=2, dash=(4, 4)
        )
        self._drag_ghost_ids.append(gid)

    def _on_release(self, event):
        """鼠标释放"""
        if not self._dragging:
            return

        for gid in self._drag_ghost_ids:
            self.delete(gid)
        self._drag_ghost_ids.clear()

        target_icon = self._find_icon_at(event.x, event.y)
        if target_icon and target_icon != self._drag_icon_name:
            if self.on_icon_dragged:
                self.on_icon_dragged(self._drag_icon_name, target_icon)

        self._dragging = False
        self._render()

    def update_layout(self, layout: DesktopLayout):
        """更新布局"""
        self._layout = layout
        self._render()

    def select_icon(self, icon_name: Optional[str]):
        """选中指定图标"""
        self._selected_icon = icon_name
        self._render()


class DragDropPreviewCanvas(PreviewCanvas):
    """增强版预览画布"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._swap_mode = True

    def set_swap_mode(self, enabled: bool):
        self._swap_mode = enabled

    def _on_release(self, event):
        if not self._dragging:
            return

        for gid in self._drag_ghost_ids:
            self.delete(gid)
        self._drag_ghost_ids.clear()

        if self._swap_mode:
            target_icon = self._find_icon_at(event.x, event.y)
            if target_icon and target_icon != self._drag_icon_name:
                if self.on_icon_dragged:
                    self.on_icon_dragged(self._drag_icon_name, target_icon)

        self._dragging = False
        self._render()
