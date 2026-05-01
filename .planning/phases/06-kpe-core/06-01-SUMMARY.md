---
phase: 06-kpe-core
plan: "01"
subsystem: kpe-core
tags: [protocol-registry, keyword-routing, query-classification, prot-01, prot-02]
dependency_graph:
  requires: []
  provides: [config/protocols.py, select_protocol()]
  affects: [src/retrieval/query_classifier.py, future plan 06-02 (compose_system_prompt)]
tech_stack:
  added: []
  patterns: [frozen dataclass, frozenset keyword matching, word-boundary guard for short abbreviations]
key_files:
  created:
    - config/protocols.py
    - tests/test_protocol_registry.py
    - tests/test_select_protocol.py
  modified:
    - src/retrieval/query_classifier.py
decisions:
  - "ProtocolConfig frozen=True: immutable registry prevents accidental mutation at runtime"
  - "Word-boundary guard for keywords <=4 chars: prevents 'ABC' in non-ABC context matching abc protocol"
  - "_PROTOCOL_PRIORITY order: variance_analysis before budgeting (varians anggaran), cost_classification before cvp (biaya tetap/variabel), cvp last before general"
  - "No import from config/glossary.py in protocols.py: glossary injection deferred to compose_system_prompt() in Plan 02"
metrics:
  duration: "7 minutes"
  completed: "2026-03-29T13:10:02Z"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 06 Plan 01: Protocol Registry and Rule-Based Selector Summary

**One-liner:** Static ProtocolConfig registry with 9 accounting protocols and rule-based `select_protocol()` using frozenset keyword matching with word-boundary guard for short abbreviations.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create config/protocols.py | 891d7ea | config/protocols.py, tests/test_protocol_registry.py |
| 2 | Extend query_classifier.py with select_protocol() | 8ceb217 | src/retrieval/query_classifier.py, tests/test_select_protocol.py |

## Files Created / Modified

### Created
- **`config/protocols.py`** — `ProtocolConfig` frozen dataclass + `PROTOCOL_REGISTRY` dict with 9 protocols
- **`tests/test_protocol_registry.py`** — 52 unit tests for protocol registry (all passing)
- **`tests/test_select_protocol.py`** — 18 unit tests for `select_protocol()` (all passing)

### Modified
- **`src/retrieval/query_classifier.py`** — Added `from config.protocols import PROTOCOL_REGISTRY` import, `_PROTOCOL_PRIORITY` list, and `select_protocol()` function. Existing `is_calculation_query()` untouched.

## Protocol Keys Added to PROTOCOL_REGISTRY

| Key | Display Name | ID Keywords (count) | EN Keywords (count) | Few-Shot |
|-----|-------------|---------------------|---------------------|----------|
| variance_analysis | Variance Analysis | 13 | 11 | Yes |
| abc | Activity-Based Costing | 11 | 6 | No |
| transfer_pricing | Transfer Pricing | 10 | 8 | No |
| relevant_costing | Relevant Costing | 17 | 9 | No |
| product_profitability | Product Profitability | 13 | 7 | No |
| budgeting | Budgeting | 18 | 11 | No |
| cost_classification | Cost Classification | 22 | 13 | No |
| cvp | CVP Analysis | 13 | 7 | Yes |
| general | General | 0 (empty) | 0 (empty) | No |

All 9 protocols contain `## Jawaban Singkat`, `## Analisis`, `## Rekomendasi` in their `steps` field.

## select_protocol() Behavior

**Function signature:** `select_protocol(query: str) -> str`

**Algorithm:**
1. Lowercase the query; pad with spaces for word-boundary matching: `q_padded = f" {q_lower} "`
2. Iterate `_PROTOCOL_PRIORITY` in order
3. For each protocol (except "general"), check all `keywords_id | keywords_en` against the query
4. Short keywords (len ≤ 4): check `f" {kw} " in q_padded` (word-boundary guard)
5. Long keywords (len > 4): check `kw in q_lower` (substring match)
6. Return first matching protocol key, or "general" as fallback

