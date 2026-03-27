---
phase: 03-agentic-orchestration
plan: 03
subsystem: agents
tags: [langgraph, memorysaver, crag, conversation-memory, generate-response, query-type, budget-logging]

# Dependency graph
requires:
  - phase: 03-agentic-orchestration/03-01
    provides: RAGState with Phase 3 fields, route_node, crag_grade_node, crag_router
  - phase: 03-agentic-orchestration/03-02
    provides: reformulate_node, generate_calc_node, query_type stub in generate_response
provides:
  - build_phase3_graph() with full CRAG loop + MemorySaver checkpointer
  - generate_response with Calculation prompt selection + conversation_history injection
  - generate_node and generate_calc_node with RETR-05 llm_call_count logging
  - 13 tests covering graph topology, backward compat, conversation memory accumulation
affects: [03-04-streamlit-ui, app/main.py]

# Tech tracking
tech-stack:
  added: [langgraph.checkpoint.memory.MemorySaver]
  patterns:
    - "MemorySaver compiled graph with thread_id for conversation persistence"
    - "Annotated[list, operator.add] reducer accumulates conversation_history across turns"
    - "query_type parameter selects prompt variant (Calculation/Synthesis/Standard)"
    - "RETR-05 budget observability via logger.info(llm_call_count=...)"
    - "conversation_history slice [-10:] prevents unbounded context growth"

key-files:
  created:
    - tests/test_phase3_graph.py
    - tests/test_conversation_memory.py
  modified:
    - src/agents/graph.py
    - src/generation/generator.py
    - src/agents/nodes.py
    - tests/test_multi_source_comparison.py
    - tests/test_relational_queries.py

key-decisions:
  - "generate_response conversation_history sliced to last 10 messages (5 turns) — prevents Pitfall 3 context overflow"
  - "preprocess_node wired between route and retrieve in Phase 3 graph — RESEARCH.md skeleton was incomplete (intentional plan override)"
  - "sys.modules patching removed from test_phase3_graph.py — LightRAG lazy import in _get_lightrag() means no import-time side effects"
  - "Test mock functions updated with **kwargs to accept query_type and conversation_history without breaking existing mock contract"

patterns-established:
  - "All node mock functions in tests should use **kwargs to accept future generate_response parameters"
  - "build_phase3_graph() follows same backward-compat pattern as build_phase2_graph() — new function alongside, never modify old"

requirements-completed: [GEN-02, GEN-03, UI-02, RETR-05]

# Metrics
duration: 9min
completed: 2026-03-22
---

# Phase 3 Plan 03: Phase 3 Graph Wiring + Conversation Memory Summary

**Phase 3 LangGraph compiled with MemorySaver, full CRAG loop (route -> preprocess -> retrieve -> graph_retrieve -> rerank -> crag_grade -> [generate|generate_calc|reformulate]), and generate_response extended with Calculation prompt selection + conversation history injection**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-22T11:02:27Z
- **Completed:** 2026-03-22T11:11:06Z
- **Tasks:** 2
- **Files modified:** 7 (5 source + 2 test files fixed)

## Accomplishments

- `build_phase3_graph()` compiles full Phase 3 topology with MemorySaver checkpointer — conversation history accumulates across invocations via same `thread_id`
- `generate_response` selects `SYSTEM_PROMPT_GENERATOR_CALCULATION` for Calculation queries and injects last 5 turns of conversation history (10 messages max)
- `generate_node` and `generate_calc_node` both log `llm_call_count` via `logger.info` satisfying RETR-05 budget observability requirement
- Phase 1 and Phase 2 graphs preserved unchanged with full backward compatibility verified
- 13 new tests: graph topology (9 nodes), backward compat, MemorySaver accumulation, thread isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend generate_response + update generate_node** - `84882cc` (feat)
2. **Task 2 RED: Add failing tests** - `fe20345` (test)
3. **Task 2 GREEN: Add build_phase3_graph()** - `8893120` (feat)

_Note: Task 2 used TDD pattern — test commit before implementation commit._

## Files Created/Modified

