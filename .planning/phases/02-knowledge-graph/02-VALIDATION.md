---
phase: 2
slug: knowledge-graph
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-22
updated: 2026-03-22
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` (rootdir = D:/trusty-rag-akmen) |
| **Quick run command** | `python -m pytest tests/test_lightrag_setup.py tests/test_entity_normalization.py tests/test_graph_retrieve.py tests/test_synthesis_generation.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~4 seconds |
| **Total tests** | 111 (68 pre-existing + 43 new from Nyquist audit) |

---

## Sampling Rate

- **After every task commit:** Run quick Phase 2 test subset
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** <5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File | Status |
|---------|------|------|-------------|-----------|-------------------|------|--------|
| 2-01-01 | 01 | 1 | INDEX-04 | unit | `python -m pytest tests/test_lightrag_setup.py -x -q` | ✅ exists | ✅ green |
| 2-01-02 | 01 | 1 | INDEX-04 | integration | `python -m pytest tests/test_ingestion.py -x -q` | ✅ exists | ✅ green |
| 2-01-03 | 01 | 1 | INDEX-04 | unit | `python -m pytest tests/test_entity_normalization.py -x -q` | ✅ exists | ✅ green |
| 2-02-01 | 02 | 2 | RETR-03 | unit | `python -m pytest tests/test_graph_retrieve.py -x -q` | ✅ exists | ✅ green |
| 2-02-02 | 02 | 2 | RETR-03 | integration | `python -m pytest tests/test_query_modes.py -x -q` | ✅ exists | ✅ green |
| 2-03-01 | 03 | 3 | GEN-04 | manual | N/A — synthesis quality judgment | N/A | manual-only |
| 2-03-02 | 03 | 3 | GEN-05 | integration | `python -m pytest tests/test_relational_queries.py -x -q` | ✅ exists | ✅ green |
| 2-03-03 | 03 | 3 | GEN-06 | integration | `python -m pytest tests/test_multi_source_comparison.py -x -q` | ✅ exists | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-textbook synthesis quality (Horngren vs Garrison) | GEN-04 | Synthesis quality is subjective — requires human evaluation of attribution accuracy and relevance | Ask "bandingkan pandangan Horngren vs Garrison tentang overhead allocation", verify answer attributes perspectives to correct source textbooks |
| Indonesian query × English knowledge graph correctness | GEN-05, GEN-06 | Cross-lingual retrieval quality requires domain expert judgment | Ask relational query in Indonesian, verify answer draws on knowledge graph relationships not just vector similarity |

---

## Validation Sign-Off

- [x] All tasks have automated verify or manual-only designation
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] All MISSING gaps filled by Nyquist auditor (4/4)
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ✅ complete

---

## Validation Audit 2026-03-22

| Metric | Count |
|--------|-------|
| Gaps found | 4 |
| Resolved | 4 |
| Escalated | 0 |
| Tests before audit | 68 |
| Tests after audit | 111 |
| New test files | 4 (test_ingestion.py, test_query_modes.py, test_relational_queries.py, test_multi_source_comparison.py) |
