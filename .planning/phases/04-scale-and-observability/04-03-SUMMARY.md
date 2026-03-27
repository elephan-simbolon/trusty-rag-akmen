---
phase: 04-scale-and-observability
plan: 03
subsystem: ingestion
tags: [embedder, contextual-window, rag, chunk-hierarchy, late-chunking]

# Dependency graph
requires:
  - phase: 04-scale-and-observability
    provides: incremental ingestion guard (replace_existing, check_book_exists, delete_book in pipeline.py)

provides:
  - build_contextual_text() in embedder.py with 256-word truncation and empty parent passthrough
  - embed_chunks_batch() contextual window mode via use_contextual_window=True + parent_texts dict
  - pipeline.py parent text collection from hierarchy_nodes and contextual embedding wiring
  - CLI --contextual flag in scripts/ingest.py activating end-to-end contextual window embedding
  - 7 unit tests in tests/test_contextual_embedding.py

affects: [04-scale-and-observability, ingestion-pipeline, embed-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Contextual window embedding: [Context: parent_text_truncated_256w]\n\nchunk_text format"
    - "section_path key in chunk metadata used as lookup key for parent_texts dict"
    - "use_contextual_window=False default preserves backward compatibility in embed_chunks_batch"

key-files:
  created:
    - tests/test_contextual_embedding.py
  modified:
    - src/ingestion/indexing/embedder.py
    - src/ingestion/pipeline.py
    - scripts/ingest.py

key-decisions:
  - "Contextual text prefix format is '[Context: {truncated_parent}]\n\n{chunk_text}' — square brackets mark the injected context so model can distinguish context from content"
  - "Max 256 words from parent text — conservative limit that stays well within Qwen3-Embedding-8B 8192-token limit even with long chunk text"
  - "Empty/whitespace parent returns chunk_text unchanged — diagram chunks and standalone formula index chunks have no parent context"
  - "parent_texts dict keyed by section_path from chunk metadata — matches the hierarchy_builder section grouping key"
  - "argparse help string with % must be escaped as %% to avoid ValueError in format_help()"

patterns-established:
  - "TDD Red-Green: failing tests committed before implementation for contextual embedding"
  - "Contextual window as API-compatible substitute for true late chunking when token-level pooling unavailable"

requirements-completed: [CHUNK-05]

# Metrics
duration: 12min
completed: 2026-03-22
---

# Phase 4 Plan 3: Contextual Window Embedding Summary

**API-compatible late chunking via parent-context prefix injection: each child chunk is embedded with up to 256 words of its parent section prepended, activated end-to-end via --contextual CLI flag through pipeline to Qwen3-Embedding-8B**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-22T12:31:00Z
- **Completed:** 2026-03-22T12:43:43Z
- **Tasks:** 2 (Task 1 TDD, Task 2 wiring)
- **Files modified:** 4

## Accomplishments

- `build_contextual_text()` prepends truncated parent section text to chunk text using `[Context: ...]` format, returning unchanged text when parent is empty
- `embed_chunks_batch()` gains `use_contextual_window` and `parent_texts` parameters — backward compatible, default behavior unchanged
- `run_ingestion_pipeline()` collects parent texts from hierarchy_nodes after Step 5 and passes them to embed_chunks_batch when `use_contextual=True`
- `scripts/ingest.py` exposes `--contextual` CLI flag with complete end-to-end activation path
- 7 unit tests covering all edge cases: prepend format, 256-word truncation, empty parent passthrough, default mode, contextual mode, missing section_path fallback

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `b8f0933` (test)
2. **Task 1 GREEN: build_contextual_text + embed_chunks_batch changes** - `3086a34` (feat)
3. **Task 2: Pipeline and CLI wiring** - `ad70bb0` (feat)

_Note: TDD Task 1 has two commits (test RED then feat GREEN)_

## Files Created/Modified

- `tests/test_contextual_embedding.py` — 7 unit tests for build_contextual_text and contextual embed_chunks_batch
- `src/ingestion/indexing/embedder.py` — Added build_contextual_text(), modified embed_chunks_batch() signature
- `src/ingestion/pipeline.py` — Added use_contextual param, parent text collection after Step 5, contextual args to Step 8
- `scripts/ingest.py` — Added --contextual argparse flag, passes use_contextual=args.contextual to pipeline

## Decisions Made

- Contextual text prefix format `[Context: {truncated_parent}]\n\n{chunk_text}` uses square brackets to mark injected context so the embedding model can distinguish context from content
- Max 256 words chosen as a conservative limit that stays well within Qwen3-Embedding-8B 8192-token limit even with long child chunks
- Empty and whitespace-only parent returns chunk_text unchanged — diagram chunks and formula index synthetic chunks have no parent context
- `parent_texts` dict keyed by `section_path` from chunk metadata matches the hierarchy_builder section grouping key naturally
- argparse `%` in help strings must be escaped as `%%` to avoid `ValueError: incomplete format` in `format_help()` — auto-fixed under Rule 1

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Escaped % in --contextual help string**
- **Found during:** Task 2 (CLI verification)
- **Issue:** argparse `format_help()` treats `%` in help strings as format specifiers; `~15-25%` caused `ValueError: incomplete format`
- **Fix:** Changed `~15-25%` to `~15-25%%` in the `--contextual` argument's help string
- **Files modified:** scripts/ingest.py
- **Verification:** `uv run python scripts/ingest.py --help` executed without error and displayed `--contextual`
- **Committed in:** ad70bb0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Trivial fix. No scope creep.

## Issues Encountered

- Pre-existing test failures in `test_incremental_ingestion.py` (3 tests for `check_book_exists`/`delete_book` pipeline integration) were confirmed as TDD RED-phase tests from plan 04-02 — not caused by this plan's changes. All 193 non-integration/non-GPU tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Contextual window embedding is fully implemented and ready for use during ingestion
- Activated with: `uv run python scripts/ingest.py book.pdf --contextual`
- Plan 04-04 can proceed — no blockers from this plan

---
*Phase: 04-scale-and-observability*
*Completed: 2026-03-22*

## Self-Check: PASSED

- tests/test_contextual_embedding.py: FOUND
- src/ingestion/indexing/embedder.py: FOUND
- src/ingestion/pipeline.py: FOUND
- scripts/ingest.py: FOUND
- .planning/phases/04-scale-and-observability/04-03-SUMMARY.md: FOUND
- Commit b8f0933 (TDD RED): FOUND
- Commit 3086a34 (TDD GREEN): FOUND
- Commit ad70bb0 (Task 2): FOUND
