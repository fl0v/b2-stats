"""Build the b2-stats-tray.exe on Windows.

Run this ON a Windows machine (or via .github/workflows/build-windows.yml) —
PyInstaller does not cross-compile a Windows binary from Linux/macOS.

Usage (from the repo root, in a venv with -e . and pyinstaller installed):
    pip install pyinstaller
    python scripts/build_windows.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if sys.platform != "win32":
        print("This script must be run on Windows to produce a .exe.", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "b2-stats-tray",
        "--onefile",
        "--windowed",
        str(REPO_ROOT / "b2_stats" / "tray.py"),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