- `src/agents/graph.py` - Added `build_phase3_graph()` with 9 nodes, CRAG loop, MemorySaver; added imports for new nodes
- `src/generation/generator.py` - Added `conversation_history` param, `SYSTEM_PROMPT_GENERATOR_CALCULATION` import, query_type-based prompt selection
- `src/agents/nodes.py` - Updated `generate_node` (query_type + history + llm_call_count + RETR-05 logging), fixed `generate_calc_node` (RETR-05 logging)
- `tests/test_phase3_graph.py` - New: 8 tests for graph topology, node presence, backward compat, thread_id invocation
- `tests/test_conversation_memory.py` - New: 5 tests for MemorySaver accumulation, thread isolation, Annotated reducer
- `tests/test_multi_source_comparison.py` - Fixed 3 mock signatures (`**kwargs` for new generate_response params)
- `tests/test_relational_queries.py` - Fixed 3 mock signatures (`**kwargs` for new generate_response params)

## Decisions Made

- Conversation history sliced to last 10 messages (5 turns) inside `generate_response` to prevent Pitfall 3 context overflow from RESEARCH.md
- `preprocess_node` wired between `route` and `retrieve` in Phase 3 graph — the RESEARCH.md skeleton showed `route -> retrieve` directly, but preprocess (glossary expansion + embedding) is required before retrieval
- Removed `sys.modules` patching from `test_phase3_graph.py` — LightRAG is lazily imported inside `_get_lightrag()` so no import-time side effects occur
- Test mock functions updated with `**kwargs` to accept `query_type` and `conversation_history` without breaking existing positional argument contract

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock signatures incompatible with new generate_response parameters**

- **Found during:** Task 1 verification (`uv run pytest tests/ -m "not integration and not gpu"`)
- **Issue:** `test_multi_source_comparison.py` and `test_relational_queries.py` defined mock `capture_generate_response(query, context_docs, graph_context="")` without accepting `query_type` or `conversation_history`. When `generate_node` was updated to pass these as keyword args, the mocks raised `TypeError: got an unexpected keyword argument 'query_type'`.
- **Fix:** Added `**kwargs` to all 6 affected mock function signatures in both test files
- **Files modified:** `tests/test_multi_source_comparison.py`, `tests/test_relational_queries.py`
- **Verification:** Full suite went from 1 failure to 163 passed before Task 2
- **Committed in:** `84882cc` (part of Task 1 commit)

**2. [Rule 1 - Bug] Fixed test helper using sys.modules patching causing numpy re-import error**

- **Found during:** Task 2 TDD GREEN phase (first test run)
- **Issue:** `_make_phase3_graph_with_mocks()` used `patch.dict(sys.modules, {"lightrag": MagicMock()})` which caused `ImportError: cannot load module more than once per process` when numpy was triggered by another test in the same session
- **Fix:** Removed the `sys.modules` patch entirely — `graph.py` import doesn't trigger LightRAG at module level (lazy import in `_get_lightrag()`)
- **Files modified:** `tests/test_phase3_graph.py`
- **Verification:** All 13 graph+memory tests pass after fix
- **Committed in:** `8893120` (part of Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in tests caused by new parameters)
**Impact on plan:** Both fixes necessary for tests to run. No scope creep — all fixes directly caused by Task 1 changes.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 graph is fully functional and tested
- `build_phase3_graph()` ready for Streamlit UI integration in Plan 03-04
- Streamlit needs: `st.session_state.session_id = str(uuid.uuid4())` + `thread_id` config passed to `graph.invoke()`
- All 176 non-integration tests pass

## Self-Check: PASSED

- FOUND: src/agents/graph.py (build_phase3_graph, MemorySaver, CRAG edges, preprocess edge, Phase 1+2 preserved)
- FOUND: src/generation/generator.py (query_type, conversation_history, SYSTEM_PROMPT_GENERATOR_CALCULATION, history slice)
- FOUND: src/agents/nodes.py (generate_node with query_type/history/llm_call_count/RETR-05, generate_calc_node RETR-05, CRAG gap msg)
- FOUND: tests/test_phase3_graph.py
- FOUND: tests/test_conversation_memory.py
- FOUND: .planning/phases/03-agentic-orchestration/03-03-SUMMARY.md
- COMMIT 84882cc: FOUND
- COMMIT fe20345: FOUND
- COMMIT 8893120: FOUND
- All 176 non-integration tests pass

---
*Phase: 03-agentic-orchestration*
*Completed: 2026-03-22*
