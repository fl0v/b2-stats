from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

APP_NAME = "b2-stats"


@dataclass
class Config:
    application_key_id: str
    application_key: str
    cache_ttl_minutes: int
    include_all_versions: bool
    cache_path: Path


def default_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def default_config_path() -> Path:
    return default_config_dir() / "config.yaml"


def resolve_config_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env_path = os.environ.get("B2_STATS_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    return default_config_path()


def load_config(explicit_path: str | None = None) -> Config:
    path = resolve_config_path(explicit_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"No config file found at {path}.\n"
            f"Copy config.example.yaml there (or point --config / "
            f"B2_STATS_CONFIG at your own file) and fill in your B2 "
            f"application key."
        )

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    try:
        key_id = str(raw["application_key_id"])
        key = str(raw["application_key"])
    except KeyError as e:
        raise ValueError(f"Missing required config field: {e.args[0]}") from e

    return Config(
        application_key_id=key_id,
        application_key=key,
        cache_ttl_minutes=int(raw.get("cache_ttl_minutes", 360)),
        include_all_versions=bool(raw.get("include_all_versions", True)),
        cache_path=path.parent / "cache.json",
    )
