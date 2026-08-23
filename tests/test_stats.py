from __future__ import annotations

from unittest import mock

import pytest

from b2_stats import b2_client, stats
from b2_stats.config import Config


@pytest.mark.parametrize(
    "num_bytes, expected",
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.00 KB"),
        (5 * 1024**3, "5.00 GB"),
        (2 * 1024**4, "2.00 TB"),
    ],
)
def test_human_size(num_bytes, expected):
    assert stats.human_size(num_bytes) == expected


def test_bucket_stats_dataclass_roundtrip():
    b = stats.BucketStats(
        name="backups",
        file_count=3,
        current_bytes=100,
        total_bytes_incl_versions=150,
        estimated_monthly_cost=0.01,
    )
    d = b.to_dict()
    assert d == {
        "name": "backups",
        "file_count": 3,
        "current_bytes": 100,
        "total_bytes_incl_versions": 150,
        "estimated_monthly_cost": 0.01,
    }
    assert stats.BucketStats(**d) == b


def test_format_table_includes_total_row_and_estimate_disclaimer():
    bucket_stats = [
        stats.BucketStats("backups", 2, 7 * 1024**3, 8 * 1024**3, 0.05),
        stats.BucketStats("photos", 1, 100 * 1024**2, 100 * 1024**2, 0.0),
    ]
    table = stats.format_table(bucket_stats, fetched_at="2026-08-23T21:06:34+00:00")

    assert "backups" in table
    assert "photos" in table
    assert "TOTAL" in table
    assert "3" in table  # total file count
    assert "estimate" in table.lower()
    assert "2026-08-23T21:06:34+00:00" in table


def test_collect_uses_include_all_versions_flag(
    fake_auth, fake_buckets, fake_current_files, fake_all_versions
):
    config = Config(
        application_key_id="id",
        application_key="key",
        cache_ttl_minutes=360,
        include_all_versions=True,
        cache_path=None,
    )

    with mock.patch.object(b2_client, "authorize", return_value=fake_auth), \
         mock.patch.object(
             b2_client, "list_buckets", return_value=fake_buckets), \
         mock.patch.object(
             b2_client, "iter_file_names",
             side_effect=lambda auth, bucket_id: iter(fake_current_files[bucket_id]),
         ) as names_mock, \
         mock.patch.object(
             b2_client, "iter_file_versions",
             side_effect=lambda auth, bucket_id: iter(fake_all_versions[bucket_id]),
         ):
        result = stats.collect(config)

    # current_bytes/file_count must come from the single iter_file_versions pass,
    # not a separate iter_file_names call - see _bucket_stats.
    names_mock.assert_not_called()
    by_name = {b.name: b for b in result}
    assert by_name["backups"].file_count == 2
    assert by_name["backups"].current_bytes == 7 * 1024**3
    assert by_name["backups"].total_bytes_incl_versions == 8 * 1024**3
    assert by_name["photos"].current_bytes == by_name["photos"].total_bytes_incl_versions


def test_collect_excludes_deleted_files_from_current_bytes(fake_auth, fake_buckets):
    config = Config(
        application_key_id="id",
        application_key="key",
        cache_ttl_minutes=360,
        include_all_versions=True,
        cache_path=None,
    )
    versions = {
        "b1": [
            # newest version of doc.txt is a hide marker: file was deleted, so
            # it must not count towards file_count/current_bytes even though
            # older versions still take up storage and count towards the total.
            b2_client.FileEntry("doc.txt", 0, "hide"),
            b2_client.FileEntry("doc.txt", 3 * 1024**3, "upload"),
            b2_client.FileEntry("live.txt", 1 * 1024**3, "upload"),
        ],
        "b2": [],
    }

    with mock.patch.object(b2_client, "authorize", return_value=fake_auth), \
         mock.patch.object(b2_client, "list_buckets", return_value=fake_buckets), \
         mock.patch.object(b2_client, "iter_file_names") as names_mock, \
         mock.patch.object(
             b2_client, "iter_file_versions",
             side_effect=lambda auth, bucket_id: iter(versions[bucket_id]),
         ):
        result = stats.collect(config)

    names_mock.assert_not_called()
    backups = next(b for b in result if b.name == "backups")
    assert backups.file_count == 1
    assert backups.current_bytes == 1 * 1024**3
    assert backups.total_bytes_incl_versions == 4 * 1024**3


def test_collect_current_only_when_versions_disabled(
    fake_auth, fake_buckets, fake_current_files, fake_all_versions
):
    config = Config(
        application_key_id="id",
        application_key="key",
        cache_ttl_minutes=360,
        include_all_versions=False,
        cache_path=None,
    )

    with mock.patch.object(b2_client, "authorize", return_value=fake_auth), \
         mock.patch.object(b2_client, "list_buckets", return_value=fake_buckets), \
         mock.patch.object(
             b2_client, "iter_file_names",
             side_effect=lambda auth, bucket_id: iter(fake_current_files[bucket_id]),
         ), \
         mock.patch.object(
             b2_client, "iter_file_versions",
             side_effect=lambda auth, bucket_id: iter(fake_all_versions[bucket_id]),
         ) as versions_mock:
        result = stats.collect(config)

    versions_mock.assert_not_called()
    by_name = {b.name: b for b in result}
    assert by_name["backups"].total_bytes_incl_versions == by_name["backups"].current_bytes
