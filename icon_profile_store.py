"""
Persistent profile storage for desktop icon metadata and category overrides.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from desktop_scanner import DesktopIcon

SCHEMA_VERSION = 1
PROFILE_FILENAME = "icon_profile.json"


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _profile_path() -> str:
    return os.path.join(_app_dir(), PROFILE_FILENAME)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_path(path: str) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(path.strip()))


def build_icon_key(icon: DesktopIcon) -> str:
    normalized_path = _normalize_path(icon.target_path)
    if normalized_path:
        return f"path::{normalized_path}"
    normalized_name = (icon.name or "").strip().lower()
    return f"name::{normalized_name}"


def _default_profile() -> Dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": None,
        "icons": {},
    }


def load_profile() -> Dict:
    filepath = _profile_path()
    if not os.path.exists(filepath):
        return _default_profile()

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _default_profile()

    if not isinstance(data, dict):
        return _default_profile()

    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("updated_at", None)
    if not isinstance(data.get("icons"), dict):
        data["icons"] = {}
    return data


def save_profile(profile: Dict) -> str:
    filepath = _profile_path()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    return filepath


def upsert_scan_icons(icons: List[DesktopIcon]) -> str:
    profile = load_profile()
    entries = profile.setdefault("icons", {})
    now = _now()

    for icon in icons:
        key = build_icon_key(icon)
        entry = entries.get(key, {})
        entry.update(
            {
                "key": key,
                "name": icon.name,
                "target_path": icon.target_path,
                "last_seen_at": now,
                "scan_position": {
                    "index": icon.index,
                    "x": icon.x,
                    "y": icon.y,
                },
            }
        )
        entry.setdefault("manual_category", None)
        entries[key] = entry

    profile["updated_at"] = now
    return save_profile(profile)


def get_manual_overrides(icons: List[DesktopIcon]) -> Dict[str, str]:
    profile = load_profile()
    entries = profile.get("icons", {})
    overrides: Dict[str, str] = {}

    for icon in icons:
        key = build_icon_key(icon)
        entry = entries.get(key)
        if not isinstance(entry, dict):
            continue
        manual_category = entry.get("manual_category")
        if isinstance(manual_category, str) and manual_category:
            overrides[key] = manual_category

    return overrides


def update_classification_snapshot(
    icons: List[DesktopIcon],
    layout_positions: Optional[Dict[str, Tuple[int, int]]] = None,
) -> str:
    profile = load_profile()
    entries = profile.setdefault("icons", {})
    now = _now()

    for icon in icons:
        key = build_icon_key(icon)
        entry = entries.get(key, {})
        entry.update(
            {
                "key": key,
                "name": icon.name,
                "target_path": icon.target_path,
                "category": icon.category,
                "last_seen_at": now,
                "scan_position": {
                    "index": icon.index,
                    "x": icon.x,
                    "y": icon.y,
                },
            }
        )

        if layout_positions and icon.name in layout_positions:
            lx, ly = layout_positions[icon.name]
            entry["layout_position"] = {"x": int(lx), "y": int(ly)}

        entries[key] = entry

    profile["updated_at"] = now
    return save_profile(profile)


def set_manual_category(icon: DesktopIcon, category: str) -> str:
    profile = load_profile()
    entries = profile.setdefault("icons", {})
    now = _now()

    key = build_icon_key(icon)
    entry = entries.get(key, {})
    entry.update(
        {
            "key": key,
            "name": icon.name,
            "target_path": icon.target_path,
            "category": category,
            "manual_category": category,
            "manual_updated_at": now,
            "last_seen_at": now,
            "scan_position": {
                "index": icon.index,
                "x": icon.x,
                "y": icon.y,
            },
        }
    )
    entries[key] = entry
    profile["updated_at"] = now
    return save_profile(profile)

