# Desktop Icon Organizer

一款 Windows 11 风格的桌面图标自动分类整理工具，支持智能分类、布局预览、拖拽排列、一键应用到桌面，并可显示持久化的半透明分类边框叠加层。

## 功能特性

- **智能图标分类** — 内置 14 类关键词规则库，支持本地关键词匹配、扩展名推断和 DuckDuckGo 联网搜索
- **可视化布局预览** — 实时预览分类结果，支持拖拽交换图标位置
- **一键应用到桌面** — 通过 Win32 API 直接操控桌面图标位置，无需重启
- **桌面叠加层** — 在桌面显示半透明分类边框，主程序退出后依然保持显示
- **备份与还原** — 支持桌面布局备份、自定义布局方案保存与加载
- **Windows 11 风格界面** — 深色主题，现代化 UI 设计

## 系统要求

- Windows 10 / 11
- Python 3.9+
- 管理员权限（操作桌面图标需要）

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python main.py
```

> 注意：需要以管理员权限运行，否则无法扫描和移动桌面图标。

## 使用方法

1. **扫描桌面** — 自动获取当前桌面上所有图标信息
2. **自动分类** — 使用关键词规则对图标进行分类
3. **联网分类** — 对无法匹配的图标通过联网搜索进行分类
4. **预览布局** — 在预览画布中查看分类结果，可拖拽调整
5. **应用布局** — 将布局应用到实际桌面
6. **显示/隐藏边框** — 在桌面显示或隐藏分类边框叠加层

## 项目结构

```
├── main.py                # 主程序入口（GUI）
├── desktop_scanner.py     # 桌面图标扫描模块（Win32 API）
├── icon_classifier.py     # 图标分类模块
├── layout_engine.py       # 布局引擎模块
├── preview_canvas.py      # 布局预览画布模块
├── desktop_overlay.py     # 桌面叠加层模块
├── overlay_process.py     # 独立叠加层进程
├── backup_manager.py      # 备份管理模块
├── PingFang SC.ttf        # 叠加层中文字体
├── requirements.txt       # Python 依赖
├── backups/               # 桌面布局备份目录
└── layouts/               # 自定义布局方案目录
```

## 技术实现

- **GUI 框架**：CustomTkinter
- **图标扫描**：Win32 API 跨进程通信（`SysListView32` 控件）
- **图像渲染**：Pillow（叠加层使用 `UpdateLayeredWindow` + BGRA 位图）
- **叠加层架构**：独立子进程 + JSON 文件 IPC + PID 心跳检测
- **分类引擎**：多级匹配策略（关键词 → 扩展名 → 联网搜索）

## 分类类别

| 类别 | 颜色 | 说明 |
|---|---|---|
| 浏览器 | 蓝灰 | Chrome, Edge, Firefox 等 |
| 办公软件 | 深蓝 | Office, WPS, PDF 阅读器 |
| 开发工具 | 暗紫 | IDE, 编辑器, Git 工具 |
| 影音娱乐 | 暗红 | 播放器, 音乐, 直播 |
| 社交通讯 | 暗青 | 微信, QQ, 钉钉 |
| 系统工具 | 暗绿 | 系统设置, 驱动, 终端 |
| 游戏 | 暗橙 | Steam, Epic, 游戏平台 |
| 设计创意 | 暗粉 | PS, AI, Figma |
| 其他 | 灰色 | 未分类图标 |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
