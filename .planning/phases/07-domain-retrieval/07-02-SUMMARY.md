---
phase: 07-domain-retrieval
plan: "02"
subsystem: retrieval, ingestion
tags: [qdrant, domain-filter, hybrid-search, source-domain, pipeline, metadata, RETR-01, RETR-04]

# Dependency graph
requires:
  - phase: 07-domain-retrieval
    plan: "03"
    provides: Wave 0 test stubs for RETR-01 and RETR-04

provides:
  - domain_filter parameter in hybrid_search with Prefetch.filter wiring (RETR-01)
  - source_domain in every returned metadata dict from hybrid_search (fallback "accounting")
  - source_domain parameter in run_ingestion_pipeline stamped onto all chunk metadata (RETR-04)
  - --source-domain CLI flag in scripts/ingest.py (default "accounting", choices: accounting/consulting)

affects:
  - 07-01 (upload_batch and backfill complete the RETR-02 chain; domain_filter is now ready for activation)
  - backend query pipeline (hybrid_search callers can now optionally pass domain_filter)
  - scripts/ingest.py CLI callers (new optional --source-domain flag)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "domain_filter defaults to None — do NOT activate until RETR-02 backfill is 100% complete (silently degraded retrieval otherwise)"
    - "FieldCondition/Filter/MatchValue on Prefetch objects (pre-fusion, per-vector-type) — not on outer query_points call"
    - "source_domain fallback 'accounting' covers transition period before backfill"

key-files:
  created: []
  modified:
    - src/retrieval/vector_search.py
    - src/ingestion/pipeline.py
    - scripts/ingest.py
    - tests/test_domain_retrieval.py

key-decisions:
  - "domain_filter=None default — retrieve_node does NOT pass domain_filter in Phase 07; opt-in infrastructure only, activated in Phase 08"
  - "filter=payload_filter on each Prefetch (dense and sparse), not on outer query_points — filter must apply pre-fusion"
  - "source_domain fallback 'accounting' in hybrid_search metadata — covers untagged points during transition before backfill"
  - "capture_embed_chunks side effect with correct embed_chunks_batch signature fixed in test — Rule 1 auto-fix"

patterns-established:
  - "Domain tagging: stamp source_domain on chunk metadata during ingestion; filter on retrieval via Prefetch.filter"

requirements-completed:
  - RETR-01
  - RETR-04

# Metrics
duration: 15min
completed: 2026-03-30
---

# Phase 07 Plan 02: Domain Retrieval Infrastructure Summary

**domain_filter parameter added to hybrid_search with Prefetch.filter wiring (RETR-01), and source_domain threaded from --source-domain CLI flag through run_ingestion_pipeline to all chunk metadata (RETR-04)**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-30T00:00:00Z
- **Completed:** 2026-03-30T00:15:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `domain_filter: str | None = None` to `hybrid_search` — builds `Filter(must=[FieldCondition(...)])` applied to both dense and sparse `Prefetch` objects; `None` passes `filter=None` (no-op, backward compatible)
- Added `source_domain` to every result dict's `metadata` key in `hybrid_search` (fallback `"accounting"` for untagged points)
- Added `source_domain: str = "accounting"` to `run_ingestion_pipeline` and stamped it onto all content chunks (after `enrich_metadata`) and diagram caption chunks
- Added `--source-domain` argparse flag to `scripts/ingest.py` with `default="accounting"` and `choices=["accounting", "consulting"]`; forwarded to `run_ingestion_pipeline`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add domain_filter to hybrid_search and source_domain to returned metadata** - `83e21b6` (feat)
2. **Task 2: Thread source_domain from CLI flag through pipeline to chunk metadata** - `e12872f` (feat)

**Plan metadata:** (docs commit pending)

_Note: TDD tasks — tests were pre-written (Wave 0, plan 07-03); implementation made them green._

## Files Created/Modified

