"""Bounded native-text qualification for the published extraction manifest.

This module deliberately owns only producer-side mechanics. It does not make
source-sufficiency, regulatory, readiness, or RA evidence decisions.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


CONTRACT_VERSION = "document-extraction-manifest-v1"
PROFILE_ID = "mineru_pipeline_native_text_v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^[0-9a-f]{7,64}$")


class NativeTextQualificationError(ValueError):
    """Raised when a producer payload cannot be safely constructed."""


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._row is not None and self._cell is not None:
            self._row.append(_normalise_text("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _normalise_text(value: str) -> str:
    return " ".join(value.replace("\u00a0", " ").split())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(path: Path, *, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise NativeTextQualificationError(
            f"Path escapes output root: {path}"
        ) from error
    portable = PurePosixPath(relative.as_posix())
    if portable.is_absolute() or ".." in portable.parts:
        raise NativeTextQualificationError(f"Unsafe relative path: {relative}")
    return portable.as_posix()


def _artifact_type(path: Path) -> str:
    name = path.name.lower()
    if name.endswith("_content_list_v2.json"):
        return "content_list_v2"
    if name.endswith("_content_list.json"):
        return "content_list"
    if name.endswith("_middle.json"):
        return "middle_json"
    if name.endswith("_model.json"):
        return "model_output"
    if path.suffix.lower() in {".md", ".txt"}:
        return "markdown"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        return "image"
    return "parser_output"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NativeTextQualificationError(
            f"Cannot load parser JSON artifact: {path}"
        ) from error


def _content_pages(content_list_v2: Any) -> list[list[Mapping[str, Any]]]:
    if not isinstance(content_list_v2, list):
        raise NativeTextQualificationError("content_list_v2 must be an array")
    if content_list_v2 and all(isinstance(item, dict) for item in content_list_v2):
        raw_pages: list[Any] = [content_list_v2]
    else:
        raw_pages = content_list_v2

    pages: list[list[Mapping[str, Any]]] = []
    for page in raw_pages:
        if isinstance(page, dict):
            page = [page]
        if not isinstance(page, list) or not all(isinstance(item, dict) for item in page):
            raise NativeTextQualificationError(
                "content_list_v2 pages must contain block objects"
            )
        pages.append(page)
    return pages


def _find_string(node: Any, keys: set[str]) -> str | None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key in keys and isinstance(value, str):
                return value
            found = _find_string(value, keys)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_string(value, keys)
            if found is not None:
                return found
    return None


def _table_cells(block: Mapping[str, Any]) -> list[list[str]]:
    html = _find_string(block, {"html", "table_body"})
    if not html:
        return []
    parser = _TableParser()
    parser.feed(html)
    parser.close()
    return parser.rows


def _node_text(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, Mapping):
        values: list[str] = []
        for value in node.values():
            values.extend(_node_text(value))
        return values
    if isinstance(node, list):
        values = []
        for value in node:
            values.extend(_node_text(value))
        return values
    return []


def _configuration_sha256(
    *,
    backend_requested: str,
    backend_effective: str,
    parse_method: str,
    language: str,
    formula_enabled: bool,
    table_enabled: bool,
    image_analysis_enabled: bool,
    offline: bool,
) -> str:
    configuration = {
        "backend_requested": backend_requested,
        "backend_effective": backend_effective,
        "parse_method": parse_method,
        "language": language,
        "formula_enabled": formula_enabled,
        "table_enabled": table_enabled,
        "image_analysis_enabled": image_analysis_enabled,
        "offline": offline,
    }
    encoded = json.dumps(
        configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _manifest_artifacts(output_root: Path, manifest_path: Path | None) -> list[dict[str, str]]:
    files = sorted(
        path for path in output_root.rglob("*") if path.is_file()
    )
    artifacts: list[dict[str, str]] = []
    for index, path in enumerate(files, start=1):
        if manifest_path is not None and path.resolve() == manifest_path.resolve():
            continue
        relative_path = _safe_relative_path(path, root=output_root)
        artifacts.append(
            {
                "artifact_id": f"MINERU-ARTIFACT-{index:04d}",
                "artifact_type": _artifact_type(path),
                "relative_path": relative_path,
                "sha256": _sha256_file(path),
            }
        )
    return artifacts


def _artifact_path(manifest: Mapping[str, Any], artifact_type: str, *, root: Path) -> Path:
    for artifact in manifest.get("outputs", []):
        if isinstance(artifact, Mapping) and artifact.get("artifact_type") == artifact_type:
            relative_path = artifact.get("relative_path")
            if isinstance(relative_path, str):
                candidate = (root / Path(relative_path)).resolve()
                try:
                    candidate.relative_to(root.resolve())
                except ValueError as error:
                    raise NativeTextQualificationError(
                        f"Artifact path escapes output root: {relative_path}"
                    ) from error
                return candidate
    raise NativeTextQualificationError(f"Missing artifact type: {artifact_type}")


def build_native_text_manifest(
    *,
    output_root: Path,
    parse_dir: Path,
    source_path: Path,
    source_id: str,
    source_version_id: str,
    extraction_run_id: str,
    repository_sha: str,
    accelerator_profile: str,
    model_identifiers: Mapping[str, Any] | None = None,
    backend_requested: str = "pipeline",
    backend_effective: str = "pipeline",
    parse_method: str = "auto",
    language: str = "en",
    formula_enabled: bool = True,
    table_enabled: bool = True,
    image_analysis_enabled: bool = False,
    offline: bool = True,
    warnings: Sequence[str] = (),
    errors: Sequence[str] = (),
    fallback_used: bool = False,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Build a completed native-text manifest from a local parser directory."""
    output_root = output_root.resolve()
    parse_dir = parse_dir.resolve()
    source_path = source_path.resolve()
    if not parse_dir.is_dir():
        raise NativeTextQualificationError(f"Parser output directory is missing: {parse_dir}")
    try:
        parse_dir.relative_to(output_root)
    except ValueError as error:
        raise NativeTextQualificationError("Parser output escapes output root") from error
    if not source_path.is_file():
        raise NativeTextQualificationError(f"Input source is missing: {source_path}")
    if not _REVISION_RE.fullmatch(repository_sha):
        raise NativeTextQualificationError("repository_sha must be a lowercase Git SHA")
    for name, value in {
        "source_id": source_id,
        "source_version_id": source_version_id,
        "extraction_run_id": extraction_run_id,
        "accelerator_profile": accelerator_profile,
    }.items():
        if not isinstance(value, str) or not value.strip():
            raise NativeTextQualificationError(f"{name} must be non-empty")

    content_list_v2_path = _artifact_path(
        {"outputs": _manifest_artifacts(output_root, manifest_path)},
        "content_list_v2",
        root=output_root,
    )
    middle_json_path = _artifact_path(
        {"outputs": _manifest_artifacts(output_root, manifest_path)},
        "middle_json",
        root=output_root,
    )
    content_list_v2 = _load_json(content_list_v2_path)
    middle_json = _load_json(middle_json_path)
    pages = _content_pages(content_list_v2)
    pdf_info = middle_json.get("pdf_info") if isinstance(middle_json, Mapping) else None
    native_page_count = len(pdf_info) if isinstance(pdf_info, list) else len(pages)
    if native_page_count <= 0:
        raise NativeTextQualificationError("Native page count must be positive")

    page_blocks: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    table_index = 0
    for page_index, page in enumerate(pages):
        for block_index, block in enumerate(page):
            block_id = f"NATIVE-P{page_index + 1:04d}-B{block_index + 1:04d}"
            locator = f"/{page_index}/{block_index}"
            page_blocks.append(
                {
                    "block_id": block_id,
                    "page_number": page_index + 1,
                    "block_type": str(block.get("type", "unknown")),
                    "locator": locator,
                }
            )
            if str(block.get("type", "")).lower() in {"table", "simple_table", "complex_table"}:
                tables.append(
                    {
                        "table_index": table_index,
                        "block_id": block_id,
                        "page_number": page_index + 1,
                        "locator": locator,
                        "cells": _table_cells(block),
                    }
                )
                table_index += 1

    try:
        from mineru.version import __version__
    except ImportError:
        __version__ = "unknown"

    artifacts = _manifest_artifacts(output_root, manifest_path)
    return {
        "contract_version": CONTRACT_VERSION,
        "extraction_run_id": extraction_run_id,
        "source_id": source_id,
        "source_version_id": source_version_id,
        "input_sha256": _sha256_file(source_path),
        "mineru_identity": {
            "repository_sha": repository_sha,
            "package_version": str(__version__),
            "backend": backend_effective,
            "model_identifiers": dict(model_identifiers or {}),
            "configuration_sha256": _configuration_sha256(
                backend_requested=backend_requested,
                backend_effective=backend_effective,
                parse_method=parse_method,
                language=language,
                formula_enabled=formula_enabled,
                table_enabled=table_enabled,
                image_analysis_enabled=image_analysis_enabled,
                offline=offline,
            ),
        },
        "runtime_identity": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "accelerator_profile": accelerator_profile,
        },
        "status": "completed",
        "native_page_count": native_page_count,
        "outputs": artifacts,
        "page_blocks": page_blocks,
        "tables": tables,
        "images": [],
        "ocr_profile": None,
        "warnings": list(warnings),
        "errors": list(errors),
        "fallback_used": fallback_used,
        "derivative_not_native_source_evidence": True,
        "does_not_establish_source_sufficiency": True,
    }


