"""Build the b2-stats-tray.exe on Windows.

Run this ON a Windows machine (or via .github/workflows/build-windows.yml) —
PyInstaller does not cross-compile a Windows binary from Linux/macOS.

Usage (from the repo root, in a venv with -e . and pyinstaller installed):
    pip install -e . pyinstaller
    python scripts/build_windows.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _check_dependencies_importable() -> bool:
    """Fail fast with a clear message instead of a runtime crash in the exe.

    If pystray/Pillow aren't importable in *this* interpreter, PyInstaller
    (invoked as `sys.executable -m PyInstaller` below) won't bundle them
    either, and the built exe will crash with ModuleNotFoundError on launch.
    """
    check = subprocess.run(
        [sys.executable, "-c", "import pystray, PIL"],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        print(
            "pystray/Pillow are not importable with this Python "
            f"({sys.executable}):\n{check.stderr}\n"
            "Install the project's dependencies with THIS interpreter first:\n"
            f"    {sys.executable} -m pip install -e .\n",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    if sys.platform != "win32":
        print("This script must be run on Windows to produce a .exe.", file=sys.stderr)
        return 1

    if not _check_dependencies_importable():
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "b2-stats-tray",
        "--onefile",
        "--windowed",
        # pystray picks its backend (e.g. pystray._win32) via a dynamic
        # importlib.import_module() call, which PyInstaller's static
        # analysis can't see — without --collect-all it silently omits
        # that backend and the exe fails at runtime.
        "--collect-all",
        "pystray",
        str(REPO_ROOT / "scripts" / "tray_entry.py"),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
