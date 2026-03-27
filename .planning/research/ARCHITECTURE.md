# Architecture Research

**Domain:** Domain-specific Agentic RAG system for textbook knowledge retrieval
**Researched:** 2026-03-22
**Confidence:** HIGH (core patterns), MEDIUM (LightRAG specifics), HIGH (ingestion/retrieval separation)

---

## Standard Architecture

### The Fundamental Split: Offline Ingestion vs Online Retrieval

The single most important architectural decision for any production RAG system is treating the ingestion pipeline and the retrieval pipeline as **two independent, separately deployable programs** — not two phases of the same script.

This is validated across NVIDIA's RAG 101 guide, Databricks production cookbook, and Unstructured.io's best practices: the offline workflow builds a searchable memory; the online workflow assembles context per query. When blurred, you lose debuggability — failures become impossible to diagnose (data quality? retrieval logic? generation prompt?).

For Trusty RAG Akmen specifically, this split maps cleanly:

- **Offline:** runs once (or when new textbooks arrive). Heavy computation. GPU local. SiliconFlow batch API. Days of runtime is acceptable.
- **Online:** runs per query. Must be fast. No GPU. SiliconFlow real-time API. Target <10s for simple, <20s for complex.

The proposed architecture correctly separates these. This is validated as the correct approach.

---

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         OFFLINE INGESTION PIPELINE                        │
│                        (runs once per textbook batch)                     │
│                                                                           │
│  ┌────────────┐   ┌────────────────────────┐   ┌──────────────────────┐ │
│  │  PDF Input  │   │    Stage 1: Parsing    │   │  Stage 2: Chunking   │ │
│  │  (raw PDFs) │──▶│  PyMuPDF → route       │──▶│  Structure-aware     │ │
│  │  20-30 books│   │  Docling (text-based)  │   │  Content-type split  │ │
│  └────────────┘   │  MinerU (scanned)       │   │  Parent-child hier.  │ │
│                   │  Qwen-VL (diagrams)     │   │  Metadata enrichment │ │
│                   │  GPU LOCAL              │   │  CPU (no GPU needed) │ │
│                   └────────────────────────┘   └──────────┬───────────┘ │
│                                                            │              │
│              ┌─────────────────────────────────────────────┘              │
│              ▼                           ▼                                │
│  ┌───────────────────────┐  ┌─────────────────────────────────────────┐  │
│  │  Stage 3a: Vector     │  │  Stage 3b: Graph Index                  │  │
│  │  Index (SiliconFlow)  │  │  (SiliconFlow — LightRAG entity extract)│  │
│  │                       │  │                                         │  │
│  │  Qwen3-Embedding-8B   │  │  LightRAG + Qwen3-30B-A3B              │  │
│  │  → Qdrant Cloud       │  │  → nano-vectordb + NetworkX             │  │
│  │  (dense + BM25 sparse)│  │  Entity types + Relationship types      │  │
│  └───────────────────────┘  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

                    ↓  (indexes persist in Qdrant Cloud + LightRAG workdir)

