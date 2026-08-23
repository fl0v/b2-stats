from __future__ import annotations

import argparse
import queue
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

import pystray
from PIL import Image, ImageDraw

from . import cache
from .config import load_config
from .stats import format_table

_action_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()


def _make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((4, 4, 60, 60), radius=10, fill=(15, 76, 129, 255))
    draw.text((14, 20), "B2", fill=(255, 255, 255, 255))
    return img


class TrayApp:
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self.root = tk.Tk()
        self.root.withdraw()
        self.text_window: tk.Toplevel | None = None
        self.text_widget: scrolledtext.ScrolledText | None = None

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
            bucket_stats, fetched_at, _was_cached = cache.get_or_fetch(config, force=force_refresh)
            text = format_table(bucket_stats, fetched_at)
        except Exception as e:  # noqa: BLE001 - surface any failure in the popup itself
            text = f"Error fetching B2 stats:\n{e}"

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

    def run(self) -> None:
        self.root.after(200, self._poll_queue)
        threading.Thread(target=self.icon.run, daemon=True).start()
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
