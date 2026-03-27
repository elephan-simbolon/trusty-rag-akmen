---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [python, uv, pydantic-settings, openai, tenacity, qdrant, langgraph, pytest, streamlit, qwen3]

# Dependency graph
requires: []
provides:
  - pyproject.toml with all Phase 1 dependencies pinned (langgraph, qdrant-client, mineru, docling, llama-index-core, chonkie)
  - config/settings.py with pydantic-settings BaseSettings and SecretStr API keys
  - config/glossary.py with 125 bilingual EN->ID accounting terms (LANG-02)
  - config/prompts.py with Indonesian system prompts and citation format
  - src/llm/client.py with 5 SiliconFlow API functions (embed_query, embed_document, embed_batch, generate, rerank)
  - Complete test stub infrastructure (32 stubs, all Phase 1 requirements covered)
affects: [01-02, 01-03, 01-04, 01-05, 01-06, all future plans]

# Tech tracking
tech-stack:
  added:
    - pydantic-settings 2.x (type-safe config from .env with SecretStr)
    - openai (OpenAI-compatible SiliconFlow client)
    - tenacity (exponential backoff retry for all API calls)
    - httpx (SiliconFlow /rerank endpoint, not covered by openai client)
    - pytest + pytest-timeout + pytest-asyncio (test infrastructure)
    - langgraph==1.1.3, langchain==1.2.13, qdrant-client==1.17.1
    - mineru==2.7.6, docling==2.81.0, pymupdf==1.27.2.2
    - llama-index-core==0.14.18, chonkie[semantic]==1.6.1
    - PyTorch cu126 wheels (via extra-index-url in pyproject.toml)
  patterns:
    - Asymmetric embedding: embed_query uses instruction prefix, embed_document does not
    - SecretStr for all API keys (never logged or serialized plaintext)
    - Tenacity retry identical config across all 5 API functions: 5 attempts, min=60s, max=300s exponential
    - @pytest.mark.skip stubs for Wave 0 Nyquist compliance (test infrastructure before implementation)
    - Bilingual prompt injection: Indonesian prose + English terms in parentheses

key-files:
  created:
    - pyproject.toml
    - .python-version
    - .env.example
    - .gitignore
    - config/__init__.py
    - config/settings.py
    - config/glossary.py
    - config/prompts.py
    - src/__init__.py
    - src/llm/__init__.py
    - src/llm/client.py
    - src/ingestion/__init__.py
    - src/ingestion/parsing/__init__.py
    - src/ingestion/chunking/__init__.py
    - src/ingestion/indexing/__init__.py
    - src/retrieval/__init__.py
    - src/tools/__init__.py
    - src/agents/__init__.py
    - src/generation/__init__.py
    - src/monitoring/__init__.py
    - app/__init__.py
    - scripts/__init__.py
    - pytest.ini
    - .streamlit/config.toml
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_pdf_parser.py
    - tests/test_vram_cleanup.py
    - tests/test_diagram_extraction.py
    - tests/test_page_markers.py
    - tests/test_element_classifier.py
    - tests/test_chunking.py
    - tests/test_embedding.py
    - tests/test_qdrant_indexing.py
    - tests/test_retrieval.py
    - tests/test_crosslingual.py
    - tests/test_generation.py
  modified: []

key-decisions:
  - "siliconflow_api_key has default SecretStr('') so Settings() works without .env (test environments)"
  - "httpx used directly for /rerank endpoint since openai client has no rerank method"
  - "GLOSSARY has 125 terms (exceeds 100 minimum) across 8 categories for complete bilingual coverage"
  - "Test stubs reference Plan 02-05 in skip reasons to communicate intended implementation timeline"

patterns-established:
  - "Asymmetric embedding pattern: embed_query prefixes with instruction, embed_document does not"
  - "All SiliconFlow API calls wrapped in identical tenacity @retry config via shared _RETRY_CONFIG dict"
  - "config/ module is the single source of truth for settings, glossary, and prompts"
  - "Wave 0 Nyquist: test stubs created alongside implementation scaffold, not after"

requirements-completed: [LANG-02]

