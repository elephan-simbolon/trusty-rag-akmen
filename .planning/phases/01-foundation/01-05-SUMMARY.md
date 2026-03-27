---
phase: 01-foundation
plan: 05
subsystem: retrieval
tags: [qdrant, langgraph, hybrid-search, bm25, reranker, qwen3, citation, bilingual]

# Dependency graph
requires:
  - phase: 01-04
    provides: get_qdrant_client, compute_sparse_vector, qdrant upload pipeline
  - phase: 01-01
    provides: embed_query, generate, rerank (llm client functions)
  - phase: 01-02
    provides: config/glossary.py (GLOSSARY, GLOSSARY_REVERSE), config/prompts.py (SYSTEM_PROMPT_GENERATOR)
provides:
  - Hybrid search (dense + BM25 RRF fusion) via src/retrieval/vector_search.py
  - Query preprocessor with glossary expansion + instruction-prefix embedding
  - Reranker wrapper (Qwen3-Reranker-8B) preserving metadata through reranking
  - LangGraph Phase 1 graph: preprocess->retrieve->rerank->generate linear flow
  - Citation builder with deduplication by (book_title, chapter, page_start)
  - Bilingual response generator with glossary snippet injection
affects: [02-graphrag, 03-agentic, ui-phase]

# Tech tracking
tech-stack:
  added: [langgraph StateGraph, NearestQuery for qdrant hybrid prefetch]
  patterns:
    - Linear LangGraph graph with RAGState TypedDict for phase-extensible state
    - NearestQuery(nearest=...) for qdrant-client 1.17.1 Prefetch queries (not Query union type)
    - Error propagation via RAGState["error"] field with graceful fallbacks in each node
    - Citation deduplication by (book_title, chapter, page_start) set membership

key-files:
  created:
    - src/retrieval/preprocessor.py
    - src/retrieval/vector_search.py
    - src/retrieval/reranker.py
    - src/agents/state.py
    - src/agents/nodes.py
    - src/agents/graph.py
    - src/generation/generator.py
    - src/generation/citation_builder.py
  modified:
    - tests/test_retrieval.py
    - tests/test_crosslingual.py
    - tests/test_generation.py

key-decisions:
  - "NearestQuery(nearest=...) is the correct qdrant-client 1.17.1 API for Prefetch queries — Query is a Union type alias, not instantiable"
  - "rerank_node falls back to top-k of retrieved_docs if reranking fails — avoids hard failure on API errors"
  - "generate_node returns Indonesian fallback message when no docs available — no error propagation to UI"
  - "build_citations deduplicates by (book_title, chapter, page_start) — prevents duplicate citations from overlapping chunks"

patterns-established:
  - "RAGState error field: each node checks state.get('error') before executing, propagates gracefully"
  - "Retrieval pipeline: preprocessor -> hybrid_search(top_k=20) -> rerank_results(top_k=5) -> generate_response"
  - "Citation format locked: 'Book Title, Chapter X, hal. N-M' per GEN-01 requirement"

requirements-completed: [RETR-01, RETR-02, LANG-01, LANG-03, GEN-01]

# Metrics
duration: 4min
completed: 2026-03-22
---

# Phase 01 Plan 05: Online Query Pipeline Summary

**Hybrid search (dense+BM25 RRF) + Qwen3 reranker + LangGraph 4-node linear graph + bilingual generator with citation deduplication**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-22T06:04:59Z
- **Completed:** 2026-03-22T06:09:10Z
- **Tasks:** 2 of 2
- **Files modified:** 11

## Accomplishments

- Retrieval pipeline: glossary expansion, dense+BM25 hybrid search via Qdrant RRF, Qwen3-Reranker-8B reranking with metadata passthrough
- LangGraph Phase 1 graph: 4-node linear preprocess->retrieve->rerank->generate flow with RAGState, error propagation, and graceful fallbacks
- Citation builder with "Book, Chapter, hal. N-M" format and deduplication; bilingual generator injects glossary snippet into system prompt
- All 9 tests pass: 2 retrieval, 3 crosslingual, 2 generation (+ 2 previously passing from test_retrieval.py)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create retrieval pipeline (preprocessor, hybrid search, reranker)** - `d6269aa` (feat)
2. **Task 2: Create LangGraph state machine, generator, and citation builder** - `f26b96a` (feat)

