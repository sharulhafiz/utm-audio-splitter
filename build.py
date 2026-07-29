#!/usr/bin/env python3
"""Build standalone executables for UTM Audio Splitter using PyInstaller."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "UTM Audio Splitter"
APP_SCRIPT = "app.py"
ICON_MAP = {
    "Windows": "icon.ico",
    "Darwin": "icon.icns",
    "Linux": "icon.png",
}

REQUIREMENTS = [
    "customtkinter>=6.0.0",
    "pyinstaller>=6.0",
]


def main():
    system = platform.system()
    print(f"🔨 Building {APP_NAME} for {system}...")

    # Install deps
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet"] + REQUIREMENTS
    )

    # Clean previous build
    for d in ("build", "dist"):
        if os.path.isdir(d):
            shutil.rmtree(d)

    # PyInstaller command
    icon_file = ICON_MAP.get(system)
    icon_arg = []
    if icon_file and os.path.isfile(icon_file):
        icon_arg = ["--icon", icon_file]

    name_map = {
        "Windows": "UTM-Audio-Splitter.exe",
        "Darwin": "UTM-Audio-Splitter",
        "Linux": "utm-audio-splitter",
    }

    out_name = name_map.get(system, "UTM-Audio-Splitter")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", out_name,
        *icon_arg,
        "--add-data", f"README.md{';' if system == 'Windows' else ':'}.",
        APP_SCRIPT,
    ]

    print("$ " + " ".join(cmd))
    subprocess.check_call(cmd)

    # Locate output
    dist_path = Path("dist") / out_name
    if system == "Windows":
        dist_path = dist_path.with_suffix(".exe")

    if dist_path.exists():
        print(f"\n✅ Build complete: {dist_path.resolve()}")
    else:
        print(f"\n⚠️  Build may have failed — check dist/ directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
