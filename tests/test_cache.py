from __future__ import annotations

from unittest import mock

from b2_stats import cache, stats
from b2_stats.config import Config


def make_config(tmp_path, ttl_minutes=360):
    return Config(
        application_key_id="id",
        application_key="key",
        cache_ttl_minutes=ttl_minutes,
        include_all_versions=True,
        cache_path=tmp_path / "cache.json",
    )


def fake_bucket_stats():
    return [stats.BucketStats("backups", 2, 100, 100, 0.01)]


def test_first_call_fetches_and_writes_cache(tmp_path):
    config = make_config(tmp_path)
    with mock.patch.object(stats, "collect", return_value=fake_bucket_stats()) as collect_mock:
        result, fetched_at, was_cached = cache.get_or_fetch(config)

    collect_mock.assert_called_once()
    assert was_cached is False
    assert result == fake_bucket_stats()
    assert config.cache_path.is_file()


def test_second_call_within_ttl_hits_cache(tmp_path):
    config = make_config(tmp_path)
    with mock.patch.object(stats, "collect", return_value=fake_bucket_stats()) as collect_mock:
        cache.get_or_fetch(config)
        result, fetched_at, was_cached = cache.get_or_fetch(config)

    collect_mock.assert_called_once()  # second call must not re-fetch
    assert was_cached is True
    assert result == fake_bucket_stats()


def test_force_refresh_bypasses_cache(tmp_path):
    config = make_config(tmp_path)
    with mock.patch.object(stats, "collect", return_value=fake_bucket_stats()) as collect_mock:
        cache.get_or_fetch(config)
        cache.get_or_fetch(config, force=True)

    assert collect_mock.call_count == 2


def test_expired_cache_triggers_refetch(tmp_path):
    config = make_config(tmp_path, ttl_minutes=0)
    with mock.patch.object(stats, "collect", return_value=fake_bucket_stats()) as collect_mock:
        cache.get_or_fetch(config)
        _result, _fetched_at, was_cached = cache.get_or_fetch(config)

    assert collect_mock.call_count == 2
    assert was_cached is False


def test_corrupt_cache_file_is_ignored(tmp_path):
    config = make_config(tmp_path)
    config.cache_path.parent.mkdir(parents=True, exist_ok=True)
    config.cache_path.write_text("not valid json")

    with mock.patch.object(stats, "collect", return_value=fake_bucket_stats()) as collect_mock:
        result, _fetched_at, was_cached = cache.get_or_fetch(config)

    collect_mock.assert_called_once()
    assert was_cached is False
    assert result == fake_bucket_stats()
