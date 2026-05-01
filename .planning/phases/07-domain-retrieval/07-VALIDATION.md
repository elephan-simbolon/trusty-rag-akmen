---
phase: 07
slug: domain-retrieval
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
audited: 2026-03-30
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest.ini: testpaths=tests, addopts=--timeout=30 -q) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `uv run pytest tests/test_domain_retrieval.py tests/test_domain_citation.py -x` |
| **Full suite command** | `uv run pytest -m "not integration and not gpu"` |
| **Estimated runtime** | ~5s (phase tests) / ~20s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_domain_retrieval.py tests/test_domain_citation.py -x`
- **After every plan wave:** Run `uv run pytest -m "not integration and not gpu"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | RETR-02 | unit | `uv run pytest tests/test_domain_retrieval.py::test_upload_batch_includes_source_domain tests/test_domain_retrieval.py::test_backfill_calls_set_payload tests/test_domain_retrieval.py::test_backfill_verification -x` | ✅ | ✅ green |
| 07-01-02 | 01 | 1 | RETR-02 | unit | `uv run pytest tests/test_domain_retrieval.py::test_backfill_calls_set_payload tests/test_domain_retrieval.py::test_backfill_verification -x` | ✅ | ✅ green |
| 07-02-01 | 02 | 1 | RETR-01 | unit | `uv run pytest tests/test_domain_retrieval.py::test_domain_filter_passed_to_prefetch tests/test_domain_retrieval.py::test_domain_filter_consulting tests/test_domain_retrieval.py::test_no_domain_filter_returns_all tests/test_domain_retrieval.py::test_search_results_include_source_domain -x` | ✅ | ✅ green |
| 07-02-02 | 02 | 1 | RETR-04 | unit | `uv run pytest tests/test_domain_retrieval.py::test_ingest_source_domain_flag tests/test_domain_retrieval.py::test_pipeline_threads_source_domain tests/test_domain_retrieval.py::test_ingest_default_source_domain -x` | ✅ | ✅ green |
| 07-03-01 | 03 | 1 | RETR-03 | unit | `uv run pytest tests/test_domain_citation.py::test_accounting_citation_label tests/test_domain_citation.py::test_consulting_citation_label tests/test_domain_citation.py::test_citations_include_source_domain -x` | ✅ | ✅ green |
| 07-03-02 | 03 | 1 | RETR-01–04 | unit (suite) | `uv run pytest -m "not integration and not gpu"` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_domain_retrieval.py` — stubs for RETR-01, RETR-02, RETR-04 (hybrid_search domain_filter, upload_batch payload, backfill script, ingest flag)
- [x] `tests/test_domain_citation.py` — stubs for RETR-03 (citation label differentiation: [Sumber N] vs [Kerangka N])

*(Existing `tests/test_retrieval.py` covers no-filter hybrid_search path — new files are separate for phase scope clarity)*

**Wave 0 complete — all 13 tests green (2026-03-30)**

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Backfill script execution against live Qdrant Cloud | RETR-02 | Requires live Qdrant connection; one-time operational migration | Run `uv run python scripts/backfill_source_domain.py` and confirm output: `Backfill complete: N/N points tagged` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s (actual: 2.62s for 13 tests)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-30

---

## Validation Audit 2026-03-30

| Metric | Count |
|--------|-------|
| Gaps found | 6 (all ❌ W0 → pending) |
| Resolved | 6 |
| Escalated | 0 |
| Tests run | 13 |
| Tests passed | 13 |
| Tests failed | 0 |
| Runtime | 2.62s |
