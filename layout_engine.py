"""
布局引擎模块
负责将分类后的图标按照网格分区布局（竖向分区）
每个图标分配独立 cell，类别间有分隔，确保无堆叠
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from desktop_scanner import DesktopIcon
from icon_classifier import CATEGORIES


@dataclass
class Cell:
    """网格单元"""
    grid_x: int       # 网格列号（像素坐标）
    grid_y: int       # 网格行号（像素坐标）
    pixel_x: int = 0  # 实际像素X（绝对位置）
    pixel_y: int = 0  # 实际像素Y（绝对位置）
    icon: Optional[DesktopIcon] = None
    category: str = ""
    is_header: bool = False
    header_text: str = ""


@dataclass
class CategoryLayout:
    """单个类别的布局信息"""
    category: str
    icons: List[DesktopIcon]
    start_x: int      # 该类别起始像素X
    end_x: int        # 该类别结束像素X
    columns: int
    column_width: int
    row_height: int
    padding_left: int
    padding_right: int


@dataclass
class DesktopLayout:
    """完整的桌面布局"""
    total_width: int
    total_height: int
    cell_width: int
    cell_height: int
    category_layouts: List[CategoryLayout]
    cells: List[Cell] = field(default_factory=list)
    icon_positions: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # icon_name -> (x, y)


# ===================== 默认参数 =====================

DEFAULT_CELL_WIDTH = 82     # 图标单元宽度
DEFAULT_CELL_HEIGHT = 96    # 图标单元高度（含标签）
CATEGORY_HEADER_HEIGHT = 30  # 分类标题高度（像素）
CATEGORY_GAP = 10           # 类别之间的间距（像素）
GRID_MARGIN_X = 12          # 网格左边距
GRID_MARGIN_Y = 12          # 网格上边距
ICON_SIZE = 48              # 图标图像大小
LABEL_HEIGHT = 20           # 标签高度


def calculate_layout(
    classified: Dict[str, List[DesktopIcon]],
    desktop_width: int,
    desktop_height: int,
    cell_width: int = DEFAULT_CELL_WIDTH,
    cell_height: int = DEFAULT_CELL_HEIGHT,
    category_order: Optional[List[str]] = None,
) -> DesktopLayout:
    """
    计算分类后的桌面布局 —— 竖向分区

    策略:
    1. 类别从左到右竖向排列
    2. 每个类别占一列或多列，宽度按图标数量比例分配
    3. 所有类别占满整个桌面宽度
    4. 每个图标有固定 cell，互不重叠
    """
    if not classified:
        return DesktopLayout(
            total_width=desktop_width, total_height=desktop_height,
            cell_width=cell_width, cell_height=cell_height, category_layouts=[]
        )

    # 确定类别顺序
    if category_order is None:
        category_order = [cat for cat in CATEGORIES if cat in classified]
        for cat in classified:
            if cat not in category_order:
                category_order.append(cat)

    # 过滤空类别
    active_categories = [(cat, classified[cat]) for cat in category_order if classified.get(cat)]

    if not active_categories:
        return DesktopLayout(
            total_width=desktop_width, total_height=desktop_height,
            cell_width=cell_width, cell_height=cell_height, category_layouts=[]
        )

    usable_width = desktop_width - 2 * GRID_MARGIN_X
    cat_count = len(active_categories)

    # 计算每个类别的列数 —— 按图标数量比例分配宽度
    cat_col_counts = []
    for cat_name, icons in active_categories:
        icon_count = len(icons)
        # 该类别至少需要的列数
        min_cols = max(1, math.ceil(math.sqrt(icon_count)))
        cat_col_counts.append(min_cols)

    total_requested_cols = sum(cat_col_counts)
    max_total_cols = usable_width // cell_width

    if total_requested_cols > max_total_cols:
        # 需要压缩：按比例缩减
        scale = max_total_cols / total_requested_cols
        cat_col_counts = [max(1, math.ceil(c * scale)) for c in cat_col_counts]
        # 确保总列数不超过上限
        while sum(cat_col_counts) > max_total_cols and max(cat_col_counts) > 1:
            max_idx = cat_col_counts.index(max(cat_col_counts))
            cat_col_counts[max_idx] -= 1
    else:
        # 有余量：优先分给图标多的类别
        remaining = max_total_cols - total_requested_cols
        # 按图标数量从大到小分配额外列
        sorted_indices = sorted(range(cat_count), key=lambda i: len(active_categories[i][1]), reverse=True)
        for idx in sorted_indices:
            if remaining <= 0:
                break
            icon_count = len(active_categories[idx][1])
            max_cols_for_cat = max(1, usable_width // cell_width)
            if cat_col_counts[idx] < max_cols_for_cat:
                cat_col_counts[idx] += 1
                remaining -= 1

    # 加上类别间距
    total_gaps = (cat_count - 1) * CATEGORY_GAP
    available_for_cells = usable_width - total_gaps

    # 按列数比例分配像素宽度
    total_cols = sum(cat_col_counts)
    if total_cols == 0:
        total_cols = 1

    all_cells = []
    all_icon_positions = []
    category_layouts = []

    current_x = GRID_MARGIN_X

    for i, (cat_name, icons) in enumerate(active_categories):
        cols = cat_col_counts[i]
        icon_count = len(icons)

        # 该类别的像素宽度
        cat_pixel_width = int(available_for_cells * cols / total_cols)
        # 最后一个类别取剩余宽度
        if i == cat_count - 1:
            cat_pixel_width = usable_width - (current_x - GRID_MARGIN_X)

        # 每列的实际宽度
        col_width = cat_pixel_width // cols
        # 每行高度
        rows_needed = math.ceil(icon_count / cols) if cols > 0 else 1

        # 创建标题
        header_y = GRID_MARGIN_Y
        header_cell = Cell(
            grid_x=i, grid_y=0,
            pixel_x=current_x, pixel_y=header_y,
            category=cat_name,
            is_header=True,
            header_text=cat_name,
        )
        all_cells.append(header_cell)

        # 图标起始Y（标题下方）
        icon_start_y = header_y + CATEGORY_HEADER_HEIGHT

        # 创建图标 cells
        icon_index = 0
        for row_i in range(rows_needed):
            for col_i in range(cols):
                if icon_index >= icon_count:
                    break

                icon = icons[icon_index]
                px = current_x + col_i * col_width
                py = icon_start_y + row_i * cell_height

                cell = Cell(
                    grid_x=i,
                    grid_y=row_i + 1,
                    pixel_x=px,
                    pixel_y=py,
                    icon=icon,
                    category=cat_name,
                )
                all_cells.append(cell)
                # 记录图标像素位置（图标在cell内居中）
                icon_px = px + (col_width - ICON_SIZE) // 2
                icon_py = py + 4
                all_icon_positions.append((icon.index, icon_px, icon_py))

                icon_index += 1
            if icon_index >= icon_count:
                break

        cat_layout = CategoryLayout(
            category=cat_name,
            icons=icons,
            start_x=current_x,
            end_x=current_x + cat_pixel_width,
            columns=cols,
            column_width=col_width,
            row_height=cell_height,
            padding_left=current_x,
            padding_right=current_x + cat_pixel_width,
        )
        category_layouts.append(cat_layout)

        # 移到下一个类别
        current_x += cat_pixel_width + CATEGORY_GAP

    total_w = current_x - CATEGORY_GAP + GRID_MARGIN_X
    max_cat_height = max(
        GRID_MARGIN_Y + CATEGORY_HEADER_HEIGHT +
        math.ceil(len(icons) / cat_col_counts[i]) * cell_height
        for i, (_, icons) in enumerate(active_categories)
    ) if active_categories else desktop_height

    layout = DesktopLayout(
        total_width=total_w,
        total_height=max_cat_height,
        cell_width=cell_width,
        cell_height=cell_height,
        category_layouts=category_layouts,
        cells=all_cells,
        icon_positions={},
    )

    # 构建 icon_name -> (x, y) 映射（用于预览定位）
    for cell in layout.cells:
        if cell.icon and not cell.is_header:
            icon_px = cell.pixel_x + (cell_width // 2)  # 简化：cell中心
            icon_py = cell.pixel_y + (cell_height // 2)
            layout.icon_positions[cell.icon.name] = (cell.pixel_x, cell.pixel_y)

    return layout


def get_cell_pixel_position(cell: Cell, layout: DesktopLayout) -> Tuple[int, int]:
    """获取 cell 的像素位置"""
    return cell.pixel_x, cell.pixel_y


def get_header_pixel_position(cell: Cell, layout: DesktopLayout) -> Tuple[int, int]:
    """获取标题 cell 的像素位置"""
    return cell.pixel_x, cell.pixel_y


def layout_to_icon_list(layout: DesktopLayout) -> List[Tuple[str, int, int]]:
    """
    将布局转换为图标位置列表
    返回: [(icon_name, new_x, new_y), ...]
    使用图标名称而非索引，确保桌面变化后仍能正确匹配
    坐标为物理像素，每个图标有独立 cell，位置互不重叠
    """
    positions = []
    for cell in layout.cells:
        if cell.icon and not cell.is_header:
            # 图标在 cell 内水平居中，垂直偏移少量
            offset_x = layout.cell_width // 4
            offset_y = max(2, layout.cell_height // 10)
            px = cell.pixel_x + offset_x
            py = cell.pixel_y + offset_y
            positions.append((cell.icon.name, px, py))
    return positions


def calculate_preview_scale(
    layout: DesktopLayout,
    canvas_width: int,
    canvas_height: int,
) -> float:
    """计算预览缩放比例"""
    total_width = layout.total_width
    total_height = layout.total_height

    if total_width <= 0 or total_height <= 0:
        return 1.0

    scale_x = canvas_width / total_width
    scale_y = canvas_height / total_height
    return min(scale_x, scale_y, 1.0)  # 不放大


if __name__ == "__main__":
    from desktop_scanner import DesktopIcon

    test_icons = {
        "浏览器": [
            DesktopIcon(0, "Chrome", 0, 0),
            DesktopIcon(1, "Firefox", 0, 0),
            DesktopIcon(2, "Edge", 0, 0),
        ],
        "办公套件": [
            DesktopIcon(3, "Word", 0, 0),
            DesktopIcon(4, "Excel", 0, 0),
            DesktopIcon(5, "PowerPoint", 0, 0),
            DesktopIcon(6, "Outlook", 0, 0),
            DesktopIcon(7, "OneNote", 0, 0),
        ],
        "开发工具": [
            DesktopIcon(8, "VSCode", 0, 0),
            DesktopIcon(9, "Python", 0, 0),
            DesktopIcon(10, "Git", 0, 0),
            DesktopIcon(11, "Docker", 0, 0),
            DesktopIcon(12, "Terminal", 0, 0),
            DesktopIcon(13, "IntelliJ", 0, 0),
        ],
        "其他": [
            DesktopIcon(14, "Unknown", 0, 0),
        ],
    }

    layout = calculate_layout(test_icons, 1920, 1080)
    positions = layout_to_icon_list(layout)

    print(f"布局尺寸: {layout.total_width} x {layout.total_height}")
    print(f"共 {len(layout.cells)} 个 cells, {len(positions)} 个图标位置")
    for cl in layout.category_layouts:
        print(f"[{cl.category}] 列{cl.start_x}-{cl.end_x}, {cl.columns}列, {len(cl.icons)}个图标")
    for idx, x, y in positions:
        print(f"  icon[{idx}] -> ({x}, {y})")
