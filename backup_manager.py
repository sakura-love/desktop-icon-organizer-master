"""
备份管理模块
负责桌面图标布局的备份、还原、保存和加载
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from desktop_scanner import DesktopIcon


def get_app_dir():
    """获取应用程序所在目录（兼容打包后的exe）"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe，使用exe所在目录
        return os.path.dirname(sys.executable)
    else:
        # 脚本运行，使用脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))


BACKUP_DIR = os.path.join(get_app_dir(), "backups")
LAYOUT_DIR = os.path.join(get_app_dir(), "layouts")


def ensure_dirs():
    """确保备份和布局目录存在"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(LAYOUT_DIR, exist_ok=True)


def backup_current_layout(icons: List[DesktopIcon], name: Optional[str] = None) -> str:
    """
    备份当前桌面布局
    返回备份文件路径
    """
    ensure_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if name:
        filename = f"backup_{name}_{timestamp}.json"
    else:
        filename = f"backup_{timestamp}.json"

    filepath = os.path.join(BACKUP_DIR, filename)

    data = {
        "type": "backup",
        "name": name or "自动备份",
        "timestamp": datetime.now().isoformat(),
        "icon_count": len(icons),
        "icons": [
            {
                "index": icon.index,
                "name": icon.name,
                "x": icon.x,
                "y": icon.y,
                "target_path": icon.target_path,
            }
            for icon in icons
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def save_layout(
    icons: List[DesktopIcon],
    classified: Dict[str, List[DesktopIcon]],
    name: str,
) -> str:
    """
    保存自定义布局方案
    返回布局文件路径
    """
    ensure_dirs()

    safe_name = "".join(c for c in name if c.isalnum() or c in "_- ")[:50]
    filepath = os.path.join(LAYOUT_DIR, f"layout_{safe_name}.json")

    data = {
        "type": "layout",
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "categories": {
            cat: [icon.name for icon in icon_list]
            for cat, icon_list in classified.items()
        },
        "icon_info": {
            icon.name: {
                "target_path": icon.target_path,
                "category": icon.category,
            }
            for icon in icons
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def load_layout(filepath: str) -> Optional[Dict]:
    """加载布局方案"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_backup(filepath: str) -> Optional[List[Dict]]:
    """加载备份，返回图标位置列表"""
    data = load_layout(filepath)
    if data and data.get("type") == "backup":
        return data.get("icons", [])
    return None


def get_latest_backup() -> Optional[str]:
    """获取最新的备份文件"""
    ensure_dirs()
    backups = sorted(Path(BACKUP_DIR).glob("backup_*.json"), key=os.path.getmtime, reverse=True)
    return str(backups[0]) if backups else None


def list_backups() -> List[Dict]:
    """列出所有备份"""
    ensure_dirs()
    backups = []
    for filepath in sorted(Path(BACKUP_DIR).glob("backup_*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            backups.append({
                "filepath": str(filepath),
                "name": data.get("name", ""),
                "timestamp": data.get("timestamp", ""),
                "icon_count": data.get("icon_count", 0),
            })
        except Exception:
            pass
    return backups


def list_layouts() -> List[Dict]:
    """列出所有已保存的布局"""
    ensure_dirs()
    layouts = []
    for filepath in sorted(Path(LAYOUT_DIR).glob("layout_*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            layouts.append({
                "filepath": str(filepath),
                "name": data.get("name", ""),
                "timestamp": data.get("timestamp", ""),
                "categories": list(data.get("categories", {}).keys()),
            })
        except Exception:
            pass
    return layouts


def delete_backup(filepath: str):
    """删除备份文件"""
    try:
        os.remove(filepath)
    except Exception:
        pass


def delete_layout(filepath: str):
    """删除布局文件"""
    try:
        os.remove(filepath)
    except Exception:
        pass


if __name__ == "__main__":
    # 测试
    print("备份列表:")
    for b in list_backups():
        print(f"  {b['name']} ({b['timestamp']}) - {b['icon_count']} 个图标")

    print("\n布局列表:")
    for l in list_layouts():
        print(f"  {l['name']} ({l['timestamp']}) - 类别: {', '.join(l['categories'][:3])}")
