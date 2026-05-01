---
phase: 06-kpe-core
plan: "02"
subsystem: kpe-core
tags: [modular-prompt, protocol-registry, compose-system-prompt, rag-state, prot-03, prot-04]
dependency_graph:
  requires: [config/protocols.py, select_protocol()]
  provides: [compose_system_prompt(), RAGState.protocol_key, generate_response(protocol_key)]
  affects: [src/agents/state.py, src/agents/nodes.py, src/generation/generator.py, config/prompts.py]
tech_stack:
  added: []
  patterns: [modular prompt composition, local import to avoid circular, additive blocks, protocol-driven system prompt]
key_files:
  created: []
  modified:
    - config/prompts.py
    - src/agents/state.py
    - src/agents/nodes.py
    - src/generation/generator.py
    - tests/test_synthesis_generation.py
    - tests/test_multi_source_comparison.py
decisions:
  - "Local import of PROTOCOL_REGISTRY inside compose_system_prompt() avoids circular import at module load time"
  - "_SYNTHESIS_BLOCK is appended to _RULES_BLOCK (not a separate section) to maintain numbered rule continuity"
  - "is_calculation=True adds _CALCULATION_BLOCK additively — protocol steps are always included"
  - "select_protocol import added to same line as is_calculation_query for simplicity"
metrics:
  duration: "6 minutes"
  completed: "2026-03-29T13:19:16Z"
  tasks_completed: 2
  files_created: 0
  files_modified: 6
---

# Phase 06 Plan 02: Modular Prompt Composition and Protocol Wiring Summary

**One-liner:** Modular `compose_system_prompt()` assembles 6 ordered blocks (persona, rules, calc, protocol steps, few-shot, glossary) and is wired through RAGState.protocol_key → route_node → generate_response() replacing three hardcoded prompt constants.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add compose_system_prompt() to config/prompts.py | 4d42d8b | config/prompts.py |
| 2 | Extend RAGState, route_node, generate_*_node, generate_response() | 2ca2f3e | src/agents/state.py, src/agents/nodes.py, src/generation/generator.py, tests/test_synthesis_generation.py, tests/test_multi_source_comparison.py |

## Files Modified

### config/prompts.py
- Added deprecated comments before `SYSTEM_PROMPT_GENERATOR`, `SYSTEM_PROMPT_GENERATOR_CALCULATION`, `SYSTEM_PROMPT_SYNTHESIS` — all three remain importable
- Added 4 atomic blocks: `_PERSONA_BLOCK`, `_RULES_BLOCK`, `_SYNTHESIS_BLOCK`, `_CALCULATION_BLOCK`
- Added `compose_system_prompt(protocol_key, glossary_snippet, is_calculation=False, has_graph_context=False) -> str`
- `SYSTEM_PROMPT_REFORMULATOR` unchanged

### src/agents/state.py
- Added `protocol_key: Optional[str]` after `conversation_history` field
- RAGState now has 15 fields (was 14)

### src/agents/nodes.py
- Added `select_protocol` to existing `is_calculation_query` import line
- `route_node()`: calls `select_protocol(query)` and includes `"protocol_key": protocol_key` in both Calculation and Simple return dicts; updated docstring
- `generate_node()`: added `protocol_key=state.get("protocol_key", "general")` to `generate_response()` call
- `generate_calc_node()`: added `protocol_key=state.get("protocol_key", "general")` to `generate_response()` call

### src/generation/generator.py
- Replaced `from config.prompts import (SYSTEM_PROMPT_GENERATOR, SYSTEM_PROMPT_GENERATOR_CALCULATION, SYSTEM_PROMPT_SYNTHESIS)` with `from config.prompts import compose_system_prompt`
- Added `protocol_key: str = "general"` parameter to `generate_response()` signature
- Replaced Phase 3 if/elif/else system_prompt selection block with single `compose_system_prompt()` call
- All other logic (user_content, history, LLM call, citation building, return) unchanged

## compose_system_prompt() Block Structure

| Block # | Content | Condition |
|---------|---------|-----------|
| 1 | `_PERSONA_BLOCK` — persona sentence | Always |
| 2 | `_RULES_BLOCK` (rules 1-5) + `_SYNTHESIS_BLOCK` (rules 6-7) if graph context | Always |
| 3 | `_CALCULATION_BLOCK` — calc disclaimer | Only if `is_calculation=True` |
| 4 | `protocol.steps` — protocol-specific section headers | Always (from PROTOCOL_REGISTRY) |
| 5 | `protocol.few_shot` — example Q&A | Only if non-empty |
| 6 | `Glosarium istilah:\n{glossary_snippet}` | Always |

