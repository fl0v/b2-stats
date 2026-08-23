"""PyInstaller entry point for the tray app.

PyInstaller treats whatever file it's pointed at as a top-level script, not
a module inside the b2_stats package — so b2_stats/tray.py's relative
imports (`from . import cache`, etc.) fail at runtime with "attempted
relative import with no known parent package". Importing it as a package
here, and having PyInstaller build *this* file instead, avoids that.
"""
from b2_stats.tray import main

if __name__ == "__main__":
    raise SystemExit(main())
