---
phase: 08
slug: consulting-book-ingestion
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
audited: 2026-03-30
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest.ini: testpaths=tests, addopts=--timeout=30 -q) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `uv run pytest tests/test_consulting_ingestion.py -x` |
| **Full suite command** | `uv run pytest -m "not integration and not gpu"` |
| **Estimated runtime** | ~2s (phase tests) / ~21s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_consulting_ingestion.py -x`
- **After every plan wave:** Run `uv run pytest -m "not integration and not gpu"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | INGEST-01, INGEST-02 | unit | `uv run pytest tests/test_consulting_ingestion.py -x` | ✅ | ✅ green |
| 08-02-01 | 02 | 1 | INGEST-01 | unit | `uv run pytest tests/test_consulting_ingestion.py::test_no_vlm_skips_captioning tests/test_consulting_ingestion.py::test_vlm_enabled_by_default -x` | ✅ | ✅ green |
| 08-02-02 | 02 | 1 | INGEST-01 | unit | `uv run pytest tests/test_consulting_ingestion.py::test_no_vlm_flag_exists tests/test_consulting_ingestion.py::test_vlm_default_true -x` | ✅ | ✅ green |
| 08-02-03 | 02 | 1 | INGEST-02 | unit | `uv run pytest tests/test_consulting_ingestion.py::test_pipeline_stamps_author tests/test_consulting_ingestion.py::test_pipeline_stamps_empty_author -x` | ✅ | ✅ green |
| 08-02-04 | 02 | 1 | INGEST-02 | unit | `uv run pytest tests/test_consulting_ingestion.py::test_author_flag_forwarded tests/test_consulting_ingestion.py::test_author_default_empty tests/test_consulting_ingestion.py::test_consulting_chunk_has_author_and_domain -x` | ✅ | ✅ green |
| 08-02-05 | 02 | 1 | INGEST-01, INGEST-02 | unit (suite) | `uv run pytest -m "not integration and not gpu"` | ✅ | ✅ green (373 passed) |
| 08-02-03 (UAT) | 02 | 2 | INGEST-01, INGEST-02 | manual (UAT) | `uv run python scripts/test_query.py "apa itu issue tree dalam consulting?" -v 2>&1 \| grep -i "Kerangka"` | manual | ✅ verified |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_consulting_ingestion.py` — 9 unit tests covering INGEST-01 (VLM gate: 4 tests: `test_no_vlm_skips_captioning`, `test_vlm_enabled_by_default`, `test_no_vlm_flag_exists`, `test_vlm_default_true`) dan INGEST-02 (author field: 5 tests: `test_pipeline_stamps_author`, `test_pipeline_stamps_empty_author`, `test_author_flag_forwarded`, `test_author_default_empty`, `test_consulting_chunk_has_author_and_domain`) — semua ✅ green

*(Reuse `_make_pipeline_mocks()` helper pattern dari `tests/test_incremental_ingestion.py`)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Status |
|----------|-------------|------------|--------|
| 3-book dry-run ingestion produces correct chunk counts dan metadata | INGEST-01, INGEST-02 | Requires live PDFs + Qdrant + SiliconFlow API | ✅ Completed (dry-run 2026-03-29) |
| Full 21-book ingestion selesai tanpa error | INGEST-01 | Operational batch run; requires all 21 PDFs available | ✅ Completed — 10,134 chunks ingested |
| Query consulting framework mengembalikan [Kerangka N] labels | INGEST-01, INGEST-02 | Requires live data in Qdrant | ✅ Verified via `/gsd:verify-work` 2026-03-30 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s (2s for phase tests)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ✅ 2026-03-30

---

## Validation Audit 2026-03-30

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tests verified green | 9 (phase) + 373 (full suite) |
| Manual-only completed | 3 |

All requirements (INGEST-01, INGEST-02) have automated unit test coverage. Full suite 373 passed, 0 failed. Manual verifications completed and documented. Phase is Nyquist-compliant.
