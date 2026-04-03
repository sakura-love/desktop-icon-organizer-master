"""
图标分类模块
使用本地关键词库 + 联网搜索进行图标分类
"""

import json
import os
import re
from typing import Dict, List, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from desktop_scanner import DesktopIcon


# ===================== 类别定义 =====================

CATEGORIES = [
    "浏览器",
    "办公套件",
    "开发工具",
    "系统工具",
    "媒体播放",
    "社交通讯",
    "图形设计",
    "文件管理",
    "安全工具",
    "游戏娱乐",
    "教育学习",
    "财务工具",
    "网络工具",
    "其他",
]

CATEGORY_COLORS = {
    "浏览器":   "#5B7FA5",
    "办公套件": "#8B7E5A",
    "开发工具": "#5A8B6A",
    "系统工具": "#7A7D82",
    "媒体播放": "#8B5A5A",
    "社交通讯": "#5A7D8B",
    "图形设计": "#8B6B3A",
    "文件管理": "#6A7A85",
    "安全工具": "#7A5A5A",
    "游戏娱乐": "#6A5A7A",
    "教育学习": "#5A8B7A",
    "财务工具": "#8B7A3A",
    "网络工具": "#5A6A8B",
    "其他":     "#757575",
}

# 关键词分类规则
KEYWORD_RULES: Dict[str, List[str]] = {
    "浏览器": [
        "chrome", "firefox", "edge", "opera", "safari", "brave", "vivaldi",
        "tor", "maxthon", "360se", "360chrome", "qq浏览器", "百度浏览器",
        "uc浏览器", "sogou", "搜狗浏览器", "猎豹浏览器", "thunderbird",
        "browser", "navigator", "internet explorer", "ie browser",
    ],
    "办公套件": [
        "word", "excel", "powerpoint", "powerpnt", "ppt", "outlook",
        "onenote", "access", "office", "wps", "wpp", "et", "libreoffice",
        "openoffice", "onlyoffice", "印象笔记", "notion", "obsidian",
        "typora", "markdown", "xmind", "mindmanager", "visio",
        "pdf", "acrobat", "foxit", "福昕", "文档", "表格", "演示",
        "pages", "numbers", "keynote", "roam research",
        "邮箱", "mail", "邮件", "邮箱大师", "flomo", "笔记", "笔记软件",
        "会议", "meeting", "tomeet", "腾讯会议", "zoom", "teams meeting",
    ],
    "开发工具": [
        "python", "pycharm", "vscode", "visual studio code", "code",
        "intellij", "idea", "eclipse", "netbeans", "android studio",
        "xcode", "visual studio", "devenv", "git", "github desktop",
        "sourcetree", "tortoisegit", "tortoisesvn", "svn",
        "docker", "docker desktop", "postman", "insomnia",
        "node", "npm", "yarn", "pip", "conda", "anaconda",
        "mysql", "workbench", "navicat", "dbeaver", "datagrip",
        "redis", "mongodb", "robomongo", "studio 3t",
        "putty", "xshell", "securecrt", "mobaxterm", "termius",
        "cmder", "conemu", "windows terminal", "hyper",
        "sublime", "notepad++", "vim", "neovim", "emacs", "atom",
        "gitkraken", "lazygit", "rider", "clion", "goland",
        "webstorm", "phpstorm", "rust", "cargo", "gradle",
        "maven", "jenkins", "terraform", "kubernetes", "k8s",
        "fiddler", "charles", "wireshark",
        "cursor", "cherry studio", "ai chat", "ollama",
    ],
    "系统工具": [
        "任务管理器", "task manager", "regedit", "注册表", "cmd", "powershell",
        "control", "设置", "settings", "设备管理器", "disk management",
        "磁盘管理", "diskpart", "msconfig", "服务", "services",
        "资源监视器", "resource monitor", "事件查看器", "event viewer",
        "directx", "dxdiag", "system", "系统", "驱动", "driver",
        "cleanup", "磁盘清理", "defrag", "碎片整理",
        "ccleaner", "dism++", "geek uninstaller", "revo uninstaller",
        "everything", "voidtools", "listary", "wox", "utools",
        "火绒安全", "火绒", "软媒", "魔方", "优化大师",
        "清理大师", "清理", "todesk", "向日葵", "sunlogin", "remote",
        "desk", "此电脑", "计算机", "我的电脑", "控制面板", "回收站",
    ],
    "媒体播放": [
        "vlc", "potplayer", "mpv", "mpc", "mpc-hc", "mpc-be",
        "foobar2000", "aimp", "musicbee", "itunes", "spotify",
        "qq音乐", "网易云音乐", "酷狗音乐", "酷我音乐", "apple music",
        "kmplayer", "gom player", "realplayer", "media player",
        "mplayer", "plex", "kodi", "jriver",
        "视频", "音乐", "播放器", "影视", "影音", "猫影视",
        "录屏", "obs studio", "obs", "bandicam", "录屏软件",
        "音乐解锁", "lx music", "音乐工具",
        "audition", "adobe audition",
    ],
    "社交通讯": [
        "wechat", "微信", "weixin", "qq", "tim", "dingtalk", "钉钉",
        "feishu", "飞书", "lark", "welink", "华为会议",
        "skype", "zoom", "discord", "telegram",
        "slack", "whatsapp", "line", "kakao", "viber",
        "微博", "twitter", "tiktok", "douyin", "抖音",
        "bilibili", "哔哩哔哩", "知乎", "豆瓣", "小红书",
        "facebook", "instagram", "snapchat", "linkedin",
        "必剪", "剪映", "capcut",
    ],
    "图形设计": [
        "photoshop", "ps ", "illustrator", "ai ", "indesign", "id ",
        "lightroom", "lr ", "premiere", "pr ", "after effects", "ae ",
        "figma", "sketch", "adobe xd", "axure", "mockplus",
        "gimp", "krita", "paint.net", "clip studio", "csp",
        "blender", "cinema 4d", "c4d", "maya", "3ds max", "zbrush",
        "coreldraw", "cdr", "affinity", "procreate",
        "canva", "design", "设计", "绘图", "修图",
        "sai ", "paint tool sai", "gaomon", "数位板", "绘图板",
        "spid", "stylus",
    ],
    "文件管理": [
        "7zip", "7-zip", "winrar", "rar", "bandizip", "好压",
        "haozip", "peazip", "izarc", "total commander", "tc",
        "directory opus", "dopus", "xyplorer", "freecommander",
        "double commander", "files", "files2", "clover",
        "everything", "search", "搜索", "文件", "压缩",
        "sftp", "filezilla", "winscp", "flashfxp",
        "图吧工具箱", "硬件工具", "硬件检测",
        "壁纸", "wallpaper", "壁纸导出",
    ],
    "安全工具": [
        "360安全", "360total", "kaspersky", "卡巴斯基", "norton",
        "mcafee", "avg", "avast", "avira", "bitdefender",
        "eset", "nod32", "malwarebytes", "adwcleaner",
        "火绒", "huorong", "windows defender",
        "杀毒", "安全", "防火墙", "firewall",
    ],
    "游戏娱乐": [
        "steam", "epic", "epic games", "gog", "origin", "ea app",
        "ubisoft connect", "uplay", "battlenet", "战网",
        "riot", "英雄联盟", "lol", "瓦罗兰特", "valorant",
        "cs2", "csgo", "dota2", "pubg", "绝地求生",
        "minecraft", "我的世界", "roblox", "genshin", "原神",
        "game", "游戏", "launcher", "启动器",
        "nvidia", "geforce experience", "amd", "radeon",
        "xbox", "playstation", "switch", "emulator", "模拟器",
    ],
    "教育学习": [
        "coursera", "udemy", "edx", "khan", "可汗学院",
        "慕课", "mooc", "学堂在线", "中国大学",
        "anki", "quizlet", "百词斩", "扇贝",
        "matlab", "mathematica", "maple", "spss", "stata",
        "origin", "latex", "texstudio", "overleaf",
        "wolfram", "geogebra", "desmos",
        "教育", "学习", "词典", "翻译", "有道", "金山词霸",
        "粉笔", "直播课",
    ],
    "财务工具": [
        "支付宝", "alipay", "微信支付", "银行", "bank",
        "招商银行", "工商银行", "建设银行", "农业银行",
        "中国银行", "交通银行", "网银", "personal capital",
        "mint", "记账", "财务", "stock", "股票", "基金",
        "同花顺", "东方财富", "雪球", "tushare",
    ],
    "网络工具": [
        "clash", "v2ray", "shadowsocks", "ssr", "trojan",
        "wireguard", "openvpn", "proxifier", "netch",
        "flclash", "clash for windows",
        "idm", "internet download", "fdm", "aria2",
        "transmission", "qbittorrent", "utorrent", "迅雷",
        "百度网盘", "阿里云盘", "蓝奏云", "onedrive",
        "dropbox", "google drive", "坚果云", "夸克网盘",
        "网络", "下载", "网盘", "代理", "proxy", "vpn",
        "zyfun",
    ],
}