- `src/retrieval/vector_search.py` - Added `FieldCondition`, `Filter`, `MatchValue` imports; `domain_filter` parameter; `payload_filter` construction; filter on both Prefetch objects; `source_domain` in metadata dict
- `src/ingestion/pipeline.py` - Added `source_domain: str = "accounting"` parameter; stamps `source_domain` on content chunks and diagram chunks
- `scripts/ingest.py` - Added `--source-domain` argparse flag; passes `source_domain=args.source_domain` to `run_ingestion_pipeline`
- `tests/test_domain_retrieval.py` - Fixed `capture_embed_chunks` mock function signature (Rule 1 auto-fix)

## Decisions Made

- `domain_filter` defaults to `None` — `retrieve_node` in `src/agents/nodes.py` does NOT pass `domain_filter` in Phase 07. Domain filtering is opt-in infrastructure to be activated in Phase 08 after RETR-02 backfill is verified complete. Enabling now while untagged points exist would silently degrade retrieval.
- Filter placed on each `Prefetch` (pre-fusion, per-vector-type) not on the outer `query_points` call — this is the correct qdrant-client 1.17.1 pattern for pre-fusion domain filtering.
- `source_domain` fallback `"accounting"` in `hybrid_search` metadata dict — covers transition period before RETR-02 backfill completes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_pipeline_threads_source_domain mock signature mismatch**
- **Found during:** Task 2 (Thread source_domain through pipeline)
- **Issue:** Test's `capture_upload` side effect for `embed_chunks_batch` patch had signature `(client, chunks, collection_name=None)` but `embed_chunks_batch` is called as `(chunks, batch_size=16, checkpoint_path=..., upload_fn=..., ...)` — TypeError on call
- **Fix:** Renamed to `capture_embed_chunks` with correct signature matching `embed_chunks_batch` API; returns `len(chunks)` as expected
- **Files modified:** `tests/test_domain_retrieval.py`
- **Verification:** Test passes after fix
- **Committed in:** `e12872f` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in pre-written test mock)
**Impact on plan:** Auto-fix required for test correctness. No scope creep. The actual assertion (checking `inspect.signature(run_ingestion_pipeline)`) was always correct — only the mock setup was wrong.

## Issues Encountered

- `test_backfill_*` tests in `tests/test_domain_retrieval.py` fail because `scripts/backfill_source_domain.py` (RETR-02, plan 07-01) doesn't exist yet — this is expected in parallel execution; RETR-02 tests are out of scope for this plan
- Pre-existing failures in `test_graph_retrieve.py`, `test_langfuse_integration.py`, `test_query_modes.py`, `test_relational_queries.py` (missing `fast_graphrag` module, langfuse config issues) — pre-existing, unrelated to this plan's changes

## User Setup Required

None - no external service configuration required. Domain filtering is infrastructure only; activation is deferred to Phase 08 after RETR-02 backfill.

## Next Phase Readiness

- RETR-01 infrastructure complete: `hybrid_search` accepts `domain_filter` and returns `source_domain` in metadata
- RETR-04 infrastructure complete: ingestion pipeline stamps `source_domain` on all chunks; CLI flag available
- Waiting on RETR-02 (plan 07-01): `upload_batch` pass-through + backfill script needed before domain filtering can be safely activated
- After RETR-02 verified: pass `domain_filter=settings.default_domain` in `retrieve_node` to enable domain-aware retrieval

## Self-Check: PASSED

- FOUND: `src/retrieval/vector_search.py`
- FOUND: `src/ingestion/pipeline.py`
- FOUND: `scripts/ingest.py`
- FOUND: `.planning/phases/07-domain-retrieval/07-02-SUMMARY.md`
- FOUND: commit `83e21b6` (Task 1)
- FOUND: commit `e12872f` (Task 2)
- 7/7 RETR-01 + RETR-04 tests pass

---
*Phase: 07-domain-retrieval*
*Completed: 2026-03-30*
