---
phase: 07-domain-retrieval
plan: "03"
subsystem: testing, generation
tags: [citations, domain-filter, qdrant, source_domain, label-differentiation, tdd]

# Dependency graph
requires:
  - phase: 06-kpe-core
    provides: generator.py _build_context_block, citation_builder.py build_citations
provides:
  - Wave 0 test stubs for all Phase 07 requirements (RETR-01, RETR-02, RETR-03, RETR-04)
  - Domain-aware citation labels ([Sumber N] for accounting, [Kerangka N] for consulting) in LLM context block
  - source_domain field in build_citations output dict (for frontend use)
  - Sync contract comment in citation_builder.py documenting label parity requirement
affects:
  - 07-01, 07-02 (can now verify their work against these test stubs)
  - frontend (receives source_domain in citation dicts for label rendering)
  - generator.py callers (context block labels now vary by domain)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "source_domain='consulting' -> [Kerangka N], else -> [Sumber N] — label mapping in both generator._build_context_block and citation_builder.build_citations must stay in sync"
    - "Wave 0 tests written before production code — test stubs provide verification targets for parallel plan execution"

key-files:
  created:
    - tests/test_domain_retrieval.py
    - tests/test_domain_citation.py
  modified:
    - src/generation/generator.py
    - src/generation/citation_builder.py

key-decisions:
  - "source_domain absent in metadata defaults to 'accounting' — backward compatible with all pre-Phase-07 points in Qdrant"
  - "source_domain not added to build_citation() formatted string — only in build_citations() dict, so citation text format (GEN-01) is unchanged"
  - "Sync comment added above build_citation() in citation_builder.py to document label parity requirement between generator.py and citation_builder.py"

patterns-established:
  - "Label sync pattern: _build_context_block (LLM sees labels) and build_citations (frontend sees labels) must map source_domain identically — one comment documents this invariant"

requirements-completed:
  - RETR-03
  - RETR-01
  - RETR-02
  - RETR-04

# Metrics
duration: 5min
completed: 2026-03-30
---

# Phase 07 Plan 03: Domain Citation Labels + Wave 0 Tests Summary

**Wave 0 test stubs (13 functions) for RETR-01/02/03/04 plus RETR-03 implementation: [Sumber N]/[Kerangka N] domain-aware label differentiation in both LLM context block and frontend citation dicts**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T04:52:31Z
- **Completed:** 2026-03-30T04:57:31Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `tests/test_domain_retrieval.py` with 10 test functions for RETR-01 (4), RETR-02 (3), RETR-04 (3) — all with real assertions that fail until Plans 01 and 02 are executed
- Created `tests/test_domain_citation.py` with 3 test functions for RETR-03 — all pass after Task 2
- Updated `_build_context_block` in generator.py to emit `[Kerangka N:]` for consulting docs and `[Sumber N:]` for accounting docs (or absent source_domain)
- Updated `build_citations` in citation_builder.py to include `source_domain` in every returned citation dict with fallback `"accounting"`

## Task Commits

1. **Task 1: Write Wave 0 test files** - `f2bc000` (test)
2. **Task 2: Implement citation label differentiation** - `9084662` (feat)

**Plan metadata:** `(docs commit — see below)`

## Files Created/Modified

- `tests/test_domain_retrieval.py` — 10 unit tests for RETR-01 (domain_filter in hybrid_search), RETR-02 (upload_batch + backfill), RETR-04 (ingest.py --source-domain flag + pipeline signature); mocks Qdrant client, no live services required
- `tests/test_domain_citation.py` — 3 unit tests for RETR-03: accounting label, consulting label, source_domain in build_citations output; pure Python, no mocks needed
- `src/generation/generator.py` — `_build_context_block` updated: reads `source_domain` from metadata, emits `[Kerangka N]` for consulting, `[Sumber N]` for anything else (accounting or absent)
- `src/generation/citation_builder.py` — `build_citations` updated: adds `"source_domain": metadata.get("source_domain", "accounting")` to every citation dict; sync comment added above `build_citation()`

## Decisions Made

- `source_domain` absent defaults to `"accounting"` — backward compatible with all existing Qdrant points before Phase 07 backfill
- `build_citation()` formatted string is NOT changed — `source_domain` appears only in `build_citations()` dict, preserving GEN-01 locked citation format
- Sync comment placed above `build_citation()` rather than in the docstring — visible at the top of the function block without requiring doc scroll

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing failures in `test_graph_retrieve.py`, `test_langfuse_integration.py`, `test_query_modes.py`, and `test_relational_queries.py` — caused by `fast_graphrag` module not installed in this environment. Confirmed these failures exist before any changes (via `git stash` verification). Out of scope for this plan.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Wave 0 tests in place: Plans 01 and 02 can verify their hybrid_search domain_filter, upload_batch, backfill, and ingest.py changes against real assertions
- RETR-03 fully implemented and green: 3/3 citation tests pass
- Plans 01 and 02 execution will make the remaining 10 retrieval tests green
- No blockers for parallel execution of Plans 01 and 02

---
*Phase: 07-domain-retrieval*
*Completed: 2026-03-30*

## Self-Check: PASSED

- FOUND: tests/test_domain_retrieval.py
- FOUND: tests/test_domain_citation.py
- FOUND: .planning/phases/07-domain-retrieval/07-03-SUMMARY.md
- FOUND: commit f2bc000 (Task 1 — Wave 0 test stubs)
- FOUND: commit 9084662 (Task 2 — RETR-03 implementation)
