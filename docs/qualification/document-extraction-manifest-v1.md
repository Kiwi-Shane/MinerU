# `document-extraction-manifest-v1` qualification matrix

This record is the MinerU source-owner qualification boundary for the
published `document-extraction-manifest-v1` contract. It records bounded
technical extraction evidence only. It does not establish native-source
sufficiency, RA evidence, regulatory readiness, private-runtime approval, or
release approval.

## Profile disposition

| Profile | Intended scope | Status | Boundary |
|---|---|---|---|
| `mineru_pipeline_native_text_v1` | Native-text PDF, local `pipeline` backend, `parse_method=auto`, no VLM enrichment | `qualified_with_bounded_limitation` | Qualified only for the recorded local model/runtime and the public plus synthetic one-page fixture set. New backend, model, language, fallback, or fixture family requires requalification. |
| `mineru_pipeline_ocr_v1` | Scanned PDF with fixed OCR model and language-routing policy | `deferred` | No OCR gold qualification was performed in this D3 slice. |
| `mineru_hybrid_complex_layout_v1` | Complex tables, multi-column pages, images, and formulas | `deferred` | No VLM/hybrid qualification was performed in this D3 slice. |

The native-text result is a bounded producer qualification. It does not
authorize automatic use of the derivative as native source evidence.

## D3 operator run

The final run was performed on 2026-07-23 from MinerU source revision
`72fcb4a5d688b2d23acd619f3de2f2bd85c44775`, using the local model snapshot
`ed6b654c018d742e65a17671e379c5e6ecc87ec9` in image
`sha256:e034f798206a8cdd384a6c3986693cbfe385fe2ed585952963eaeac84ec836c4`.
The source checkout was mounted read-only into the existing local-model
container. The run used an internal `--network none` container network, no
host ports, no provider, no private data, and no VLM/OCR path.

The run used two input cases:

| Case | Input SHA-256 | Manifest SHA-256 | Pages | Artifacts | Blocks | Tables |
|---|---|---|---:|---:|---:|---:|
| Public repository `tests/unittest/pdfs/test.pdf` | `ae9e3f14cc3bea88dd0ce4e2715b3b03561378501318df61f0889df207aed25b` | `c430418debb505d8bd2b9a2dd0600f3226c56275ed2e8a250e0564e1b1da831a` | 1 | 9 | 5 | 1 |
| Generated non-private native-text fixture | `e6adc545f15d6e84994df043a1fd5ecda0709cb05d2630bcef5107d6e1be6ae1` | `30a911826eb9fd8914b79e926a0d83c99271d018df95711d8b71a35bccc7000c` | 1 | 7 | 6 | 1 |

Generated PDFs and parser output were retained only in local engineering
evidence at
`E:\Codex\30-evidence\ra-recovery-program-v1-0\d3-native-text-20260723-r2`.
The sanitized aggregate report is `report.json`; source contents and parser
derivatives are not committed.

## Acceptance result

| Acceptance target | Result | Disposition |
|---|---:|---|
| Critical identifiers, numbers, units, and negation | 11/11 matched | `pass` |
| Critical table cells and row/column association | 9/9 matched | `pass` |
| Page/block/table locators | 13/13 valid; 0 invalid | `pass` |
| Declared artifact SHA-256 checks | 16/16 artifacts matched; 0 missing; 0 mismatched | `pass` |
| Unmanifested parser outputs | 0 | `pass` |
| Completed status, parser errors, warnings, and fallback | 2/2 completed; 0 errors; 0 warnings; fallback false | `pass` |

The executable implementation is `mineru/qualification/native_text.py`. It
constructs the source-owned manifest from the complete parser output
inventory and evaluates the bounded gold checks fail-closed. The operator
entry point is `tools/qualify_native_text.py`; generated fixtures and output
are not repository artifacts.

## Remaining qualification gates

This D3 result does not qualify OCR, hybrid/VLM, rotated pages, long
documents, multilingual or Traditional Chinese coverage, encrypted/corrupt
inputs, duplicate/superseded source handling, host-level egress policy, or
model/license provenance. It also does not perform Knowhere retrieval, RA
native-source verification, RA accept/reject/defer, AIWB context export,
private-data processing, or runtime release. Those remain separate D4-D9
gates.
