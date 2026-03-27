# Feature Research

**Domain:** AI-powered domain-specific RAG assistant for cost & management accounting
**Researched:** 2026-03-22
**Confidence:** HIGH (core features verified against official docs, architecture spec, and multiple research sources)

---

## Context

**User:** Single financial consultant (Aris Simbolon) answering client questions about cost & management accounting using 20-30 English textbooks, responding in Indonesian with English technical terms.

**Core pain points driving feature requirements:**
1. Finding references takes 30-60 minutes per question (opening PDFs one by one)
2. Synthesizing perspectives across Horngren, Garrison, Hansen & Mowen is time-consuming
3. Manual calculations (BEP, variance analysis, overhead rate) are error-prone

**Success threshold:** Reduce reference lookup from 45-60 minutes to 5-10 minutes, with citable source attribution (book + chapter + page).

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the user will assume exist. Missing any = the tool fails its core purpose.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Q&A with source citations | The entire value prop is "give me an answer with the book/page so I can cite it to clients" — without citations, the tool is no better than ChatGPT | MEDIUM | Must cite: book title, chapter, page number for every response. Citation accuracy averages 65-70% without explicit attribution training — requires deliberate implementation with page-level metadata at ingestion time |
| Indonesian-language output | The user is an Indonesian consultant answering Indonesian clients — English-only output would require a manual translation step that defeats the purpose | LOW | Output is Indonesian prose + English technical terms in parentheses. This is a generation prompt/config concern, not a separate feature to build |
| Conceptual Q&A (definition, explanation, procedure) | Primary use case: client asks "what is ABC costing?" and consultant needs an answer with a citation | LOW | Handled by basic vector RAG + citation builder. Simple queries are 2-LLM-call path |
| PDF ingestion of English textbooks | Without ingesting the source textbooks, nothing works — this is table stakes infrastructure | HIGH | 20-30 textbooks v1, up to 100 in v4. The quality of parsing (MinerU + Docling) directly determines retrieval quality. Chunking config affects retrieval quality as much as embedding model choice (Vectara NAACL 2025) |
| Cross-lingual retrieval (Indonesian query → English corpus) | User queries in Indonesian; all 20-30 textbooks are in English — a translation layer would add latency and cost | MEDIUM | Qwen3-Embedding-8B is #1 MTEB Multilingual (score 70.58) enabling direct cross-lingual matching without query translation. Supplement with bilingual glossary (~200-500 terms) and hybrid dense+BM25 search |
| Basic chat UI | Without a UI, the tool is unusable — even a minimal Streamlit interface is required | LOW | Streamlit or Chainlit. Must display: response, citations, calculation steps. No need for visual knowledge graph navigation in v1 |
| Session-level conversation memory | Users ask follow-up questions ("elaborate on point 3" / "now calculate with these numbers") — a stateless system would feel broken | MEDIUM | LangGraph maintains state natively. Implement contextual window (last N turns) with query reformulation for follow-ups. Do not store cross-session history in v1 |
| Calculation with step-by-step output | Client scenarios regularly include calculation requests alongside conceptual questions ("compare costing methods AND calculate BEP with this data") — error-prone manual calculation is pain point #3 | MEDIUM | Calculator tool: Python eval for BEP, variance analysis (material/labor/overhead), overhead allocation rate, contribution margin, ROI, residual income. Always show calculation steps. Always attach disclaimer: "verifikasi hasil dengan sumber resmi" |

### Differentiators (Competitive Advantage)

