from __future__ import annotations

import pytest

from b2_stats import config as config_module


def write_config(path, extra: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "application_key_id: keyid123\n"
        "application_key: secretkey456\n"
        + extra
    )


def test_load_config_missing_everywhere_raises_with_help(tmp_path, monkeypatch):
    monkeypatch.delenv("B2_STATS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "program_dir", lambda: tmp_path / "prog")
    monkeypatch.setattr(config_module, "home_config_dir", lambda: tmp_path / "home-config")
    monkeypatch.setattr(config_module, "home_dotfile_dir", lambda: tmp_path / "home-dotfile")

    with pytest.raises(FileNotFoundError) as excinfo:
        config_module.load_config()

    message = str(excinfo.value)
    assert "No config file found" in message
    assert "app_keys.htm" in message
    assert "cloud-storage-create-and-manage-app-keys" in message


def test_load_config_explicit_path_missing_raises(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    with pytest.raises(FileNotFoundError) as excinfo:
        config_module.load_config(str(missing))
    assert str(missing) in str(excinfo.value)


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


def test_explicit_or_env_path_prefers_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("B2_STATS_CONFIG", str(tmp_path / "env.yaml"))
    resolved = config_module.explicit_or_env_path(str(tmp_path / "explicit.yaml"))
    assert resolved == tmp_path / "explicit.yaml"


def test_explicit_or_env_path_uses_env_when_no_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("B2_STATS_CONFIG", str(tmp_path / "env.yaml"))
    resolved = config_module.explicit_or_env_path(None)
    assert resolved == tmp_path / "env.yaml"


def test_explicit_or_env_path_none_when_neither_set(monkeypatch):
    monkeypatch.delenv("B2_STATS_CONFIG", raising=False)
    assert config_module.explicit_or_env_path(None) is None


def test_fallback_search_paths_order_and_dedup(monkeypatch, tmp_path):
    same_dir = tmp_path / "same"
    monkeypatch.setattr(config_module, "program_dir", lambda: same_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "home_config_dir", lambda: tmp_path / "home-config")
    monkeypatch.setattr(config_module, "home_dotfile_dir", lambda: tmp_path / "home-dotfile")

    paths = config_module.fallback_search_paths()

    assert paths == [
        same_dir / "config.yaml",
        tmp_path / "config.yaml",
        tmp_path / "home-config" / "config.yaml",
        tmp_path / "home-dotfile" / "config.yaml",
    ]


def test_fallback_search_paths_finds_program_dir_config(monkeypatch, tmp_path):
    prog_dir = tmp_path / "portable"
    write_config(prog_dir / "config.yaml")
    monkeypatch.setattr(config_module, "program_dir", lambda: prog_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "home_config_dir", lambda: tmp_path / "home-config")
    monkeypatch.setattr(config_module, "home_dotfile_dir", lambda: tmp_path / "home-dotfile")

    cfg = config_module.load_config()
    assert cfg.application_key_id == "keyid123"


def test_fallback_search_paths_falls_back_to_dotfile_dir(monkeypatch, tmp_path):
    dotfile_dir = tmp_path / "home-dotfile"
    write_config(dotfile_dir / "config.yaml")
    monkeypatch.setattr(config_module, "program_dir", lambda: tmp_path / "prog")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "home_config_dir", lambda: tmp_path / "home-config")
    monkeypatch.setattr(config_module, "home_dotfile_dir", lambda: dotfile_dir)

    cfg = config_module.load_config()
    assert cfg.application_key_id == "keyid123"