def _resolve_json_pointer(root: Any, pointer: str) -> Any:
    if pointer == "":
        return root
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = root
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, Mapping):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current


def _check(passed: bool, **details: Any) -> dict[str, Any]:
    return {"passed": passed, **details}


def evaluate_native_text_manifest(
    *,
    manifest_path: Path,
    source_path: Path,
    gold: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate a manifest and public/synthetic gold set fail-closed."""
    output_root = manifest_path.resolve().parent
    try:
        manifest = _load_json(manifest_path)
        if not isinstance(manifest, Mapping):
            raise NativeTextQualificationError("Manifest root must be an object")
    except (OSError, NativeTextQualificationError) as error:
        return {"profile": PROFILE_ID, "passed": False, "error": str(error), "checks": {}}

    checks: dict[str, dict[str, Any]] = {}
    checks["contract"] = _check(
        manifest.get("contract_version") == CONTRACT_VERSION
        and manifest.get("derivative_not_native_source_evidence") is True
        and manifest.get("does_not_establish_source_sufficiency") is True,
        contract_version=manifest.get("contract_version"),
    )
    expected_input_sha = _sha256_file(source_path) if source_path.is_file() else ""
    checks["input_sha256"] = _check(
        manifest.get("input_sha256") == expected_input_sha,
        expected=expected_input_sha,
        observed=manifest.get("input_sha256"),
    )

    warnings = manifest.get("warnings", [])
    errors = manifest.get("errors", [])
    fallback_used = manifest.get("fallback_used")
    checks["warnings_and_fallback"] = _check(
        manifest.get("status") == "completed"
        and isinstance(warnings, list)
        and not warnings
        and isinstance(errors, list)
        and not errors
        and fallback_used is False,
        status=manifest.get("status"),
        warnings=warnings,
        errors=errors,
        fallback_used=fallback_used,
    )

    declared: dict[str, Mapping[str, Any]] = {}
    invalid_paths: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    outputs = manifest.get("outputs", [])
    if isinstance(outputs, list):
        for artifact in outputs:
            if not isinstance(artifact, Mapping):
                invalid_paths.append("<non-object-artifact>")
                continue
            relative_path = artifact.get("relative_path")
            if not isinstance(relative_path, str):
                invalid_paths.append(str(relative_path))
                continue
            candidate = (output_root / Path(relative_path)).resolve()
            try:
                candidate.relative_to(output_root)
            except ValueError:
                invalid_paths.append(relative_path)
                continue
            declared[relative_path.replace("\\", "/")] = artifact
            if not candidate.is_file():
                missing.append(relative_path)
            elif artifact.get("sha256") != _sha256_file(candidate):
                mismatched.append(relative_path)
    else:
        invalid_paths.append("outputs")
    checks["artifact_hashes"] = _check(
        not invalid_paths and not missing and not mismatched,
        declared=len(declared),
        missing=len(missing),
        missing_paths=missing,
        mismatched=len(mismatched),
        mismatched_paths=mismatched,
        invalid_paths=len(invalid_paths),
        invalid_paths_values=invalid_paths,
    )

    manifest_relative = _safe_relative_path(manifest_path, root=output_root)
    actual = {
        _safe_relative_path(path, root=output_root)
        for path in output_root.rglob("*")
        if path.is_file() and path.resolve() != manifest_path.resolve()
    }
    unmanifested = sorted(actual - set(declared))
    checks["unmanifested_outputs"] = _check(
        not unmanifested,
        manifest=manifest_relative,
        paths=unmanifested,
    )

    locators_invalid = 0
    locator_records = list(manifest.get("page_blocks", [])) + list(manifest.get("tables", []))
    try:
        content_list_v2_path = _artifact_path(manifest, "content_list_v2", root=output_root)
        content_list_v2 = _load_json(content_list_v2_path)
        for record in locator_records:
            try:
                locator = record["locator"]
                _resolve_json_pointer(content_list_v2, locator)
            except (KeyError, IndexError, TypeError, ValueError):
                locators_invalid += 1
    except (NativeTextQualificationError, OSError, json.JSONDecodeError):
        locators_invalid = len(locator_records) or 1
    checks["locators"] = _check(
        bool(locator_records) and locators_invalid == 0,
        checked=len(locator_records),
        invalid=locators_invalid,
    )

    text_fragments: list[str] = []
    try:
        text_fragments.extend(_node_text(content_list_v2))
        markdown_path = _artifact_path(manifest, "markdown", root=output_root)
        text_fragments.append(markdown_path.read_text(encoding="utf-8"))
    except (NativeTextQualificationError, OSError, UnicodeError):
        pass
    aggregate_text = _normalise_text(" ".join(text_fragments)).casefold()
    text_mismatches: list[str] = []
    text_matched = 0
    critical_text = gold.get("critical_text", [])
    if not isinstance(critical_text, list):
        critical_text = []
    for item in critical_text:
        if not isinstance(item, Mapping):
            text_mismatches.append("<invalid>")
            continue
        item_id = str(item.get("id", "<missing-id>"))
        expected = _normalise_text(str(item.get("text", ""))).casefold()
        count = aggregate_text.count(expected) if expected else 0
        expected_count = item.get("expected_count", 1)
        if count >= int(expected_count):
            text_matched += 1
        else:
            text_mismatches.append(item_id)
    checks["critical_text"] = _check(
        text_matched == len(critical_text),
        expected=len(critical_text),
        matched=text_matched,
        mismatches=text_mismatches,
    )

    table_mismatches: list[str] = []
    table_matched = 0
    tables = manifest.get("tables", [])
    if not isinstance(tables, list):
        tables = []
    critical_cells = gold.get("critical_table_cells", [])
    if not isinstance(critical_cells, list):
        critical_cells = []
    for item in critical_cells:
        if not isinstance(item, Mapping):
            table_mismatches.append("<invalid>")
            continue
        item_id = str(item.get("id", "<missing-id>"))
        try:
            table = tables[int(item["table_index"])]
            cells = table["cells"]
            observed = cells[int(item["row"])][int(item["column"])]
            expected = _normalise_text(str(item["text"]))
        except (KeyError, IndexError, TypeError, ValueError):
            observed = None
            expected = ""
        if observed == expected:
            table_matched += 1
        else:
            table_mismatches.append(item_id)
    checks["critical_table_cells"] = _check(
        table_matched == len(critical_cells),
        expected=len(critical_cells),
        matched=table_matched,
        mismatches=table_mismatches,
        table_count=len(tables),
    )

    return {
        "profile": PROFILE_ID,
        "passed": all(check["passed"] for check in checks.values()),
        "technical_completion": "qualified" if all(check["passed"] for check in checks.values()) else "failed",
        "ra_evidence_state": "deferred",
        "release_decision": "defer",
        "checks": checks,
    }