Features that set this tool apart from generic ChatGPT/RAG approaches. These are where the real value beyond "fast Q&A" lives.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cross-textbook synthesis | Consultant's hardest problem: "What does Horngren say vs Garrison vs Hansen & Mowen on this topic?" — synthesizing 3-4 textbooks manually takes hours | HIGH | Requires: parallel retrieval from multiple books, metadata filtering by book_title, LLM synthesis prompt that explicitly names each source. Knowledge graph (LightRAG) is the key enabler — entity relationships span across books |
| CRAG quality gate | Every retrieved document is graded CORRECT/AMBIGUOUS/INCORRECT before generation. For accounting domain where formula errors have real consequences, this is non-negotiable correctness insurance | HIGH | CRAG Correct action achieves 78.1% accuracy vs 51.4% vanilla RAG. Wrong accounting answers can mislead clients on actual financial decisions. Implement as a grading step in LangGraph before generation |
| Adaptive complexity routing | Most queries are simple definitions — running full graph+CRAG on "what is fixed cost?" wastes API budget. Routing saves 40-60% API calls | MEDIUM | 4 levels: Simple (2 LLM calls) → Medium (3) → Complex (4-5) → Calculation (2-3). The classifier is itself a lightweight LLM call. Critical for staying within $8-35/month budget |
| Knowledge graph for relational queries | "What concepts are prerequisite to understanding ABC costing?" and "How does activity-based costing relate to balanced scorecard?" are relational queries that vector search handles poorly | HIGH | LightRAG with entity types: CostType, CostingMethod, Formula, AccountingStandard, ManagementTechnique. Relationships: CONTRASTS_WITH, USES_FORMULA, PREREQUISITE_OF, GOVERNS. Dual-level retrieval (local for specific entities, hybrid for comparative queries) |
| Table and formula extraction quality | Accounting textbooks are dense with variance analysis tables, cost sheets, overhead allocation formulas — if parsing destroys table structure, retrieval of numerical data fails entirely | HIGH | MinerU (AGPL) for scanned/complex PDFs + Docling (MIT, 97.9% table accuracy, F1 0.968 for formulas) for text-based PDFs. Formula index chunks per chapter (separate chunk listing all key formulas with descriptions — high-relevance retrieval targets) |
| Formula knowledge index | Beyond retrieving text about formulas, the system needs a dedicated lookup structure so calculation queries find the right formula immediately | MEDIUM | During ingestion, create formula-index chunks per chapter: each lists all formulas with LaTeX + natural language description. These are high-relevance retrieval targets for the Calculation routing path |
| Bilingual accounting glossary | "Overhead rate", "contribution margin", "variance analysis" must reliably bridge Indonesian queries to English source text | LOW | ~200-500 bilingual terms injected into system prompt and as BM25 index entries. Ensures terminological bridging even when embedding space alignment has gaps for rare accounting terms |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem useful but would either destroy the budget, add complexity without value, or undermine the tool's positioning.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Web search / live internet data | "What if a textbook doesn't cover a standard?" — seems like a useful escape hatch | (1) Destroys trust: the tool's value is citations from authoritative textbooks, not scraped web pages. (2) Compliance risk: mixing unvetted web content with textbook content makes citations unreliable. (3) Out of scope per PROJECT.md | Add more textbooks (IFRS standards, CMA guides) to the corpus rather than enabling web search. The corpus is the trust boundary |
| Visual knowledge graph navigation | "Browse topics through a graph" sounds great for exploration | (1) High UI complexity for low practical value — consultant uses the tool to answer specific questions, not to explore. (2) Building an interactive graph visualization is a separate engineering problem. (3) Explicitly excluded in PROJECT.md v1 scope | Phase 5 consideration only. LightRAG CLI / programmatic graph queries cover the relational use case without a graph UI |
| Multi-user / authentication | "Could be useful for a team" — potential commercial expansion | (1) Personal tool for one user in v1. (2) Auth adds session management, user data isolation, and security surface area. (3) Explicitly out of scope per PROJECT.md | Architecture is kept clean for future scale, but do not build auth for v1. Single-user local tool |
| Hierarchical agent pattern (full supervisor or hierarchical multi-agent) | "More agents = smarter?" — natural intuition | (1) Full supervisor: 6+ LLM calls per query. Hierarchical: 10+ LLM calls. At $0.001/query budget, 10-call overhead pushes simple queries from $0.001 to $0.01+. (2) Overkill for a single-user personal tool. (3) LangChain itself now recommends tool-calling pattern over supervisor library for most use cases | Supervisor + Tool-Calling pattern: 2-5 calls per query, single reasoning loop invoking multiple tools |
| Real-time / streaming corpus updates | "Add a new textbook instantly" | (1) LightRAG graph construction via API takes hours per book (entity extraction pass). (2) Immediate re-indexing would spike API costs unpredictably. (3) Incremental ingestion (add books without full reindex) is sufficient | Offline batch ingestion pipeline with incremental support. Add new books during off-hours, not mid-session |
| Fine-tuned / locally-hosted LLM | "Self-hosted = cheaper long-term" | (1) GTX 1660 Ti 6 GB cannot run 8B+ models for inference at useful throughput. (2) Fine-tuning requires labeled data the project doesn't have. (3) Local embedding alone would take 33 days for 200K pages vs 4-12 hours via API | Use SiliconFlow cloud API for all intelligence. GPU local is for PDF parsing only — this is the explicit architecture decision |
| Automatic answer correction / professional advice | "The AI should tell the user when they're wrong" | (1) Creates liability — this is not a professional accounting service, it's a reference tool. (2) "Correcting" clients based on textbook retrieval may be incorrect in context. | Maintain clear disclaimer on every calculation: "verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional" |
| Social login / OAuth | "Make it easier to access" | Personal tool, zero need for OAuth complexity | Simple deployment with no authentication. Direct access |