# Metrics
duration: 5min
completed: 2026-03-22
---

# Phase 01 Plan 01: Project Scaffold Summary

**uv-managed Python project with pydantic-settings config, 125-term bilingual accounting glossary, tenacity-wrapped SiliconFlow client (5 API functions), and 32 test stubs covering all Phase 1 requirements**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-22T05:34:15Z
- **Completed:** 2026-03-22T05:39:28Z
- **Tasks:** 3
- **Files modified:** 37 created, 0 modified

## Accomplishments

- Complete Python project scaffold with all directories from RESEARCH.md (src/llm, src/ingestion/*, src/retrieval, src/tools, src/agents, src/generation, src/monitoring, app, scripts)
- Type-safe configuration via pydantic-settings with SecretStr for API keys, all SiliconFlow and Qdrant parameters
- SiliconFlow client with 5 functions using identical tenacity retry (embed_query with instruction prefix, embed_document without, embed_batch, generate, rerank)
- 125-term bilingual accounting glossary with GLOSSARY (EN->ID) and GLOSSARY_REVERSE (ID->EN) dicts (LANG-02)
- 32 test stubs across 11 files covering all Phase 1 requirement IDs; pytest exits 0 (all skipped, Wave 0 Nyquist complete)

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold with uv, dependencies, config, and .gitignore** - `6437b1a` (feat)
2. **Task 2: SiliconFlow LLM client with tenacity retry and instruction-prefix embedding** - `3420a75` (feat)
3. **Task 3: Complete test stub infrastructure (Wave 0 Nyquist compliance)** - `dc11343` (test)

**Plan metadata:** (docs commit — see final_commit)

## Files Created/Modified

- `pyproject.toml` - All Phase 1 dependencies pinned, cu126 PyTorch extra-index-url
- `config/settings.py` - pydantic-settings BaseSettings with SecretStr API keys and all model/Qdrant params
- `config/glossary.py` - 125 bilingual accounting terms EN->ID + GLOSSARY_REVERSE dict (LANG-02)
- `config/prompts.py` - Indonesian system prompts with citation format and glossary_snippet placeholder
- `src/llm/client.py` - 5 SiliconFlow API functions with tenacity retry; asymmetric embedding prefix
- `tests/conftest.py` - 5 shared fixtures: sample_pdf_path, sample_markdown, mock_siliconflow, mock_qdrant_client, sample_chunks
- `pytest.ini` - Test configuration with timeout=30, markers (integration, e2e, gpu)
- `tests/test_*.py` (11 files) - 32 stubs covering INGEST-01-05, CHUNK-01-08, INDEX-01-05, RETR-01-02, LANG-01-03, GEN-01
- `.streamlit/config.toml` - Dark theme with Trusty RAG Akmen brand colors
- All `__init__.py` files for complete package structure

## Decisions Made

- `siliconflow_api_key` defaults to `SecretStr("")` so `Settings()` constructs without a .env file in test environments
- Used `httpx.post()` directly for the `/rerank` endpoint since the OpenAI client does not expose a rerank method
- GLOSSARY has 125 terms (exceeds the 100 minimum) spanning 8 categories for comprehensive bilingual coverage
- Shared `_RETRY_CONFIG` dict for tenacity to avoid repeating identical retry parameters across all 5 functions
- Test stubs reference implementing plan numbers in skip reason strings to communicate implementation timeline

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for this scaffold plan. Copy `.env.example` to `.env` and fill in API keys before running any plan that calls SiliconFlow or Qdrant.

## Next Phase Readiness

- Plan 01-02 (PDF parsing pipeline) can import from `config.settings` and `src.llm.client` immediately
- All test stubs are in place; pytest infrastructure is ready for TDD implementation in Plans 02-05
- The `mock_siliconflow` fixture in conftest.py patches `src.llm.client.get_openai_client` at the correct import path

## Self-Check: PASSED

All created files confirmed present. All task commits verified in git log:
- 6437b1a: feat(01-01) scaffold
- 3420a75: feat(01-01) LLM client
- dc11343: test(01-01) test stubs

---
*Phase: 01-foundation*
*Completed: 2026-03-22*
