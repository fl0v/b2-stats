from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

APP_NAME = "b2-stats"

APP_KEYS_URL = "https://secure.backblaze.com/app_keys.htm"
APP_KEYS_GUIDE_URL = "https://www.backblaze.com/docs/cloud-storage-create-and-manage-app-keys"


@dataclass
class Config:
    application_key_id: str
    application_key: str
    cache_ttl_minutes: int
    include_all_versions: bool
    cache_path: Path


def program_dir() -> Path:
    """Directory containing the running script or (when frozen) .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    try:
        return Path(sys.argv[0]).resolve().parent
    except (IndexError, OSError):
        return Path.cwd()


def home_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def home_dotfile_dir() -> Path:
    return Path.home() / f".{APP_NAME}"


def default_config_path() -> Path:
    """The recommended location to put config.yaml (used in help text)."""
    return home_config_dir() / "config.yaml"


def fallback_search_paths() -> list[Path]:
    """Locations checked, in order, when no --config/env override is given."""
    candidates = [
        program_dir() / "config.yaml",
        Path.cwd() / "config.yaml",
        home_config_dir() / "config.yaml",
        home_dotfile_dir() / "config.yaml",
    ]
    seen: set[Path] = set()
    unique: list[Path] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def explicit_or_env_path(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    env_path = os.environ.get("B2_STATS_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    return None


def _missing_config_message(checked: list[Path]) -> str:
    checked_lines = "\n".join(f"  - {p}" for p in checked)
    return (
        f"No config file found. Checked:\n"
        f"{checked_lines}\n"
        f"\n"
        f"To fix this:\n"
        f"  1. Copy config.example.yaml to one of the paths above (recommended: "
        f"{default_config_path()}).\n"
        f"  2. Edit it, filling in your B2 application_key_id and application_key.\n"
        f"\n"
        f"Need an application key? Create one at:\n"
        f"  {APP_KEYS_URL}\n"
        f"Backblaze's guide on creating & managing application keys:\n"
        f"  {APP_KEYS_GUIDE_URL}\n"
    )


def load_config(explicit_path: str | None = None) -> Config:
    override = explicit_or_env_path(explicit_path)
    if override is not None:
        path = override
        if not path.is_file():
            raise FileNotFoundError(_missing_config_message([path]))
    else:
        candidates = fallback_search_paths()
        path = next((c for c in candidates if c.is_file()), None)
        if path is None:
            raise FileNotFoundError(_missing_config_message(candidates))

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