**Plan metadata:** (docs commit pending)

## Files Created/Modified

- `src/retrieval/preprocessor.py` - Glossary expansion of Indonesian queries + embed_query with instruction prefix
- `src/retrieval/vector_search.py` - Hybrid search with NearestQuery dense+sparse prefetch and RRF FusionQuery
- `src/retrieval/reranker.py` - Reranking wrapper preserving original metadata through llm_rerank
- `src/agents/state.py` - RAGState TypedDict schema for Phase 1 LangGraph graph
- `src/agents/nodes.py` - preprocess/retrieve/rerank/generate nodes with error propagation
- `src/agents/graph.py` - build_phase1_graph() compiles to CompiledStateGraph
- `src/generation/citation_builder.py` - build_citation/build_citations with dedup by (title,chapter,page)
- `src/generation/generator.py` - Bilingual response synthesis with glossary injection + citation block append
- `tests/test_retrieval.py` - RETR-01 (hybrid search), RETR-02 (reranker reordering) — both pass
- `tests/test_crosslingual.py` - LANG-01 (Indonesian query embedding), LANG-02 (glossary injection), LANG-03 (bilingual output) — all pass
- `tests/test_generation.py` - GEN-01 citation format and required fields — both pass

## Decisions Made

- **NearestQuery not Query:** qdrant-client 1.17.1 `Query` is a Union type alias (not instantiable). `NearestQuery(nearest=...)` is the correct API for Prefetch queries. Auto-fixed per Rule 1.
- **rerank_node fallback:** Falls back to top-k slice of retrieved_docs if reranking fails — avoids hard failure on SiliconFlow API errors.
- **generate_node Indonesian fallback:** Returns Indonesian message ("Tidak ditemukan referensi...") when no docs are available, rather than raising an exception.
- **Citation deduplication:** Deduplicates by (book_title, chapter, page_start) set — prevents duplicate citations from overlapping chunks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Prefetch query instantiation — Query is not instantiable**
- **Found during:** Task 1 (hybrid search implementation)
- **Issue:** Plan specified `Query(nearest=query_embedding)` but `Query` in qdrant-client 1.17.1 is a Union type alias (`typing.Union`) and cannot be instantiated directly — raises `TypeError: Cannot instantiate typing.Union`
- **Fix:** Replaced `Query(nearest=...)` with `NearestQuery(nearest=...)` which is the correct concrete model for nearest-neighbor Prefetch queries
- **Files modified:** src/retrieval/vector_search.py (import and both Prefetch calls)
- **Verification:** Test `test_hybrid_search_returns_results` passes
- **Committed in:** d6269aa (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Required fix for correctness. NearestQuery is the correct qdrant-client API. No scope creep.

## Issues Encountered

None beyond the NearestQuery auto-fix above.

## User Setup Required

None - no external service configuration required for this plan. Tests use mocked Qdrant and SiliconFlow clients.

## Next Phase Readiness

- Online query pipeline is complete and tested. The graph accepts a query string and returns a bilingual response with citations.
- Phase 1 Plan 06 (Streamlit UI) can call `build_phase1_graph()` and invoke the compiled graph with `{"query": user_query}`.
- Phase 3 CRAG integration: add CRAG node between rerank and generate — the graph is intentionally simple to accept this.
- Phase 3 routing: add complexity routing node after preprocess to replace the linear flow with conditional branching.

## Self-Check: PASSED

- All 8 source files exist on disk
- Both task commits (d6269aa, f26b96a) verified in git log
- All 7 tests pass (pytest tests/test_retrieval.py tests/test_crosslingual.py tests/test_generation.py)

---
*Phase: 01-foundation*
*Completed: 2026-03-22*
