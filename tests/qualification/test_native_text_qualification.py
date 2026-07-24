from __future__ import annotations

import json
from pathlib import Path

import pytest

from mineru.qualification.native_text import (
    build_native_text_manifest,
    evaluate_native_text_manifest,
)


def _write_fake_parse(
    tmp_path: Path,
    *,
    warnings: list[str] | None = None,
    fallback_used: bool = False,
) -> tuple[Path, Path, Path]:
    output_root = tmp_path / "output"
    parse_dir = output_root / "report" / "auto"
    parse_dir.mkdir(parents=True)
    source_path = tmp_path / "report.pdf"
    source_path.write_bytes(b"synthetic native text source")

    content_list_v2 = [
        [
            {
                "type": "paragraph",
                "content": {
                    "paragraph_content": [
                        {
                            "type": "text",
                            "content": (
                                "Device ID RA-NT-001; input 5 V; do not exceed "
                                "10 mA."
                            ),
                        }
                    ]
                },
            },
            {
                "type": "table",
                "content": {
                    "html": (
                        "<table><tr><th>Parameter</th><th>Nominal</th></tr>"
                        "<tr><td>Voltage</td><td>5 V</td></tr></table>"
                    )
                },
            },
        ]
    ]
    (parse_dir / "report_content_list_v2.json").write_text(
        json.dumps(content_list_v2), encoding="utf-8"
    )
    (parse_dir / "report_content_list.json").write_text(
        json.dumps(
            [
                {
                    "type": "table",
                    "table_body": content_list_v2[0][1]["content"]["html"],
                }
            ]
        ),
        encoding="utf-8",
    )
    (parse_dir / "report_middle.json").write_text(
        json.dumps({"pdf_info": [{"page_idx": 0}]}), encoding="utf-8"
    )
    (parse_dir / "report.md").write_text(
        "Device ID RA-NT-001; input 5 V; do not exceed 10 mA.\n",
        encoding="utf-8",
    )

    manifest = build_native_text_manifest(
        output_root=output_root,
        parse_dir=parse_dir,
        source_path=source_path,
        source_id="SRC-SYNTHETIC-NATIVE-TEXT",
        source_version_id="SRC-SYNTHETIC-NATIVE-TEXT-V001",
        extraction_run_id="EXT-SYNTHETIC-NATIVE-TEXT-001",
        repository_sha="7" * 40,
        accelerator_profile="cpu",
        warnings=warnings or [],
        fallback_used=fallback_used,
    )
    manifest_path = output_root / "document-extraction-manifest-v1.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    gold = {
        "critical_text": [
            {"id": "device-id", "text": "RA-NT-001"},
            {"id": "voltage", "text": "5 V"},
            {"id": "current-limit", "text": "10 mA"},
            {"id": "negation", "text": "do not exceed"},
        ],
        "critical_table_cells": [
            {"id": "header-parameter", "table_index": 0, "row": 0, "column": 0, "text": "Parameter"},
            {"id": "header-nominal", "table_index": 0, "row": 0, "column": 1, "text": "Nominal"},
            {"id": "voltage-cell", "table_index": 0, "row": 1, "column": 0, "text": "Voltage"},
            {"id": "voltage-value", "table_index": 0, "row": 1, "column": 1, "text": "5 V"},
        ],
    }
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")
    return output_root, source_path, gold_path