**Priority order:**
```
variance_analysis → abc → transfer_pricing → relevant_costing →
product_profitability → budgeting → cost_classification → cvp → general
```

**Verified routing cases:**

| Query | Expected | Result |
|-------|----------|--------|
| "jelaskan break-even point" | cvp | PASS |
| "hitung varians harga bahan baku" | variance_analysis | PASS |
| "apa itu activity-based costing?" | abc | PASS |
| "bagaimana harga transfer ditetapkan?" | transfer_pricing | PASS |
| "biaya relevan dalam keputusan make or buy" | relevant_costing | PASS |
| "profitabilitas produk lini A" | product_profitability | PASS |
| "bagaimana membuat master budget?" | budgeting | PASS |
| "apa perbedaan biaya tetap dan biaya variabel?" | cost_classification | PASS |
| "apa itu akuntansi manajemen?" | general | PASS |
| "" (empty) | general | PASS |
| "kontrak ABC dengan vendor lainnya" | NOT abc | PASS (word-boundary guard) |

## Decisions Made

1. **`ProtocolConfig` uses `frozen=True`** — Registry is read-only at runtime; prevents mutation bugs in downstream prompt composition.

2. **Word-boundary guard for keywords ≤4 chars** — Short tokens like "abc", "bep", "cvp" appear frequently in non-accounting contexts (e.g., "kontrak ABC dengan vendor"). The padded space check `f" {kw} "` prevents false positives without regex overhead.

3. **`_PROTOCOL_PRIORITY` order** — Specificity-first ordering: `variance_analysis` before `budgeting` (prevents "varians anggaran" from routing to budgeting); `cost_classification` before `cvp` (prevents broad cost terms from routing to CVP prematurely).

4. **No glossary import in `config/protocols.py`** — Glossary expansion happens in `preprocessor.py` and will be injected into system prompts in `compose_system_prompt()` (Plan 02). This avoids circular import risk between `config/protocols.py` and `config/glossary.py`.

5. **TDD approach applied** — Both tasks followed RED-GREEN cycle: failing tests created first, then implementation to make them pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test for "no glossary import" used too-broad string match**
- **Found during:** Task 1 TDD RED → GREEN cycle
- **Issue:** Initial test checked `"glossary" not in source` which failed because the docstring comment mentions "glossary.py" for documentation purposes
- **Fix:** Refined test to only check import statement lines (lines starting with `import ` or `from `) rather than full source
- **Files modified:** tests/test_protocol_registry.py
- **Commit:** 891d7ea (included in Task 1 commit)

### Pre-existing Failures (Out of Scope)

16 tests fail due to missing `fast_graphrag` module (`ModuleNotFoundError: No module named 'fast_graphrag'`). These failures existed before this plan and affect `test_query_modes.py`, `test_relational_queries.py`, `test_fastgraphrag_setup.py`, `test_graphrag_ingestion.py`. All are tagged as `integration` or related to GraphRAG features not modified in this plan.

## Known Stubs

None — all protocol data is fully specified. No hardcoded empty values or placeholder text that would prevent plan goals from being achieved.

## Test Results

```
tests/test_protocol_registry.py  — 52 passed
tests/test_select_protocol.py    — 18 passed
tests/test_query_routing.py      — 15 passed (existing, unchanged)
Total plan-related tests: 85 passed, 0 failed
```

## Self-Check: PASSED

Files exist:
- FOUND: D:/trusty-rag-akmen/config/protocols.py
- FOUND: D:/trusty-rag-akmen/src/retrieval/query_classifier.py
- FOUND: D:/trusty-rag-akmen/tests/test_protocol_registry.py
- FOUND: D:/trusty-rag-akmen/tests/test_select_protocol.py

Commits exist:
- FOUND: 891d7ea (feat(06-01): add ProtocolConfig dataclass and PROTOCOL_REGISTRY)
- FOUND: 8ceb217 (feat(06-01): add select_protocol() rule-based routing)
