# Copyright (c) Opendatalab. All rights reserved.

import json
import os
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from mineru.cli import models_download
from mineru.utils import models_download_utils as model_utils


class _FakeJsonResponse:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.status_code = 200
        self._payload = payload or {"config_version": "1.3.2"}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _clear_model_download_caches() -> None:
    model_utils._resolve_auto_model_source_cached.cache_clear()
    model_utils._snapshot_download_cached_impl.cache_clear()


def test_existing_configured_model_path_does_not_probe_or_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_root = tmp_path / "models"
    (model_root / "weights").mkdir(parents=True)
    config_path = tmp_path / "mineru.json"
    config_path.write_text(
        json.dumps({"models-dir": {"pipeline": str(model_root)}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MINERU_TOOLS_CONFIG_JSON", str(config_path))
    monkeypatch.delenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, raising=False)
    monkeypatch.delenv(model_utils.MINERU_OFFLINE_ENV_VAR, raising=False)

    def unexpected_resolution() -> str:
        raise AssertionError("configured local model path must not resolve a remote source")

    monkeypatch.setattr(model_utils, "resolve_model_source", unexpected_resolution)

    assert model_utils.auto_download_and_get_model_root_path("weights", "pipeline") == str(model_root)


def test_missing_model_fails_closed_before_remote_snapshot_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, raising=False)
    monkeypatch.delenv(model_utils.MINERU_OFFLINE_ENV_VAR, raising=False)
    monkeypatch.setattr(model_utils, "resolve_model_source", lambda: "huggingface")

    def unexpected_snapshot(*_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("remote snapshot download must be blocked by default")

    monkeypatch.setattr(model_utils, "_snapshot_download_cached", unexpected_snapshot)

    with pytest.raises(RuntimeError, match="model downloads are disabled by default"):
        model_utils.auto_download_and_get_model_root_path(
            "missing/weights",
            "pipeline",
        )


def test_auto_source_probe_fails_closed_without_download_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, raising=False)
    monkeypatch.delenv(model_utils.MINERU_OFFLINE_ENV_VAR, raising=False)
    _clear_model_download_caches()

    with pytest.raises(RuntimeError, match="model downloads are disabled by default"):
        model_utils.resolve_auto_model_source()


def test_auto_source_probe_uses_timeout_and_does_not_follow_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, "1")
    monkeypatch.delenv(model_utils.MINERU_OFFLINE_ENV_VAR, raising=False)
    _clear_model_download_caches()
    calls: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> _FakeJsonResponse:
        calls.update(url=url, kwargs=kwargs)
        return _FakeJsonResponse()

    monkeypatch.setattr(model_utils.requests, "get", fake_get)

    assert model_utils.resolve_auto_model_source() == "huggingface"
    assert calls == {
        "url": model_utils.HUGGINGFACE_MODELS_PAGE_URL,
        "kwargs": {
            "timeout": model_utils.HUGGINGFACE_MODELS_PAGE_TIMEOUT,
            "allow_redirects": False,
        },
    }


def test_offline_mode_overrides_explicit_download_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, "1")
    monkeypatch.setenv(model_utils.MINERU_OFFLINE_ENV_VAR, "1")

    with pytest.raises(RuntimeError, match="offline mode"):
        model_utils.ensure_model_download_allowed()


def test_config_template_fetch_has_timeout_and_no_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, "1")
    calls: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> _FakeJsonResponse:
        calls.update(url=url, kwargs=kwargs)
        return _FakeJsonResponse()

    monkeypatch.setattr(model_utils.requests, "get", fake_get)

    assert model_utils.download_json("https://config.example/mineru.json") == {
        "config_version": "1.3.2"
    }
    assert calls == {
        "url": "https://config.example/mineru.json",
        "kwargs": {
            "timeout": model_utils.DEFAULT_MODEL_HTTP_TIMEOUT_SECONDS,
            "allow_redirects": False,
        },
    }


def test_model_download_cli_grants_only_temporary_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR, raising=False)
    observed: list[bool] = []

    def fake_effective_source(requested_source: str) -> str:
        assert requested_source == "huggingface"
        observed.append(os.getenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR) == "1")
        return "huggingface"

    def fake_download(_model_source: str) -> None:
        observed.append(os.getenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR) == "1")

    monkeypatch.setattr(
        models_download,
        "get_effective_download_model_source",
        fake_effective_source,
    )
    monkeypatch.setattr(models_download, "download_pipeline_models", fake_download)

    result = CliRunner().invoke(
        models_download.download_models,
        ["--source", "huggingface", "--model_type", "pipeline"],
    )

    assert result.exit_code == 0, result.output
    assert observed == [True, True]
    assert os.getenv(model_utils.MODEL_DOWNLOAD_ENABLED_ENV_VAR) is None
