---
phase: 07-domain-retrieval
verified: 2026-03-30T00:00:00Z
status: human_needed
score: 3/4 truths verified programmatically; 1 requires live Qdrant (RETR-02 count equality)
human_verification:
  - test: "Run `uv run python scripts/backfill_source_domain.py` against the live Qdrant collection"
    expected: "Script exits cleanly with log: 'Backfill complete: N/N points tagged with source_domain=accounting' where both numbers are equal and equal the total collection point count"
    why_human: "Success Criterion #2 requires client.count(filter=source_domain='accounting') == total collection count. This is a live Qdrant call — cannot be automated without a running Qdrant instance. The backfill must be run once before domain_filter goes live in Phase 08."
---

# Phase 07: Domain Retrieval Infrastructure Verification Report

**Phase Goal:** The retrieval pipeline can filter by source domain and all existing Qdrant points carry source_domain="accounting" — the foundation that makes multi-domain search safe and correct
**Verified:** 2026-03-30
**Status:** human_needed (all code verified; one operational step requires live Qdrant confirmation)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A retrieval call with domain_filter="accounting" returns only accounting chunks; domain_filter="consulting" returns only consulting; no filter returns all | VERIFIED | `hybrid_search` in `vector_search.py` builds `Filter(must=[FieldCondition(key="source_domain", match=MatchValue(value=domain_filter))])` and passes it to both Prefetch objects when domain_filter is non-None. filter=None when domain_filter is None. 4 RETR-01 unit tests pass. |
| 2 | Every existing Qdrant point has source_domain="accounting" — verified by count equality before domain filtering goes live | HUMAN NEEDED | `scripts/backfill_source_domain.py` exists and is correct: creates payload index, calls `set_payload` once with `IsEmptyCondition` filter, then asserts `total == tagged`. The script must be executed against the live Qdrant collection to satisfy this criterion. Unit tests for backfill logic pass (mocked). |
| 3 | User sees [Sumber N] labels on accounting citations and [Kerangka N] labels on consulting citations | VERIFIED | `_build_context_block` in `generator.py` reads `source_domain` from metadata, maps "consulting" → "Kerangka" and everything else → "Sumber". `build_citations` in `citation_builder.py` includes `source_domain` in every returned dict with fallback "accounting". 3 RETR-03 unit tests pass. |
| 4 | Running ingest with --source-domain consulting correctly tags new chunks without modifying default accounting behavior | VERIFIED | `scripts/ingest.py` has `--source-domain` arg (default="accounting", choices=["accounting", "consulting"]). `run_ingestion_pipeline` has `source_domain: str = "accounting"` parameter. Both content chunks (`enriched["metadata"]["source_domain"] = source_domain`) and diagram chunks include the tag. 3 RETR-04 unit tests pass. |

