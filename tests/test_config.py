from __future__ import annotations

import pytest

from b2_stats import config as config_module


def write_config(path, extra: str = ""):
    path.write_text(
        "application_key_id: keyid123\n"
        "application_key: secretkey456\n"
        + extra
    )


def test_load_config_missing_file_raises(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    with pytest.raises(FileNotFoundError):
        config_module.load_config(str(missing))


def test_load_config_missing_required_field_raises(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("application_key_id: keyid123\n")
    with pytest.raises(ValueError):
        config_module.load_config(str(path))


def test_load_config_applies_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    write_config(path)
    cfg = config_module.load_config(str(path))

    assert cfg.application_key_id == "keyid123"
    assert cfg.application_key == "secretkey456"
    assert cfg.cache_ttl_minutes == 360
    assert cfg.include_all_versions is True
    assert cfg.cache_path == path.parent / "cache.json"


def test_load_config_overrides(tmp_path):
    path = tmp_path / "config.yaml"
    write_config(path, "cache_ttl_minutes: 15\ninclude_all_versions: false\n")
    cfg = config_module.load_config(str(path))

    assert cfg.cache_ttl_minutes == 15
    assert cfg.include_all_versions is False


def test_resolve_config_path_prefers_explicit_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("B2_STATS_CONFIG", str(tmp_path / "env.yaml"))
    resolved = config_module.resolve_config_path(str(tmp_path / "explicit.yaml"))
    assert resolved == tmp_path / "explicit.yaml"


def test_resolve_config_path_uses_env_when_no_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("B2_STATS_CONFIG", str(tmp_path / "env.yaml"))
    resolved = config_module.resolve_config_path(None)
    assert resolved == tmp_path / "env.yaml"


def test_resolve_config_path_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("B2_STATS_CONFIG", raising=False)
    resolved = config_module.resolve_config_path(None)
    assert resolved == config_module.default_config_path()
