# D3 native-text MinerU qualification design

## Goal

Create a source-owned, reproducible qualification slice for
`mineru_pipeline_native_text_v1`. The slice must prove the mechanical
boundaries that RA needs before accepting MinerU native-text derivatives into
the runtime path:

- critical identifiers, numbers, units, and negation are present with zero
  recorded mismatches;
- critical table cells remain associated with the expected table block;
- every emitted page block has a valid page locator;
- every declared artifact exists and its SHA-256 matches;
- no parser output file is left unmanifested;
- the effective backend is the requested local pipeline path, with no silent
  fallback, parser errors, or unrecorded warnings.

The result is a bounded source-owner qualification record. It is not source
sufficiency, native-source verification, RA evidence, regulatory readiness,
private-data approval, or release approval.

## Scope

### Included

- A small source-owned manifest builder for a completed local pipeline parse.
- A deterministic evaluator for the native-text acceptance checks above.
- A public repository PDF fixture that exercises existing table and numeric
  assertions.
- A generated, non-private one-page PDF fixture that exercises an identifier,
  units, a negation, and a small table.
- Unit tests for fail-closed manifest and evaluator behavior.
- An opt-in operator test/command that runs the real MinerU pipeline and emits
  only sanitized aggregate evidence.

### Excluded

- OCR, VLM, hybrid, HTTP-client, remote model, or external provider paths.
- Private or client source data.
- Knowhere retrieval, RA acceptance, AIWB export, or runtime release.
- Any direct mutation of an authoritative draft or source record.
- A new RA-owned copy of the MinerU schema.

## Contract boundary

MinerU remains the canonical owner of
`schemas/document-extraction-manifest-v1.schema.json`. The D3 module only
constructs and evaluates a payload against that published contract. It does
not add RA status, source sufficiency, readiness, or regulatory fields.

The manifest is written beside the parser output. Its `outputs` inventory is
the complete regular-file inventory under the parse directory, excluding the
manifest itself. Relative paths must remain inside that directory. Page and
table records retain JSON-pointer locators into `content_list_v2`.

## Qualification profiles and evidence

The profile is qualified only for the exact bounded configuration used by the
operator run: local `pipeline`, `parse_method=auto`, no VLM enrichment, and
the recorded model/runtime identity. Any backend, model, language, fallback,
or output-shape change requires a new qualification run.

The operator report records counts and hashes, not extracted private content.
It keeps technical qualification separate from RA evidence state and release
decision. OCR and complex-layout/VLM remain deferred profiles.
