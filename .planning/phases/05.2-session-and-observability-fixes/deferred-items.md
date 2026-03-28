# Deferred Items — Phase 05.2

## Pre-existing Test Failures (out of scope for 05.2-01)

These failures existed before Phase 05.2 changes and are unrelated to session_id/Langfuse wiring.
Verified by running the test suite against the baseline commit before any 05.2 changes.

### test_qdrant_indexing.py — Collection error
- `ImportError: cannot import name 'upload_chunks'` — the uploader API changed but test not updated.

### test_graph_retrieve.py (6 failures) + test_query_modes.py (20+ failures)
- All fail with `AttributeError: 'src.agents.nodes' does not have attribute '_get_lightrag'`
- The `_get_lightrag` private function was renamed or removed; tests not updated.

### test_multi_source_comparison.py (1 failure)
- `test_synthesis_prompt_selected_for_multi_source_comparison` — likely related to nodes.py change.

**Total pre-existing failures:** 32 tests in 4 test files.
**Impact on 05.2-01:** None. All 12 new/modified tests in `test_session_id.py` and `test_langfuse_integration.py` pass.