**Score:** 3/4 truths verified (4/4 code verified; Truth #2 awaits operational confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/retrieval/vector_search.py` | domain_filter parameter; source_domain in returned metadata | VERIFIED | `domain_filter: str \| None = None` as last param. `payload_filter` built and passed to both Prefetch objects. `source_domain` in metadata dict with `"accounting"` fallback (line 96). |
| `scripts/backfill_source_domain.py` | Idempotent migration: create_payload_index + bulk set_payload + count verification | VERIFIED | All three safety steps present. `get_qdrant_client` imported at module level for test patchability. `set_payload` called once with `IsEmptyCondition` filter. `AssertionError` raised on count mismatch. |
| `src/ingestion/pipeline.py` | source_domain parameter threaded into all chunk metadata dicts | VERIFIED | `source_domain: str = "accounting"` in signature. Stamped on content chunks (line 115) and diagram chunks (line 130). |
| `scripts/ingest.py` | --source-domain CLI flag (default 'accounting') forwarded to run_ingestion_pipeline | VERIFIED | `--source-domain` argument with `default="accounting"`, `choices=["accounting", "consulting"]`. Passed as `source_domain=args.source_domain` to `run_ingestion_pipeline`. |
| `src/generation/generator.py` | domain-aware [Sumber N] / [Kerangka N] labels in _build_context_block | VERIFIED | `_build_context_block` reads `domain = meta.get("source_domain", "accounting")`, maps "consulting" → "Kerangka", else → "Sumber". Label in f-string: `[{label} {i}: {source}]`. |
| `src/generation/citation_builder.py` | source_domain field in build_citations output dict | VERIFIED | `"source_domain": metadata.get("source_domain", "accounting")` added to citations.append dict (line 63). Sync comment added above `build_citation`. |
| `src/ingestion/indexing/qdrant_uploader.py` | source_domain KEYWORD payload index in create_collection | VERIFIED | `for field in ["book_title", "chapter", "content_type", "source_domain"]:` at line 74. upload_batch docstring documents source_domain flow-through. |
| `tests/test_domain_retrieval.py` | 10 test functions covering RETR-01 (4), RETR-02 (3), RETR-04 (3) | VERIFIED | Exactly 10 test functions present. All have real assertions. All 10 pass. |
| `tests/test_domain_citation.py` | 3 test functions covering RETR-03 | VERIFIED | Exactly 3 test functions present. All have real assertions. All 3 pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `ingest.py --source-domain` | `pipeline.py source_domain param` | `source_domain=args.source_domain` | WIRED | Line 93 in ingest.py passes `source_domain=args.source_domain` to `run_ingestion_pipeline` |
| `pipeline.py source_domain` | chunk metadata | `enriched["metadata"]["source_domain"] = source_domain` | WIRED | Line 115 stamps content chunks; line 130 stamps diagram chunks explicitly |
| chunk metadata | Qdrant payload | `**chunk.get("metadata", {})` spread in upload_batch | WIRED | qdrant_uploader.py line 119 spreads all metadata keys including source_domain into PointStruct payload |
| `hybrid_search domain_filter` | Prefetch.filter | `Filter(must=[FieldCondition(key="source_domain", ...)])` | WIRED | payload_filter built at line 51-53; passed to both Prefetch objects at lines 63 and 73 |
| `_build_context_block` label | `build_citations` label | Identical mapping: "consulting" → label key | WIRED | Both use `"Kerangka" if domain == "consulting" else "Sumber"`. Comment in citation_builder.py explicitly flags sync requirement. |
| backfill script | live Qdrant | `client.set_payload(points=Filter(IsEmptyCondition))` | WIRED (code) / UNRUN (operational) | Code is correct; must be executed against live collection before Phase 08 activates domain_filter |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `vector_search.hybrid_search` | `payload_filter` | `domain_filter` param (caller-supplied) | Yes — Filter is passed to Prefetch, not bypassed | FLOWING |
| `generator._build_context_block` | `domain` / `label` | `doc["metadata"]["source_domain"]` from retrieval results | Yes — source_domain populated by pipeline.py at ingest time | FLOWING |
| `citation_builder.build_citations` | `source_domain` field | `metadata.get("source_domain", "accounting")` | Yes — fallback "accounting" covers transition; real value from retrieval | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| hybrid_search accepts domain_filter param | `uv run python -c "import inspect; from src.retrieval.vector_search import hybrid_search; print(list(inspect.signature(hybrid_search).parameters.keys()))"` | `['query_embedding', 'query_text', 'top_k', 'collection_name', 'book_filter', 'domain_filter']` | PASS |
| All 13 phase tests pass | `uv run pytest tests/test_domain_retrieval.py tests/test_domain_citation.py -v` | 13 passed in 2.53s | PASS |
| Full unit suite: no new failures | `uv run pytest -m "not integration and not gpu"` | 329 passed, 16 failed (all pre-existing: fast_graphrag not installed + Langfuse config) | PASS (no regression) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| RETR-01 | Plan 02 | User mendapat retrieval yang memfilter berdasarkan source_domain | SATISFIED | `hybrid_search` domain_filter param + Prefetch.filter wiring. 4 unit tests. |
| RETR-02 | Plan 01 | Semua existing Qdrant points di-backfill dengan source_domain="accounting" | SATISFIED (code) / HUMAN NEEDED (operational) | `backfill_source_domain.py` exists and is correct. Requires execution against live Qdrant before Phase 08. |
| RETR-03 | Plan 03 | User melihat [Sumber N] / [Kerangka N] labels per domain | SATISFIED | `_build_context_block` and `build_citations` both implement domain-aware labels. Labels consistent between LLM prompt and frontend. 3 unit tests. |
| RETR-04 | Plan 02 | Pipeline ingestion menerima --source-domain flag | SATISFIED | `--source-domain` flag in ingest.py, threaded through pipeline.py to all chunk metadata. 3 unit tests. |

All 4 requirements in REQUIREMENTS.md Phase 07 traceability table are accounted for. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/retrieval/vector_search.py` | — | `domain_filter=None` default — domain filtering is opt-in infrastructure | Info | Intentional design: domain_filter=None until RETR-02 backfill is confirmed complete. Not a bug. |
| `scripts/backfill_source_domain.py` | 30 | Module-level `get_qdrant_client` import with `# noqa: E402` | Info | Required deviation from plan spec: enables `patch("scripts.backfill_source_domain.get_qdrant_client")` in tests. Documented in SUMMARY-01. |

No blockers. No stubs. No unimplemented functions. No hardcoded empty returns.

### Human Verification Required

#### 1. Backfill Live Qdrant Collection (RETR-02 Operational Confirmation)

**Test:** Run `uv run python scripts/backfill_source_domain.py` against the live Qdrant collection (with .env credentials present).

**Expected:**
```
INFO ... Payload index on source_domain: created (or already existed — idempotent)
INFO ... set_payload complete — all previously untagged points now carry source_domain='accounting'
INFO ... Backfill complete: N/N points tagged with source_domain='accounting'
INFO ... Result: {'total': N, 'tagged': N}
```
Where both N values are identical and equal the total collection point count (visible in Qdrant Cloud dashboard).

**Why human:** Success Criterion #2 requires a live Qdrant connection to verify `client.count(filter=source_domain="accounting") == client.count(total)`. This cannot be automated in the unit test suite without a running Qdrant instance. The backfill must complete successfully before Phase 08 activates domain_filter in the query pipeline — passing a non-None domain_filter before all points are tagged will silently degrade retrieval by excluding untagged points.

**After confirming:** Phase 08 may safely pass `domain_filter="accounting"` (or `"consulting"`) to `hybrid_search`.

### Gaps Summary

No functional gaps. All code artifacts exist, are substantive, and are correctly wired. The 13 phase unit tests all pass. The 16 pre-existing failures in the full test suite are unchanged from before Phase 07 (fast_graphrag not installed, Langfuse config — documented in Plan 01 SUMMARY).

The only outstanding item is operational: `scripts/backfill_source_domain.py` must be executed against the live Qdrant collection to complete the RETR-02 migration. The script is correct and idempotent — re-running it is safe.

---

_Verified: 2026-03-30_
_Verifier: Claude (gsd-verifier)_
