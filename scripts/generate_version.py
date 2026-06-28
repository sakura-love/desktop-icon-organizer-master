#!/usr/bin/env python3
"""CI 构建时从 git tag 读取版本号，写入 version.txt 供应用和 PyInstaller 使用。"""
import argparse, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def get_version():
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/"):
        return ref[len("refs/tags/"):].lstrip("v")
    try:
        r = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True, cwd=ROOT)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().lstrip("v")
    except: pass
    return "0.0.0"

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--print", action="store_true")
    args = a.parse_args()
    v = get_version()
    if args.print:
        print(v)
    else:
        (ROOT / "version.txt").write_text(v, encoding="utf-8")
        print(f"version.txt generated (v{v})")

if __name__ == "__main__":
    main()
