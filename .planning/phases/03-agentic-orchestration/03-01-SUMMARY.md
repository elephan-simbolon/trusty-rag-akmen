---
phase: 03-agentic-orchestration
plan: "01"
subsystem: agents/retrieval
tags: [langgraph, rag-state, query-routing, rule-based-classification, tdd]
dependency_graph:
  requires: []
  provides:
    - RAGState with 15 fields (Phase 1+2+3 backward-compatible)
    - is_calculation_query rule-based classifier (RETR-06)
    - route_node graph entry point (RETR-05)
  affects:
    - src/agents/graph.py (will import route_node in build_phase3_graph)
    - src/agents/nodes.py (route_node now available)
tech_stack:
  added:
    - src/retrieval/query_classifier.py (new module, stdlib only: re)
  patterns:
    - Annotated[list, operator.add] TypedDict reducer for MemorySaver accumulation
    - Rule-based keyword+number pattern detection (0 LLM calls for Calculation routing)
    - TDD RED→GREEN cycle for pure-function modules
key_files:
  created:
    - src/retrieval/query_classifier.py
    - tests/test_query_routing.py
  modified:
    - src/agents/state.py
    - src/agents/nodes.py
decisions:
  - "Rule-based Calculation detection (keyword AND number) fires before any LLM classifier — saves 1 LLM call, preserves Simple=2 budget (RETR-06)"
  - "route_node always resets crag_iterations=0 and crag_grade=None to prevent MemorySaver persistence from prior turns (Pitfall 1)"
  - "conversation_history uses Annotated[list, operator.add] reducer — LangGraph applies it automatically on state merge, no manual list management needed"
  - "Full 4-tier LLM classifier deferred to Phase 4 — Phase 3 v1 uses rule-based Calculation detection + Simple default"
metrics:
  duration: "3 min"
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_changed: 4
---

# Phase 3 Plan 01: RAGState Extension + Query Routing Summary

**One-liner:** Phase 3 RAGState with 5 new fields, rule-based Calculation detector (0 LLM calls), and route_node as the Phase 3 graph entry point.

## What Was Built

Two tasks completed under a TDD cycle:

**Task 1** extended `src/agents/state.py` with 5 Phase 3 fields while preserving all 10 existing Phase 1+2 fields, created `src/retrieval/query_classifier.py` with the `is_calculation_query` rule-based detector, and created `tests/test_query_routing.py` with 15 tests covering RETR-05, RETR-06, and RAGState field completeness.

**Task 2** added `route_node` to `src/agents/nodes.py` as the Phase 3 graph entry point. The function uses `is_calculation_query` for Calculation detection (0 LLM calls) and defaults to Simple for all other queries. It always resets `crag_iterations=0` and `crag_grade=None` to prevent MemorySaver state bleed across turns.

## Commits

| Hash | Message |
|------|---------|
| b985672 | feat(03-01): extend RAGState for Phase 3 + add is_calculation_query |
| 0ca252d | feat(03-01): add route_node to nodes.py (RETR-05) |

## Test Results

- `tests/test_query_routing.py`: 15/15 passed
- Full suite (`not integration and not gpu`): 126/126 passed, no regressions

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `src/agents/state.py` contains `query_type: Optional[str]` | PASS |
| `src/agents/state.py` contains `crag_grade: Optional[str]` | PASS |
| `src/agents/state.py` contains `crag_iterations: Optional[int]` | PASS |
| `src/agents/state.py` contains `llm_call_count: Optional[int]` | PASS |
| `src/agents/state.py` contains `conversation_history: Annotated[list, operator.add]` | PASS |
| `src/agents/state.py` contains `import operator` | PASS |
| `src/agents/state.py` still contains `graph_docs: Optional[list[dict]]` (Phase 2 preserved) | PASS |
| `src/retrieval/query_classifier.py` contains `def is_calculation_query(query: str) -> bool:` | PASS |
| `src/retrieval/query_classifier.py` contains `_CALC_KEYWORDS = frozenset(` | PASS |
| `src/retrieval/query_classifier.py` contains `_NUMBER_PATTERN = re.compile(` | PASS |
| `tests/test_query_routing.py` exits 0 | PASS |
| `src/agents/nodes.py` contains `def route_node(state: RAGState) -> dict:` | PASS |
| `src/agents/nodes.py` contains `from src.retrieval.query_classifier import is_calculation_query` | PASS |
| `route_node` returns dict with keys: `query_type`, `llm_call_count`, `crag_iterations`, `crag_grade` | PASS |
| `from src.agents.nodes import route_node` succeeds without error | PASS |
| All existing tests pass (no regressions) | PASS |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Item | Result |
|------|--------|
| src/agents/state.py | FOUND |
| src/retrieval/query_classifier.py | FOUND |
| tests/test_query_routing.py | FOUND |
| 03-01-SUMMARY.md | FOUND |
| commit b985672 | FOUND |
| commit 0ca252d | FOUND |