Blocks joined with `"\n\n"`. Falls back to "general" protocol if `protocol_key` not in registry.

## Deprecated Constants Status

All three deprecated constants remain importable from `config.prompts`:

| Constant | Status | Note |
|----------|--------|------|
| `SYSTEM_PROMPT_GENERATOR` | Importable, deprecated comment added | Used in backward-compat tests |
| `SYSTEM_PROMPT_GENERATOR_CALCULATION` | Importable, deprecated comment added | No longer used at runtime |
| `SYSTEM_PROMPT_SYNTHESIS` | Importable, deprecated comment added | Used in legacy constant tests |
| `SYSTEM_PROMPT_REFORMULATOR` | Unchanged, no comment | Still used by reformulate_node() |

## test_total_field_count Expected Failure

`tests/test_query_routing.py::TestRAGStateFields::test_total_field_count` FAILS as expected:
- Test asserts `len(annotations) == 14`
- RAGState now has 15 fields (protocol_key added)
- Plan 03 will update the test to assert 15 fields

All other 14 tests in test_query_routing.py pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two tests asserted old SYSTEM_PROMPT_SYNTHESIS persona phrase**
- **Found during:** Task 2 — after verifying full unit suite
- **Issue:** `tests/test_synthesis_generation.py::test_synthesis_uses_synthesis_prompt_when_graph_context_present` and `tests/test_multi_source_comparison.py::test_synthesis_prompt_selected_for_multi_source_comparison` both checked `"textbook dan knowledge graph" in system_msg`. This phrase was the persona sentence of the old `SYSTEM_PROMPT_SYNTHESIS` constant. The new `compose_system_prompt()` uses `_PERSONA_BLOCK` ("berdasarkan textbook") + `_SYNTHESIS_BLOCK` (which contains "knowledge graph" separately). The old phrase no longer appears in runtime prompts.
- **Fix:** Updated both assertions to `"knowledge graph" in system_msg` — this phrase is uniquely present in `_SYNTHESIS_BLOCK` and absent from non-synthesis prompts, so the behavioral intent of the test is preserved.
- **Files modified:** tests/test_synthesis_generation.py, tests/test_multi_source_comparison.py
- **Commit:** 2ca2f3e (included in Task 2 commit)

### Pre-existing Failures (Out of Scope, Unchanged)

The following test failures existed before this plan and are unrelated to the changes made:
- `test_query_modes.py` — 9 failures due to `ModuleNotFoundError: No module named 'fast_graphrag'`
- `test_relational_queries.py` — 4 failures due to same missing module
- `test_graph_retrieve.py` — 2 failures due to same missing module
- `test_langfuse_integration.py` — 2 failures due to Langfuse configuration not present in test env
- `test_fastgraphrag_setup.py`, `test_graphrag_ingestion.py` — collection errors due to missing module

## Test Results

```
tests/test_generation.py          — 6 passed
tests/test_synthesis_generation.py — 11 passed (1 assertion updated)
tests/test_multi_source_comparison.py — 9 passed (1 assertion updated)
tests/test_query_routing.py       — 14 passed, 1 FAILED (test_total_field_count — expected, Plan 03 fixes)
tests/test_protocol_registry.py   — 52 passed (unchanged)
tests/test_select_protocol.py     — 18 passed (unchanged)
```

## Known Stubs

None — all prompt blocks and wiring are fully specified with real content.

## Self-Check: PASSED

Files exist:
- FOUND: D:/trusty-rag-akmen/config/prompts.py
- FOUND: D:/trusty-rag-akmen/src/agents/state.py
- FOUND: D:/trusty-rag-akmen/src/agents/nodes.py
- FOUND: D:/trusty-rag-akmen/src/generation/generator.py

Commits exist:
- FOUND: 4d42d8b (feat(06-02): add compose_system_prompt() and deprecated aliases to config/prompts.py)
- FOUND: 2ca2f3e (feat(06-02): extend RAGState, route_node, generate_*_node and generator for protocol_key wiring)
