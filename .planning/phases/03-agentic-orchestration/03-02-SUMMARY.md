---
phase: 03-agentic-orchestration
plan: "02"
subsystem: agents
tags: [crag, quality-gate, rate-limiting, nodes, generator, tdd]
dependency_graph:
  requires: [03-01]
  provides: [crag_grade_node, reformulate_node, crag_router, generate_calc_node, query_type-stub, _log_rate_limit]
  affects: [src/agents/nodes.py, src/generation/generator.py, src/llm/client.py]
tech_stack:
  added: []
  patterns: [CRAG quality gate, tenacity before_sleep callback, TDD RED/GREEN]
key_files:
  created:
    - tests/test_crag_evaluation.py
    - tests/test_rate_limiting.py
  modified:
    - src/agents/nodes.py
    - src/generation/generator.py
    - src/llm/client.py
decisions:
  - "crag_grade_node reads rerank_score key (not score) from reranked_docs — matches reranker.py interface contract"
  - "crag_router caps at iterations >= 2 to allow exactly 2 reformulation attempts before graceful degradation"
  - "query_type is a no-op stub in generate_response — accepted but not yet used for prompt selection (full implementation in 03-03)"
  - "_log_rate_limit delegates non-429 errors to tenacity's before_sleep_log — no change in retry behavior, only logging enhancement"
metrics:
  duration: 5 min
  completed: "2026-03-22"
  tasks_completed: 2
  files_modified: 5
---

# Phase 03 Plan 02: CRAG Quality Gate + Rate Limit Logging Summary

**One-liner:** CRAG quality gate nodes (grade/router/reformulate) + generate_calc_node with Calculation routing + 429-specific rate limit logging via _log_rate_limit tenacity callback.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | crag_grade_node, crag_router, reformulate_node, generate_calc_node + query_type stub | fcf02cf | src/agents/nodes.py, src/generation/generator.py |
| 2 | Rate limit handling enhancement (MON-05) | d45be57 | src/llm/client.py, tests/test_rate_limiting.py |

**Test commits (TDD RED phase):**
- 11cbb03: test(03-02): failing tests for CRAG nodes and generate_response stub (29 tests)
- f3e5a04: test(03-02): failing tests for 429 rate limit handling (8 tests)

## What Was Built

### Task 1: CRAG Quality Gate Nodes

**`crag_grade_node(state)`** — Grades retrieval quality from reranker scores already in state (zero additional API calls):
- Reads `rerank_score` from `reranked_docs` (not `score` — critical for correct key)
- Thresholds: `>= 0.5` → CORRECT, `>= 0.2` → AMBIGUOUS, `< 0.2` → INCORRECT
- Empty/None reranked_docs → INCORRECT
- Increments `crag_iterations` by 1

**`crag_router(state)`** — Conditional edge function:
- CORRECT or `iterations >= 2` (cap) → `"generate"` or `"generate_calc"` based on `query_type`
- AMBIGUOUS/INCORRECT under cap → `"reformulate"`
- Graceful degradation: at cap, serves best-effort answer instead of refusing

**`reformulate_node(state)`** — LLM-based query reformulation:
- Writes to `"query"` key so `retrieve_node` reads it on next loop iteration
- Costs 1 LLM call, increments `llm_call_count`
- On failure: keeps original query, does not increment count

**`generate_calc_node(state)`** — Calculation-specific generation:
- Calls `generate_response(query_type="Calculation")`
- Returns response with disclaimer (via SYSTEM_PROMPT_GENERATOR_CALCULATION)
- Adds `conversation_history` with user/assistant turns
- Falls back gracefully on error or empty docs

**`generate_response` stub:** Added `query_type: str = "Simple"` as backward-compatible no-op parameter. Accepted but ignored — full prompt selection logic goes in Plan 03-03.

### Task 2: Rate Limit Logging (MON-05)

**`_log_rate_limit(retry_state)`** — Custom tenacity before_sleep callback:
- 429 errors → logs `"SiliconFlow rate limit (429) hit — retrying in X.Xs (attempt N)"`
- Non-429 errors → delegates to `before_sleep_log(logger, logging.WARNING)`
- Both `_RETRY_CONFIG` and `_UI_RETRY_CONFIG` now use this callback
- Retry behavior unchanged (tenacity still catches all Exception subclasses)

## Verification

```
uv run pytest tests/test_crag_evaluation.py tests/test_rate_limiting.py -x -q
# 37 passed

uv run python -c "from src.agents.nodes import crag_grade_node, crag_router, reformulate_node, generate_calc_node; print('All CRAG nodes importable')"
# All CRAG nodes importable

uv run python -c "from src.generation.generator import generate_response; import inspect; sig = inspect.signature(generate_response); assert 'query_type' in sig.parameters; print('query_type stub OK')"
# query_type stub OK

uv run pytest tests/ -m "not integration and not gpu" -q
# 163 passed, 17 warnings
```

## Decisions Made

1. **rerank_score key (not score):** `crag_grade_node` uses `doc.get("rerank_score", 0.0)` — matches the interface contract in `reranker.py` which sets `"rerank_score"` on each result dict. RESEARCH.md example used wrong key `"score"`.

2. **Cap at iterations >= 2:** Allows 2 reformulation loops (iterations 1 and 2) before degrading to generate. The cap is checked AFTER `crag_grade_node` increments, so `iterations >= 2` means we've already tried at least twice.

3. **query_type no-op stub:** Adding `query_type: str = "Simple"` to `generate_response` now means `generate_calc_node` can call it without TypeError. The actual prompt switching (SYSTEM_PROMPT_GENERATOR_CALCULATION) is deferred to Plan 03-03 Task 1 to keep this plan's scope bounded.

4. **_log_rate_limit delegation:** Non-429 errors go through tenacity's own `before_sleep_log` to preserve existing logging behavior — only 429s get the special "SiliconFlow rate limit" message for MON-05 monitoring dashboards.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect test calling convention for tenacity retry predicate**
- **Found during:** Task 2 GREEN phase
- **Issue:** Test `test_retry_config_contains_httpx_status_error` called the tenacity `retry_if_exception_type` predicate with a raw exception object, but the predicate expects a `retry_state` object with an `outcome` attribute. This raised `AttributeError: 'HTTPStatusError' object has no attribute 'outcome'`.
- **Fix:** Rewrote test to verify (a) the retry is an `isinstance` of `retry_if_exception_type`, and (b) `httpx.HTTPStatusError` is a subclass of `Exception`, confirming coverage without needing to call the predicate directly.
- **Files modified:** tests/test_rate_limiting.py
- **Commit:** d45be57 (included in GREEN commit)

## Self-Check: PASSED

All files present:
- FOUND: src/agents/nodes.py
- FOUND: src/generation/generator.py
- FOUND: src/llm/client.py
- FOUND: tests/test_crag_evaluation.py
- FOUND: tests/test_rate_limiting.py

All commits verified:
- 11cbb03: test(03-02) RED phase CRAG tests
- fcf02cf: feat(03-02) CRAG nodes + query_type stub
- f3e5a04: test(03-02) RED phase rate limiting tests
- d45be57: feat(03-02) rate limit logging
