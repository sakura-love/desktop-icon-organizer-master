# Desktop Icon Organizer

A Windows desktop icon organization tool with scanning, automatic/online classification, visual layout preview, drag-to-adjust, overlay borders, backup/restore, and one-click apply.

## Highlights
- Desktop icon scanning based on Win32 ListView APIs.
- Automatic classification (keyword + extension) and online fallback classification.
- Interactive layout preview with drag-and-swap.
- Category overlay borders rendered in a separate process.
- Backup, restore, save layout, and load layout.
- Persistent startup overlay restore support.

## Recent Updates

### v2.0 (2026-04-25)
- Added persistent icon profile storage (`icon_profile.json`) after scan.
- Classification results now persist icon category and layout position.
- Manual category changes are persisted and take priority in future auto/online classification.
- Added multiple overlay border styles:
  - `rounded`
  - `square`
  - `corner`
  - `bracket`
- Border style selector now shows Chinese labels in UI.
- Fixed overlay process duplication issue:
  - enforce single-instance overlay behavior
  - detect both source mode (`overlay_process.py`) and packaged mode (`--overlay`)
  - clean stale duplicate overlay processes when needed
- Updated build output name to `DesktopIconOrganizer_v2.0.exe`.

### Previous Patch (2026-04-13)
- Improved packaged runtime stability around temporary extraction cleanup.
- Improved overlay subprocess startup environment isolation.

## Screenshots

![Original Desktop](screenshots/1.png)
![Main Window](screenshots/2.png)
![Layout Preview](screenshots/3.png)
![Apply Layout](screenshots/4.png)
![Overlay Border](screenshots/5.png)

## Requirements
- Windows 10/11
- Python 3.9+
- Administrator privilege (recommended for reliable desktop icon operations)

## Quick Start

### Option A: Run from source
```bash
git clone https://github.com/sakura-love/desktop-icon-organizer-master.git
cd desktop-icon-organizer-master
pip install -r requirements.txt
python main.py
```

### Option B: Build executable
```bash
pip install pyinstaller
python -m PyInstaller --clean --noconfirm build.spec
```
Output executable:
- `dist/DesktopIconOrganizer_v2.0.exe`

## Typical Workflow
1. Scan desktop icons.
2. Run automatic classification or online classification.
3. Review in preview and drag icons if needed.
4. Optionally modify category for specific icons (manual overrides are persisted).
5. Select overlay border style and show overlay.
6. Apply layout to desktop.
7. Optionally save persistent layout / backups.

## Project Structure
```text
desktop-icon-organizer-master/
├── main.py                   # Main GUI app
├── desktop_scanner.py        # Desktop icon scan/apply module
├── icon_classifier.py        # Classification engine
├── icon_profile_store.py     # Persistent icon profile and manual overrides
├── layout_engine.py          # Layout calculation
├── preview_canvas.py         # Layout preview canvas
├── desktop_overlay.py        # Overlay manager and renderer
├── overlay_process.py        # Standalone overlay subprocess
├── backup_manager.py         # Backup/layout management
├── build.spec                # PyInstaller spec
├── build.bat                 # Build helper script
├── requirements.txt          # Python dependencies
├── screenshots/              # README screenshots
├── backups/                  # Backup files
└── layouts/                  # Saved layout files
```

## Notes
- In packaged mode, overlay process runs via `--overlay`.
- If overlay seems stale, use “Hide Border” and show again.
- The repository may contain local build artifacts in `build/`, `dist/`, and `__pycache__/`.

## License
MIT License. See [LICENSE](LICENSE).
