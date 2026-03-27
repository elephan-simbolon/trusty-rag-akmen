---
phase: 04-scale-and-observability
plan: 01
subsystem: monitoring
tags: [langfuse, observability, tracing, token-usage, cost-tracking]
dependency_graph:
  requires: []
  provides: [langfuse-handler-factory, token-usage-capture, langfuse-settings]
  affects: [app/main.py, src/generation/generator.py, src/llm/client.py]
tech_stack:
  added: [langfuse==4.0.1]
  patterns: [lazy-import-anti-auth-error, new-handler-per-request, graceful-degradation]
key_files:
  created:
    - src/monitoring/langfuse_client.py
    - tests/test_langfuse_integration.py
  modified:
    - config/settings.py
    - .env.example
    - src/llm/client.py
    - app/main.py
    - src/generation/generator.py
decisions:
  - "Lazy import of langfuse inside function body avoids auth errors in test environments (Anti-Pattern from RESEARCH.md)"
  - "New CallbackHandler() per graph.invoke() call prevents trace bleed across Streamlit reruns (Pitfall 7)"
  - "return_usage=False default on generate() preserves backward compatibility for all existing callers"
  - "update_token_usage() wrapped in try/except — token tracking is best-effort, never blocks query pipeline"
  - "Trace-level metadata span (query_type, crag_grade) recorded AFTER graph.invoke — needs result to populate"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_changed: 7
---

# Phase 04 Plan 01: Langfuse Observability Integration Summary

**One-liner:** Langfuse v4 CallbackHandler wired into LangGraph with per-node span tracing, SiliconFlow token usage captured via generate(return_usage=True), and graceful no-op when keys absent.

## What Was Built

### Task 1: Langfuse Settings, Handler Factory, and Token Usage Helper (TDD)

**RED phase:** Wrote 5 failing tests covering handler creation, disabled state, graceful empty-key degradation, token usage key structure, and Settings field existence.

**GREEN phase:** Implemented the actual code so all 5 tests pass:

- **config/settings.py**: Added 4 Langfuse fields (`langfuse_public_key`, `langfuse_secret_key`, `langfuse_base_url`, `langfuse_enabled`) after `lightrag_working_dir`. All default to safe values so `Settings()` works without a `.env` file.
- **.env.example**: Added `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` template entries.
- **src/monitoring/langfuse_client.py**: New file with two exported functions:
  - `get_langfuse_handler(session_id, user_id)` — returns `CallbackHandler` or `None`; uses lazy import to avoid auth errors in test environments; creates new instance per call to prevent trace bleed.
  - `update_token_usage(input_tokens, output_tokens)` — updates current Langfuse observation with `usage_details`; silently no-ops when no active observation.
- **tests/test_langfuse_integration.py**: 5 unit tests, all pass, no live Langfuse connection required.

Commit: `782e90f`

### Task 2: Extend generate(), Wire Langfuse into Streamlit UI, Capture Token Usage

- **src/llm/client.py**: Extended `generate()` signature with `return_usage: bool = False`. When `True`, returns `{"text": ..., "usage": {"prompt_tokens": N, "completion_tokens": N}}` instead of plain `str`. The tenacity `_UI_RETRY_CONFIG` retry decorator is preserved on both return paths. Backward compatible — existing callers get the same `str` return type.
- **app/main.py**: Added `from src.monitoring.langfuse_client import get_langfuse_handler`. In the `graph.invoke` block, creates a `CallbackHandler` per query and passes it via `invoke_config["callbacks"]`. After invoke completes, records trace-level metadata (`query_type`, `crag_grade`, `llm_call_count`, `thread_id`) via `langfuse.start_as_current_observation()`. All Langfuse calls wrapped in `try/except` for best-effort semantics.
- **src/generation/generator.py**: Added `from src.monitoring.langfuse_client import update_token_usage`. Changed `generate(messages, temperature=0.3)` call to `generate(messages, temperature=0.3, return_usage=True)`, extracts usage tokens, calls `update_token_usage()` to inject `usage_details` into the active Langfuse span.

Commit: `13846e7`

## Test Results

- `uv run pytest tests/test_langfuse_integration.py -x -q`: 5/5 passed
- `uv run pytest -m "not integration and not gpu"`: 193/193 passed (no regressions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Installed langfuse dependency before implementation**
- **Found during:** Task 1 setup
- **Issue:** `langfuse` was not yet installed; `import langfuse` would fail
- **Fix:** Ran `uv add langfuse` which installed langfuse 4.0.1 and updated `pyproject.toml` and `uv.lock`
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** `782e90f` (included in Task 1 commit)

**2. [Rule 1 - Bug] Test patching scope fixed for test_handler_created**
- **Found during:** Task 1 GREEN phase (first test run)
- **Issue:** Test patched `sys.modules` before calling the function but outside the `with` block where the import occurs. The lazy `from langfuse.langchain import CallbackHandler` in the function body executed after `patch.dict` exited, so the real langfuse was imported.
- **Fix:** Moved the `get_langfuse_handler()` call inside the combined `with patch(...), patch.dict(...)` context so the mock is active during the lazy import.
- **Files modified:** `tests/test_langfuse_integration.py`
- **Commit:** `782e90f`

## Architecture Decisions Made

| Decision | Rationale |
|----------|-----------|
| Lazy import for langfuse inside function body | Avoids `langfuse.LangfuseAuthenticationError` in test environments where LANGFUSE_PUBLIC_KEY is absent (Anti-Pattern in RESEARCH.md) |
| New `CallbackHandler()` per `graph.invoke()` | Prevents trace bleed between concurrent Streamlit reruns sharing a module-level handler (Pitfall 7 in RESEARCH.md) |
| `return_usage=False` default in `generate()` | Backward compatible — all existing callers continue returning plain `str` without change |
| Trace-level metadata after `graph.invoke` | `query_type` and `crag_grade` exist only in the `result` dict, not before the call |
| `update_token_usage` wrapped in silent `except` | Token tracking failure must never propagate up to the query pipeline or Streamlit UI |

## Self-Check: PASSED

| File | Status |
|------|--------|
| src/monitoring/langfuse_client.py | FOUND |
| tests/test_langfuse_integration.py | FOUND |
| config/settings.py | FOUND |
| .env.example | FOUND |
| src/llm/client.py | FOUND |
| app/main.py | FOUND |
| src/generation/generator.py | FOUND |

| Commit | Status |
|--------|--------|
| 782e90f | FOUND |
| 13846e7 | FOUND |
