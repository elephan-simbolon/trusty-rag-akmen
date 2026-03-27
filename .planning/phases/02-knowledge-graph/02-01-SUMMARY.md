---
phase: 02-knowledge-graph
plan: 01
subsystem: knowledge-graph
tags: [lightrag, lightrag-hku, nano-vectordb, entity-normalization, knowledge-graph, siliconflow, qwen3, async, ingestion]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: config/settings.py Settings class, config/glossary.py GLOSSARY/GLOSSARY_REVERSE, Phase 1 chunk backup JSON format
provides:
  - LightRAG client module with SiliconFlow-backed async LLM and embedding functions
  - ACCOUNTING_ENTITY_TYPES (10 domain-specific entity categories)
  - Entity normalizer with 27 variant->canonical mappings for deduplication
  - Async ingestion pipeline with source metadata prepending and audit/full modes
  - CLI script for offline LightRAG ingestion (scripts/ingest_lightrag.py)
affects: [02-02-graph-retrieval, 02-03-synthesis-generation, phase-03-agentic]

# Tech tracking
tech-stack:
  added: [lightrag-hku==1.4.11, nest-asyncio]
  patterns:
    - Async LightRAG functions wrapping openai_complete_if_cache and openai_embed
    - EmbeddingFunc adapter pattern for LightRAG embedding integration
    - audit_mode=True default for 50-chunk quality verification before full ingestion
    - Failed-chunk exception swallowing with logging (no re-raise) to prevent zombie task pollution
    - Source metadata prepended to chunks: "[Source: book, chapter, page]\n\ntext"

key-files:
  created:
    - src/knowledge_graph/__init__.py
    - src/knowledge_graph/lightrag_client.py
    - src/knowledge_graph/entity_normalizer.py
    - src/knowledge_graph/graph_ingestion.py
    - scripts/ingest_lightrag.py
    - tests/test_lightrag_setup.py
    - tests/test_entity_normalization.py
  modified:
    - config/settings.py (added lightrag_working_dir field)

key-decisions:
  - "_embedding_func uses no instruction prefix — LightRAG embeds entities as documents, not queries (asymmetric prefix applies only to Qdrant path)"
  - "audit_mode=True (50 chunks) is the default — always sample before full ingestion to verify entity extraction quality on accounting domain"
  - "Individual chunk failures are logged and counted but not re-raised — prevents zombie task pollution mid-batch"
  - "lightrag-hku installs nano-vectordb (file-based JSON) as built-in storage — no Qdrant routing for LightRAG vectors (locked decision from pre-phase 1)"

patterns-established:
  - "Pattern 1: LightRAG async initialization — always call initialize_storages() after construction, finalize_storages() after ingestion"
  - "Pattern 2: SiliconFlow-backed LightRAG — pass base_url and api_key via openai_complete_if_cache and openai_embed, not via environment variables"
  - "Pattern 3: Entity normalization priority order — exact match > case-insensitive > GLOSSARY_REVERSE > return unchanged"

requirements-completed: [INDEX-04]

# Metrics
duration: 8min
completed: 2026-03-22
---

# Phase 02 Plan 01: LightRAG Knowledge Graph Client and Ingestion Pipeline Summary

**LightRAG knowledge graph client with Qwen3-30B-A3B via SiliconFlow, 10 accounting entity types, 27-variant entity normalizer, and async ingestion pipeline with 50-chunk audit mode**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-22T08:44:00Z
- **Completed:** 2026-03-22T08:52:57Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- LightRAG initialized with Qwen3-30B-A3B (LLM) and Qwen3-Embedding-8B (embedding) via SiliconFlow, with 10 accounting-specific entity types in addon_params
- Entity normalizer with 27 variant->canonical mappings (plus GLOSSARY_REVERSE fallback) resolves LightRAG entity deduplication problem before graph is queryable
- Async ingestion pipeline reads Phase 1 JSON chunk backup, prepends source metadata, and inserts with audit/full modes — all 15 unit tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: LightRAG client module with SiliconFlow backend** - `8365203` (feat)
2. **Task 2: Entity normalizer and ingestion pipeline with CLI** - `e1a123d` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `src/knowledge_graph/__init__.py` - Empty module init
- `src/knowledge_graph/lightrag_client.py` - ACCOUNTING_ENTITY_TYPES, async _llm_model_func, async _embedding_func, EmbeddingFunc, build_lightrag_instance()
- `src/knowledge_graph/entity_normalizer.py` - ACCOUNTING_CANONICAL (27 entries), normalize_entity_name() with 3-step priority
- `src/knowledge_graph/graph_ingestion.py` - ingest_chunks_to_lightrag() async with audit_mode, source metadata prepend, finalize_storages()
- `scripts/ingest_lightrag.py` - CLI with argparse, chunks_path positional, --full flag
- `tests/test_lightrag_setup.py` - 6 unit tests for LightRAG client setup
- `tests/test_entity_normalization.py` - 9 unit tests for entity normalization
- `config/settings.py` - Added lightrag_working_dir: str = "./lightrag_storage"

## Decisions Made

- `_embedding_func` has no instruction prefix — LightRAG embeds entities as documents, not queries. Asymmetric prefix strategy applies only to the Qdrant retrieval path (embed_query in src/llm/client.py)
- `audit_mode=True` is the default — always verify 50-chunk entity extraction quality before full ingestion (accounting domain extraction quality is unverified)
- Individual chunk failures are caught, logged, and counted but not re-raised — prevents zombie task pollution per LightRAG Pitfall 2 in research doc
- LightRAG uses built-in nano-vectordb (file-based JSON) — no Qdrant routing, locked decision from pre-phase 1 to avoid configuration conflicts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing lightrag-hku dependency**
- **Found during:** Pre-task setup (before Task 1 execution)
- **Issue:** `lightrag-hku==1.4.11` was not installed; `import lightrag` raised ModuleNotFoundError
- **Fix:** Ran `pip install lightrag-hku==1.4.11 nest-asyncio`
- **Files modified:** None (package installation only)
- **Verification:** `python -c "import lightrag; print(lightrag.__version__)"` prints `v1.4.11`
- **Committed in:** Not committed (runtime dependency, listed in requirements)

---

**Total deviations:** 1 auto-fixed (1 blocking — missing dependency)
**Impact on plan:** Necessary prerequisite for all subsequent LightRAG work. No scope creep.

## Issues Encountered

None — after dependency installation, all plan tasks executed exactly as specified.

## User Setup Required

None — no external service configuration required for the module itself. The ingestion CLI requires a `.env` file with `SILICONFLOW_API_KEY` when actually running ingestion against SiliconFlow (existing requirement from Phase 1).

## Next Phase Readiness

- LightRAG client ready for Plan 02-02 (graph retrieval node integration into LangGraph)
- Entity normalizer ready to apply post-extraction during online query path
- Ingestion CLI ready for 50-chunk audit run against Phase 1 chunk backup JSON
- LightRAG working dir (`./lightrag_storage`) will be created on first `build_lightrag_instance()` call

---
*Phase: 02-knowledge-graph*
*Completed: 2026-03-22*