def test_native_text_manifest_and_gold_evaluation_pass(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is True
    assert result["checks"]["critical_text"]["matched"] == 4
    assert result["checks"]["critical_table_cells"]["matched"] == 4
    assert result["checks"]["locators"]["invalid"] == 0
    assert result["checks"]["artifact_hashes"]["mismatched"] == 0
    assert result["checks"]["unmanifested_outputs"]["paths"] == []


def test_page_blocks_bind_locator_to_manifested_artifact(tmp_path: Path) -> None:
    output_root, _source_path, _gold_path = _write_fake_parse(tmp_path)
    manifest = json.loads(
        (output_root / "document-extraction-manifest-v1.json").read_text(
            encoding="utf-8"
        )
    )
    output_paths = {item["relative_path"] for item in manifest["outputs"]}

    assert manifest["page_blocks"]
    assert all(
        block["artifact_path"] in output_paths for block in manifest["page_blocks"]
    )
    assert all(
        block["artifact_path"].endswith("_content_list_v2.json")
        for block in manifest["page_blocks"]
    )


def test_native_text_evaluator_rejects_stale_source_hash(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)
    source_path.write_bytes(b"changed source")

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is False
    assert result["checks"]["input_sha256"]["passed"] is False


def test_native_text_evaluator_rejects_unmanifested_output(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)
    (output_root / "report" / "auto" / "unmanifested.log").write_text(
        "unexpected output", encoding="utf-8"
    )

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is False
    assert result["checks"]["unmanifested_outputs"]["paths"] == [
        "report/auto/unmanifested.log"
    ]


def test_native_text_evaluator_rejects_missing_declared_artifact(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)
    (output_root / "report" / "auto" / "report.md").unlink()

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is False
    assert result["checks"]["artifact_hashes"]["missing"] == 1


def test_native_text_evaluator_rejects_invalid_locator(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)
    manifest_path = output_root / "document-extraction-manifest-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["page_blocks"][0]["locator"] = "/0/99"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = evaluate_native_text_manifest(
        manifest_path=manifest_path,
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is False
    assert result["checks"]["locators"]["invalid"] == 1


@pytest.mark.parametrize(
    ("warnings", "fallback_used"),
    [(["parser warning"], False), ([], True)],
)
def test_native_text_evaluator_rejects_warning_or_fallback(
    tmp_path: Path,
    warnings: list[str],
    fallback_used: bool,
) -> None:
    output_root, source_path, gold_path = _write_fake_parse(
        tmp_path, warnings=warnings, fallback_used=fallback_used
    )

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is False
    assert result["checks"]["warnings_and_fallback"]["passed"] is False


def test_native_text_evaluator_rejects_critical_token_mismatch(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    gold["critical_text"][0]["text"] = "WRONG-ID"

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=gold,
    )

    assert result["passed"] is False
    assert result["checks"]["critical_text"]["mismatches"] == ["device-id"]


def test_native_text_evaluator_rejects_artifact_hash_mismatch(tmp_path: Path) -> None:
    output_root, source_path, gold_path = _write_fake_parse(tmp_path)
    artifact_path = output_root / "report" / "auto" / "report.md"
    artifact_path.write_text("changed output", encoding="utf-8")

    result = evaluate_native_text_manifest(
        manifest_path=output_root / "document-extraction-manifest-v1.json",
        source_path=source_path,
        gold=json.loads(gold_path.read_text(encoding="utf-8")),
    )

    assert result["passed"] is False
    assert result["checks"]["artifact_hashes"]["mismatched"] >= 1


def test_manifest_rebuild_excludes_existing_manifest(tmp_path: Path) -> None:
    output_root, source_path, _gold_path = _write_fake_parse(tmp_path)
    manifest_path = output_root / "document-extraction-manifest-v1.json"
    rebuilt = build_native_text_manifest(
        output_root=output_root,
        parse_dir=output_root / "report" / "auto",
        source_path=source_path,
        source_id="SRC-SYNTHETIC-NATIVE-TEXT",
        source_version_id="SRC-SYNTHETIC-NATIVE-TEXT-V001",
        extraction_run_id="EXT-SYNTHETIC-NATIVE-TEXT-002",
        repository_sha="7" * 40,
        accelerator_profile="cpu",
        manifest_path=manifest_path,
    )

    assert all(
        artifact["relative_path"] != "document-extraction-manifest-v1.json"
        for artifact in rebuilt["outputs"]
    )
