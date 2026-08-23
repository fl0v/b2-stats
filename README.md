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
```

Or, on Linux/macOS, use the Makefile: `make install` (CLI/tray deps only) or
`make dev-install` (adds pytest).

Then copy `config.example.yaml` to one of the locations below and fill in
an application key.

### Config file location

Unless you pass `--config PATH` (or set `B2_STATS_CONFIG`), both the CLI and
the tray app look for `config.yaml` in this order, using the first one that
exists:

1. Next to the running program (the folder containing `b2-stats-tray.exe`,
   handy for a portable install)
2. The current directory
3. `~/.config/b2-stats/config.yaml` (or `%APPDATA%\b2-stats\config.yaml` on
   Windows) — the recommended location
4. `~/.b2-stats/config.yaml`

If none of those exist, both apps print exactly which paths they checked
and how to fix it.

### Getting an application key

Create one at https://secure.backblaze.com/app_keys.htm — a read-only key
scoped to `listFiles` + `listBuckets` is enough. Backblaze's guide:
https://www.backblaze.com/docs/cloud-storage-create-and-manage-app-keys

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