def classify_by_keywords(icon: DesktopIcon) -> Optional[str]:
    """使用关键词匹配进行分类"""
    name_lower = icon.name.lower()
    path_lower = (icon.target_path or "").lower()

    # 按匹配度排序：优先匹配文件名和路径
    best_match = None
    best_score = 0

    for category, keywords in KEYWORD_RULES.items():
        score = 0
        for keyword in keywords:
            kw = keyword.lower()
            # 精确匹配文件名得高分
            if kw in name_lower:
                score += 10
                # 完全匹配文件名（去除扩展名）
                name_no_ext = os.path.splitext(name_lower)[0]
                if name_no_ext == kw or name_no_ext == f"{kw}.exe":
                    score += 20
            # 路径匹配
            if kw in path_lower:
                score += 5

        if score > best_score:
            best_score = score
            best_match = category

    return best_match


def classify_by_extension(icon: DesktopIcon) -> Optional[str]:
    """根据文件扩展名/类型推断分类"""
    path = icon.target_path or ""
    ext = os.path.splitext(path)[1].lower()

    ext_map = {
        ".exe": None,
        ".msi": "系统工具",
        ".bat": "开发工具",
        ".cmd": "开发工具",
        ".ps1": "开发工具",
        ".py": "开发工具",
        ".js": "开发工具",
        ".html": "开发工具",
        ".url": "浏览器",
        ".lnk": None,
        ".pdf": "办公套件",
        ".doc": "办公套件",
        ".docx": "办公套件",
        ".xls": "办公套件",
        ".xlsx": "办公套件",
        ".ppt": "办公套件",
        ".pptx": "办公套件",
        ".txt": "办公套件",
        ".md": "办公套件",
        ".png": "图形设计",
        ".jpg": "图形设计",
        ".jpeg": "图形设计",
        ".psd": "图形设计",
        ".ai": "图形设计",
        ".mp3": "媒体播放",
        ".mp4": "媒体播放",
        ".mkv": "媒体播放",
        ".avi": "媒体播放",
        ".zip": "文件管理",
        ".rar": "文件管理",
        ".7z": "文件管理",
    }

    return ext_map.get(ext)


