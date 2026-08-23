from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pystray
from PIL import Image, ImageTk

from . import cache
from .config import load_config
from .stats import human_size, totals

_action_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

_TOOLTIP_BASE = "B2 Stats"
_SCHEDULED_CHECK_SECONDS = 60


def _asset_path(name: str) -> Path:
    """Locates a bundled asset both when run from source and when frozen by
    PyInstaller. --onefile extracts data files added via --add-data under
    sys._MEIPASS, preserving the destination path we pass at build time
    (b2_stats/assets/...) - see build_windows.py. Mirrors config.program_dir()'s
    frozen-detection pattern rather than importlib.resources, whose resource
    reader doesn't reliably support PyInstaller's archive-based package loader.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return base / "b2_stats" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name


def _make_icon_image() -> Image.Image:
    """The Backblaze flame mark, bundled as a package asset (see pyproject.toml's
    package-data and build_windows.py's --add-data for how it ships in the .exe)."""
    with _asset_path("backblaze_mark.png").open("rb") as f:
        return Image.open(f).convert("RGBA").copy()


_COLUMNS = ("bucket", "files", "current", "incl_versions", "cost")
_HEADINGS = {
    "bucket": ("Bucket", 220, "w"),
    "files": ("Files", 80, "e"),
    "current": ("Current size", 110, "e"),
    "incl_versions": ("Size incl. versions", 150, "e"),
    "cost": ("Est. $/month", 100, "e"),
}


class TrayApp:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self.root = tk.Tk()
        self.root.withdraw()
        self.window: tk.Toplevel | None = None
        self.tree: ttk.Treeview | None = None
        self.status_var: tk.StringVar | None = None
        self.refresh_btn: ttk.Button | None = None
        self._fetch_lock = threading.Lock()
        self._fetch_thread: threading.Thread | None = None
        self._display_pending = False

        self.icon = pystray.Icon(
            "b2-stats",
            _make_icon_image(),
            "B2 Stats",
            menu=pystray.Menu(
                pystray.MenuItem("Show Stats", self._queue_show, default=True),
                pystray.MenuItem("Refresh", self._queue_refresh),
                pystray.MenuItem("Quit", self._queue_quit),
            ),
        )

    def _queue_show(self, icon, item) -> None:
        _action_queue.put(("show", False))

    def _queue_refresh(self, icon, item) -> None:
        _action_queue.put(("show", True))

    def _queue_quit(self, icon, item) -> None:
        _action_queue.put(("quit", None))

    def _poll_queue(self) -> None:
        try:
            while True:
                action, arg = _action_queue.get_nowait()
                if action == "show":
                    self._show_stats(force_refresh=bool(arg))
                elif action == "stats_ready":
                    if self._display_pending:
                        bucket_stats, fetched_at, error = arg
                        if error:
                            self._show_error(error)
                        else:
                            self._populate(bucket_stats, fetched_at)
                        self._display_pending = False
                    # else: a silent background prefetch/scheduled refresh finished -
                    # just leave the cache warm, don't pop the window open on its own.
                elif action == "quit":
                    self.icon.stop()
                    self.root.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _show_stats(self, force_refresh: bool) -> None:
        try:
            config = load_config(self.config_path)
        except Exception as e:  # noqa: BLE001 - surface any failure in the popup itself
            self._show_error(str(e))
            return

        self._display_pending = True
        self._raise_window()
        if self._start_fetch(config, force_refresh):
            self._show_loading()
        else:
            self._fetch_and_queue(config, force_refresh)

    def _start_fetch(self, config, force_refresh: bool) -> bool:
        """Kicks off a background fetch if one isn't already running and the cache
        needs it. Returns True if the caller should wait for it (already running or
        just started), False if the cache is fresh and the caller can render inline."""
        with self._fetch_lock:
            if self._fetch_thread is not None and self._fetch_thread.is_alive():
                return True
            if not force_refresh and cache.is_fresh(config):
                return False
            self._set_tooltip(f"{_TOOLTIP_BASE} — refreshing…")
            self._fetch_thread = threading.Thread(
                target=self._fetch_and_queue, args=(config, force_refresh), daemon=True
            )
            self._fetch_thread.start()
            return True

    def _prefetch(self) -> None:
        """Warms the cache in the background as soon as the app launches, so the
        popup can render instantly the first time the user clicks the tray icon."""
        try:
            config = load_config(self.config_path)
        except Exception:  # noqa: BLE001 - silent: errors surface when the user clicks Show
            return
        self._start_fetch(config, force_refresh=False)

    def _fetch_and_queue(self, config, force_refresh: bool) -> None:
        bucket_stats = fetched_at = error = None
        try:
            bucket_stats, fetched_at, _was_cached = cache.get_or_fetch(config, force=force_refresh)
            _files, _current, total_all, total_cost = totals(bucket_stats)
            self._set_tooltip(
                f"{_TOOLTIP_BASE} — {human_size(total_all)} · ${total_cost:.2f}/mo "
                f"(as of {time.strftime('%H:%M')})"
            )
        except Exception as e:  # noqa: BLE001 - surface any failure in the popup itself
            error = str(e)
            self._set_tooltip(f"{_TOOLTIP_BASE} — refresh failed")
        _action_queue.put(("stats_ready", (bucket_stats, fetched_at, error)))

    def _set_tooltip(self, text: str) -> None:
        try:
            self.icon.title = text[:127]
        except Exception:  # noqa: BLE001 - tooltip is cosmetic, never fatal
            pass

    def _ensure_window(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("B2 Stats")
        self.window.geometry("700x360")
        self.window.minsize(520, 240)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        # Keep a reference on self - Tk drops PhotoImages with no surviving
        # Python reference even while still displayed.
        self._window_icon = ImageTk.PhotoImage(_make_icon_image())
        self.window.iconphoto(False, self._window_icon)

        toolbar = ttk.Frame(self.window, padding=8)
        toolbar.pack(fill="x")
        self.refresh_btn = ttk.Button(
            toolbar, text="Refresh", command=lambda: self._show_stats(force_refresh=True)
        )
        self.refresh_btn.pack(side="left")
        self.status_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="left", padx=12)

        tree_frame = ttk.Frame(self.window, padding=(8, 0, 8, 8))
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=_COLUMNS, show="headings", selectmode="none")
        for col, (label, width, anchor) in _HEADINGS.items():
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.tag_configure("total", font=("TkDefaultFont", 9, "bold"))

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _raise_window(self) -> None:
        self._ensure_window()
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def _show_loading(self) -> None:
        self._ensure_window()
        self.refresh_btn.state(["disabled"])
        self.status_var.set("Fetching B2 stats (scanning buckets)... this may take a while.")

    def _populate(self, bucket_stats, fetched_at: str) -> None:
        self._ensure_window()
        self.tree.delete(*self.tree.get_children())
        for b in bucket_stats:
            self.tree.insert(
                "", "end",
                values=(
                    b.name,
                    f"{b.file_count:,}",
                    human_size(b.current_bytes),
                    human_size(b.total_bytes_incl_versions),
                    f"${b.estimated_monthly_cost:,.2f}",
                ),
            )
        total_files, total_current, total_all, total_cost = totals(bucket_stats)
        self.tree.insert(
            "", "end",
            values=(
                "TOTAL",
                f"{total_files:,}",
                human_size(total_current),
                human_size(total_all),
                f"${total_cost:,.2f}",
            ),
            tags=("total",),
        )
        self.status_var.set(
            f"As of {fetched_at} - cost is a storage-only estimate, not a bill"
        )
        self.refresh_btn.state(["!disabled"])

    def _show_error(self, message: str) -> None:
        self._raise_window()
        self.status_var.set(f"Error: {message}")
        self.refresh_btn.state(["!disabled"])
        messagebox.showerror("B2 Stats", message, parent=self.window)

    def _scheduled_refresh(self) -> None:
        """Runs on the Tk main loop every _SCHEDULED_CHECK_SECONDS; auto-refreshes
        the cache in the background once its TTL expires, even if the user never
        clicks the tray icon."""
        try:
            config = load_config(self.config_path)
            self._start_fetch(config, force_refresh=False)
        except Exception:  # noqa: BLE001 - errors surface next time the user clicks Show
            pass
        self.root.after(_SCHEDULED_CHECK_SECONDS * 1000, self._scheduled_refresh)

    def run(self) -> None:
        self.root.after(200, self._poll_queue)
        self.root.after(_SCHEDULED_CHECK_SECONDS * 1000, self._scheduled_refresh)
        threading.Thread(target=self.icon.run, daemon=True).start()
        threading.Thread(target=self._prefetch, daemon=True).start()
        self.root.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="b2-stats-tray",
        description="B2 stats tray icon app",
        epilog=(
            "Without --config, looks for config.yaml next to the program, in the "
            "current directory, then in ~/.config/b2-stats/ (or %APPDATA%\\b2-stats\\ "
            "on Windows), then in ~/.b2-stats/."
        ),
    )
    parser.add_argument("--config", metavar="PATH", help="Path to config.yaml")
    args = parser.parse_args(argv)

    app = TrayApp(config_path=args.config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
