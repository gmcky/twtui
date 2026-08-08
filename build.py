#!/usr/bin/env python3
"""Build the standalone Windows exe with PyInstaller. Run: py build.py"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(ROOT, "assets", "twitch.ico")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile", "--console", "--name", "twitch",
    "--icon", ICON,
    "--paths", os.path.join(ROOT, "src"),
    "--distpath", os.path.join(ROOT, "dist"),
    "--workpath", os.path.join(ROOT, "build_tmp"),
    "--specpath", os.path.join(ROOT, "build_tmp"),
    os.path.join(ROOT, "watch.py"),
]
raise SystemExit(subprocess.call(cmd))
