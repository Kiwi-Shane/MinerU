# D3 native-text MinerU qualification implementation plan

> **For agentic workers:** Use `superpowers:executing-plans` task by task.

**Goal:** Qualify the bounded local MinerU native-text pipeline profile using
source-owned manifest construction, critical-token/table gold, locator and
artifact-integrity checks, and a sanitized operator evidence record.

**Constraints:** Start from the live MinerU default head. Do not use private
data, VLM/OCR paths, external providers, upstream synchronization, or direct
RA schema duplication. Keep parser outputs outside Git.

## Task 1: Lock the acceptance contract with red tests

- [x] Add unit tests for a completed manifest and native-text evaluation.
- [x] Add failure tests for stale input hash, missing artifact, unmanifested
      output, invalid locator, fallback/warning, and critical-token mismatch.
- [x] Add a test for table-cell association and zero-error aggregate counts.
- [x] Run the focused selection and capture the expected red result (`ModuleNotFoundError` before the implementation exists).

## Task 2: Implement the bounded source-owned qualification module

- [x] Add `mineru/qualification/native_text.py` with a strict manifest builder
      and fail-closed evaluator.
- [x] Add a generated public synthetic fixture helper and an opt-in operator
      runner; do not retain generated PDFs or parser outputs in Git.
- [x] Keep output inventory, SHA-256, locators, fallback, and warning checks
      explicit and independently reported.

## Task 3: Verify the real native-text profile

- [x] Run the focused unit tests and static checks (`10 passed`; Ruff passed).
- [x] Run the real pipeline against the existing public table fixture and the
      generated native-text token fixture in the bounded offline container.
- [x] Record exact source revision, image digest, model identity, input hashes,
      artifact counts, and aggregate pass/fail counts in the qualification
      record. Do not retain extracted content.

## Task 4: Update source-owner qualification documentation

- [x] Update `docs/qualification/document-extraction-manifest-v1.md` with the
      D3 bounded result and explicit remaining profile limitations.
- [x] Run diff/private-artifact checks and inspect the final worktree.
- [x] Commit and push the MinerU feature branch at `d178143147ae86e3cc087391382f941789665706`.
      status to the RA handoff.
