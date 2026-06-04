"""Tests del compresor HAR (Sprint 2.4-HF6)."""
import json

import pytest

from app.services.engine.har_compressor import (
    _canonical_url,
    _entry_fingerprint,
    _is_static_asset,
    _is_tracking,
    _should_keep_header,
    compress_har,
)


def test_detecta_assets_estaticos():
    assert _is_static_asset("https://example.com/style.css")
    assert _is_static_asset("https://example.com/logo.png")
    assert _is_static_asset("https://cdn.example.com/font.woff2")
    assert _is_static_asset("https://example.com/script.js")
    assert not _is_static_asset("https://api.example.com/users")
    # data.json without static extension is a real API; not flagged
    assert not _is_static_asset("https://api.example.com/data/users")


def test_detecta_tracking():
    assert _is_tracking("https://www.google-analytics.com/collect")
    assert _is_tracking("https://www.googletagmanager.com/gtm.js")
    assert _is_tracking("https://www.facebook.com/tr/?ev=PageView")
    assert _is_tracking("https://stats.hotjar.com/v6/track")
    assert not _is_tracking("https://api.miempresa.com/users")


def test_filtra_headers_de_ruido():
    assert not _should_keep_header("cookie")
    assert not _should_keep_header("Cookie")
    assert not _should_keep_header("sec-ch-ua")
    assert not _should_keep_header("user-agent")
    assert not _should_keep_header("accept-encoding")
    assert _should_keep_header("authorization")
    assert _should_keep_header("content-type")
    assert _should_keep_header("Content-Type")
    assert _should_keep_header("x-api-key")


def test_canonical_url_remueve_query_dinamico():
    u1 = _canonical_url("https://api.example.com/users?_=1234567890")
    u2 = _canonical_url("https://api.example.com/users?_=9999999999")
    assert u1 == u2


def test_fingerprint_detecta_duplicados():
    entry1 = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/login?t=1",
            "postData": {"text": '{"user":"x"}'},
        }
    }
    entry2 = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/login?t=2",
            "postData": {"text": '{"user":"x"}'},
        }
    }
    entry3 = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/login?t=1",
            "postData": {"text": '{"user":"y"}'},
        }
    }
    assert _entry_fingerprint(entry1) == _entry_fingerprint(entry2)
    assert _entry_fingerprint(entry1) != _entry_fingerprint(entry3)


def test_compress_har_basico():
    """HAR con asset + tracking + duplicado debe filtrar y deduplicar."""
    har = {
        "log": {
            "version": "1.2",
            "creator": {"name": "test"},
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/login",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                            {"name": "Cookie", "value": "session=abc"},
                            {"name": "User-Agent", "value": "Mozilla..."},
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": '{"u":"x"}',
                        },
                    },
                    "response": {"status": 200, "statusText": "OK", "content": {}},
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://cdn.example.com/style.css",
                        "headers": [],
                    },
                    "response": {"status": 200, "statusText": "OK", "content": {}},
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "https://www.google-analytics.com/collect",
                        "headers": [],
                    },
                    "response": {"status": 200, "statusText": "OK", "content": {}},
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/login?_=999",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": '{"u":"x"}',
                        },
                    },
                    "response": {"status": 200, "statusText": "OK", "content": {}},
                },
            ],
        }
    }
    har_content = json.dumps(har)
    compressed, stats = compress_har(har_content)

    assert stats["entries_original"] == 4
    assert stats["entries_static_filtered"] == 1
    assert stats["entries_tracking_filtered"] == 1
    assert stats["entries_unique"] == 1
    assert stats["compressed_size"] < stats["original_size"]

    result = json.loads(compressed)
    assert len(result["log"]["entries"]) == 1

    entry = result["log"]["entries"][0]
    assert entry.get("_duplicate_count") == 2

    headers = entry["request"]["headers"]
    header_names = [h["name"].lower() for h in headers]
    assert "cookie" not in header_names
    assert "user-agent" not in header_names
    assert "content-type" in header_names


def test_compress_har_invalido_lanza_error():
    with pytest.raises(ValueError):
        compress_har("esto no es JSON")


def test_compress_har_trunca_bodies_grandes():
    big_body = "x" * 5000
    har = {
        "log": {
            "version": "1.2",
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/upload",
                        "headers": [],
                        "postData": {"mimeType": "text/plain", "text": big_body},
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "content": {},
                    },
                }
            ],
        }
    }
    compressed, _ = compress_har(json.dumps(har))
    result = json.loads(compressed)
    body = result["log"]["entries"][0]["request"]["postData"]["text"]
    assert len(body) < 5000
    assert "truncado" in body
