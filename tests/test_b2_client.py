from __future__ import annotations

from unittest import mock

import pytest

from b2_stats import b2_client


def _response(status_code=200, json_data=None, text=""):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def test_authorize_success():
    ok_response = _response(200, {
        "accountId": "acc1",
        "apiUrl": "https://api000.example.com",
        "authorizationToken": "tok1",
    })
    with mock.patch("b2_stats.b2_client.requests.get", return_value=ok_response) as get_mock:
        auth = b2_client.authorize("keyid", "appkey")

    assert auth == b2_client.AuthContext("acc1", "https://api000.example.com", "tok1")
    args, kwargs = get_mock.call_args
    assert kwargs["auth"] == ("keyid", "appkey")


def test_authorize_failure_raises_b2error():
    bad_response = _response(401, text="unauthorized")
    with mock.patch("b2_stats.b2_client.requests.get", return_value=bad_response):
        with pytest.raises(b2_client.B2Error):
            b2_client.authorize("keyid", "wrongkey")


def test_list_buckets_parses_response(fake_auth):
    resp = _response(200, {
        "buckets": [
            {"bucketId": "b1", "bucketName": "backups", "bucketType": "allPrivate"},
            {"bucketId": "b2", "bucketName": "photos", "bucketType": "allPublic"},
        ]
    })
    with mock.patch("b2_stats.b2_client.requests.post", return_value=resp):
        buckets = b2_client.list_buckets(fake_auth)

    assert buckets == [
        b2_client.Bucket("b1", "backups", "allPrivate"),
        b2_client.Bucket("b2", "photos", "allPublic"),
    ]


def test_post_failure_raises_b2error(fake_auth):
    resp = _response(500, text="server error")
    with mock.patch("b2_stats.b2_client.requests.post", return_value=resp):
        with pytest.raises(b2_client.B2Error):
            b2_client.list_buckets(fake_auth)


def test_iter_file_names_follows_pagination(fake_auth):
    page1 = _response(200, {
        "files": [{"fileName": "a.txt", "contentLength": 10, "action": "upload"}],
        "nextFileName": "b.txt",
    })
    page2 = _response(200, {
        "files": [{"fileName": "b.txt", "contentLength": 20, "action": "upload"}],
        "nextFileName": None,
    })
    with mock.patch("b2_stats.b2_client.requests.post", side_effect=[page1, page2]) as post_mock:
        entries = list(b2_client.iter_file_names(fake_auth, "bucket1"))

    assert entries == [
        b2_client.FileEntry("a.txt", 10, "upload"),
        b2_client.FileEntry("b.txt", 20, "upload"),
    ]
    assert post_mock.call_count == 2
    second_call_body = post_mock.call_args_list[1].kwargs["json"]
    assert second_call_body["startFileName"] == "b.txt"


def test_iter_file_versions_follows_pagination_with_file_id(fake_auth):
    page1 = _response(200, {
        "files": [{"fileName": "a.txt", "contentLength": 10, "action": "upload"}],
        "nextFileName": "a.txt",
        "nextFileId": "fileid2",
    })
    page2 = _response(200, {
        "files": [{"fileName": "a.txt", "contentLength": 5, "action": "hide"}],
        "nextFileName": None,
        "nextFileId": None,
    })
    with mock.patch("b2_stats.b2_client.requests.post", side_effect=[page1, page2]) as post_mock:
        entries = list(b2_client.iter_file_versions(fake_auth, "bucket1"))

    assert entries == [
        b2_client.FileEntry("a.txt", 10, "upload"),
        b2_client.FileEntry("a.txt", 5, "hide"),
    ]
    second_call_body = post_mock.call_args_list[1].kwargs["json"]
    assert second_call_body["startFileName"] == "a.txt"
    assert second_call_body["startFileId"] == "fileid2"
