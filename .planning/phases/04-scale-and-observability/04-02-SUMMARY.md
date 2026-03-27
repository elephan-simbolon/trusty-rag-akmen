---
phase: 04-scale-and-observability
plan: "02"
subsystem: ingestion
tags: [qdrant, incremental-ingestion, lightrag, manifest, cli]

requires:
  - phase: 01-foundation
    provides: qdrant_uploader.py with upload_chunks and health_check
  - phase: 02-knowledge-graph
    provides: ingest_chunks_to_lightrag for LightRAG ingestion CLI

provides:
  - check_book_exists() in qdrant_uploader: scroll-based book existence check
  - delete_book() in qdrant_uploader: FilterSelector delete-by-book_title
  - replace_existing param in run_ingestion_pipeline
  - --replace CLI flag in ingest.py
  - ingested_books.json manifest tracking in ingest_lightrag.py
  - unit tests for all incremental ingestion behaviors

affects:
  - 04-scale-and-observability (contextual embedding, evaluation)
  - Future ingestion of additional textbooks

tech-stack:
  added: []
  patterns:
    - FilterSelector delete-by-filter (targeted book removal, not collection recreation)
    - Manifest JSON tracking for idempotent LightRAG ingestion
    - TDD (RED-GREEN) for Qdrant integration functions
    - Lazy import of lightrag inside main() to allow --help without full install

key-files:
  created:
    - tests/test_incremental_ingestion.py
  modified:
    - src/ingestion/indexing/qdrant_uploader.py
    - src/ingestion/pipeline.py
    - scripts/ingest.py
    - scripts/ingest_lightrag.py

key-decisions:
  - "check_book_exists uses scroll(limit=1) — existence check only, not count; fast even on large collections"
  - "delete_book uses FilterSelector not delete_collection — targeted per-book removal, other books unaffected"
  - "replace_existing=False default raises ValueError (not silent skip) — forces explicit opt-in to replacement"
  - "LightRAG manifest only updated on full ingestion (--full), not audit runs — audit is sampling, not commitment"
  - "lightrag import moved inside main() in ingest_lightrag.py — allows --help and argparse to work without lightrag installed"

patterns-established:
  - "Pattern: Incremental guard before expensive pipeline (check existence before 9-step ingest)"
  - "Pattern: JSON manifest for external service tracking when the service has no built-in book registry"

requirements-completed: [INGEST-06]

duration: 12min
completed: "2026-03-22"
---

# Phase 04 Plan 02: Incremental Ingestion Guard Summary

**Qdrant check_book_exists/delete_book with FilterSelector, pipeline ValueError guard, --replace CLI flag, and LightRAG ingested_books.json manifest — prevents duplicate chunks when adding new textbooks**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-22T12:31:00Z
- **Completed:** 2026-03-22T12:43:06Z
- **Tasks:** 2 (TDD: Task 1 had 3 commits, Task 2 had 1 commit)
- **Files modified:** 5 (qdrant_uploader, pipeline, ingest.py, ingest_lightrag.py, test file)

## Accomplishments

- `check_book_exists()` and `delete_book()` added to qdrant_uploader using Qdrant scroll/FilterSelector APIs
- Pipeline raises `ValueError` on duplicate book ingestion unless `replace_existing=True` is passed
- CLI `--replace` flag wired through ingest.py to the pipeline
- LightRAG `ingest_lightrag.py` now tracks ingested books in `lightrag_storage/ingested_books.json` manifest
- All 5 unit tests pass (TDD RED-GREEN cycle completed)
- Full non-integration test suite: 193 tests pass, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `9fc3cc2` (test: add failing tests for incremental ingestion guard)
2. **Task 1 GREEN: Implementation** - `c2b46d2` (feat: add check_book_exists, delete_book, pipeline guard)
3. **Task 2: CLI flags and manifest** - `2c67b32` (feat: add --replace flag and LightRAG book manifest tracking)

## Files Created/Modified

- `tests/test_incremental_ingestion.py` — 5 unit tests for incremental ingestion (TDD RED commit)
- `src/ingestion/indexing/qdrant_uploader.py` — added `check_book_exists()`, `delete_book()`, Filter/FilterSelector imports
- `src/ingestion/pipeline.py` — added `replace_existing` param, incremental guard block, settings/check_book_exists/delete_book imports
- `scripts/ingest.py` — added `--replace` flag, passes `replace_existing=args.replace` to pipeline
- `scripts/ingest_lightrag.py` — added `--replace` flag, `get_ingested_books()`, `mark_book_ingested()`, manifest skip logic, lazy lightrag import

## Decisions Made

- `check_book_exists` uses `scroll(limit=1)` — existence-only check, avoids counting all points for a book (fast for large collections)
- `delete_book` uses `FilterSelector` not `delete_collection` — surgical per-book deletion, other books unaffected (Anti-pattern in RESEARCH.md explicitly listed)
- Default `replace_existing=False` raises `ValueError` instead of silently skipping — forces explicit acknowledgment of replacement intent
- LightRAG manifest updated only after full ingestion (`--full`), not after audit runs — audit (50-chunk sample) is verification, not commitment
- `lightrag` import moved inside `main()` in `ingest_lightrag.py` — enables `--help` without `lightrag` installed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved lightrag module-level import inside main() to fix --help**
- **Found during:** Task 2 (CLI flag verification)
- **Issue:** `from src.knowledge_graph.graph_ingestion import ingest_chunks_to_lightrag` at module level caused `ModuleNotFoundError: No module named 'lightrag'` when running `--help`. This blocked the acceptance criteria test `uv run python scripts/ingest_lightrag.py --help | grep --replace`.
- **Fix:** Moved the import inside `main()` so argparse initialization runs before any lightrag code is imported.
- **Files modified:** `scripts/ingest_lightrag.py`
- **Verification:** `uv run python scripts/ingest_lightrag.py --help` shows `--replace` flag correctly.
- **Committed in:** `2c67b32` (Task 2 commit)
- **Note:** This was a pre-existing issue (the original script also had module-level lightrag import). Fixed inline as it blocked the verification step.

---

**Total deviations:** 1 auto-fixed (1 blocking issue)
**Impact on plan:** Pre-existing lightrag import issue fixed as part of Task 2. No scope creep.

## Issues Encountered

- Python `with` statement does not support `*unpacking` inside context manager — used `contextlib.ExitStack` to apply multiple patches in test helper functions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Incremental ingestion guard is production-ready — new textbooks can be added via `ingest.py` without affecting existing books
- `--replace` flag enables safe re-ingestion when a book is updated
- LightRAG manifest prevents redundant entity extraction (expensive SiliconFlow API calls) for already-processed books
- Ready for scale testing: adding 5-30 additional textbooks without full re-ingestion

---
*Phase: 04-scale-and-observability*
*Completed: 2026-03-22*