┌──────────────────────────────────────────────────────────────────────────┐
│                         ONLINE RETRIEVAL PIPELINE                         │
│                          (runs per user query)                            │
│                                                                           │
│  User Query (Indonesian)                                                  │
│      │                                                                    │
│      ▼                                                                    │
│  ┌────────────────────────────────────┐                                  │
│  │     Query Preprocessing Layer       │                                  │
│  │  Language detect + glossary lookup  │                                  │
│  │  Query embedding (Qwen3-Emb-8B API) │                                  │
│  └──────────────────┬─────────────────┘                                  │
│                     ▼                                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │              LangGraph Orchestration Layer                          │  │
│  │                                                                     │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │       Complexity Router (1 LLM call, Qwen3-30B-A3B)          │  │  │
│  │  └──────┬──────────┬──────────────┬──────────────┬─────────────┘  │  │
│  │         │          │              │              │                  │  │
│  │      Simple     Medium         Complex      Calculation             │  │
│  │      2 calls    3 calls        4-5 calls     2-3 calls              │  │
│  │         │          │              │              │                  │  │
│  │  ┌──────┴──────────┴──────────────┴──────────────┴──────────────┐  │  │
│  │  │                  Tool Invocation Layer                         │  │  │
│  │  │  vector_search() │ graph_query() │ reranker() │ calculator()   │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                     │                                                     │
│          ┌──────────┼──────────────┐                                     │
│          ▼          ▼              ▼                                      │
│  ┌─────────────┐ ┌─────────┐ ┌──────────────┐                           │
│  │ Qdrant Cloud│ │LightRAG │ │  Calculator  │                           │
│  │ (vector+BM25│ │(GraphRAG│ │  (Python)    │                           │
│  └──────┬──────┘ └────┬────┘ └──────┬───────┘                           │
│         └─────────────┴─────────────┘                                    │
│                          │                                                │
│                          ▼                                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    CRAG Quality Gate                                 │  │
│  │   Grade relevance: CORRECT / AMBIGUOUS / INCORRECT                  │  │
│  │   If AMBIGUOUS/INCORRECT → reformulate → re-retrieve (max 2x)       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                          │                                                │
│                          ▼                                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                   Response Generation                                │  │
│  │   Qwen3-30B-A3B-Instruct-2507 via SiliconFlow                      │  │
│  │   Indonesian output + English technical terms + source citations    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                          │                                                │
│                          ▼                                                │
│               Streamlit / Chainlit UI                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| PDF Router (PyMuPDF) | Quick-scan: detect text-based vs scanned PDF | Docling, MinerU |
| Docling | Parse text-based PDFs: tables (97.9% accuracy), formulas (F1 0.968), layout | Chunking pipeline |
| MinerU | Parse scanned/complex PDFs: sequential model loading for 6 GB VRAM | Chunking pipeline |
| VLM Captioner (Qwen-VL) | Convert diagram images to structured text descriptions | SiliconFlow API |
| Chunking Pipeline | 7-step hybrid: structure-aware → content-type → parent-child → metadata | Vector indexer, Graph indexer |
| Formula Index Builder | Create per-chapter formula reference chunks as high-relevance retrieval targets | Qdrant |
| Vector Indexer | Embed chunks via Qwen3-Embedding-8B, store in Qdrant with BM25 sparse vectors | Qdrant Cloud |
| Graph Indexer (LightRAG) | Extract entities/relations, build knowledge graph | LightRAG workdir (nano-vectordb + NetworkX) |
| Query Preprocessor | Language detect, bilingual glossary lookup, query embedding | Qwen3-Embedding-8B API |
| Complexity Router | Single LLM call classifies query into Simple/Medium/Complex/Calculation | LangGraph |
| Supervisor Agent (LangGraph) | Coordinates tool calling, maintains state machine, handles retry on CRAG fail | All tools |
| vector_search tool | Hybrid Qdrant search (dense + BM25), metadata filtering by book/chapter | Qdrant Cloud |
| graph_query tool | LightRAG query (local/naive/hybrid/mix mode by query type) | LightRAG |
| reranker tool | Qwen3-Reranker-8B cross-encoder scoring + deduplication | SiliconFlow API |
| calculator tool | Python eval for accounting formulas (BEP, variance analysis, overhead rate) | Python stdlib |
| CRAG Grader | Evaluate retrieved doc relevance, trigger reformulation loop if below threshold | LangGraph state |
| Response Generator | Construct bilingual Indonesian response with source citations | Qwen3-30B-A3B API |
| Monitoring (LangSmith/Langfuse) | Trace all LLM calls, log latency and token usage | All LLM-touching components |

---

## Validated Architecture Decisions

### Decision 1: Offline/Online Separation — VALIDATED

**What the research says:** Universal production best practice. NVIDIA, Databricks, Unstructured all explicitly state this as the correct pattern. The offline pipeline builds a searchable memory; the online pipeline assembles context per query. Changing one does not break the other.

**For Trusty RAG Akmen:** The GPU-local parsing constraint makes this non-optional. Parsing 20-30 textbooks takes 2-4 days of GPU time — this cannot be done online. The separation is correct and well-motivated.

**Component boundary:** `src/ingestion/` (offline) has zero runtime dependency on `src/retrieval/` (online). They communicate only through shared storage: Qdrant index + LightRAG workdir.

### Decision 2: Supervisor with Tool-Calling Pattern — VALIDATED

**What the research says:** LangChain's own documentation now recommends tool-calling pattern over the older `langgraph-supervisor` library for most use cases. The pattern reduces LLM calls because one supervisor call can invoke multiple tools sequentially within a single reasoning loop. Confirmed at 2-5 API calls per query vs 6+ (full supervisor) or 10+ (hierarchical).

**Confidence:** HIGH — this is LangChain's current official recommendation.

**Implementation note:** Use `create_react_agent` with tool binding. The supervisor makes one call per routing decision, not per tool invocation.

### Decision 3: CRAG Quality Gate — VALIDATED

**What the research says:** The original CRAG paper (arXiv 2401.15884, accepted EMNLP) shows consistent improvement across short-form and long-form tasks. The key component is the lightweight retrieval evaluator that grades documents as CORRECT/AMBIGUOUS/INCORRECT and triggers query reformulation when below threshold. LangGraph is explicitly used as the reference implementation framework in multiple CRAG tutorials (DataCamp, Meilisearch).

**For Trusty RAG Akmen:** A CRAG quality gate is especially important for an accounting domain where incorrect formula citations have professional consequences. The reformulation loop should cap at 2 iterations to prevent runaway API costs.

**Confidence:** HIGH.

### Decision 4: Adaptive 4-Level Routing — VALIDATED with Refinement

**What the research says:** Adaptive RAG with query complexity classification is well-established (Adaptive-RAG paper, RouteRAG framework, Microsoft METIS). Research shows up to 4x cost reduction by routing simple queries away from expensive multi-step pipelines.

**Validation:** The 4-level taxonomy (Simple/Medium/Complex/Calculation) is well-reasoned for accounting. However, the complexity classifier itself is an additional LLM call. For the Calculation category specifically, consider a rule-based pre-check (presence of numbers + arithmetic keywords) before using an LLM call for classification — this would reduce the Simple path from 2 total calls to 1.

**Confidence:** HIGH for the pattern; MEDIUM for the exact 4-level taxonomy without empirical testing on accounting queries.

### Decision 5: Hybrid Chunking 7-Step Pipeline — VALIDATED

**What the research says:** Multiple 2025 sources confirm hybrid chunking as the correct approach for structured documents like textbooks. Parent-child hierarchy is specifically recommended for "textbooks, legal contracts, or extensive technical manuals." The 512-token sweet spot for narrative text is backed by FloTorch 2026 benchmark (69% end-to-end accuracy) and Vectara NAACL 2025 findings.

**Key validation:** The content-type routing within chunking (table → preserve whole, formula → atomic unit + description, narrative → recursive 512-token) is well-supported by production RAG documentation.

**Confidence:** HIGH for the overall approach; MEDIUM for specific token counts until measured against actual textbook quality.

### Decision 6: Parent-Child Hierarchy — VALIDATED

**What the research says:** Explicitly recommended for documents with hierarchical structure. Child chunks (200-512 tokens) used for retrieval matching; parent chunks (1000-1500 tokens) returned for generation context. LlamaIndex `HierarchicalNodeParser` + `AutoMergingRetriever` is the standard implementation path.

**Confidence:** HIGH.

### Decision 7: LightRAG for GraphRAG — VALIDATED with Caveat

**What the research says:** LightRAG was accepted at EMNLP 2025 as a peer-reviewed paper. The dual-level retrieval (low-level = entity-specific, high-level = thematic/multi-hop) is architecturally sound. LightRAG now has confirmed Qwen3-30B-A3B extraction enhancements as of 2025. Citation support was recently added.

**Key caveat:** The proposed architecture correctly keeps LightRAG's built-in nano-vectordb separate from Qdrant. This is the correct isolation decision — attempting to use Qdrant as LightRAG's internal vector store introduces configuration complexity without meaningful benefit for this scale (120,000 chunks fits comfortably in nano-vectordb).

**Known LightRAG limitation:** Entity extraction quality drops significantly with models smaller than 30B. The Qwen3-30B-A3B choice is well-motivated.

**Confidence:** MEDIUM — LightRAG is relatively new (2024), and real-world accounting domain knowledge graph quality is unverified until first ingestion run.

---

## Data Flow

### Ingestion Data Flow (Offline)

```
Raw PDF
    │
    ▼
PyMuPDF quick scan (CPU, ~0.12s/page)
    │
    ├── text-based PDF → Docling (GPU, ~1-2 pages/s)
    └── scanned PDF   → MinerU (GPU, ~0.3-0.8 pages/s)
    │
    ▼
Structured Markdown + HTML tables + LaTeX formulas
    │
    ├── Diagrams → image extract → Qwen-VL captioning (SiliconFlow API)
    │
    ▼
[CPU] 7-Step Hybrid Chunker
    │
    ├── Step 1: Structure-aware split (heading hierarchy → breadcrumb metadata)
    ├── Step 2: Content-type classifier (narrative | table | formula | diagram | example)
    ├── Step 3: Content-type specific split (512t narrative, preserve tables, atomic formulas)
    ├── Step 4: Parent-child hierarchy (HierarchicalNodeParser: 1000-1500t parent, 200-512t child)
    ├── Step 5: Late chunking (batch embed full sections via API before splitting)
    ├── Step 6: Formula index chunks (per-chapter formula reference chunks)
    └── Step 7: Metadata enrichment (book_title, chapter, section_path, content_type, page_number)
    │
    ├── [PARALLEL] Vector Indexing (SiliconFlow batch API)
    │       Qwen3-Embedding-8B → Qdrant Cloud (dense + BM25 sparse)
    │       ~120,000 chunks → ~$4-8 one-time cost
    │
    └── [PARALLEL] Graph Indexing (SiliconFlow batch API)
            LightRAG entity/relation extraction via Qwen3-30B-A3B
            → nano-vectordb + NetworkX (LightRAG workdir)
            ~$5-15 one-time cost
```

### Query Data Flow (Online)

```
User query (Indonesian text)
    │
    ▼
Query Preprocessor
    ├── Language detection
    ├── Bilingual glossary lookup (200-500 EN↔ID accounting terms)
    └── Query embedding (Qwen3-Embedding-8B via SiliconFlow)
    │
    ▼
LangGraph State Machine (Supervisor Agent)
    │
    ▼
Complexity Router [1 LLM call]
    │
    ├── Simple (definition/fact) ─────────────────────────────────┐
    │       vector_search(top_k=5)                                 │
    │       → CRAG grade → Generate                               │
    │       Total: 2 LLM calls                                    │
    │                                                              │
    ├── Medium (explanation/procedure) ───────────────────────────┤
    │       vector_search(top_k=10) + reranker                    │
    │       → CRAG grade → Generate                               │
    │       Total: 3 LLM calls                                    │
    │                                                              │
    ├── Complex (comparison/synthesis) ───────────────────────────┤
    │       vector_search + graph_query(hybrid/mix mode) + reranker│
    │       → CRAG grade → Generate                               │
    │       Total: 4-5 LLM calls                                  │
    │                                                              │
    └── Calculation (BEP/variance/overhead) ──────────────────────┤
            formula graph query + calculator tool                  │
            → Generate with step-by-step working                  │
            Total: 2-3 LLM calls                                  │
                                                                   │
    ◄──────────────────────────────────────────────────────────────┘
    │
    ▼
CRAG Quality Gate
    ├── CORRECT    → proceed to generation
    ├── AMBIGUOUS  → query reformulation → re-retrieve (max 2 iterations)
    └── INCORRECT  → query reformulation → re-retrieve (max 2 iterations)
    │
    ▼
Response Generator [1 LLM call]
    Qwen3-30B-A3B: Indonesian response + EN terms + source citations
    │
    ▼
Frontend (Streamlit / Chainlit)
```

---

## Recommended Project Structure

```
trusty-rag-akmen/
├── config/
│   ├── settings.py          # Pydantic BaseSettings: all API keys, model names, thresholds
│   ├── glossary.py          # Bilingual EN↔ID accounting glossary (~200-500 terms)
│   └── prompts.py           # All system prompts centralized (router, grader, generator)
│
├── src/
│   ├── llm/                 # SiliconFlow client wrapper, model registry
│   │   └── client.py        # OpenAI-compatible client with base_url override
│   │
│   ├── ingestion/           # OFFLINE PIPELINE — no runtime import from retrieval/
│   │   ├── parsing/
│   │   │   ├── router.py    # PyMuPDF quick-scan: returns "text-based" | "scanned"
│   │   │   ├── docling_parser.py    # Text-based PDFs, batch_size=4, CUDA
│   │   │   ├── mineru_parser.py     # Scanned PDFs, --vram 6, sequential loading
│   │   │   ├── vlm_captioner.py    # Diagram → Qwen-VL via SiliconFlow
│   │   │   └── gpu_utils.py        # VRAM cleanup: del/gc/empty_cache/synchronize
│   │   ├── chunking/
│   │   │   ├── classifier.py       # Element type: narrative|table|formula|diagram|example
│   │   │   ├── structure_splitter.py    # Heading hierarchy → breadcrumb metadata
│   │   │   ├── content_splitter.py      # Per-type split rules
│   │   │   ├── hierarchy_builder.py     # LlamaIndex HierarchicalNodeParser
│   │   │   ├── late_chunker.py          # Chonkie LateChunker via API batch
│   │   │   ├── formula_indexer.py       # Per-chapter formula reference chunks
│   │   │   └── metadata_enricher.py     # book_title, chapter, section_path, page_number
│   │   ├── indexing/
│   │   │   ├── embedder.py          # Qwen3-Embedding-8B batch via SiliconFlow
│   │   │   ├── qdrant_uploader.py   # Dense + BM25 sparse upload
│   │   │   └── lightrag_builder.py  # LightRAG entity/relation extraction + graph build
│   │   └── pipeline.py             # End-to-end orchestrator, stage sequencing
│   │
│   ├── retrieval/           # ONLINE PIPELINE — no GPU, no batch jobs
│   │   ├── preprocessor.py  # Language detect, glossary expand, query embed
│   │   ├── router.py        # 4-level complexity classifier (LLM call)
│   │   ├── vector_search.py # Qdrant hybrid search (dense + BM25), metadata filter
│   │   ├── graph_search.py  # LightRAG query wrapper (mode selection by query type)
│   │   ├── reranker.py      # Qwen3-Reranker-8B via SiliconFlow
│   │   └── crag.py          # Relevance grader + reformulation loop (max 2 retries)
│   │
│   ├── tools/               # LangChain @tool wrappers for Supervisor Agent
│   │   ├── vector_search_tool.py
│   │   ├── graph_query_tool.py
│   │   ├── reranker_tool.py
│   │   └── calculator_tool.py   # Python eval: BEP, variance, overhead, contribution margin
│   │
│   ├── agents/              # LangGraph state machine
│   │   ├── state.py         # GraphState schema (query, retrieved_docs, grade, history)
│   │   ├── supervisor.py    # create_react_agent with tool binding
│   │   ├── nodes.py         # Router node, grader node, generator node
│   │   ├── edges.py         # Conditional edges: grade result → next node
│   │   └── graph.py         # Compile LangGraph state machine
│   │
│   ├── generation/
│   │   ├── generator.py     # Response synthesis with bilingual instructions
│   │   ├── formatter.py     # Markdown formatting, calculation step-by-step
│   │   └── citation_builder.py  # Extract + format source citations from metadata
│   │
│   └── monitoring/
│       └── tracer.py        # LangSmith/Langfuse integration, token usage logging
│
├── app/
│   └── main.py              # Streamlit / Chainlit UI entry point
│
├── scripts/
│   ├── ingest.py            # CLI: ingest all PDFs from data/raw/
│   ├── ingest_single.py     # CLI: ingest one book incrementally
│   ├── test_query.py        # CLI: test retrieval + generation without UI
│   └── build_formula_index.py  # CLI: rebuild formula index only
│
├── tests/
│   ├── test_parsing.py
│   ├── test_chunking.py
│   ├── test_retrieval.py
│   ├── test_router.py
│   ├── test_crag.py
│   ├── test_calculator.py
│   └── test_e2e.py
│
└── data/                    # gitignored
    ├── raw/                 # Source PDF textbooks
    ├── parsed/              # Docling/MinerU output (Markdown + HTML tables)
    ├── chunks/              # Serialized chunk JSON with metadata
    ├── llamaindex_store/    # HierarchicalNodeParser storage
    └── lightrag_workdir/    # LightRAG graph + nano-vectordb
```

### Structure Rationale

- **`ingestion/` vs `retrieval/` hard boundary:** The most important structural decision. `pipeline.py` in ingestion imports nothing from retrieval. This enables running ingestion as a separate process (even on a different machine) and prevents accidental online/offline bleed.
- **`tools/` as thin wrappers:** Each tool is a `@tool`-decorated function that delegates to `retrieval/`. This keeps business logic in `retrieval/` (testable without LangGraph) while exposing the interface LangGraph needs.
- **`agents/` owns only orchestration:** `state.py`, `nodes.py`, `edges.py` contain no retrieval or generation logic directly. They call into `retrieval/` and `generation/` via tools. This makes the state machine testable in isolation.
- **`config/prompts.py` centralized:** All system prompts in one file prevents prompt drift and makes prompt tuning discoverable without grepping through agent code.
- **`gpu_utils.py` explicit:** The VRAM cleanup sequence (del → gc.collect → empty_cache → synchronize) is safety-critical for GTX 1660 Ti. Centralizing it prevents bugs from inconsistent cleanup between Docling and MinerU sessions.

---

## Architectural Patterns

### Pattern 1: Supervisor with Tool-Calling (ReAct Loop)

**What:** One supervisor LLM call decides which tools to invoke. Tools execute, return results to state. Supervisor either calls another tool or produces final output. No intermediate LLM calls between tool invocations.

**When to use:** When multiple retrieval strategies need to be combined per query, and the combination varies by query type. Eliminates the overhead of having separate specialist agents that each require an LLM call to invoke.

**Trade-offs:**
- Pro: Lowest API call count (2-5 per query)
- Pro: Single reasoning context means supervisor can synthesize across tool results
- Con: Supervisor prompt must be more complex to handle all tool types
- Con: No true parallelism (tools called sequentially within one reasoning loop)

**Example (LangGraph):**
```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://api.siliconflow.com/v1",
    model="Qwen/Qwen3-30B-A3B-Instruct-2507",
    api_key=settings.siliconflow_api_key
)

agent = create_react_agent(
    llm,
    tools=[vector_search_tool, graph_query_tool, reranker_tool, calculator_tool],
    state_modifier=system_prompt
)
```

### Pattern 2: CRAG Quality Gate with Bounded Retry

**What:** After retrieval, an LLM grader evaluates document relevance (CORRECT/AMBIGUOUS/INCORRECT). If grade is below threshold, the query is reformulated and retrieval is attempted again. Loop is capped at 2 retries to prevent runaway costs.

**When to use:** Domain-specific applications where incorrect retrieval has real consequences (accounting errors, medical information, legal advice).

**Trade-offs:**
- Pro: Significantly improves precision on domain-specific queries where terminological drift causes poor retrieval
- Pro: Query reformulation catches cases where original Indonesian phrasing maps poorly to English textbook vocabulary
- Con: Adds 1 LLM call per retrieval attempt (grading)
- Con: Can increase latency 2-3x on INCORRECT queries

**Implementation note:** The grader prompt should be the same model (Qwen3-30B-A3B) but with a much shorter system prompt — binary classification, not generation. Consider caching grade results for identical (query, doc_hash) pairs within a session.

### Pattern 3: Parent-Child Retrieval with AutoMerging

**What:** Index child chunks (200-512 tokens) for retrieval matching. When a child is retrieved, fetch its parent chunk (1000-1500 tokens) for generation context. LlamaIndex `AutoMergingRetriever` automates this by replacing child nodes with parent nodes when a threshold fraction of children from the same parent are retrieved.

**When to use:** Textbooks with clear hierarchical section structure. When retrieved passages need more surrounding context than the child chunk provides.

**Trade-offs:**
- Pro: High-precision retrieval (small chunks match queries better) + high-context generation (parent chunks provide surrounding text)
- Con: Doubles storage requirements (both parent and child chunks stored)
- Con: AutoMergingRetriever adds query-time overhead

**LlamaIndex implementation path:**
```python
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.retrievers import AutoMergingRetriever

parser = HierarchicalNodeParser.from_defaults(
    chunk_sizes=[1500, 512, 128]  # parent → child → grandchild
)
```

### Pattern 4: Dual-Store Isolation (Qdrant + LightRAG Independent)

**What:** Qdrant serves direct vector search (used by `vector_search` tool). LightRAG maintains its own internal storage (nano-vectordb + NetworkX graph). They do not share storage or indexes.

**When to use:** When adding GraphRAG to an existing vector-based RAG system. Avoids configuration complexity of forcing LightRAG to use external vector stores.

**Trade-offs:**
- Pro: Each store is independently queryable and debuggable
- Pro: LightRAG operates as a black box — internal changes to LightRAG don't affect Qdrant setup
- Con: Two separate indexes to maintain and keep synchronized on ingestion
- Con: Slightly higher total storage footprint

**This is the correct decision for Trusty RAG Akmen at current scale.** The LightRAG GitHub issue #248 confirms that forcing LightRAG to use Qdrant as its internal vector store is possible but introduces configuration complexity without benefit at <200,000 chunk scale.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| SiliconFlow API | OpenAI-compatible REST, single `ChatOpenAI` client with `base_url` override | Rate limit: 50 RPD default, 1000 RPD after $10 purchase. Use exponential backoff. |
| Qdrant Cloud | Official `qdrant-client` Python SDK, `AsyncQdrantClient` for online path | Free tier: 1 GB RAM, 4 GB disk. Scalar quantization reduces ~120K vectors to well within limits. |
| LightRAG | Python library, `LightRAG(working_dir=..., llm_model_func=..., embedding_func=...)` | SiliconFlow integration confirmed via `lightrag_siliconcloud_demo.py` in repo. |
| LangSmith / Langfuse | LangChain callbacks (`LangSmithCallbackHandler` / Langfuse SDK) | Both support free tier. LangSmith tightly integrated with LangGraph for trace visualization. |

### Internal Boundaries

| Boundary | Communication Pattern | Notes |
|----------|-----------------------|-------|
| `ingestion/` → `retrieval/` | File system only (Qdrant index + LightRAG workdir). No direct import. | This is the offline/online separation boundary. |
| `retrieval/` → `tools/` | Direct Python import, tools are thin wrappers | Tools call retrieval functions, add `@tool` decorator |
| `tools/` → `agents/` | LangChain tool protocol (function + schema) | Agent binds tools, calls them by name |
| `agents/` → `generation/` | LangGraph state (pass retrieved docs via state dict) | Generator reads from state, not called directly by supervisor |
| All LLM-touching modules → `monitoring/` | LangChain callback injection | `tracer.py` provides callback handler added to all chains |

---

## Build Order (Phase Dependencies)

The component dependency graph dictates a specific build order:

```
Phase 1 (Foundation)
└── SiliconFlow client + model registry
└── Qdrant Cloud connection + collection setup
└── Basic end-to-end: single PDF → chunks → vectors → query → generate
    (Validates API connectivity, embedding/retrieval quality before building complexity)

Phase 2 (GraphRAG)
└── LightRAG integration (depends on: SiliconFlow client)
└── graph_query tool (depends on: LightRAG working)
└── Validate graph retrieval improves comparison-type queries

Phase 3 (Agentic Orchestration)
└── LangGraph state machine (depends on: vector_search + graph_query tools working)
└── Complexity router (depends on: LangGraph state machine)
└── CRAG quality gate (depends on: router, retrieval tools)
└── Full Supervisor + Tool-Calling loop

Phase 4 (Scale + Optimization)
└── Full corpus ingestion (depends on: all ingestion pipeline validated on small set)
└── Performance tuning: chunk sizes, top_k values, router thresholds
└── Cost optimization: cache CRAG grades, tune retry limits

Phase 5 (Polish)
└── UI (Streamlit/Chainlit)
└── Monitoring dashboards
└── Incremental ingestion for new textbooks
```

**Critical dependency:** Do not build Phase 3 (agentic) before validating Phase 1 (basic RAG quality). Agentic complexity is only worth the added API cost if the underlying retrieval quality is ≥70% precision on test queries. A poor retrieval foundation cannot be fixed by adding routing layers on top.

---

## Anti-Patterns

### Anti-Pattern 1: Running All Components in One Python Process

**What people do:** Single script that calls PyMuPDF → Docling → MinerU → embed → index → query in sequence.

**Why it's wrong:** MinerU peaks at 3-5 GB VRAM during sequential model loading. Docling uses 0.5-1 GB. Running both in the same Python process without explicit VRAM cleanup between them risks OOM errors on 6 GB VRAM. Also makes the ingestion pipeline impossible to resume if it crashes midway through 100 textbooks.

**Do this instead:** Implement `pipeline.py` as a resumable stage-based orchestrator. Each stage writes its output to disk before the next begins. Add stage checkpointing (a simple JSON file tracking which books have completed each stage). Free VRAM explicitly after each parser completes.

### Anti-Pattern 2: Embedding All Chunks Before Chunking Strategy is Validated

**What people do:** Immediately embed all 120,000 chunks after first ingestion run.

**Why it's wrong:** The chunking strategy (512-token sizes, overlap amounts, parent-child split points) may need adjustment after testing retrieval quality on sample queries. Re-embedding 120,000 chunks costs ~$4-8 each time. Adjusting chunk sizes after embedding requires full re-ingestion.

**Do this instead:** Ingest 3-5 textbooks first. Test 20-30 representative queries. Validate that chunk boundaries and sizes produce good retrieval results before committing to full corpus embedding.

### Anti-Pattern 3: Using LightRAG's Internal Vector Store for Both Purposes

**What people do:** Configure LightRAG to use Qdrant as its internal vector store to "unify" storage.

**Why it's wrong:** LightRAG's graph entity/relation vectors have different dimensionality and retrieval semantics than document chunk vectors. Mixing them in one Qdrant collection creates indexing complexity. LightRAG's built-in nano-vectordb is well-suited for its ~10,000-50,000 entity vectors at this scale.

**Do this instead:** Keep stores separate as proposed. Qdrant for document chunk retrieval. LightRAG for graph-aware entity retrieval. Query both via separate tools, combine results at the agent level.

### Anti-Pattern 4: Making the Complexity Router an LLM Call for All Queries

**What people do:** Every query, including pure Calculation queries with obvious numeric structure, passes through the 1-LLM-call complexity router.

**Why it's wrong:** Wastes a SiliconFlow API call on queries that can be identified with a regex or simple heuristic (e.g., query contains numbers + calculation keywords like "hitung", "BEP", "variance").

**Do this instead:** Apply a fast rule-based pre-check before the LLM router. If the query matches calculation patterns with high confidence, skip to the Calculation path. Use the LLM router only for ambiguous cases. This reduces Simple/Calculation path from 2 calls to 1.5 calls on average.

### Anti-Pattern 5: Prompts Scattered Across Source Files

**What people do:** Write system prompts inline in agent/tool/generator Python files.

**Why it's wrong:** Prompt tuning (the most common iteration activity) requires hunting through source files. Changes are hard to track. Bilingual glossary gets duplicated.

**Do this instead:** Centralize all prompts in `config/prompts.py`. Each prompt is a named constant or dataclass. Tuning prompts is then a single-file change without touching business logic.

---

## Scaling Considerations

This is a personal tool for one user. Current targets:

| Scale | Architecture | Notes |
|-------|-------------|-------|
| Current: 1 user, 500 queries/day | Single-process Python app, Qdrant Cloud free tier, no concurrency needed | The current architecture is appropriately simple for this scale |
| Future: 10 concurrent users | Add async throughout (AsyncQdrantClient already recommended), consider Redis for session state instead of in-memory | Qdrant free tier handles 10 concurrent queries easily |
| Future: 100+ users or commercial | Move to paid Qdrant tier (horizontal scaling), consider dedicated LightRAG service, add Redis rate limiting per user | Architecture is modular enough to extract components into services without rewrite |

**First bottleneck if scaled:** SiliconFlow API rate limits (50 RPD free tier, 1000 RPD paid). At 500 queries/day with average 3 LLM calls each = 1,500 RPD — exceeds free tier. Budget $10 purchase unlocks 1,000 RPD; multiple accounts or paid tier for higher volume.

**Second bottleneck:** Qdrant Cloud free tier (1 GB RAM). At 120,000 chunks × 1,024 dimensions × 4 bytes = ~500 MB for dense vectors + BM25 sparse overhead. Should fit with scalar quantization but will be near limit. Pay tier at $25/month provides significantly more headroom.

---

## Sources

- NVIDIA RAG 101 guide — offline/online separation as production standard: [https://developer.nvidia.com/blog/rag-101-demystifying-retrieval-augmented-generation-pipelines/](https://developer.nvidia.com/blog/rag-101-demystifying-retrieval-augmented-generation-pipelines/)
- LangGraph agentic RAG official documentation: [https://docs.langchain.com/oss/python/langgraph/agentic-rag](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- CRAG original paper (EMNLP): [https://arxiv.org/abs/2401.15884](https://arxiv.org/abs/2401.15884)
- CRAG LangGraph implementation guide (DataCamp): [https://www.datacamp.com/tutorial/corrective-rag-crag](https://www.datacamp.com/tutorial/corrective-rag-crag)
- LightRAG EMNLP 2025 paper: [https://github.com/HKUDS/LightRAG](https://github.com/HKUDS/LightRAG)
- Adaptive RAG with complexity classification: [https://www.analyticsvidhya.com/blog/2025/03/adaptive-rag-systems-with-langgraph/](https://www.analyticsvidhya.com/blog/2025/03/adaptive-rag-systems-with-langgraph/)
- Parent-child chunking for hierarchical documents: [https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089)
- Qdrant hybrid search (dense + BM25): [https://qdrant.tech/articles/hybrid-search/](https://qdrant.tech/articles/hybrid-search/)
- HybridRAG faithfulness benchmarks: from Trusty_RAG_Akmen.md (faithfulness 0.96 vector+graph vs 0.94 vector-only)
- Production RAG best practices (Unstructured): [https://unstructured.io/insights/rag-systems-best-practices-unstructured-data-pipeline](https://unstructured.io/insights/rag-systems-best-practices-unstructured-data-pipeline)

---
*Architecture research for: Trusty RAG Akmen — AI-powered cost & management accounting assistant*
*Researched: 2026-03-22*
