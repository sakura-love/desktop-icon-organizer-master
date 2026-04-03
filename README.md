<div align="center">

# 🖥️ Desktop Icon Organizer

**一款优雅的 Windows 桌面图标自动分类整理工具**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)](https://github.com/sakura-love/desktop-icon-organizer-master)
[![Python](https://img.shields.io/badge/python-3.9%2B-yellow.svg)](https://www.python.org/)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [截图预览](#-截图预览) • [技术架构](#-技术架构)

</div>

---

## ✨ 功能特性

<table>
<tr>
<td width="50%">

### 🤖 智能图标分类

- **14 种预设类别** — 浏览器、办公、开发、游戏、社交通讯等
- **多级分类策略** — 关键词匹配 → 扩展名推断 → 联网搜索
- **DuckDuckGo 集成** — 无法识别的图标自动联网查询
- **拖拽调整** — 可视化预览中自由调整图标位置

</td>
<td width="50%">

### 🖥️ 桌面叠加层

- **分类边框** — 在桌面显示半透明分类边框
- **持久化显示** — 主程序退出后叠加层依然保持
- **独立进程** — 叠加层运行于独立子进程，不影响主程序
- **一键切换** — 显示/隐藏边框随时切换

</td>
</tr>
<tr>
<td width="50%">

### 📐 布局管理

- **实时预览** — 等比缩放显示布局效果
- **一键应用** — Win32 API 直接操控桌面图标
- **即时生效** — 无需重启资源管理器
- **竖向分区** — 每个类别独立一列，整齐美观

</td>
<td width="50%">

### 💾 备份与还原

- **自动备份** — 应用布局前自动保存当前状态
- **自定义方案** — 保存常用布局方案随时加载
- **历史记录** — 支持查看和还原历史备份
- **一键还原** — 随时恢复到任意备份点

</td>
</tr>
</table>

---

## 🚀 快速开始

### 方式一：直接运行（推荐）

1. 前往 [Releases](https://github.com/sakura-love/desktop-icon-organizer-master/releases) 下载最新版 `DesktopIconOrganizer.exe`
2. **右键 → 以管理员身份运行**
3. 开始整理你的桌面！

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/sakura-love/desktop-icon-organizer-master.git
cd desktop-icon-organizer-master

# 安装依赖
pip install -r requirements.txt

# 运行（需管理员权限）
python main.py
```

### 打包为单文件

```bash
pip install pyinstaller
python -m PyInstaller build.spec --clean --noconfirm
```

---

## 📸 截图预览

### 1. 原始桌面
![原始桌面](screenshots/1.png)

### 2. 软件主界面
![软件主界面](screenshots/2.png)

### 3. 布局预览
![布局预览](screenshots/3.png)

### 4. 应用到桌面
![应用到桌面](screenshots/4.png)

### 5. 分类边框叠加层
![分类边框叠加层](screenshots/5.png)

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    MainApp (GUI)                        │
│              customtkinter + Windows 11 深色主题         │
└───────────────────────┬─────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    ▼                   ▼                   ▼
┌───────────┐   ┌───────────────┐   ┌───────────────┐
│  Scanner  │   │  Classifier   │   │ Layout Engine │
│ Win32 API │   │ Keyword+AI    │   │ Grid Layout   │
└───────────┘   └───────────────┘   └───────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │ Overlay Process │
              │ 独立子进程 + IPC │
              └─────────────────┘
```

| 模块 | 技术 | 说明 |
|---|---|---|
| GUI 框架 | CustomTkinter | Windows 11 风格深色主题 |
| 图标扫描 | Win32 API | 跨进程访问 `SysListView32` |
| 图像渲染 | Pillow | BGRA 位图 + `UpdateLayeredWindow` |
| 叠加层 | 独立进程 + JSON IPC | PID 心跳检测 + 控制文件通信 |
| 分类引擎 | 多级策略 | 关键词 → 扩展名 → 联网搜索 |

---

## 📁 项目结构

```
desktop-icon-organizer-master/
├── main.py                # 主程序入口 (GUI)
├── desktop_scanner.py     # 桌面图标扫描模块
├── icon_classifier.py     # 图标分类模块
├── layout_engine.py       # 布局引擎模块
├── preview_canvas.py      # 布局预览画布
├── desktop_overlay.py     # 桌面叠加层管理
├── overlay_process.py     # 独立叠加层进程
├── backup_manager.py      # 备份管理模块
├── PingFang SC.ttf        # 叠加层中文字体
├── app.ico                # 应用图标
├── requirements.txt       # Python 依赖
├── build.spec             # PyInstaller 配置
├── backups/               # 桌面布局备份
└── layouts/               # 自定义布局方案
```

---

## 🎨 分类类别

| 类别 | 颜色 | 包含应用 |
|---|---|---|
| 🌐 浏览器 | 蓝灰 | Chrome, Edge, Firefox, Safari... |
| 📄 办公软件 | 深蓝 | Office, WPS, PDF 阅读器... |
| 💻 开发工具 | 暗紫 | VS Code, PyCharm, Git... |
| 🎬 影音娱乐 | 暗红 | 播放器, 音乐, 直播... |
| 💬 社交通讯 | 暗青 | 微信, QQ, 钉钉, Telegram... |
| ⚙️ 系统工具 | 暗绿 | 设置, 驱动, 终端, 压缩... |
| 🎮 游戏 | 暗橙 | Steam, Epic, 游戏启动器... |
| 🎨 设计创意 | 暗粉 | PS, AI, Figma, Blender... |
| 📦 其他 | 灰色 | 未分类应用 |

---

## ⚙️ 系统要求

- **操作系统**: Windows 10 / 11
- **权限**: 需要以管理员身份运行
- **Python**: 3.9+ (仅从源码运行时需要)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star 支持一下！**

Made with ❤️ by [sakura-love](https://github.com/sakura-love)

</div>
