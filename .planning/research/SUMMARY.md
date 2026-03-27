# Project Research Summary

**Project:** Trusty RAG Akmen
**Domain:** Agentic RAG system for cost & management accounting textbook retrieval (Indonesian/English bilingual)
**Researched:** 2026-03-22
**Confidence:** HIGH

## Executive Summary

Trusty RAG Akmen is a domain-specific, agentic retrieval-augmented generation system targeting a single Indonesian accounting consultant who needs fast, citable answers from 20-30 English-language textbooks. Research across stack, features, architecture, and pitfalls converges on a well-understood architecture: an offline ingestion pipeline (GPU-local PDF parsing + SiliconFlow batch embedding) that writes to two persistent indexes (Qdrant Cloud for vector/BM25 search, LightRAG nano-vectordb for knowledge graph), feeding an online LangGraph state machine that routes queries through four complexity tiers (Simple/Medium/Complex/Calculation) with a CRAG quality gate before generation. The core value proposition — exact citations with book title, chapter, and page number — depends entirely on getting page-level metadata right at ingestion time. This is non-negotiable and must be built correctly in Phase 1.

The recommended approach prioritizes correctness over feature breadth. The Phase 1 MVP (vector RAG + citations + bilingual retrieval + calculator) validates whether the tool actually saves the consultant 40-50 minutes per question. Only after that validation does it make sense to invest Phase 2 effort in the knowledge graph and Phase 3 effort in full agentic orchestration with CRAG. The technology choices are mature and well-validated: LangGraph 1.1.3 for orchestration, Qwen3-Embedding-8B for cross-lingual retrieval (#1 MTEB Multilingual), Qwen3-30B-A3B-Instruct-2507 via SiliconFlow for generation, and the MinerU+Docling parser split for GPU-local PDF extraction on a GTX 1660 Ti 6 GB.

The primary risks are operational, not architectural. MinerU's VRAM fragmentation bug (GitHub issue #3399) will cause OOM crashes on batch ingestion without explicit per-document VRAM cleanup. SiliconFlow's 50 RPD default limit makes large-scale LightRAG entity extraction impossible without a tier upgrade. Citation page numbers will be wrong for multi-page sections without inline page markers injected at parse time. None of these are showstoppers — all have documented workarounds — but all three must be addressed in Phase 1 before any large-scale ingestion begins. The cost model ($8-35/month for 500 queries/day) is confirmed viable given Qwen3-30B-A3B's MoE pricing on SiliconFlow.

---

## Key Findings

### Recommended Stack

The stack is validated across all major dimensions. LangGraph (1.1.3) is the correct orchestration layer — it owns the state machine, routing logic, and CRAG loop. LangChain (1.2.13) is the toolbox, not the orchestrator. LightRAG (1.4.11) handles knowledge graph extraction with a September 2025 update specifically optimized for Qwen3-30B-A3B entity extraction. Qdrant Cloud free tier (1 GB RAM, 4 GB disk) is sufficient for 20-30 textbooks with scalar quantization applied. All LLM and embedding inference runs through SiliconFlow cloud API — the GTX 1660 Ti 6 GB is reserved for PDF parsing only.

The critical non-obvious decisions: use cu126 PyTorch wheels (not cu128) for GTX 1660 Ti CC 7.5 compatibility, use LightRAG's built-in nano-vectordb (not Qdrant) for graph storage to avoid configuration conflicts, and use Langfuse (MIT, self-hostable) over LangSmith for monitoring given accounting data privacy needs.

**Core technologies:**
- LangGraph 1.1.3: Agentic orchestration, CRAG state machine — only mature framework for explicit stateful RAG loops
- Qwen3-Embedding-8B (SiliconFlow): Multilingual dense embeddings — #1 MTEB Multilingual (70.58), handles Indonesian query vs English corpus natively with no translation layer
- Qwen3-30B-A3B-Instruct-2507 (SiliconFlow): LLM generation and routing — MoE (3.3B active), $0.10/$0.39 per 1M tokens, supports extended thinking for Complex queries
- Qwen3-Reranker-8B (SiliconFlow): Cross-encoder reranking — top performer on MMTEB-R, critical for cross-lingual retrieval quality
- MinerU 2.7.6 + Docling 2.81.0: Complementary PDF parsers — MinerU for scanned/complex (YOLO+OCR), Docling for text-native (97.9% table accuracy); split by PyMuPDF triage scan
- LightRAG 1.4.11: Knowledge graph for relational/synthesis queries — EMNLP 2025 paper, Qwen3-30B-A3B entity extraction confirmed
- Qdrant Cloud Free Tier: Primary vector store — 1 GB RAM / 4 GB disk, scalar quantization fits 500K-800K chunks, sufficient for 20-30 textbooks
- LlamaIndex HierarchicalNodeParser + Chonkie LateChunker: Hybrid chunking — parent-child hierarchy + contextually-enriched chunk embeddings
- Langfuse: LLM observability — self-hostable, MIT license, RAG-specific scoring (context relevance, groundedness)

### Expected Features

**Must have (table stakes) — Phase 1:**
- Q&A with source citations (book title, chapter, page number) — without this the tool has no advantage over ChatGPT
- Indonesian-language output with English technical terms in parentheses — generation config concern, not a build feature
- PDF ingestion pipeline for 5-10 key textbooks (Horngren, Garrison, Hansen & Mowen) — validates parsing quality on target corpus
- Cross-lingual retrieval (Indonesian query → English corpus) via Qwen3-Embedding-8B + bilingual glossary (~200-500 terms)
- Calculation tool (BEP, variance analysis, overhead rate) with step-by-step output and mandatory disclaimer
- Basic Streamlit chat UI with citation display and calculation step rendering
- Session-level conversation memory via LangGraph state (last N turns + query reformulation for follow-ups)

**Should have (differentiators) — Phase 2-3:**
- Cross-textbook synthesis (Horngren vs Garrison vs Hansen & Mowen on same topic) — requires knowledge graph
- Knowledge graph (LightRAG) for relational queries (CONTRASTS_WITH, PREREQUISITE_OF, USES_FORMULA)
- CRAG quality gate (CORRECT/AMBIGUOUS/INCORRECT grading) — 78.1% accuracy vs 51.4% vanilla RAG
- Adaptive complexity routing (4-level: Simple 2 calls / Medium 3 / Complex 4-5 / Calculation 2-3) — 40-60% API cost reduction
- Formula index chunks (per-chapter formula reference targets for calculation routing path)
- Bilingual accounting glossary as BM25 index entries for terminological bridging

**Defer to v2+:**
- Multi-user support and authentication — single user in v1, no auth complexity
- Visual knowledge graph navigation — high UI complexity, low immediate value
- Cross-session conversation history persistence — defer until explicitly requested
- Full corpus expansion to 100 textbooks — Phase 4 only after 20-30 book architecture is validated
- Web search integration — destroys trust model (citations must come from owned textbook corpus only)

### Architecture Approach

The architecture is a clean two-pipeline split: an offline ingestion pipeline (GPU-local, runs once per textbook batch, days of runtime acceptable) and an online retrieval pipeline (no GPU, per-query, target <10s simple / <20s complex). These communicate only through shared persistent storage: Qdrant Cloud for vector+BM25 indexes and LightRAG workdir for knowledge graph. The online pipeline is a LangGraph state machine implementing a Supervisor with Tool-Calling (ReAct) pattern — one supervisor LLM call routes the query, invokes the appropriate tools (vector_search, graph_query, reranker, calculator), passes retrieved context through the CRAG quality gate, and calls the response generator. This pattern requires 2-5 LLM calls per query vs 10+ for hierarchical multi-agent patterns.

**Major components:**
1. PDF Ingestion Pipeline (`src/ingestion/`) — PyMuPDF triage, MinerU/Docling parsing, 7-step hybrid chunking, parallel vector+graph indexing; zero runtime dependency on retrieval pipeline
2. LangGraph Supervisor Agent (`src/agents/`) — state machine with complexity router, tool binding, CRAG loop with 2-iteration cap; coordinates all online retrieval tools
3. Hybrid Retrieval Layer (`src/retrieval/`) — Qdrant hybrid search (dense + BM25), LightRAG graph query (local/naive/hybrid/mix by query type), Qwen3-Reranker-8B cross-encoder
4. CRAG Quality Gate (`src/retrieval/crag.py`) — grades retrieved docs CORRECT/AMBIGUOUS/INCORRECT, triggers query reformulation (max 2 retries), returns "not in corpus" response after cap
5. Response Generator (`src/generation/`) — bilingual Indonesian output with English terms, source citation builder, calculation step formatter, mandatory calculation disclaimer
6. Monitoring (`src/monitoring/tracer.py`) — Langfuse trace logging for all LLM calls, token usage, CRAG grade distribution

### Critical Pitfalls

1. **MinerU VRAM fragmentation (GitHub #3399)** — After every document call the full cleanup sequence (`del model; gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()`). Set `PYTORCH_CUDA_ALLOC_CONF='max_split_size_mb:512,expandable_segments:True'`. Process documents in subprocess pool so OS reclaims VRAM between files. Never run MinerU and Docling in the same Python process.

2. **Citation page numbers lost during chunking** — Inject page boundary markers (`<!-- PAGE_START:245 -->`) into Markdown text at parse time, not just metadata. After chunking, parse markers within each chunk to compute actual `page_start`/`page_end`. Strip markers before embedding. Without this, all chunks from a multi-page section carry the starting page number — directly contradicts the tool's core value proposition.

3. **Table splitting destroys financial data context** — Before any text splitting, run an element classifier to detect Markdown tables. Keep tables ≤20 rows as atomic chunks (up to 1,024 tokens). For tables >20 rows, repeat column headers at the start of every child chunk. Naive RecursiveCharacterTextSplitter on tables yields only 30% accuracy vs 73.8% for structure-aware chunking (LangChain benchmark).

4. **SiliconFlow 50 RPD default limit blocks ingestion** — LightRAG entity extraction requires one LLM call per chunk (120,000 chunks for 30 books). At 50 RPD this takes 2,400 days. Purchase credits ($10+ triggers tier upgrade to 1,000 RPD) before any large-scale ingestion. Implement exponential backoff with jitter (tenacity) on all SiliconFlow calls. Store intermediate results after every successful API call for resumable ingestion.

5. **CRAG reformulation infinite loop on out-of-scope queries** — Without an iteration cap, queries outside the indexed corpus cycle through unlimited reformulations. Implement hard cap of 2 reformulations. After cap, return structured "not in corpus" response in Indonesian with suggestion to rephrase. Add cosine similarity threshold (<0.55 → skip generation). Log all out-of-scope queries to identify corpus gaps.

6. **LightRAG entity deduplication failure at scale** — LLM-based extraction creates separate nodes for "ABC Costing", "Activity-Based Costing", "ABC method" (three nodes for one concept). At 30 books, 30-50% of entities may be duplicated, fragmenting the relationship graph. Build canonical accounting glossary (200-500 terms) pre-ingestion and run post-extraction deduplication pass merging nodes with >0.92 embedding similarity.

7. **Qwen3-Embedding-8B requires instruction prefix on queries** — Cross-lingual performance degrades 1-5% without task-specific prefix. Always wrap query embeddings (not document embeddings) with: `"Instruct: Retrieve English accounting textbook passages relevant to the Indonesian accounting query\nQuery: {user_query}"`. Store as constant in `config/settings.py` — never inline.

---

## Implications for Roadmap

Based on combined research, the natural phase structure follows the dependency chain: you cannot retrieve what is not indexed, you cannot add CRAG before basic retrieval is proven, and you cannot implement 4-way routing before all routing targets exist.

### Phase 1: Foundation — Ingestion Pipeline + Basic RAG
**Rationale:** Everything downstream depends on index quality. The ingestion pipeline (parsing, chunking, metadata, embedding) must be built correctly before any retrieval work begins. This phase also validates the core hypothesis: does RAG over accounting textbooks actually reduce lookup time?
**Delivers:** Searchable index of 5-10 key textbooks, basic vector RAG with citations, cross-lingual retrieval, calculation tool, Streamlit UI
**Addresses (from FEATURES.md):** All P1 table-stakes features — citations, Indonesian output, ingestion pipeline, cross-lingual retrieval, calculation, chat UI, bilingual glossary
**Avoids (from PITFALLS.md):** MinerU VRAM fragmentation (subprocess isolation), page number loss (inline page markers), table splitting destruction (element classifier), instruction prefix requirement (config constant), SiliconFlow rate limit (tier upgrade before ingestion), Qdrant hybrid search config (create collection with dense+sparse from start)
**Research flag:** Needs deeper research on MinerU GPU memory management patterns and Qdrant scalar quantization configuration for 1,024-dim vectors.

### Phase 2: Knowledge Graph Integration
**Rationale:** Vector-only retrieval cannot answer "what does Horngren say vs Garrison" or "what are prerequisites to ABC costing?" — these require the knowledge graph. Phase 2 adds LightRAG after Phase 1 proves the vector retrieval baseline.
**Delivers:** LightRAG knowledge graph over ingested corpus, entity-aware relational queries, cross-textbook synthesis capability
**Uses (from STACK.md):** LightRAG 1.4.11 with built-in nano-vectordb, Qwen3-30B-A3B entity extraction, entity normalization pipeline against canonical glossary
**Implements:** Graph Indexer component + graph_query tool + entity deduplication post-processing
**Avoids (from PITFALLS.md):** LightRAG entity deduplication failure (canonical glossary pre-built in Phase 1), LightRAG+SiliconFlow model name parameter bug (use reference config exactly)
**Research flag:** Needs phase-specific research — LightRAG accounting domain entity extraction quality is unverified until first ingestion run. 50-chunk sample evaluation before full ingestion required.

### Phase 3: Agentic Orchestration + CRAG
**Rationale:** Adaptive routing and CRAG require all retrieval paths to exist (vector from Phase 1, graph from Phase 2). The 4-level router can only route to implemented paths. Phase 3 adds the full LangGraph state machine replacing the simple Phase 1 linear pipeline.
**Delivers:** Full LangGraph Supervisor agent with 4-level complexity routing, CRAG quality gate with iteration cap, session conversation memory, formula index chunks, full adaptive API cost management
**Uses (from STACK.md):** LangGraph create_react_agent, CRAG grader node, conditional edges for reformulation loop, LangGraph state for conversation history
**Implements:** Supervisor Agent, CRAG Grader, Complexity Router, all @tool wrappers, formula index chunks
**Avoids (from PITFALLS.md):** CRAG infinite loop (2-iteration hard cap + out-of-scope response), full supervisor overhead (ReAct pattern: 2-5 calls, not 10+), LangGraph+LangChain lazy import pattern
**Research flag:** Standard LangGraph patterns — well-documented with official tutorials. Skip research-phase for this phase.

### Phase 4: Scale + Optimization
**Rationale:** After architecture is validated on 20-30 books, expand to full 100-book corpus and optimize for the cost/performance tradeoffs that only become visible at scale.
**Delivers:** Full 100-textbook corpus indexed, Qdrant scalar quantization tuned, batch embedding optimized, semantic caching for frequent queries, monitoring dashboards operational
**Avoids (from PITFALLS.md):** RAM OOM from loading all chunk metadata at startup (lazy loading), Qdrant free tier disk limit without quantization (quantize at collection creation), embedding single-loop at scale (batch API calls)
**Research flag:** Qdrant scalar quantization impact on recall at 1,024 dim needs empirical validation before full corpus upload.

### Phase 5: Polish + Beta Launch
**Rationale:** Final UX hardening, documentation, and observability before sharing with clients.
**Delivers:** Production-quality citation formatting ("Horngren et al. (2021), Chapter 8, hal. 312-315"), calculation disclaimer hardened, Langfuse monitoring live, out-of-corpus query logging for gap analysis, incremental ingestion pipeline for adding new textbooks
**Research flag:** No additional research needed — implementation and UX work only.

### Phase Ordering Rationale

- Ingestion must precede retrieval: you cannot retrieve what is not indexed. Page-level metadata and table-structure chunking must be correct from the start — retrofitting requires re-chunking the entire corpus.
- Vector RAG must precede knowledge graph: LightRAG entity extraction runs over chunks that already exist. Graph indexing is Stage 3b after Stage 3a vector indexing — this ordering is non-negotiable per architecture.
- All retrieval paths must exist before 4-level routing: the router can only route to implemented destinations. Simple routing (Phase 1) → graph path added (Phase 2) → full 4-way routing (Phase 3).
- Scale before polish: Phase 4 at 100 books may reveal performance issues (RAM, Qdrant disk limits, API costs) that would require architecture changes if discovered in Phase 5.
- Book_title metadata in every chunk is a Phase 1 requirement: cross-textbook synthesis (Phase 2+) depends on it. Cannot be retrofitted without re-chunking.

### Research Flags

**Needs research-phase during planning:**
- Phase 1: MinerU subprocess isolation patterns for VRAM management on GTX 1660 Ti — community solutions exist but specifics for 2.7.x need verification
- Phase 2: LightRAG entity extraction quality on accounting domain — evaluate 50-chunk sample; entity type taxonomy may need tuning for Indonesian accounting terms
- Phase 4: Qdrant scalar quantization recall impact at 1,024 dimensions — benchmark before/after quantization on a 10K chunk subset

**Standard patterns (skip research-phase):**
- Phase 1 (core RAG): Well-documented LangGraph + Qdrant + SiliconFlow integration with multiple production examples
- Phase 3 (CRAG + routing): Official LangGraph CRAG tutorial exists; Adaptive RAG tutorial exists; pattern is standard
- Phase 5 (polish/launch): No novel technical work

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via PyPI. MTEB benchmarks verified via official Qwen blog. SiliconFlow pricing MEDIUM (USD conversion approximate). GTX 1660 Ti CUDA compatibility HIGH (CC 7.5 documented). |
| Features | HIGH | Feature set validated against architecture spec, multiple RAG-in-finance papers, and competitor analysis. Dependency graph verified — no circular dependencies. Priority ordering is well-reasoned. |
| Architecture | HIGH (patterns) / MEDIUM (LightRAG specifics) | Offline/online split, Supervisor+Tool-Calling, CRAG, hybrid chunking all validated with production sources. LightRAG accounting domain KG quality is MEDIUM — unverified until first ingestion run on actual textbooks. |
| Pitfalls | HIGH | All critical pitfalls sourced from official GitHub issues, production documentation, or peer-reviewed benchmarks. VRAM bug confirmed via MinerU issue tracker. Table chunking accuracy data from LangChain benchmark. Citation page number issue from production experience data. |

**Overall confidence:** HIGH

### Gaps to Address

- **SiliconFlow tier upgrade confirmation:** Must verify that purchasing credits actually raises the RPD limit to 1,000+ before scheduling ingestion. Contact support proactively if higher limits are needed for graph extraction.
- **LightRAG entity quality on accounting domain:** No prior study of LightRAG performance specifically on cost accounting textbooks. Plan a 50-chunk sample ingestion and entity quality audit before committing to full ingestion. Entity type taxonomy (CostType, CostingMethod, Formula, etc.) may need tuning.
- **Qdrant free tier capacity at 1,024 dimensions with scalar quantization:** Research estimates 500K-800K chunks but this is calculated, not benchmarked. Monitor actual disk and RAM usage after first 5-book ingestion and adjust if needed.
- **Chainlit governance:** Original team stepped back May 2025; project is community-maintained. Streamlit chosen for v1 — revisit Chainlit for v2 only if governance stabilizes.
- **Calculator tool edge cases:** Python eval sandboxing with asteval vs sympy choice needs explicit decision before Phase 3. Security review required — do not use bare `eval()`.

---

## Sources

### Primary (HIGH confidence)
- PyPI verified versions: langgraph 1.1.3, langchain 1.2.13, lightrag-hku 1.4.11, qdrant-client 1.17.1, mineru 2.7.6, docling 2.81.0, llama-index-core 0.14.18, chonkie 1.6.1, pymupdf 1.27.2.2
- [Qwen3 Embedding official blog](https://qwenlm.github.io/blog/qwen3-embedding/) — MTEB #1 rank 70.58, MRL truncation, instruction prefix format
- [LightRAG GitHub HKUDS](https://github.com/HKUDS/LightRAG) — EMNLP 2025, Qwen3 optimization, entity extraction guidance
- [Qdrant Pricing](https://qdrant.tech/pricing/) — free tier limits, suspension policy, scalar quantization
- [LangGraph PyPI + Changelog](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available) — production status, create_react_agent pattern
- [Docling GitHub](https://github.com/docling-project/docling) — IBM/LF AI & Data, 97.9% table accuracy benchmark
- [SiliconFlow Rate Limits](https://docs.siliconflow.cn/en/userguide/rate-limits/rate-limit-and-upgradation) — 50 RPD default, tier upgrade policy
- [MinerU VRAM issue #3399](https://github.com/opendatalab/MinerU/issues/3399) — confirmed VRAM retention bug
- [Benchmarking RAG on tables (LangChain blog)](https://blog.langchain.com/benchmarking-rag-on-tables/) — 30% vs 73.8% table chunking accuracy
- [CRAG paper arXiv 2401.15884 + EMNLP acceptance](https://arxiv.org/abs/2401.15884) — 78.1% vs 51.4% accuracy benchmark
- NVIDIA RAG 101, Databricks RAG cookbook — offline/online separation as production best practice

### Secondary (MEDIUM confidence)
- [SiliconFlow Models pricing](https://www.siliconflow.com/models) — Qwen3 pricing in CNY (USD conversion approximate)
- [ArtificialAnalysis Qwen3-30B-A3B-2507](https://artificialanalysis.ai/models/qwen3-30b-a3b-2507) — 86.1 tok/s throughput
- [Langfuse vs LangSmith (ZenML Blog)](https://www.zenml.io/blog/langfuse-vs-langsmith) — OSS status, governance, RAG scoring
- [FloTorch 2026 benchmark](https://flotorch.ai/) — 69% end-to-end accuracy at 512 tokens
- [Less is More: Denoising Knowledge Graphs (arXiv 2025)](https://arxiv.org/html/2510.14271v1) — LLM-based KG noise problem
- [CORE-KG entity normalization (arXiv 2025)](https://arxiv.org/pdf/2506.21607) — 33% node duplication reduction

### Tertiary (LOW/MEDIUM confidence)
- WebSearch "Chainlit governance 2025" — community-maintained since May 2025 (single-source, needs monitoring)
- [PyTorch VRAM fragmentation guide 2026](https://blog.path-finder.jp/troubleshooting/pytorch-gpu-memory-guide-2026/) — expandable_segments configuration

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
