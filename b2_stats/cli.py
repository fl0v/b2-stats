from __future__ import annotations

import argparse
import json
import sys

from . import cache
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="b2-stats",
        description="Show per-bucket usage and estimated cost for Backblaze B2.",
        epilog=(
            "Without --config, looks for config.yaml next to the program, in the "
            "current directory, then in ~/.config/b2-stats/ (or %APPDATA%\\b2-stats\\ "
            "on Windows), then in ~/.b2-stats/."
        ),
    )
    parser.add_argument("--config", metavar="PATH", help="Path to config.yaml")
    parser.add_argument(
        "--refresh", action="store_true", help="Bypass the cache and re-fetch from B2"
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Print machine-readable JSON"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1

    from . import b2_client

    if args.refresh or not cache.is_fresh(config):
        print("Fetching B2 stats (scanning buckets)... this may take a while.", file=sys.stderr)

    try:
        bucket_stats, fetched_at, was_cached = cache.get_or_fetch(config, force=args.refresh)
    except b2_client.B2Error as e:
        print(f"B2 API error: {e}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(
            {
                "fetched_at": fetched_at,
                "cached": was_cached,
                "buckets": [b.to_dict() for b in bucket_stats],
            },
            indent=2,
        ))
    else:
        from . import stats as stats_module

        print(stats_module.format_table(bucket_stats, fetched_at))

    return 0


if __name__ == "__main__":
    sys.exit(main())
