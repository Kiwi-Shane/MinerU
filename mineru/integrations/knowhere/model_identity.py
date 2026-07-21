"""Derive portable model identifiers for the Knowhere manifest adapter."""

from __future__ import annotations

import os
import re
from typing import Any

from mineru.integrations.knowhere.contract import KnowhereExportOptions
from mineru.utils.enum_class import ModelPath
from mineru.utils.models_download_utils import (
    get_configured_repo_model_root,
    read_existing_tools_config,
)


_SNAPSHOT_ID_PATTERN = re.compile(
    r"(?:^|/)snapshots/([0-9a-f]{40})(?:/|$)",
    re.IGNORECASE,
)
_SNAPSHOT_NAME_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)

_REPOSITORIES = {
    "pipeline": {
        "huggingface": "opendatalab/PDF-Extract-Kit-1.0",
        "modelscope": "OpenDataLab/PDF-Extract-Kit-1.0",
    },
    "vlm": {
        "huggingface": "opendatalab/MinerU2.5-Pro-2605-1.2B",
        "modelscope": "OpenDataLab/MinerU2.5-Pro-2605-1.2B",
    },
}


def _declared_model_source(config: dict[str, Any] | None) -> str:
    candidates: list[Any] = [os.getenv("MINERU_MODEL_SOURCE")]
    if config is not None:
        candidates.append(config.get("model-source"))

    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        normalized = candidate.strip().lower()
        if normalized in {"local", "huggingface", "modelscope", "auto"}:
            return normalized
        return "unknown"
    return "unspecified"


def _snapshot_id(model_root: str | None) -> str | None:
    if not isinstance(model_root, str) or not model_root.strip():
        return None
    normalized_root = model_root.replace("\\", "/").rstrip("/")
    match = _SNAPSHOT_ID_PATTERN.search(normalized_root)
    if match is not None:
        return match.group(1).lower()
    leaf = normalized_root.rsplit("/", 1)[-1]
    if _SNAPSHOT_NAME_PATTERN.fullmatch(leaf):
        return leaf.lower()
    return None


def _formula_model_identifier() -> str:
    formula_support = os.getenv("MINERU_FORMULA_CH_SUPPORT", "False")
    if formula_support.strip().lower() in {"true", "1", "yes"}:
        return ModelPath.pp_formulanet_plus_m
    return ModelPath.unimernet_small


def _pipeline_components(options: KnowhereExportOptions) -> dict[str, Any]:
    components: dict[str, Any] = {
        "layout": ModelPath.pp_doclayout_v2,
        "ocr": ModelPath.pytorch_paddle,
    }
    if options.formula_enabled:
        components["formula"] = _formula_model_identifier()
    if options.table_enabled:
        components["table_recognition"] = {
            "wired": ModelPath.unet_structure,
            "wireless": ModelPath.slanet_plus,
        }
        components["table_classification"] = ModelPath.paddle_table_cls
    return components


def _repository_identity(
    *,
    repo_mode: str,
    model_source: str,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    repositories = _REPOSITORIES[repo_mode]
    identity: dict[str, Any] = {}
    if model_source in repositories:
        identity["repository"] = repositories[model_source]
    else:
        identity["repository_aliases"] = dict(repositories)

    snapshot_id = None
    if config is not None:
        snapshot_id = _snapshot_id(
            get_configured_repo_model_root(config, repo_mode)
        )
    if snapshot_id is not None:
        identity["snapshot_id"] = snapshot_id
    identity["snapshot_id_status"] = (
        "resolved" if snapshot_id is not None else "not_resolved"
    )
    return identity


def build_model_identifiers(
    options: KnowhereExportOptions,
    *,
    effective_backend: str,
) -> dict[str, Any]:
    """Return non-sensitive model identifiers without network access.

    The result records the declared source policy and the source-owned model
    catalog entries selected by the requested options.  A configured local
    snapshot identifier is included only when it can be read from the
    standard ``snapshots/<40-hex-id>`` path shape; absolute model paths are
    intentionally never emitted.
    """
    normalized_backend = effective_backend.strip().lower()
    if normalized_backend == "office":
        return {
            "execution": "office",
            "model_source": "not_applicable",
            "components": {},
        }
    if normalized_backend in {"vlm-http-client", "hybrid-http-client"}:
        return {
            "execution": "remote_http",
            "model_source": "remote_server",
            "server_configured": bool(
                options.server_url and options.server_url.strip()
            ),
        }

    repo_mode = "vlm" if "vlm" in normalized_backend else "pipeline"
    config = read_existing_tools_config()
    model_source = _declared_model_source(config)
    identifiers: dict[str, Any] = {
        "execution": "local",
        "model_source": model_source,
        "backend": normalized_backend,
        "method": options.method.strip().lower(),
        "components": (
            _pipeline_components(options)
            if repo_mode == "pipeline"
            else {"model_family": "MinerU2.5-Pro-2605-1.2B"}
        ),
    }
    identifiers.update(
        _repository_identity(
            repo_mode=repo_mode,
            model_source=model_source,
            config=config,
        )
    )
    return identifiers