---

## Feature Dependencies

```
[PDF Ingestion Pipeline]
    └──requires──> [MinerU + Docling Parsing]
    └──requires──> [Hybrid Chunking (7-step)]
    └──requires──> [Embedding via SiliconFlow API]
    └──requires──> [Qdrant Vector Index]
    └──enables──> [Q&A with Citations]
    └──enables──> [Calculation Feature]
    └──enables──> [Cross-textbook Synthesis]

[Q&A with Citations]
    └──requires──> [PDF Ingestion Pipeline]
    └──requires──> [Page-level metadata at chunk creation]
    └──requires──> [Citation builder in generation layer]

[Cross-lingual Retrieval]
    └──requires──> [Qwen3-Embedding-8B via SiliconFlow]
    └──requires──> [Bilingual Glossary (~200-500 terms)]
    └──requires──> [Hybrid dense+BM25 search in Qdrant]
    └──enables──> [Q&A with Citations]

[Calculation Feature]
    └──requires──> [Formula Index Chunks (created during ingestion)]
    └──requires──> [Calculator Tool (Python eval)]
    └──requires──> [Adaptive Routing — Calculation path]
    └──depends_on──> [Q&A with Citations] (calculations are always paired with textbook context)

[Cross-textbook Synthesis]
    └──requires──> [Q&A with Citations]
    └──requires──> [book_title metadata on every chunk]
    └──enhanced_by──> [Knowledge Graph (LightRAG)]

[Knowledge Graph]
    └──requires──> [PDF Ingestion Pipeline] (chunks must exist first)
    └──requires──> [LightRAG entity extraction via SiliconFlow API]
    └──requires──> [LangGraph orchestration layer]
    └──enhances──> [Cross-textbook Synthesis]
    └──enables──> [Relational queries (CONTRASTS_WITH, PREREQUISITE_OF)]

[CRAG Quality Gate]
    └──requires──> [Retrieval layer (vector + optional graph)]
    └──requires──> [LangGraph state management]
    └──enhances──> [Q&A with Citations] (by ensuring graded relevance)

[Adaptive Complexity Routing]
    └──requires──> [LangGraph orchestration layer]
    └──requires──> [All retrieval paths (Simple/Medium/Complex/Calculation) implemented]
    └──enhances──> [All features] (cost efficiency)

[Conversation Memory]
    └──requires──> [LangGraph state]
    └──requires──> [Query reformulation for follow-ups]
    └──enhances──> [Q&A with Citations] (follow-up questions work naturally)
    └──conflicts_with──> [Cross-session persistence in v1] (defer)

[Chat UI]
    └──requires──> [All backend features]
    └──requires──> [Citation display component]
    └──requires──> [Calculation step display]
```

### Dependency Notes

