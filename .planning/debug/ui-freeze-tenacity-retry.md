---
status: diagnosed
trigger: "UI freeze selama beberapa menit karena tenacity retry (5 attempts × 60-300s backoff) memblokir sebelum error handler muncul"
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:00:00Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: CONFIRMED — rerank() in src/llm/client.py is decorated with _RETRY_CONFIG (5 attempts, 60-300s backoff) and is called synchronously from the Streamlit UI main thread via the chain: app/main.py:68 -> graph.invoke -> rerank_node -> rerank_results -> rerank(). This is the sole surviving violation of the UI-thread rule established in the codebase's own _UI_RETRY_CONFIG docstring.
test: traced full call chain from app/main.py through graph.invoke() into every node
expecting: all API-calling functions in the UI-facing path use _UI_RETRY_CONFIG; rerank() is the exception
next_action: return diagnosis

## Symptoms

expected: UI menampilkan pesan error Bahasa Indonesia segera setelah API gagal, tanpa freeze berkepanjangan
actual: UI freeze selama beberapa menit karena tenacity retry (5 attempts × 60-300s backoff) memblokir sebelum error handler muncul
errors: UI freeze / no response for several minutes when API fails
reproduction: trigger API failure (e.g., network error or invalid key), observe UI freezing for minutes before error message appears
started: reported in UAT test 11

## Eliminated

- hypothesis: embed_query() uses the slow _RETRY_CONFIG
  evidence: embed_query() at client.py:78 is decorated with @retry(**_UI_RETRY_CONFIG) — correctly fast-fail
  timestamp: 2026-03-22

- hypothesis: generate() uses the slow _RETRY_CONFIG
  evidence: generate() at client.py:118 is decorated with @retry(**_UI_RETRY_CONFIG) — correctly fast-fail
  timestamp: 2026-03-22

- hypothesis: the freeze happens in the Streamlit graph setup (build_phase1_graph)
  evidence: graph is built once at session init (main.py:31), not on each query invocation; no API calls there
  timestamp: 2026-03-22

- hypothesis: vector_search.py introduces a blocking retry
  evidence: hybrid_search() has no tenacity decorator at all; uses Qdrant client directly with no retry wrapper
  timestamp: 2026-03-22

## Evidence

- timestamp: 2026-03-22
  checked: src/llm/client.py lines 30-50
  found: two distinct retry configs defined — _RETRY_CONFIG (stop=5, wait=60-300s) for batch/ingestion; _UI_RETRY_CONFIG (stop=2, wait=2-10s) for UI-facing functions. Docstring at line 40 explicitly states "Streamlit memblokir seluruh UI thread selama tenacity menunggu"
  implication: the codebase author was aware of the Streamlit single-thread blocking problem and attempted to fix it with _UI_RETRY_CONFIG

- timestamp: 2026-03-22
  checked: src/llm/client.py lines 61, 78, 95, 118, 139
  found: embed_document @retry(**_RETRY_CONFIG), embed_query @retry(**_UI_RETRY_CONFIG), embed_batch @retry(**_RETRY_CONFIG), generate @retry(**_UI_RETRY_CONFIG), rerank @retry(**_RETRY_CONFIG)
  implication: rerank() at line 139 uses _RETRY_CONFIG (5 attempts × 60-300s) — the slow batch config — even though it is called in the UI-facing query path

- timestamp: 2026-03-22
  checked: app/main.py line 68
  found: result = st.session_state.graph.invoke({"query": last_msg["content"]}) — called synchronously inside st.spinner(), blocking the Streamlit UI thread
  implication: any tenacity wait inside graph.invoke() holds the entire UI thread; no async escape

- timestamp: 2026-03-22
  checked: src/agents/graph.py — graph node order: preprocess -> retrieve -> rerank -> generate
  found: rerank_node is the 3rd step in every query invocation
  implication: a reranker API failure triggers _RETRY_CONFIG on rerank(), causing up to 5 × 300s = 1500s of blocking before raising; in practice worst case for 5 attempts with exponential backoff: attempt 1 waits 60s, attempt 2 waits ~120s, attempt 3 waits ~240s, attempt 4 waits 300s, attempt 5 waits 300s = 1020s total

- timestamp: 2026-03-22
  checked: src/retrieval/reranker.py line 26 — rerank_results() calls llm_rerank() (alias for client.rerank)
  found: no additional try/except around llm_rerank; exceptions propagate up to rerank_node which catches them (nodes.py:52), but only AFTER tenacity exhausts all retry attempts
  implication: tenacity's retry loop runs inside the call, before the exception reaches rerank_node's except clause — so rerank_node's fallback to unreranked docs only fires after the full backoff sequence

- timestamp: 2026-03-22
  checked: src/agents/nodes.py lines 41-55 (rerank_node)
  found: rerank_node has try/except that falls back to unreranked results on failure, BUT this catch only triggers after tenacity on rerank() re-raises after all 5 attempts
  implication: the fallback logic is sound, but it is invisible to the user for up to ~17 minutes before activating

## Resolution

root_cause: rerank() in src/llm/client.py (line 139) is decorated with @retry(**_RETRY_CONFIG) — the batch ingestion config with stop_after_attempt(5) and wait_exponential(min=60, max=300) — instead of @retry(**_UI_RETRY_CONFIG). Because rerank() is called synchronously from the Streamlit main thread via app/main.py:68 -> graph.invoke() -> rerank_node -> rerank_results() -> rerank(), every reranker API failure causes tenacity to hold the UI thread for up to ~17 minutes (5 retries × up to 300s backoff each) before the exception propagates to rerank_node's fallback handler or app/main.py's except clause, which then renders the Indonesian error message.

fix: change @retry(**_RETRY_CONFIG) on rerank() (client.py line 139) to @retry(**_UI_RETRY_CONFIG). This limits the worst-case freeze to 2 attempts × 10s max = ~12s before reraise, which is within the "below 30 seconds" contract already established by the codebase's own _UI_RETRY_CONFIG docstring. The rerank_node fallback (unreranked results) then activates quickly.
verification: not yet applied
files_changed: [src/llm/client.py]
