#!/usr/bin/env bash
# Runs `b2-stats` via uv, meant to be called from cron.
#
# Cron runs with a minimal environment (no login shell, sparse PATH), so this
# resolves the repo root and the `uv` binary from absolute paths instead of
# assuming either is already on PATH or that the cwd is the repo.
#
# Example crontab entry (refresh the cache every 6 hours, log to a file):
#   0 */6 * * * /path/to/b2-stats/scripts/cron_run_cli.sh >> /var/log/b2-stats.log 2>&1
#
# Any arguments are forwarded to `b2-stats` as-is, e.g. to force a refresh or
# point at a specific config:
#   scripts/cron_run_cli.sh --refresh --config /etc/b2-stats/config.yaml
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ -n "${UV_BIN:-}" ]; then
    uv_bin="$UV_BIN"
elif command -v uv >/dev/null 2>&1; then
    uv_bin="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
    uv_bin="$HOME/.local/bin/uv"
elif [ -x "/usr/local/bin/uv" ]; then
    uv_bin="/usr/local/bin/uv"
else
    echo "cron_run_cli.sh: uv not found on PATH, in \$HOME/.local/bin, or /usr/local/bin." >&2
    echo "Install uv, or set UV_BIN=/full/path/to/uv." >&2
    exit 1
fi

"$uv_bin" sync --quiet
exec "$uv_bin" run b2-stats "$@"
