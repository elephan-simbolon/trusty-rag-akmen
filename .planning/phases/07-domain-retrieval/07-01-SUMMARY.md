---
phase: 07-domain-retrieval
plan: "01"
subsystem: ingestion/indexing
tags: [qdrant, payload-index, backfill, source-domain, RETR-02]
dependency_graph:
  requires: ["03"]
  provides: [source_domain_payload_index, backfill_script]
  affects: [src/ingestion/indexing/qdrant_uploader.py, scripts/backfill_source_domain.py]
tech_stack:
  added: []
  patterns: [idempotent-migration, server-side-bulk-update, IsEmptyCondition-filter]
key_files:
  created:
    - scripts/backfill_source_domain.py
  modified:
    - src/ingestion/indexing/qdrant_uploader.py
decisions:
  - "get_qdrant_client imported at module level in backfill script (not inside function) to enable test patching via patch('scripts.backfill_source_domain.get_qdrant_client')"
  - "qdrant_client.models imports (IsEmptyCondition, Filter, etc.) kept inside backfill() to minimize module load overhead"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-30"
  tasks_completed: 2
  files_changed: 2
---

# Phase 07 Plan 01: Source Domain Payload Index + Backfill Script Summary

**One-liner:** Added `source_domain` KEYWORD payload index to `create_collection` and wrote an idempotent bulk-backfill script using `IsEmptyCondition` filter for RETR-02 migration safety.

## What Was Built

### Task 1: Add source_domain to create_collection payload index list

Modified `src/ingestion/indexing/qdrant_uploader.py`:

- Extended the KEYWORD payload index loop from 3 to 4 fields:
  ```python
  for field in ["book_title", "chapter", "content_type", "source_domain"]:
  ```
- Added docstring to `upload_batch()` documenting that `source_domain` flows through from `chunk["metadata"]` via the `**chunk.get("metadata", {})` spread (no logic change needed).

The `upload_batch` logic was already correct — the metadata spread handles any key including `source_domain` automatically once pipeline.py stamps it onto chunks (Plan 02).

### Task 2: Create idempotent backfill script

Created `scripts/backfill_source_domain.py` with an importable `backfill()` function following the safety order from 07-RESEARCH.md:

1. **`create_payload_index`** — creates KEYWORD index on `source_domain` on the live collection. Idempotent: calling it on an existing index is a no-op.
2. **`set_payload` with `IsEmptyCondition` filter** — single server-side bulk update. No per-point loops. `wait=True` ensures durability before count verification.
3. **Count verification** — `client.count(total)` vs `client.count(filter=source_domain='accounting')`. Raises `AssertionError` if `tagged != total`, surfacing incomplete migrations.

Idempotency: When all points are already tagged, `set_payload` is a no-op, counts are equal, and the script exits cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level import required for test patchability**

- **Found during:** Task 2 test execution
- **Issue:** The plan spec said to put all imports inside `backfill()` for importability, but the pre-written test patches `scripts.backfill_source_domain.get_qdrant_client` — which requires `get_qdrant_client` to be accessible as a module-level attribute.
- **Fix:** Moved `from src.services.qdrant_service import get_qdrant_client` to module level (with `# noqa: E402` comment). qdrant_client.models imports kept inside `backfill()` to minimize module load overhead.
- **Files modified:** `scripts/backfill_source_domain.py`
- **Commit:** 4256a73

## Verification Results

All 3 RETR-02 tests pass:

```
tests/test_domain_retrieval.py::test_upload_batch_includes_source_domain  PASSED
tests/test_domain_retrieval.py::test_backfill_calls_set_payload            PASSED
tests/test_domain_retrieval.py::test_backfill_verification                 PASSED
```

Full unit suite: 329 passed, 16 pre-existing failures (fast_graphrag not installed + Langfuse config — confirmed pre-existing by stash check).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 237f391 | feat(07-01): add source_domain to create_collection payload index + upload_batch docstring |
| 2 | 4256a73 | feat(07-01): create idempotent backfill script for source_domain migration |

## Self-Check: PASSED

- FOUND: scripts/backfill_source_domain.py
- FOUND: src/ingestion/indexing/qdrant_uploader.py
- FOUND: .planning/phases/07-domain-retrieval/07-01-SUMMARY.md
- FOUND: commit 237f391
- FOUND: commit 4256a73
