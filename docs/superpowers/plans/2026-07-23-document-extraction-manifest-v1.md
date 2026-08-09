# MinerU `document-extraction-manifest-v1`

## Goal

Publish the source-owned extraction-manifest schema, synthetic contract
fixture, and contract test on the MinerU feature branch based directly on the
live fork default branch.

## Scope

- Add `schemas/document-extraction-manifest-v1.schema.json`.
- Add `examples/contracts/document-extraction-manifest-v1/example.json`.
- Add `tests/contracts/test_document_extraction_manifest_v1_contract.py`.
- Add a concise qualification/ownership note if needed, without claiming
  runtime qualification.
- Do not add or activate the MinerU-to-Knowhere runtime adapter in D1.

## Verification

Run the contract test from the MinerU worktree, run JSON parsing/schema
structural checks, inspect the diff for private artifacts, then commit and
push only the feature branch. Record the final commit and artifact hashes for
the RA consumer packet.
