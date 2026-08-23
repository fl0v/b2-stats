from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import stats as stats_module
from .config import Config


def _read_cache(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(path: Path, fetched_at_epoch: float, bucket_stats: list[stats_module.BucketStats]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at_epoch": fetched_at_epoch,
        "buckets": [b.to_dict() for b in bucket_stats],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _to_bucket_stats(raw: list[dict]) -> list[stats_module.BucketStats]:
    return [stats_module.BucketStats(**b) for b in raw]


def is_fresh(config: Config) -> bool:
    """True if a cache file exists and is within its TTL (i.e. get_or_fetch(force=False)
    would return instantly without hitting the B2 API)."""
    cached = _read_cache(config.cache_path)
    if cached is None:
        return False
    age_minutes = (time.time() - cached["fetched_at_epoch"]) / 60
    return age_minutes <= config.cache_ttl_minutes


def get_or_fetch(config: Config, force: bool = False) -> tuple[list[stats_module.BucketStats], str, bool]:
    """Returns (bucket_stats, fetched_at_iso, was_cached)."""
    now = time.time()
    if not force:
        cached = _read_cache(config.cache_path)
        if cached is not None:
            age_minutes = (now - cached["fetched_at_epoch"]) / 60
            if age_minutes <= config.cache_ttl_minutes:
                fetched_at = datetime.fromtimestamp(
                    cached["fetched_at_epoch"], tz=timezone.utc
                ).isoformat(timespec="seconds")
                return _to_bucket_stats(cached["buckets"]), fetched_at, True

    bucket_stats = stats_module.collect(config)
    _write_cache(config.cache_path, now, bucket_stats)
    fetched_at = datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds")
    return bucket_stats, fetched_at, False
