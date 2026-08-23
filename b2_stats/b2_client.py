"""Thin wrapper around the Backblaze B2 native API (v2).

Docs: https://www.backblaze.com/apidocs/introduction-to-the-b2-native-api

There is no endpoint that reports bucket size or account cost directly —
size has to be derived by paginating through every file (and, optionally,
every file version) in a bucket and summing contentLength.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import requests

AUTH_URL = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
API_VERSION = "v2"
PAGE_SIZE = 10_000


class B2Error(RuntimeError):
    pass


@dataclass
class AuthContext:
    account_id: str
    api_url: str
    auth_token: str


@dataclass
class Bucket:
    bucket_id: str
    bucket_name: str
    bucket_type: str


@dataclass
class FileEntry:
    file_name: str
    content_length: int
    action: str


def authorize(key_id: str, application_key: str) -> AuthContext:
    resp = requests.get(AUTH_URL, auth=(key_id, application_key), timeout=30)
    if resp.status_code != 200:
        raise B2Error(f"b2_authorize_account failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    return AuthContext(
        account_id=data["accountId"],
        api_url=data["apiUrl"],
        auth_token=data["authorizationToken"],
    )


def _post(auth: AuthContext, endpoint: str, body: dict) -> dict:
    url = f"{auth.api_url}/b2api/{API_VERSION}/{endpoint}"
    resp = requests.post(
        url,
        json=body,
        headers={"Authorization": auth.auth_token},
        timeout=60,
    )
    if resp.status_code != 200:
        raise B2Error(f"{endpoint} failed ({resp.status_code}): {resp.text}")
    return resp.json()


def list_buckets(auth: AuthContext) -> list[Bucket]:
    data = _post(auth, "b2_list_buckets", {"accountId": auth.account_id})
    return [
        Bucket(
            bucket_id=b["bucketId"],
            bucket_name=b["bucketName"],
            bucket_type=b.get("bucketType", "unknown"),
        )
        for b in data["buckets"]
    ]


def iter_file_names(auth: AuthContext, bucket_id: str) -> Iterator[FileEntry]:
    """Current (latest, non-hidden) version of every file in the bucket."""
    start_file_name = None
    while True:
        body = {"bucketId": bucket_id, "maxFileCount": PAGE_SIZE}
        if start_file_name is not None:
            body["startFileName"] = start_file_name
        data = _post(auth, "b2_list_file_names", body)
        for f in data["files"]:
            yield FileEntry(
                file_name=f["fileName"],
                content_length=f.get("contentLength", 0) or 0,
                action=f.get("action", "upload"),
            )
        start_file_name = data.get("nextFileName")
        if not start_file_name:
            break


def iter_file_versions(auth: AuthContext, bucket_id: str) -> Iterator[FileEntry]:
    """Every stored version of every file, including hidden/deleted markers."""
    start_file_name = None
    start_file_id = None
    while True:
        body = {"bucketId": bucket_id, "maxFileCount": PAGE_SIZE}
        if start_file_name is not None:
            body["startFileName"] = start_file_name
        if start_file_id is not None:
            body["startFileId"] = start_file_id
        data = _post(auth, "b2_list_file_versions", body)
        for f in data["files"]:
            yield FileEntry(
                file_name=f["fileName"],
                content_length=f.get("contentLength", 0) or 0,
                action=f.get("action", "upload"),
            )
        start_file_name = data.get("nextFileName")
        start_file_id = data.get("nextFileId")
        if not start_file_name:
            break
