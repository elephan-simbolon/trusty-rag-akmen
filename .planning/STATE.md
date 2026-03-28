---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Milestone v1.0 archived, ready for next milestone
stopped_at: v1.0 archive complete (ROADMAP + REQUIREMENTS archived, git tag v1.0 applied)
last_updated: "2026-03-28T00:00:00Z"
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 26
  completed_plans: 26
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-22)

**Core value:** Mempercepat pencarian referensi akuntansi dari 45-60 menit menjadi 5-10 menit, dengan source citation (buku, chapter, halaman) yang bisa dipertanggungjawabkan ke klien
**Current focus:** Phase 05.2 — session-and-observability-fixes

## Current Position

Phase: 05.2
Plan: Not started

## Performance Metrics

**Velocity:**

- Total plans completed: 2
- Average duration: 6 min
- Total execution time: 0.20 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 6/6 | 39 min | 7 min |

**Recent Trend:**

- Last 5 plans: 01-01 (5 min), 01-02 (7 min), 01-03 (12 min)
- Trend: stable

*Updated after each plan completion*
| Phase 01-foundation P04 | 4 | 2 tasks | 6 files |
| Phase 01-foundation P05 | 4 | 2 tasks | 11 files |
| Phase 01-foundation P06 | 15 | 3 tasks | 2 files |
| Phase 01-foundation P08 | 525538 | 1 tasks | 1 files |
| Phase 01-foundation P08 | 5 | 1 tasks | 1 files |
| Phase 02-knowledge-graph P01 | 8 | 2 tasks | 8 files |
| Phase 02-knowledge-graph P02 | 4 | 2 tasks | 4 files |
| Phase 02-knowledge-graph P03 | 4 | 2 tasks | 4 files |
| Phase 03-agentic-orchestration P01 | 3 | 2 tasks | 4 files |
| Phase 03-agentic-orchestration P02 | 5 | 2 tasks | 5 files |
| Phase 03-agentic-orchestration P03 | 9 | 2 tasks | 7 files |
| Phase 03-agentic-orchestration P04 | 4 | 2 tasks | 4 files |
| Phase 04-scale-and-observability P01 | 4 | 2 tasks | 7 files |
| Phase 04-scale-and-observability P04-02 | 12 | 2 tasks | 5 files |
| Phase 04-scale-and-observability P03 | 12 | 2 tasks | 4 files |
| Phase 04-scale-and-observability P04 | 2 | 1 tasks | 3 files |
| Phase 04.1-ingestion-polish P01 | 4 | 1 tasks | 2 files |
| Phase 04.1-ingestion-polish P02 | 10 | 2 tasks | 3 files |
| Phase 05-polish P01 | 4 | 2 tasks | 3 files |
| Phase 05.1-cleanup-and-hardening P01 | 5 | 2 tasks | 2 files |
| Phase 05.1-cleanup-and-hardening P02 | 5 | 2 tasks | 7 files |
| Phase 05.2-session-and-observability-fixes P01 | 6 | 3 tasks | 7 files |
| Phase 05.2-session-and-observability-fixes P02 | 8 | 1 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Use cu126 PyTorch wheels (not cu128) — GTX 1660 Ti CC 7.5 safety margin
- [Pre-Phase 1]: LightRAG uses built-in nano-vectordb, not Qdrant — avoids configuration conflicts
- [Pre-Phase 1]: Langfuse over LangSmith — MIT license, self-hostable, better for accounting data privacy
- [Pre-Phase 1]: Never run MinerU and Docling in the same Python process — VRAM fragmentation bug #3399
- [Pre-Phase 1]: Inline page markers injected at parse time — critical for citation accuracy (core value)
- [01-01]: siliconflow_api_key defaults to SecretStr("") so Settings() works without .env (test environments)
- [01-01]: httpx used directly for /rerank endpoint — openai client has no rerank method
- [01-01]: Shared _RETRY_CONFIG dict for tenacity — avoid repeating identical retry params across 5 functions
- [01-01]: Asymmetric embedding — embed_query uses instruction prefix, embed_document does not (LANG-02)
- [Phase 01-02]: sys.modules patching used to mock docling in tests — lazy imports inside function body require full module injection
- [Phase 01-02]: VLM_CAPTION_PROMPT outputs English-only — captions feed into English-indexed vector store for cross-lingual retrieval
- [Phase 01-03]: TABLE_SEPARATOR regex includes | in character class to correctly match multi-column separator rows like '| --- | --- | --- |'
- [Phase 01-03]: Formula index synthetic chunk uses page_start=0/page_end=0 — it aggregates formulas from across a chapter and is not tied to any specific page
- [Phase 01-03]: classify_element priority: table > formula > example_problem > diagram > narrative_text — prevents mis-classification of mixed-content blocks
- [Phase 01-04]: ScalarQuantization(scalar=ScalarQuantizationConfig(...)) is correct qdrant-client v1.17.1 API — QuantizationConfig is a Union type alias, not instantiable directly
- [Phase 01-04]: BM25 sparse vectors use abs(hash(word)) % 2^31 for stable word-to-index mapping without a vocabulary file
- [Phase 01-04]: Chunk backup to JSON saved before embedding (step 7) — allows re-embedding without re-parsing if SiliconFlow interrupts
- [Phase 01-05]: NearestQuery(nearest=...) is correct qdrant-client 1.17.1 API for Prefetch — Query is a Union type alias, not instantiable
- [Phase 01-05]: rerank_node falls back to top-k slice of retrieved_docs on API failure — avoids hard failure on SiliconFlow errors
- [Phase 01-05]: build_citations deduplicates by (book_title, chapter, page_start) set — prevents duplicate citations from overlapping retrieval chunks
- [Phase 01-06]: st.session_state.processing flag disables chat input during graph.invoke — prevents duplicate submissions on Streamlit reruns
- [Phase 01-06]: CLI test_query imports build_phase1_graph lazily inside function body — allows syntax checking without SiliconFlow credentials
- [Phase 01-08]: rerank() adalah UI-facing function karena dipanggil dari rerank_node -> LangGraph graph -> graph.invoke() di Streamlit UI thread; harus menggunakan _UI_RETRY_CONFIG bukan _RETRY_CONFIG
- [Phase 02-knowledge-graph]: _embedding_func uses no instruction prefix — LightRAG embeds entities as documents, not queries (asymmetric prefix applies only to Qdrant path)
- [Phase 02-knowledge-graph]: audit_mode=True (50 chunks) default for LightRAG ingestion — always sample before full ingestion to verify entity extraction quality on accounting domain
- [Phase 02-knowledge-graph]: Individual LightRAG chunk failures logged and counted but not re-raised — prevents zombie task pollution mid-batch
- [Phase 02-knowledge-graph]: nest_asyncio.apply() at module level in nodes.py — enables asyncio.run() inside Streamlit event loop without 'already running' error
- [Phase 02-knowledge-graph]: Sequential pipeline (retrieve -> graph_retrieve -> rerank) chosen over parallel branching for Phase 2 simplicity
- [Phase 02-knowledge-graph]: Phase 1 graph build_phase1_graph() preserved for backward compatibility and rollback
- [Phase 02-knowledge-graph]: SYSTEM_PROMPT_SYNTHESIS placed after existing prompts — preserves Phase 1 prompts unchanged
- [Phase 02-knowledge-graph]: graph_context defaults to empty string — generate_response backward compatible, Phase 1 callers need no changes
- [Phase 02-knowledge-graph]: generate_node joins graph_docs texts with double newline — single text block avoids per-doc formatting overhead
- [Phase 03-agentic-orchestration]: Rule-based Calculation detection (keyword AND number) fires before any LLM classifier — saves 1 LLM call, preserves Simple=2 budget (RETR-06)
- [Phase 03-agentic-orchestration]: route_node always resets crag_iterations=0 and crag_grade=None to prevent MemorySaver persistence from prior turns (Pitfall 1)
- [Phase 03-agentic-orchestration]: conversation_history uses Annotated[list, operator.add] reducer — LangGraph applies it automatically on state merge, no manual list management needed
- [Phase 03-agentic-orchestration]: Full 4-tier LLM classifier deferred to Phase 4 — Phase 3 v1 uses rule-based Calculation detection + Simple default
- [Phase 03-agentic-orchestration]: crag_grade_node reads rerank_score key from reranked_docs — matches reranker.py interface contract (RESEARCH.md example used wrong key 'score')
- [Phase 03-agentic-orchestration]: query_type is a no-op stub in generate_response for Plan 03-02 — full prompt selection logic (SYSTEM_PROMPT_GENERATOR_CALCULATION) in Plan 03-03
- [Phase 03-agentic-orchestration]: _log_rate_limit delegates non-429 errors to before_sleep_log — 429s get targeted 'SiliconFlow rate limit (429) hit' message for MON-05 monitoring
- [Phase 03-agentic-orchestration]: generate_response conversation_history sliced to last 10 messages (5 turns) — prevents Pitfall 3 context overflow
- [Phase 03-agentic-orchestration]: preprocess_node wired between route and retrieve in Phase 3 graph — RESEARCH.md skeleton was incomplete (intentional override)
- [Phase 03-agentic-orchestration]: Test mock functions updated with **kwargs to accept query_type and conversation_history without breaking existing mock contract
- [Phase 03-agentic-orchestration]: render_sidebar() uses st.session_state.get('messages', []) before session state init to avoid KeyError on first render
- [Phase 03-agentic-orchestration]: query_type stored in message dict for all code paths so badge renders correctly on history replay
- [Phase 04-scale-and-observability]: Lazy import of langfuse inside function body avoids auth errors in test environments where LANGFUSE_PUBLIC_KEY is absent
- [Phase 04-scale-and-observability]: New CallbackHandler() per graph.invoke() call prevents trace bleed across Streamlit reruns (Pitfall 7)
- [Phase 04-scale-and-observability]: generate() return_usage=False default preserves backward compatibility for all existing callers
- [Phase 04-scale-and-observability]: check_book_exists uses scroll(limit=1) — fast existence check without counting all book points
- [Phase 04-scale-and-observability]: delete_book uses FilterSelector not delete_collection — surgical per-book deletion, other books unaffected (INGEST-06)
- [Phase 04-scale-and-observability]: replace_existing=False raises ValueError by default — forces explicit opt-in to book replacement
- [Phase 04-scale-and-observability]: LightRAG manifest updated only on --full ingestion, not audit runs — audit is sampling, not commitment
- [Phase 04-scale-and-observability]: Contextual window embedding prefix format is '[Context: truncated_parent]\n\nchunk_text' — square brackets mark injected context so embedding model distinguishes context from chunk content
- [Phase 04-scale-and-observability]: max_context_words=256 for contextual window embedding — conservative limit within Qwen3-Embedding-8B 8192-token limit, activated via use_contextual_window=True in embed_chunks_batch
- [Phase 04-scale-and-observability]: data/eval/ is gitignored: eval_queries.json exists on disk but not tracked in git (matches project .gitignore data/ pattern)
- [Phase 04-scale-and-observability]: PASS scoring uses any-match on book_title: one correct book citation is sufficient for a query to pass (MON-02 evaluation)
- [Phase 04.1-ingestion-polish]: entity_extract_max_gleaning=0 halves LLM calls per chunk (eliminates gleaning pass); default=1 was doubling cost needlessly
- [Phase 04.1-ingestion-polish]: max_parallel_insert=4 must be a top-level LightRAG constructor arg, NOT in addon_params — addon_params only recognizes language and entity_types
- [Phase 04.1-ingestion-polish]: SiliconFlow tier upgrade deferred: user uses .com international (no tier system); code optimizations (gleaning=0, max_parallel_insert=4) still apply within available rate limits
- [Phase 04.1-ingestion-polish]: Content filtering applied BEFORE audit_mode slice — ensures 50-chunk audit sample reflects only ingestion-worthy content types (narrative_text + example_problem)
- [Phase 04.1-ingestion-polish]: resume_lightrag_ingestion() only calls apipeline_process_enqueue_documents() — never re-enqueues (Pitfall 1: re-enqueue creates FAILED [DUPLICATE] records)
- [Phase 04.1-ingestion-polish]: manifest mark_book_ingested only on --full with result['failed']==0, or --resume with failed==0 and pending==0 — prevents premature manifest marking on partial runs
- [Phase 05-polish]: Author prefix in build_citation uses 'author + comma + space' prefix; empty string treated as absent to avoid leading comma
- [Phase 05-polish]: Removed citation_block append from generator.py — CitationList UI is the sole citation display mechanism, no duplication in response text
- [Phase 05.1-cleanup-and-hardening]: get_langfuse_handler called per query session in query_sse — prevents trace bleed (consistent with Phase 04 decision)
- [Phase 05.1-cleanup-and-hardening]: build_lightrag_instance() no longer calls initialize_storages() — lifespan is the sole call site
- [Phase 05.1-cleanup-and-hardening]: Used || '' fallback (not ?? '') in api.ts — Vite substitutes absent VITE_* vars with undefined at build time; empty string enables relative URLs in production SPA
- [Phase 05.1-cleanup-and-hardening]: Gated main.tsx startup warning to import.meta.env.DEV to prevent false-positive console.error in production
- [Phase 05.2-session-and-observability-fixes]: Langfuse v4 CallbackHandler takes no constructor args — session/user attribution via metadata in ainvoke config (langfuse_session_id, langfuse_user_id)
- [Phase 05.2-session-and-observability-fixes]: sessionIdRef = useRef(crypto.randomUUID()) — stable per-browser-session UUID generated once at component mount, persists across re-renders without state overhead
- [Phase 05.2-session-and-observability-fixes]: history_id removed from QueryRequest — was accepted by backend but never read, dead weight in API contract
- [Phase 05.2-session-and-observability-fixes]: Removed conversation_history from ainvoke input — MemorySaver alone manages history accumulation via operator.add reducer

### Roadmap Evolution

- Phase 04.1 inserted after Phase 4: ingestion-polish (URGENT) — LightRAG terlalu lambat saat ingestion (2-4 LLM call/chunk, ~15-20 hari untuk 5000 chunks di SiliconFlow 1000 RPD), dan ingestion pipeline belum masuk ke fase apapun sebelum Phase 5 (UI Polish)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: MinerU VRAM fragmentation requires subprocess isolation — must verify implementation before large-scale ingestion
- [Phase 2]: LightRAG entity extraction quality on accounting domain is unverified — plan 50-chunk sample audit before full graph ingestion
- [Phase 4]: SiliconFlow tier upgrade (purchase credits to reach 1,000 RPD) required before LightRAG entity extraction at scale — confirm before scheduling Phase 2+ ingestion

## Session Continuity

Last session: 2026-03-28T00:00:00Z
Stopped at: v1.0 archive complete — ROADMAP.md collapsed, REQUIREMENTS.md archived, PROJECT.md updated, git tag v1.0 applied
Resume file: None
