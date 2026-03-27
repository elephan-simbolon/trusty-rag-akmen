---
phase: 4
slug: scale-and-observability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest -m "not integration and not gpu" -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30 seconds (unit); ~120 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -m "not integration and not gpu" -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (unit), 120 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | MON-01, MON-03, MON-04 | unit | `uv run pytest tests/test_langfuse_integration.py -q` | W0 | pending |
| 4-01-02 | 01 | 1 | MON-01, MON-03, MON-04 | unit | `uv run pytest tests/test_langfuse_integration.py -q && uv run pytest -m "not integration and not gpu" -q` | W0 | pending |
| 4-02-01 | 02 | 1 | INGEST-06 | unit | `uv run pytest tests/test_incremental_ingestion.py -q` | W0 | pending |
| 4-02-02 | 02 | 1 | INGEST-06 | unit | `uv run python scripts/ingest.py --help \| grep -q replace` | N/A | pending |
| 4-03-01 | 03 | 1 | CHUNK-05 | unit | `uv run pytest tests/test_contextual_embedding.py -q` | W0 | pending |
| 4-03-02 | 03 | 1 | CHUNK-05 | unit | `uv run python scripts/ingest.py --help \| grep -q contextual` | N/A | pending |
| 4-04-01 | 04 | 2 | MON-02 | unit+manual | `uv run pytest tests/test_evaluation_set.py -q && uv run python scripts/evaluate_retrieval.py --dry-run` | W0 | pending |
| 4-04-02 | 04 | 2 | MON-02 | manual | Human review of 20-query eval set and Langfuse traces | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_langfuse_integration.py` — stubs for MON-01, MON-03, MON-04 (trace creation, span metadata, cost tracking)
- [ ] `tests/test_incremental_ingestion.py` — stubs for INGEST-06 (book exists check, delete-by-filter, manifest tracking)
- [ ] `tests/test_contextual_embedding.py` — stubs for CHUNK-05 (contextual window prepend logic)
- [ ] `tests/test_evaluation_set.py` — stubs for MON-02 (eval JSON structure validation)
- [ ] `tests/conftest.py` — extend with Langfuse mock fixture and book manifest fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 85% retrieval accuracy on 20-query eval set | MON-02 | Citation relevance requires human judgment; LLM-as-judge unreliable at this scale | Run `uv run python scripts/evaluate_retrieval.py -v` for 20 eval queries; score citations as PASS/FAIL; record in `data/eval/results.json` |
| Langfuse dashboard shows routing decision per query | MON-01 | Dashboard UI verification cannot be automated in unit tests | Open Langfuse UI -> filter traces -> verify routing metadata present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
