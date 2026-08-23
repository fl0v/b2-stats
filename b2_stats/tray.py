from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext

import pystray
from PIL import Image

from . import cache
from .config import load_config
from .stats import format_table, human_size, totals

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


class TrayApp:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self.root = tk.Tk()
        self.root.withdraw()
        self.text_window: tk.Toplevel | None = None
        self.text_widget: scrolledtext.ScrolledText | None = None
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
                        self._display_text(str(arg))
                        self._display_pending = False
                    # else: a silent background prefetch finished - just leave the
                    # cache warm, don't pop the window open on its own.
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
            self._display_text(f"Error fetching B2 stats:\n{e}")
            return

        self._display_pending = True
        if self._start_fetch(config, force_refresh):
            self._display_text("Fetching B2 stats (scanning buckets)... this may take a while.")
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
        try:
            bucket_stats, fetched_at, _was_cached = cache.get_or_fetch(config, force=force_refresh)
            text = format_table(bucket_stats, fetched_at)
            _files, _current, total_all, total_cost = totals(bucket_stats)
            self._set_tooltip(
                f"{_TOOLTIP_BASE} — {human_size(total_all)} · ${total_cost:.2f}/mo "
                f"(as of {time.strftime('%H:%M')})"
            )
        except Exception as e:  # noqa: BLE001 - surface any failure in the popup itself
            text = f"Error fetching B2 stats:\n{e}"
            self._set_tooltip(f"{_TOOLTIP_BASE} — refresh failed")
        _action_queue.put(("stats_ready", text))

    def _set_tooltip(self, text: str) -> None:
        try:
            self.icon.title = text[:127]
        except Exception:  # noqa: BLE001 - tooltip is cosmetic, never fatal
            pass

    def _display_text(self, text: str) -> None:
        if self.text_window is None or not self.text_window.winfo_exists():
            self.text_window = tk.Toplevel(self.root)
            self.text_window.title("B2 Stats")
            self.text_widget = scrolledtext.ScrolledText(
                self.text_window, width=90, height=20, font=("Courier New", 10)
            )
            self.text_widget.pack(fill="both", expand=True)

        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert(tk.END, text)
        self.text_widget.configure(state="disabled")
        self.text_window.deiconify()
        self.text_window.lift()
        self.text_window.focus_force()

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
