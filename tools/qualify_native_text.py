"""Run the bounded native-text profile and emit sanitized aggregate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from mineru.cli.common import do_parse, read_fn
from mineru.qualification.native_text import (
    build_native_text_manifest,
    evaluate_native_text_manifest,
)


PUBLIC_FIXTURE = Path("tests/unittest/pdfs/test.pdf")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
    ).strip()


def _write_synthetic_native_text_pdf(path: Path) -> None:
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontName = "Helvetica"
    body.fontSize = 10
    body.leading = 14
    document = SimpleDocTemplate(
        str(path), pagesize=letter, leftMargin=0.65 * inch, rightMargin=0.65 * inch
    )
    story = [
        Paragraph("D3 native-text qualification fixture", styles["Title"]),
        Paragraph("Fixture ID: D3-NT-001", body),
        Paragraph("Operating point: 5 V DC, 50 Hz, 2 mA.", body),
        Paragraph("Do not exceed 10 mA.", body),
        Paragraph("The output must not be marked PASS when current exceeds 10 mA.", body),
        Spacer(1, 12),
    ]
    table = Table(
        [
            ["Parameter", "Nominal", "Limit"],
            ["Voltage", "5 V DC", "10 V DC"],
            ["Frequency", "50 Hz", "60 Hz"],
            ["Current", "2 mA", "10 mA"],
        ],
        colWidths=[1.55 * inch, 1.55 * inch, 1.55 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    document.build(story)


def _gold_for(case_id: str) -> dict[str, Any]:
    if case_id == "public-test-pdf":
        return {
            "critical_text": [
                {"id": "year-1968", "text": "1968"},
                {"id": "year-1971", "text": "1971"},
                {"id": "table-value-098740", "text": "0.98740"},
                {"id": "table-value-000617", "text": "0.00617"},
                {"id": "table-value-687", "text": "687"},
            ],
            "critical_table_cells": [],
        }
    return {
        "critical_text": [
            {"id": "fixture-id", "text": "D3-NT-001"},
            {"id": "voltage-unit", "text": "5 V DC"},
            {"id": "frequency-unit", "text": "50 Hz"},
            {"id": "current-unit", "text": "2 mA"},
            {"id": "negation-do-not", "text": "Do not exceed 10 mA"},
            {"id": "negation-must-not", "text": "must not be marked PASS"},
        ],
        "critical_table_cells": [
            {"id": "header-parameter", "table_index": 0, "row": 0, "column": 0, "text": "Parameter"},
            {"id": "header-nominal", "table_index": 0, "row": 0, "column": 1, "text": "Nominal"},
            {"id": "header-limit", "table_index": 0, "row": 0, "column": 2, "text": "Limit"},
            {"id": "voltage-row-label", "table_index": 0, "row": 1, "column": 0, "text": "Voltage"},
            {"id": "voltage-row-value", "table_index": 0, "row": 1, "column": 1, "text": "5 V DC"},
            {"id": "frequency-row-label", "table_index": 0, "row": 2, "column": 0, "text": "Frequency"},
            {"id": "frequency-row-value", "table_index": 0, "row": 2, "column": 1, "text": "50 Hz"},
            {"id": "current-row-label", "table_index": 0, "row": 3, "column": 0, "text": "Current"},
            {"id": "current-row-value", "table_index": 0, "row": 3, "column": 1, "text": "2 mA"},
        ],
    }


def _parse_case(
    *,
    case_id: str,
    source_path: Path,
    output_root: Path,
    repository_sha: str,
    accelerator_profile: str,
    model_snapshot: str,
) -> dict[str, Any]:
    case_root = output_root / case_id
    case_root.mkdir(parents=True, exist_ok=True)

    from loguru import logger

    warning_messages: list[str] = []
    sink_id = logger.add(
        lambda message: warning_messages.append(str(message).strip()), level="WARNING"
    )
    try:
        do_parse(
            str(case_root),
            [source_path.stem],
            [read_fn(source_path)],
            ["en"],
            backend="pipeline",
            parse_method="auto",
            formula_enable=True,
            table_enable=True,
            image_analysis=False,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=True,
            f_dump_middle_json=True,
            f_dump_model_output=True,
            f_dump_orig_pdf=True,
            f_dump_content_list=True,
        )
    finally:
        logger.remove(sink_id)

    parse_dir = case_root / source_path.stem / "auto"
    manifest_path = case_root / "document-extraction-manifest-v1.json"
    manifest = build_native_text_manifest(
        output_root=case_root,
        parse_dir=parse_dir,
        source_path=source_path,
        source_id=f"SYNTHETIC-D3-{case_id.upper()}",
        source_version_id=f"SYNTHETIC-D3-{case_id.upper()}-V001",
        extraction_run_id=f"EXT-D3-{case_id.upper()}",
        repository_sha=repository_sha,
        accelerator_profile=accelerator_profile,
        model_identifiers={
            "model_source": "local",
            "snapshot_id": model_snapshot or "not_recorded",
        },
        warnings=warning_messages,
        fallback_used=False,
        manifest_path=manifest_path,
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result = evaluate_native_text_manifest(
        manifest_path=manifest_path,
        source_path=source_path,
        gold=_gold_for(case_id),
    )
    return {
        "case_id": case_id,
        "source_sha256": _sha256_file(source_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "manifest": {
            "status": manifest["status"],
            "native_page_count": manifest["native_page_count"],
            "artifact_count": len(manifest["outputs"]),
            "page_block_count": len(manifest["page_blocks"]),
            "table_count": len(manifest["tables"]),
            "warnings": len(manifest["warnings"]),
            "errors": len(manifest["errors"]),
            "fallback_used": manifest["fallback_used"],
        },
        "result": result,
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result_checks = [case["result"]["checks"] for case in cases]

    def total(name: str, key: str) -> int:
        return sum(int(check[name].get(key, 0)) for check in result_checks)

    passed = all(case["result"]["passed"] for case in cases)
    return {
        "passed": passed,
        "cases": len(cases),
        "cases_passed": sum(1 for case in cases if case["result"]["passed"]),
        "critical_text": {
            "expected": total("critical_text", "expected"),
            "matched": total("critical_text", "matched"),
        },
        "critical_table_cells": {
            "expected": total("critical_table_cells", "expected"),
            "matched": total("critical_table_cells", "matched"),
        },
        "locators": {
            "checked": total("locators", "checked"),
            "invalid": total("locators", "invalid"),
        },
        "artifact_hashes": {
            "mismatched": total("artifact_hashes", "mismatched"),
            "missing": total("artifact_hashes", "missing"),
        },
        "unmanifested_outputs": {
            "count": sum(len(check["unmanifested_outputs"]["paths"]) for check in result_checks),
        },
        "technical_completion": "qualified" if passed else "failed",
        "ra_evidence_state": "deferred",
        "release_decision": "defer",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--source-revision", default=None)
    parser.add_argument("--accelerator-profile", default="cpu")
    parser.add_argument("--model-snapshot", default="")
    parser.add_argument("--image-digest", default="not_recorded")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    repository_sha = args.source_revision or _git_revision()
    public_fixture = (Path.cwd() / PUBLIC_FIXTURE).resolve()

    with tempfile.TemporaryDirectory(prefix="mineru-d3-native-text-") as temp_dir:
        synthetic_path = Path(temp_dir) / "synthetic_native_text.pdf"
        _write_synthetic_native_text_pdf(synthetic_path)
        cases = [
            _parse_case(
                case_id="public-test-pdf",
                source_path=public_fixture,
                output_root=output_dir,
                repository_sha=repository_sha,
                accelerator_profile=args.accelerator_profile,
                model_snapshot=args.model_snapshot,
            ),
            _parse_case(
                case_id="synthetic-native-text",
                source_path=synthetic_path,
                output_root=output_dir,
                repository_sha=repository_sha,
                accelerator_profile=args.accelerator_profile,
                model_snapshot=args.model_snapshot,
            ),
        ]

    report = {
        "qualification": "d3_native_text_mineru",
        "profile": "mineru_pipeline_native_text_v1",
        "source_revision": repository_sha,
        "image_digest": args.image_digest,
        "model_snapshot": args.model_snapshot or "not_recorded",
        "cases": cases,
        "aggregate": _aggregate(cases),
        "boundary": {
            "private_data": False,
            "provider_execution": False,
            "ocr_profile": "deferred",
            "complex_layout_vlm_profile": "deferred",
            "ra_evidence_state": "deferred",
            "release_decision": "defer",
        },
    }
    report_path = args.report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["aggregate"], ensure_ascii=False, sort_keys=True))
    return 0 if report["aggregate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