def classify_online(icon: DesktopIcon) -> Optional[str]:
    """通过联网搜索进行分类"""
    if not HAS_REQUESTS:
        return None

    name = icon.name.strip()
    if not name:
        return None

    # 去除常见后缀
    clean_name = re.sub(r'\s*(快捷方式|shortcut|\.lnk|\.exe)\s*$', '', name, flags=re.IGNORECASE).strip()

    if not clean_name:
        return None

    try:
        # 使用 DuckDuckGo Instant Answer API
        url = "https://api.duckduckgo.com/"
        params = {
            "q": f"{clean_name} software application type category",
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()

        # 从 AbstractText 和 Categories 中推断
        text = ""
        if data.get("AbstractText"):
            text += data["AbstractText"] + " "
        if data.get("Heading"):
            text += data["Heading"] + " "
        if data.get("Answer"):
            text += str(data["Answer"]) + " "

        categories_str = " ".join(data.get("Categories", []))
        text += " " + categories_str

        text_lower = text.lower()

        # 简单关键词匹配返回的摘要
        for category, keywords in KEYWORD_RULES.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return category

        # 检查额外线索
        extra_keywords = {
            "浏览器": ["web browser", "browse the web"],
            "办公套件": ["office suite", "productivity", "word processor", "spreadsheet"],
            "开发工具": ["ide", "integrated development", "programming", "compiler", "code editor"],
            "媒体播放": ["media player", "video player", "audio player", "music player"],
            "社交通讯": ["messaging", "chat", "social network", "video call"],
            "图形设计": ["image editor", "photo editor", "graphic design", "video editor"],
            "安全工具": ["antivirus", "firewall", "security", "malware"],
            "游戏娱乐": ["video game", "game launcher", "gaming"],
            "文件管理": ["file manager", "file archiver", "compression"],
        }

        for category, keywords in extra_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return category

    except Exception:
        pass

    return None


def classify_icon(icon: DesktopIcon, use_online: bool = False) -> str:
    """
    分类单个图标
    优先级: 关键词匹配 > 扩展名推断 > 联网搜索 > 默认
    """
    # 1. 关键词匹配
    category = classify_by_keywords(icon)
    if category:
        return category

    # 2. 扩展名推断
    category = classify_by_extension(icon)
    if category:
        return category

    # 3. 联网搜索
    if use_online:
        category = classify_online(icon)
        if category:
            return category

    return "其他"


def classify_all_icons(
    icons: List[DesktopIcon],
    use_online: bool = False,
    progress_callback=None,
) -> Dict[str, List[DesktopIcon]]:
    """
    分类所有图标
    返回 {类别: [图标列表]} 的字典
    """
    classified: Dict[str, List[DesktopIcon]] = {cat: [] for cat in CATEGORIES}
    classified["其他"] = []

    total = len(icons)
    for i, icon in enumerate(icons):
        icon.category = classify_icon(icon, use_online=use_online)
        if icon.category not in classified:
            classified["其他"].append(icon)
        else:
            classified[icon.category].append(icon)

        if progress_callback:
            progress_callback(i + 1, total, icon.name, icon.category)

    # 移除空类别
    classified = {k: v for k, v in classified.items() if v}

    return classified


def load_custom_categories(filepath: str) -> Dict[str, List[str]]:
    """加载自定义分类规则"""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("rules", {})
    except Exception:
        return {}


def save_classification_cache(classified: Dict[str, List[DesktopIcon]], filepath: str):
    """保存分类结果缓存"""
    data = {}
    for cat, icons in classified.items():
        data[cat] = [icon.name for icon in icons]
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    # 测试分类器
    test_names = [
        "Google Chrome", "Visual Studio Code", "微信",
        "Steam", "Word", "Python 3.11",
        "未知应用程序", "7-Zip", "PotPlayer",
    ]
    for name in test_names:
        icon = DesktopIcon(index=0, name=name, x=0, y=0)
        cat = classify_icon(icon)
        print(f"  {name} -> {cat}")
