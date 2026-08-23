# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`b2-stats` shows per-bucket usage and estimated cost for Backblaze B2, as a
console script (`b2-stats`) and a system-tray app (`b2-stats-tray`) that can
be packaged into a Windows `.exe`. Backblaze's B2 native API has no billing
endpoint and no bucket-size field, so size is derived by paginating every
file (and, optionally, every file version) in every bucket, and cost is a
storage-only *estimate* against B2's published price — not an invoice
figure. This constraint shapes most of the architecture below.

## Commands

```bash
make install       # create .venv (via uv) and install runtime deps (CLI + tray)
make dev-install   # same, plus pytest
make test          # run the full test suite (uv run pytest -q)
make run           # run the CLI (b2-stats)
make tray          # run the tray app (b2-stats-tray)
make build-windows # build b2-stats-tray.exe (must run on Windows; see below)
make clean         # remove .venv, build/dist artifacts, caches
make               # (bare) lists all targets with descriptions — self-documenting
```

Package management is via [uv](https://docs.astral.sh/uv/), not raw
`pip`/`venv` — dependencies live in `pyproject.toml` (`dev`/`build` extras
for pytest/PyInstaller), `uv sync` creates and populates `.venv`, and
`uv run <cmd>` runs inside it without needing to activate anything. This
sidesteps Debian/Ubuntu's PEP 668 externally-managed-environment restriction
on bare `pip install` too.

Run a single test: `uv run pytest tests/test_cache.py::test_force_refresh_bypasses_cache -q`

CLI flags: `--config PATH`, `--refresh` (bypass cache), `--json`.

## Architecture

Pipeline: `b2_client` (raw HTTP) → `stats.collect` (orchestration) →
`cache.get_or_fetch` (TTL wrapper) → a front end (`cli.py` / `tray.py`) that
renders `stats.format_table`.

- **`b2_client.py`** — thin wrapper over the B2 native API v2
  (`b2_authorize_account`, `b2_list_buckets`, `b2_list_file_names`,
  `b2_list_file_versions`). `iter_file_names` paginates current/latest file
  versions only; `iter_file_versions` paginates *every* stored version
  (including hidden/deleted markers) — both are needed because B2 has no
  single call that returns bucket size.
- **`pricing.py`** — hardcoded, dated/sourced pricing constant
  (`PRICE_PER_GB_MONTH`) and `estimate_monthly_cost()`. Deliberately
  storage-only; download/egress and transaction charges aren't retrievable
  from this API and are documented as excluded, not silently ignored.
- **`stats.py`** — `BucketStats` dataclass and `collect(config)`, which ties
  `b2_client` + `pricing` together. Whether `total_bytes_incl_versions`
  equals `current_bytes` or a full version-history sum depends on
  `config.include_all_versions`. Also owns `human_size()` and
  `format_table()` — the single table-rendering helper shared by both the
  CLI and the tray popup, so they always render identically.
- **`cache.py`** — reads/writes a JSON file (`{fetched_at_epoch, buckets}`)
  next to the config file, keyed by TTL (`cache_ttl_minutes`). This exists
  because listing every file/version in a bucket is a paginated, rate-limited
  operation (B2 "Class C" transactions) — the tray app must not re-scan
  every bucket on every click.
- **`config.py`** — `load_config()` resolves the config file through a
  fallback chain when `--config`/`B2_STATS_CONFIG` isn't given: program
  directory → current directory → `~/.config/b2-stats/` (or
  `%APPDATA%\b2-stats\` on Windows) → `~/.b2-stats/`. If nothing is found,
  the error lists every path checked and links Backblaze's app-key docs —
  preserve that behavior (and the link) if you touch this function; don't
  collapse it back to a single default path.
- **`cli.py` / `tray.py`** — front ends. `tray.py` runs `pystray.Icon` in a
  background thread and `tkinter` on the main thread, communicating via a
  `queue.Queue` (`_action_queue`) polled with `root.after` — tkinter is not
  thread-safe, so menu callbacks from pystray's thread must never touch Tk
  widgets directly.

### Testing patterns

- Shared fixtures (`fake_auth`, `fake_buckets`, `fake_current_files`,
  `fake_all_versions`) live in `tests/conftest.py` — reuse them instead of
  redefining bucket/file fixtures per test file.
- Tests mock at the point of use: `b2_client.py` calls are patched via
  `mock.patch.object(b2_client, "authorize"/"list_buckets"/"iter_file_names"/
  "iter_file_versions", ...)`, and its HTTP layer via
  `mock.patch("b2_stats.b2_client.requests.get"/"...post", ...)` — not by
  patching `requests` globally.
- `config.py` exposes `program_dir()`, `home_config_dir()`, and
  `home_dotfile_dir()` as standalone functions (rather than inlining them
  into `fallback_search_paths()`) specifically so tests can
  `monkeypatch.setattr(config_module, ...)` each one to deterministically
  test the fallback chain without touching the real filesystem/HOME.

### Windows packaging gotchas (both fixed already, don't regress)

- PyInstaller is pointed at **`scripts/tray_entry.py`**, not
  `b2_stats/tray.py` directly — PyInstaller treats its entry file as a
  top-level script, which breaks `tray.py`'s relative imports
  (`from . import cache`). The wrapper does an absolute
  `from b2_stats.tray import main` instead.
- The build passes **`--collect-all pystray`** — pystray picks its platform
  backend (e.g. `pystray._win32`) via a runtime `importlib.import_module()`
  call that PyInstaller's static analysis can't see, so without this flag
  the backend silently isn't bundled and the built exe crashes with
  `ModuleNotFoundError` on launch.
- PyInstaller cannot cross-compile: `scripts/build_windows.py` refuses to
  run unless `sys.platform == "win32"`. Build either on a real Windows
  machine (`uv sync --extra build && uv run python scripts/build_windows.py`),
  or via `.github/workflows/build-windows.yml` (runs on `windows-latest`,
  triggered by a `v*` tag push or manual dispatch, using `astral-sh/setup-uv`).
- The tray icon (`b2_stats/assets/backblaze_mark.png`) is a non-Python data
  file, so it needs `--add-data` (`scripts/build_windows.py`) to end up in
  the frozen exe, and `[tool.setuptools.package-data]` (`pyproject.toml`) to
  end up in an installed wheel. `tray._asset_path()` resolves it via
  `sys._MEIPASS` when frozen — deliberately not `importlib.resources`, whose
  resource reader doesn't reliably support PyInstaller's onefile archive
  loader.
