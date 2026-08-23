from __future__ import annotations

import pytest

from b2_stats import b2_client


@pytest.fixture
def fake_auth() -> b2_client.AuthContext:
    return b2_client.AuthContext(account_id="acc123", api_url="https://fake.example", auth_token="tok123")


@pytest.fixture
def fake_buckets() -> list[b2_client.Bucket]:
    return [
        b2_client.Bucket(bucket_id="b1", bucket_name="backups", bucket_type="allPrivate"),
        b2_client.Bucket(bucket_id="b2", bucket_name="photos", bucket_type="allPrivate"),
    ]


@pytest.fixture
def fake_current_files() -> dict[str, list[b2_client.FileEntry]]:
    return {
        "b1": [
            b2_client.FileEntry("a.zip", 5 * 1024**3, "upload"),
            b2_client.FileEntry("b.zip", 2 * 1024**3, "upload"),
        ],
        "b2": [
            b2_client.FileEntry("p1.jpg", 100 * 1024**2, "upload"),
        ],
    }


@pytest.fixture
def fake_all_versions(fake_current_files) -> dict[str, list[b2_client.FileEntry]]:
    """b2_list_file_versions groups all versions of the same file name together,
    newest first - mirrored here so tests exercise the real ordering."""
    return {
        "b1": [
            b2_client.FileEntry("a.zip", 5 * 1024**3, "upload"),
            b2_client.FileEntry("a.zip", 1 * 1024**3, "upload"),
            b2_client.FileEntry("b.zip", 2 * 1024**3, "upload"),
        ],
        "b2": fake_current_files["b2"],
    }