- **Formula Index requires PDF Ingestion:** Formula-index chunks are created during chunking (Step 7 metadata enrichment), not at query time. They must exist in Qdrant before the Calculation routing path can target them.
- **Knowledge Graph requires completed vector index:** LightRAG entity extraction runs over chunks that already exist — graph indexing is Stage 3b, after Stage 3a vector indexing. This ordering is non-negotiable.
- **CRAG Quality Gate requires all retrieval paths:** CRAG grades whatever was retrieved — it cannot run before retrieval. It sits between retrieval and generation in the LangGraph DAG.
- **Adaptive Routing requires all paths to be implemented:** The router can only route to paths that exist. Simple routing (2 paths) can come before full 4-way routing — Phase 2 adds graph path, Phase 3 adds full routing.
- **Cross-textbook Synthesis requires book_title metadata:** This metadata must be embedded at chunk creation in Stage 2. Cannot be retrofitted without re-chunking.

---

## MVP Definition

### Launch With (v1 — Phase 1, Weeks 1-3)

Minimum to validate the core hypothesis: "does RAG over accounting textbooks actually save time vs manual PDF search?"

- [ ] PDF ingestion of 5-10 key textbooks (Horngren, Garrison, Hansen & Mowen) — validates parsing quality on target corpus
- [ ] Basic vector RAG: query → embed → retrieve → rerank → generate — the core loop
- [ ] Q&A with source citations (book + chapter + page) — non-negotiable; without this the tool has no advantage over ChatGPT
- [ ] Indonesian output with English technical terms in parentheses — table stakes for the user
- [ ] Cross-lingual retrieval via Qwen3-Embedding-8B + bilingual glossary — without this, Indonesian queries fail against English corpus
- [ ] Calculation tool (BEP, variance analysis, overhead rate) with step-by-step output — pain point #3 must be addressed in v1
- [ ] Calculation disclaimer ("verifikasi hasil") — required on every calculation response
- [ ] Streamlit/Chainlit chat UI with citation display — minimum interface to use the tool

### Add After Validation (v1.x — Phase 2-3)

Add once v1 proves the core value loop works.

- [ ] Knowledge Graph (LightRAG) — add when: user reports "I need to understand relationships between concepts" or cross-textbook synthesis responses feel shallow. Expected in Phase 2 (Weeks 4-6)
- [ ] Adaptive complexity routing (4-level) — add when: API costs exceed $15/month or response latency feels high for simple queries. Expected in Phase 3 (Weeks 7-9)
- [ ] CRAG quality gate — add when: citations start appearing wrong or retrieval quality is inconsistent. Expected in Phase 3 (Weeks 7-9)
- [ ] Session conversation memory — add when: user reports frustration with follow-up questions losing context. Can be added as early as Phase 1 end with minimal LangGraph work
- [ ] Formula index chunks (dedicated formula retrieval targets) — add in Phase 3 when calculator tool is being polished

### Future Consideration (v2+)

Defer until product-market fit with multiple users is established.

- [ ] Multi-user support with isolation — defer until commercial intent is confirmed
- [ ] Visual knowledge graph navigation — defer; high UI complexity, low immediate value
- [ ] Cross-session conversation history / memory persistence — defer until user requests it explicitly
- [ ] Expand corpus to 100 textbooks — Phase 4 (Weeks 10-12) after architecture is validated on 20-30 books
- [ ] Export/share functionality (PDF report generation from answers) — potential commercial feature

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Q&A with source citations | HIGH | MEDIUM | P1 |
| Indonesian output + English terms | HIGH | LOW | P1 |
| PDF ingestion pipeline (5-10 books) | HIGH | HIGH | P1 |
| Cross-lingual retrieval | HIGH | MEDIUM | P1 |
| Calculation with step-by-step + disclaimer | HIGH | MEDIUM | P1 |
| Basic chat UI | HIGH | LOW | P1 |
| Bilingual accounting glossary | HIGH | LOW | P1 |
| Session conversation memory | MEDIUM | MEDIUM | P2 |
| Cross-textbook synthesis | HIGH | HIGH | P2 |
| Knowledge graph (relational queries) | HIGH | HIGH | P2 |
| Adaptive complexity routing | MEDIUM | MEDIUM | P2 |
| CRAG quality gate | HIGH | MEDIUM | P2 |
| Formula index chunks | MEDIUM | LOW | P2 |
| Table + formula extraction quality (MinerU/Docling) | HIGH | HIGH | P1 (infrastructure, not UI feature) |
| Full corpus ingestion (100 books) | MEDIUM | HIGH | P3 |
| Semantic caching (frequent queries) | LOW | MEDIUM | P3 |
| Visual knowledge graph navigation | LOW | HIGH | P3 |
| Multi-user / auth | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — without these, the tool fails its core purpose
- P2: Should have — adds significant value, add after v1 is validated
- P3: Nice to have — future consideration, defer until commercial need

