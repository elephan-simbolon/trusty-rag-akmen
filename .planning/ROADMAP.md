# Roadmap: Trusty RAG Akmen

## Overview

Trusty RAG Akmen is built in five phases that follow a strict dependency chain: you cannot retrieve what is not indexed, you cannot add a knowledge graph before vector retrieval is proven, and you cannot implement adaptive routing before all routing targets exist. Phase 1 builds the complete ingestion pipeline and a working basic RAG that validates the core hypothesis (answers with citations in under 10 minutes). Phase 2 adds the LightRAG knowledge graph for relational and cross-textbook synthesis queries. Phase 3 upgrades the pipeline to a full LangGraph agentic orchestrator with CRAG quality gate and adaptive routing. Phase 4 scales the architecture to the full corpus and hardens operational observability. Phase 5 polishes the UI and prepares for regular use.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Ingestion pipeline + basic vector RAG with citations and bilingual retrieval (COMPLETE 2026-03-22)
- [x] **Phase 2: Knowledge Graph** - LightRAG integration for relational queries and cross-textbook synthesis (completed 2026-03-22)
- [x] **Phase 3: Agentic Orchestration** - Full LangGraph supervisor with CRAG quality gate and adaptive routing (completed 2026-03-22)
- [x] **Phase 4: Scale and Observability** - Full corpus ingestion, Langfuse monitoring, and cost optimization (completed 2026-03-22)
- [ ] **Phase 5: Polish** - Citation formatting, UI refinements, and incremental ingestion workflow

## Phase Details

### Phase 1: Foundation
**Goal**: User can ask accounting questions in Indonesian and receive cited answers from indexed textbooks within 10-20 seconds
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, CHUNK-06, CHUNK-07, CHUNK-08, INDEX-01, INDEX-02, INDEX-03, INDEX-05, RETR-01, RETR-02, LANG-01, LANG-02, LANG-03, GEN-01, UI-01
**Success Criteria** (what must be TRUE):
  1. User can type a query in Indonesian (e.g., "apa itu break-even point?") and receive a response that cites the exact book title, chapter, and page number of the source passage
  2. At least 5 textbooks (Horngren, Garrison, Hansen & Mowen) can be ingested through the parsing pipeline without VRAM crashes or data loss, producing chunks with accurate page-level metadata
  3. User can ask a query in Indonesian about content that exists only in English textbooks and receive a relevant answer — demonstrating cross-lingual retrieval without translation
  4. The Streamlit chat UI loads, accepts a query, and displays the response with source citations visible
  5. Ingesting a new textbook does not crash the pipeline — MinerU and Docling run in isolation with full VRAM cleanup between documents
**Plans:** 8/8 plans complete

Plans:
- [x] 01-01-PLAN.md — Project scaffold, config, LLM client, bilingual glossary, test infrastructure
- [x] 01-02-PLAN.md — PDF parsing pipeline (PyMuPDF router, Docling, MinerU subprocess, VRAM cleanup, VLM captioner)
- [x] 01-03-PLAN.md — Chunking pipeline (page markers, element classifier, splitters, hierarchy, formula index, metadata)
- [x] 01-04-PLAN.md — Indexing to Qdrant (batch embedder, collection init, dense+sparse upload, ingestion pipeline)
- [x] 01-05-PLAN.md — Retrieval + generation (hybrid search, reranker, LangGraph graph, citation builder)
- [x] 01-06-PLAN.md — Streamlit chat UI and CLI query tool
- [x] 01-07-PLAN.md — Gap closure: fast-fail UI retry config (_UI_RETRY_CONFIG) untuk embed_query dan generate
- [ ] 01-08-PLAN.md — Gap closure: terapkan _UI_RETRY_CONFIG pada rerank() (sisa gap UAT Test 11)

### Phase 2: Knowledge Graph
**Goal**: User can ask relational and comparative accounting questions that require traversing relationships between concepts across textbooks
**Depends on**: Phase 1
**Requirements**: INDEX-04, RETR-03, GEN-04, GEN-05, GEN-06
**Success Criteria** (what must be TRUE):
  1. User can ask "apa prerequisite dari ABC costing?" and receive an answer that draws on relationship data in the knowledge graph, not just vector similarity
  2. User can ask "bandingkan pandangan Horngren vs Garrison tentang overhead allocation" and receive a synthesis response that attributes each perspective to its source textbook
  3. User can ask a relational query ("apa hubungan variance analysis dengan standard costing?") and receive an answer that traces the conceptual relationship, not just a passage match
  4. The knowledge graph is queryable in at least two LightRAG modes (local and hybrid) and returns different depths of context for the same query
**Plans:** 3/3 plans complete

Plans:
- [ ] 02-01-PLAN.md — LightRAG client with SiliconFlow backend, entity normalizer, and offline ingestion pipeline
- [ ] 02-02-PLAN.md — Graph retrieve node, RAGState extension, and Phase 2 LangGraph wiring
- [ ] 02-03-PLAN.md — Synthesis generation with multi-source attribution, relational and comparison prompts

