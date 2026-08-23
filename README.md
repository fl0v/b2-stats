# b2-stats

Usage and estimated-cost stats for Backblaze B2 buckets — a console script
and a system-tray app.

Backblaze's B2 API has no billing endpoint, so **cost is an estimate**
computed from actual stored bytes (summed by paginating every file in every
bucket) against B2's published storage price. It does not include
download/egress or transaction charges, and won't match your invoice
exactly — treat it as a directional number.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
cp config.example.yaml ~/.config/b2-stats/config.yaml   # Linux/macOS
# or copy to %APPDATA%\b2-stats\config.yaml on Windows
```

Or, on Linux/macOS, use the Makefile: `make install` (CLI/tray deps only) or
`make dev-install` (adds pytest).

Edit that config file with an application key from
https://secure.backblaze.com/app_keys.htm (a read-only key with
`listFiles` + `listBuckets` is enough).

## CLI

```bash
b2-stats                 # table of buckets, sizes, estimated cost
b2-stats --refresh       # bypass the cache and re-fetch from B2
b2-stats --json          # machine-readable output
b2-stats --config /path/to/config.yaml
```

## Tray app

```bash
b2-stats-tray
```

Puts an icon in the system tray. Click it (or use the menu) to open a
window with the same stats table as the CLI. It reuses the cache
(`cache_ttl_minutes` in the config, default 6 hours) so opening the popup
doesn't re-scan every bucket each time — use "Refresh" in the menu to force
a re-fetch.

## Tests

```bash
make test          # or: .venv/bin/pytest -q
```

All tests mock the B2 HTTP API (`requests`) — no real credentials or network
access are needed to run them.

## Building the Windows .exe

PyInstaller can't cross-compile a Windows binary from Linux, so build it
either:

- on an actual Windows machine: `pip install pyinstaller`, then
  `python scripts/build_windows.py` (output in `dist/b2-stats-tray.exe`), or
- via GitHub Actions: push a `v*` tag, or run the "Build Windows tray app"
  workflow manually — it uploads `b2-stats-tray.exe` as a build artifact.

## Notes / limitations

- Listing every file version in large buckets uses B2 "Class C"
  transactions (list operations); there's a free daily allowance, but very
  large buckets could exceed it. The cache exists to avoid re-scanning on
  every tray click.
- `include_all_versions: true` (default) sums every stored version of every
  file, matching what you're actually billed for if you keep old versions.
  Set it to `false` to count only current/latest versions.