---

## Competitor Feature Analysis

Direct competitors for a personal RAG accounting assistant are sparse — this is a niche greenfield use case. The relevant comparisons are general RAG tools and AI document Q&A products.

| Feature | Generic ChatGPT | Perplexity / Elicit | Notebooklm (Google) | Our Approach |
|---------|-----------------|---------------------|---------------------|--------------|
| Source citations with page numbers | No — fabricates sources | Yes (web) — no page# | Yes (uploaded docs) | Yes — book, chapter, page from owned corpus |
| Accounting calculation accuracy | Unreliable — no tool use | No calculator | No calculator | Python eval calculator tool, always shows steps |
| Cross-lingual Indonesian-English | Partial — translation quality varies | No | No | Native cross-lingual via Qwen3-Embedding-8B multilingual embedding |
| Cross-textbook synthesis | No corpus awareness | Reads multiple sources | Multiple notebooks only | Dedicated multi-book retrieval with book_title metadata + knowledge graph |
| Knowledge graph relationships | No | No | No | LightRAG entity graph for relational queries |
| Quality gate on retrieved docs | No | No | No | CRAG grades CORRECT/AMBIGUOUS/INCORRECT before generation |
| Accounting domain expertise | Generic | Generic | Generic | Domain-specific chunking, formula index, bilingual accounting glossary |
| Cost | $20/month | $20/month | Free | $8-35/month operational |
| Private corpus (your textbooks) | No | No | Yes (limited) | Yes — full control over 20-30 textbooks |

---

## Sources

- [Best 5 RAG-Powered AI Agent Systems for Accounting Firms (2025)](https://agentiveaiq.com/listicles/best-5-rag-powered-ai-agent-systems-for-accounting-firms)
- [RAG in Finance: Top 10 Game-Changing Use Cases](https://arya.ai/blog/rag-in-finance-top-10-use-cases)
- [Guide to Adaptive RAG Systems with LangGraph](https://www.analyticsvidhya.com/blog/2025/03/adaptive-rag-systems-with-langgraph/)
- [Adaptive RAG — LangGraph official tutorial](https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_adaptive_rag/)
- [Corrective RAG (CRAG) — Meilisearch](https://www.meilisearch.com/blog/corrective-rag)
- [Open-Source Reproduction and Explainability Analysis of CRAG](https://arxiv.org/html/2603.16169)
- [LightRAG — HKUDS GitHub (EMNLP 2025)](https://github.com/HKUDS/LightRAG)
- [Citation-Aware RAG: How to add Fine Grained Citations](https://www.tensorlake.ai/blog/rag-citations)
- [Integrating Domain Knowledge for Financial QA: Multi-Retriever RAG (arXiv 2512.23848)](https://arxiv.org/abs/2512.23848)
- [Multilingual RAG for Culturally-Sensitive Tasks (arXiv 2410.01171)](https://arxiv.org/abs/2410.01171)
- [Trusty_RAG_Akmen.md — master architecture specification (524 lines)](D:/trusty-rag-akmen/Trusty_RAG_Akmen.md)
- [.planning/PROJECT.md — validated requirements and constraints](D:/trusty-rag-akmen/.planning/PROJECT.md)

---

*Feature research for: AI-powered cost & management accounting RAG assistant (Trusty RAG Akmen)*
*Researched: 2026-03-22*