### Phase 3: Agentic Orchestration
**Goal**: The system routes each query through the optimal processing path and self-corrects when retrieved content is irrelevant, keeping API costs within budget
**Depends on**: Phase 2
**Requirements**: RETR-04, RETR-05, RETR-06, GEN-02, GEN-03, UI-02, MON-05
**Success Criteria** (what must be TRUE):
  1. User can ask a calculation query ("hitung BEP dengan data ini: ...") and receive a step-by-step calculation with a mandatory disclaimer, routed without invoking a separate LLM classification call (rule-based pre-check)
  2. User can ask a follow-up question ("jelaskan lebih detail poin ke-2") in the same chat session and the system correctly uses conversation context from LangGraph state to answer without re-reading the full history
  3. When the system retrieves passages graded AMBIGUOUS or INCORRECT by the CRAG evaluator, it automatically reformulates the query and retrieves again — completing within 2 iterations maximum
  4. A query classified as Simple uses no more than 2 LLM calls; a Complex query uses no more than 5 LLM calls — measurable via request logs
  5. When a query cannot be answered from the corpus after 2 CRAG reformulations, the system returns a structured Indonesian response acknowledging the gap rather than hallucinating
**Plans:** 4/4 plans complete

Plans:
- [ ] 03-01-PLAN.md — RAGState extension, rule-based query classifier, route_node (RETR-05, RETR-06)
- [ ] 03-02-PLAN.md — CRAG quality gate nodes, generate_calc_node, rate limit handling (RETR-04, MON-05)
- [ ] 03-03-PLAN.md — Phase 3 graph wiring with MemorySaver, generate_response extension (GEN-02, GEN-03, UI-02)
- [ ] 03-04-PLAN.md — Streamlit UI integration with conversation memory, badges, sidebar (UI-02)

### Phase 4: Scale and Observability
**Goal**: The system handles the full 20-30 textbook corpus reliably with visible cost and quality metrics, and supports adding new textbooks without full re-ingestion
**Depends on**: Phase 3
**Requirements**: INGEST-06, CHUNK-05, MON-01, MON-02, MON-03, MON-04
**Success Criteria** (what must be TRUE):
  1. A new textbook can be added to the corpus and made searchable without re-ingesting the existing books — incremental ingestion works end to end
  2. Langfuse dashboard shows per-query traces including routing decision, retrieval results, CRAG grade, and token usage for every query
  3. Retrieval accuracy on a 20-query accounting evaluation set is at or above 85% (measured by human review of citation relevance)
  4. Monthly API cost for 500 queries/day stays at or below $35/month, measurable from Langfuse token usage data
  5. Response time for Simple queries is at or below 10 seconds; Complex queries at or below 20 seconds — measured on the Langfuse trace timeline
**Plans:** 4/4 plans complete

Plans:
- [ ] 04-01-PLAN.md — Langfuse v4 observability integration (settings, handler factory, UI wiring, token usage capture)
- [ ] 04-02-PLAN.md — Incremental ingestion guard (check_book_exists, delete_book, CLI --replace, LightRAG manifest)
- [ ] 04-03-PLAN.md — Contextual window embedding (API-compatible late chunking enhancement)
- [ ] 04-04-PLAN.md — 20-query evaluation set and retrieval accuracy measurement

### Phase 04.1: ingestion-polish (INSERTED)

**Goal:** LightRAG ingestion pipeline completes a full book in 15-20 minutes (down from 4-9 hours) via config bug fixes, content-type filtering, crash-safe enqueue/process split, and SiliconFlow tier upgrade
**Requirements**: POLISH-01, POLISH-02, POLISH-03, POLISH-04, POLISH-05
**Depends on:** Phase 4
**Success Criteria** (what must be TRUE):
  1. LightRAG constructor uses corrected parameters: llm_model_max_async=16, max_parallel_insert=4, entity_extract_max_gleaning=0, no insert_batch_size in addon_params
  2. Only narrative_text and example_problem chunks are sent to LightRAG entity extraction — tables, formulas, formula_index, and diagrams are filtered out
  3. Ingestion uses batched enqueue with per-batch disk flush, then separate processing — not a single ainsert() call
  4. Running --resume after a crash picks up PENDING/FAILED docs without re-enqueuing or creating duplicate records
  5. SiliconFlow L2 tier is active with adequate TPM for target throughput
**Plans:** 2/2 plans complete

Plans:
- [ ] 04.1-01-PLAN.md — LightRAG config bug fixes (max_async, max_parallel_insert, gleaning, insert_batch_size) + SiliconFlow tier upgrade
- [ ] 04.1-02-PLAN.md — Content-type filtering, enqueue/process split, --resume CLI flag, test updates

### Phase 5: Polish
**Goal**: Citations are formatted to professional standard and the UI presents information in a way that is ready for daily use with clients
**Depends on**: Phase 4
**Requirements**: UI-03
**Success Criteria** (what must be TRUE):
  1. Citations in every response are rendered in the expandable/collapsible section below the response body — the user can read the answer first and expand sources on demand
  2. Citation format is consistent and professional across all responses: "Horngren, Cost Accounting, Chapter 5, hal. 168-172"
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 4.1 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 8/8 | Complete   | 2026-03-22 |
| 2. Knowledge Graph | 3/3 | Complete   | 2026-03-22 |
| 3. Agentic Orchestration | 4/4 | Complete   | 2026-03-22 |
| 4. Scale and Observability | 4/4 | Complete   | 2026-03-22 |
| 4.1 Ingestion Polish | 1/2 | In Progress|  |
| 5. Polish | 0/TBD | Not started | - |
