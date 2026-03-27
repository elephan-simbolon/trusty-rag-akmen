---
phase: 3
slug: agentic-orchestration
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-22
audited: 2026-03-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest tests/ -m "not integration and not gpu" -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration and not gpu" -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration and not gpu" -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration and not gpu" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | RETR-05, RETR-06 | unit | `uv run pytest tests/test_query_routing.py -q` | ✅ exists | ✅ green |
| 3-01-02 | 01 | 1 | RETR-05, RETR-06 | unit | `uv run pytest tests/test_query_routing.py -q` | ✅ exists | ✅ green |
| 3-02-01 | 02 | 1 | RETR-04 | unit | `uv run pytest tests/test_crag_evaluation.py -q` | ✅ exists | ✅ green |
| 3-02-02 | 02 | 1 | MON-05 | unit | `uv run pytest tests/test_rate_limiting.py -q` | ✅ exists | ✅ green |
| 3-03-01 | 03 | 2 | GEN-02, GEN-03, RETR-05 | unit | `uv run pytest tests/test_phase3_graph.py -q` | ✅ exists | ✅ green |
| 3-03-02 | 03 | 2 | UI-02 | unit | `uv run pytest tests/test_conversation_memory.py -q` | ✅ exists | ✅ green |
| 3-04-01 | 04 | 3 | UI-02 | manual | N/A — requires browser | N/A | ✅ verified (UAT) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_query_routing.py` — 15 tests: RETR-05, RETR-06 (query routing + classification) ✅
- [x] `tests/test_crag_evaluation.py` — 29 tests: RETR-04 (CRAG grading + reformulation) ✅
- [x] `tests/test_rate_limiting.py` — 8 tests: MON-05 (429 rate limit retry + logging) ✅
- [x] `tests/test_phase3_graph.py` — 7 tests: GEN-02, GEN-03 (graph topology, calculation routing) ✅
- [x] `tests/test_conversation_memory.py` — 6 tests: UI-02 (MemorySaver conversation accumulation) ✅
- [x] `tests/conftest.py` — shared fixtures tersedia (existing, no Phase 3 changes required) ✅

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chat session follow-up question uses conversation context | UI-02 | Requires live Streamlit UI with session state | Start Streamlit, ask question, ask follow-up "jelaskan lebih detail poin ke-2", verify answer references prior context |
| Streamlit UI shows query type badge and conversation counter | UI-02 | Requires visual inspection of Streamlit UI | Start app, run calc query, check badge renders, check sidebar counter |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (full suite: 8.10s for 176 tests)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-03-22

---

## Validation Audit 2026-03-22

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Phase 3 tests total | 65 |
| Full suite (not integration/gpu) | 176 passed |
| Manual verifications | 2 (via UAT 2026-03-22) |
