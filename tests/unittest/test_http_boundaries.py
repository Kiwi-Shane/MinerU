# Copyright (c) Opendatalab. All rights reserved.

import asyncio
from pathlib import Path
from typing import Any

import pytest

from mineru.cli import api_client
from mineru.data.io import http as http_io


class _FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"payload") -> None:
        self.status_code = status_code
        self.content = content


def test_http_reader_uses_explicit_timeout_and_does_not_follow_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
        calls.update(url=url, kwargs=kwargs)
        return _FakeResponse(content=b"reader payload")

    monkeypatch.setattr(http_io.requests, "get", fake_get)

    assert http_io.HttpReader(timeout=12.5).read("https://source.example/report.pdf") == (
        b"reader payload"
    )
    assert calls == {
        "url": "https://source.example/report.pdf",
        "kwargs": {"timeout": 12.5, "allow_redirects": False},
    }


def test_http_writer_uses_explicit_timeout_and_does_not_follow_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        calls.update(url=url, kwargs=kwargs)
        return _FakeResponse(status_code=204)

    monkeypatch.setattr(http_io.requests, "post", fake_post)

    http_io.HttpWriter(timeout=17.25).write(
        "https://destination.example/upload",
        b"writer payload",
    )

    uploaded = calls["kwargs"]["files"]["file"]
    assert uploaded.read() == b"writer payload"
    assert calls["url"] == "https://destination.example/upload"
    assert calls["kwargs"]["timeout"] == 17.25
    assert calls["kwargs"]["allow_redirects"] is False


def test_httpx_client_factories_disable_redirect_following() -> None:
    sync_client = api_client.build_sync_http_client()
    try:
        assert sync_client.follow_redirects is False
    finally:
        sync_client.close()

    async_client = api_client.build_async_http_client()
    try:
        assert async_client.follow_redirects is False
    finally:
        asyncio.run(async_client.aclose())


def test_cli_modules_do_not_enable_implicit_redirect_following() -> None:
    project_root = Path(__file__).resolve().parents[2]
    for relative_path in (
        "mineru/cli/api_client.py",
        "mineru/cli/client.py",
        "mineru/cli/gradio_app.py",
        "mineru/cli/router.py",
    ):
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "follow_redirects=True" not in source, relative_path
