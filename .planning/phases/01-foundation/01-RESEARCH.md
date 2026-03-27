# Phase 1: Foundation - Research

**Researched:** 2026-03-22
**Domain:** RAG ingestion pipeline + bilingual vector retrieval + Streamlit UI (Python, PyTorch GPU local, SiliconFlow cloud API)
**Confidence:** HIGH (all critical decisions verified against prior project research; package versions from verified PyPI records; GPU constraints from official NVIDIA docs)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | Parse text-based PDFs via Docling on GTX 1660 Ti (batch_size=4, CUDA) | Docling 2.81.0 confirmed for text-native PDFs; batch_size=4 tested within 6 GB VRAM; PyMuPDF triage routes correctly |
| INGEST-02 | Parse scanned/complex PDFs via MinerU pipeline backend (--vram 6, sequential loading) | MinerU 2.7.6 `--vram 6` flag confirmed; pipeline backend only on 6 GB VRAM (VLM backends need 8-10 GB) |
| INGEST-03 | PyMuPDF quick scan to classify PDF as text-based vs scanned before routing | PyMuPDF 1.27.2.2 at ~100+ pages/sec (CPU) — correct cheap triage tool |
| INGEST-04 | Full VRAM cleanup (del, gc.collect, torch.cuda.empty_cache, synchronize) between parsers | MinerU GitHub issue #3399 confirms VRAM fragmentation bug; cleanup sequence documented |
| INGEST-05 | Extract diagrams as images and generate VLM text descriptions via Qwen-VL (SiliconFlow API) | Qwen-VL available on SiliconFlow; diagram extraction output feeds into chunking pipeline |
| CHUNK-01 | Classify each parsed element: narrative_text, table, formula, diagram, example_problem | Element classifier runs post-parse on Markdown/HTML output from MinerU/Docling |
| CHUNK-02 | Primary split by heading hierarchy (Part→Chapter→Section→Subsection) with breadcrumb metadata | Structure-aware split required before content-type split; heading hierarchy preserved by both parsers |
| CHUNK-03 | Secondary split per content type (narrative 512t/75 overlap; small tables whole; large tables with repeated headers; formulas atomic; examples up to 1024t) | Benchmarked: 512t for narrative, table preservation rules, atomic formulas — all validated |
| CHUNK-04 | Parent-child hierarchy via HierarchicalNodeParser (parent 1000-1500t, child 200-512t) with persistent StorageContext | LlamaIndex HierarchicalNodeParser 0.14.18 confirmed; StorageContext persistence required |
| CHUNK-06 | Add metadata per chunk: book_title, chapter, section_path, content_type, page_number | Metadata must be present from ingestion; retrofitting requires full re-chunk |
| CHUNK-07 | Create formula index chunk per chapter — key formulas with LaTeX + natural language | Separate formula-index chunks as high-relevance retrieval targets for Calculation path |
| CHUNK-08 | Inject inline page markers at parse time for accurate page_number on every chunk | `<!-- PAGE_START:N -->` marker injection pattern confirmed; strip before embedding |
| INDEX-01 | Embed all chunks to Qdrant Cloud via Qwen3-Embedding-8B (1024 dim, MRL truncation, scalar quantization) | Qdrant-client 1.17.1; 1024-dim with scalar quantization confirmed for free tier capacity |
| INDEX-02 | Index sparse BM25 vectors in Qdrant for hybrid search (captures exact English terms from Indonesian queries) | Qdrant supports sparse vectors with `modifier="idf"`; must create collection with dense+sparse at init |
| INDEX-03 | Store metadata per chunk as Qdrant payload for filtering | Standard Qdrant payload storage; filter by book_title, content_type, chapter |
| INDEX-05 | Use instruction prefix on embedding queries: "Instruct: Retrieve English accounting textbook passages relevant to the Indonesian accounting query" | Confirmed: Qwen3-Embedding-8B degrades 1-5% recall without prefix; documents embedded WITHOUT prefix |
| RETR-01 | Hybrid search in Qdrant (dense + BM25 + metadata filtering) per query | Qdrant hybrid search confirmed; langchain-qdrant integration available |
| RETR-02 | Reranking via Qwen3-Reranker-8B (SiliconFlow) with cross-lingual scoring | top-k=20 → rerank → top-k=5; MMTEB-R 72.94, CMTEB-R 77.45 |
| LANG-01 | Indonesian query retrieves accurately from English textbooks without query translation | Qwen3-Embedding-8B #1 MTEB Multilingual (70.58) — native cross-lingual, no translation layer |
| LANG-02 | Bilingual glossary (~200-500 accounting terms EN↔ID) injected into system prompt and as BM25 entries | Glossary in config/glossary.py; injected at generation and as BM25 index entries for bridging |
| LANG-03 | Output Indonesian prose with English technical terms in parentheses | Generation system prompt instruction; no separate build required |
| GEN-01 | Every response includes source citation: book name, chapter, page — format: "Horngren, Cost Accounting, Chapter 5, hal. 168-172" | Citation builder reads chunk metadata (book_title, chapter, page_start, page_end) |
| UI-01 | Streamlit chat UI — input query, see response, see citations, see calculation steps | Streamlit confirmed for v1; mature, handles structured data display |
</phase_requirements>

---

## Summary

Phase 1 builds the complete pipeline from raw PDF textbooks to a working bilingual RAG assistant. The work divides into two independent halves: an **offline ingestion pipeline** (GPU-local PDF parsing + cloud-API embedding) that builds a searchable Qdrant index, and an **online retrieval pipeline** (LangGraph state machine + Streamlit UI) that answers Indonesian accounting queries with cited responses.

All major technical decisions for Phase 1 were locked in the project's pre-phase research (STACK.md, ARCHITECTURE.md, PITFALLS.md). This research phase focuses on filling implementation-level gaps: how exactly to wire MinerU subprocess isolation, how to configure Qdrant collection from scratch with both vector types, how the SiliconFlow OpenAI-compatible client is initialized, and how the Phase 1 LangGraph graph should be scoped (simplified vs full agentic loop).

The most critical correctness requirement — exact page-level citations — depends entirely on inline page markers injected at parse time. This is non-negotiable and must be built before any ingestion. Three critical pitfalls from PITFALLS.md have direct Phase 1 impact: MinerU VRAM fragmentation (subprocess isolation), citation page number loss (inline markers), and table splitting destruction (element classifier with structure-aware rules). All three have documented solutions that must be implemented from the start, not as cleanup.

**Primary recommendation:** Build the ingestion pipeline first, validate it on 3 textbooks with manual citation spot-checks before proceeding to retrieval and UI. A broken ingestion pipeline produces an index that looks healthy but silently fails at query time.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LangGraph | 1.1.3 | Agentic orchestration, LangGraph state machine, simple retrieval graph for Phase 1 | Production-stable (2026-03-18). Standard for stateful RAG loops. `create_react_agent` with tool binding is the correct pattern. No serious alternative for explicit graph-state RAG. |
| LangChain | 1.2.13 | `@tool` decorators, Qdrant retriever abstractions, TextSplitter | Toolbox that LangGraph nodes call. Do NOT use as orchestrator. |
| qdrant-client | 1.17.1 | Primary vector database — dense + sparse BM25 vectors, metadata payloads | Qdrant Cloud Free Tier: 1 GB RAM, 4 GB disk. Scalar quantization reduces memory 4x. Must be configured with both dense and sparse vector specs at collection creation. |
| langchain-qdrant | latest | LangChain Qdrant integration for hybrid retrieval | Stable integration; provides QdrantVectorStore with hybrid search support |
| MinerU (mineru) | 2.7.6 | Primary PDF parser: scanned/complex PDFs (YOLO+OCR+UniMERNet+RapidTable) | `--vram 6` flag confirmed for GTX 1660 Ti. pipeline backend only (VLM backends need 8-10 GB). |
| Docling | 2.81.0 | Secondary PDF parser: text-based PDFs (97.9% table accuracy, F1 0.968 formulas) | MIT license, 258M Granite-Docling model, batch_size=4 fits 6 GB VRAM. |
| PyMuPDF (pymupdf) | 1.27.2.2 | Fast PDF triage scan (CPU, ~100 pages/sec) before routing to MinerU or Docling | Determines text-based vs scanned. Does NOT extract tables or formulas — triage only. |
| llama-index-core | 0.14.18 | HierarchicalNodeParser — parent-child chunk hierarchy with persistent StorageContext | Use exclusively for this. Do not mix LlamaIndex query engines with LangGraph. |
| Chonkie | 1.6.1 | LateChunker — contextually enriched chunk embeddings (semantic extras required) | Install: `pip install "chonkie[semantic]"`. LateChunker processes full section first, then derives enriched chunk embeddings. |
| pydantic-settings | 2.x | Type-safe configuration from .env files | BaseSettings for all settings.py. SecretStr for API keys. Must be pydantic-settings 2.x (v1 incompatible with Pydantic v2). |
| Streamlit | latest | Chat UI — input, response, citations, calculation steps | Mature, data-centric display suits citation tables. Preferred over Chainlit for v1 due to Chainlit governance uncertainty. |
| PyTorch (cu126 wheels) | cu126 | GPU computation for MinerU and Docling | GTX 1660 Ti is CC 7.5 — minimum for cu128. Use cu126 for safety margin. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | latest | Exponential backoff with jitter for SiliconFlow API calls (HTTP 429 retry) | Wrap ALL SiliconFlow calls. 60s initial wait, 2x delay, max 5 retries, jitter. Required before first ingestion. |
| python-dotenv | latest | Load .env file for API keys | Standard companion to pydantic-settings for local dev. |
| uv | latest | Dependency management (replaces pip + requirements.txt) | 10-100x faster than pip, lockfile support. Use for all dependency operations. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Streamlit | Chainlit | Chainlit has async-first design and better conversational UX, but original team stepped back May 2025 — now community-maintained. Use Chainlit only if governance stabilizes. |
| Qdrant Cloud Free | ChromaDB local | Use ChromaDB only if zero cloud dependency is required. Qdrant is better for eventual productization and has mature scalar quantization. |
| cu126 PyTorch | cu128 PyTorch | cu128 works on CC 7.5 but is the absolute minimum. cu126 provides documented safety margin. |

**Installation:**
```bash
# PyTorch for GTX 1660 Ti (cu126 — safety margin for CC 7.5)
pip install torch --index-url https://download.pytorch.org/whl/cu126

# Core RAG stack
pip install langgraph==1.1.3 langchain==1.2.13 langchain-qdrant qdrant-client==1.17.1

# PDF parsing pipeline
pip install mineru==2.7.6 docling==2.81.0 pymupdf==1.27.2.2

# Chunking
pip install llama-index-core==0.14.18 "chonkie[semantic]==1.6.1"

# Config, UI, reliability
pip install pydantic-settings streamlit tenacity python-dotenv

# Dependency management (preferred)
# uv init; uv add [packages above]
```

**Version verification (as of 2026-03-22, from PyPI records):**
| Package | Verified Version | Release Date |
|---------|-----------------|--------------|
| langgraph | 1.1.3 | 2026-03-18 |
| langchain | 1.2.13 | 2026-03-19 |
| qdrant-client | 1.17.1 | 2026-03-13 |
| mineru | 2.7.6 | 2026-02-06 |
| docling | 2.81.0 | 2026-03-20 |
| llama-index-core | 0.14.18 | 2026-03-16 |
| chonkie | 1.6.1 | 2026-03-18 |
| pymupdf | 1.27.2.2 | 2026-03-19 |

---

## Architecture Patterns

### Recommended Project Structure

```
trusty-rag-akmen/
├── config/
│   ├── settings.py          # Pydantic BaseSettings: API keys, model names, thresholds
│   ├── glossary.py          # Bilingual EN↔ID accounting glossary (~200-500 terms)
│   └── prompts.py           # ALL system prompts centralized — router, generator, grader
├── src/
│   ├── llm/
│   │   └── client.py        # SiliconFlow OpenAI-compatible client wrapper
│   ├── ingestion/           # OFFLINE PIPELINE — zero runtime import from retrieval/
│   │   ├── parsing/
│   │   │   ├── router.py          # PyMuPDF quick-scan → "text-based" | "scanned"
│   │   │   ├── docling_parser.py  # batch_size=4, CUDA, Granite-Docling
│   │   │   ├── mineru_parser.py   # --vram 6, pipeline backend, subprocess isolation
│   │   │   ├── vlm_captioner.py   # Diagram image → Qwen-VL via SiliconFlow
│   │   │   └── gpu_utils.py       # VRAM cleanup: del/gc/empty_cache/synchronize
│   │   ├── chunking/
│   │   │   ├── classifier.py       # Element: narrative|table|formula|diagram|example
│   │   │   ├── structure_splitter.py  # Heading hierarchy → breadcrumb metadata
│   │   │   ├── content_splitter.py    # Per-type split rules + table header repeat
│   │   │   ├── hierarchy_builder.py   # LlamaIndex HierarchicalNodeParser
│   │   │   ├── late_chunker.py        # Chonkie LateChunker via API batch
│   │   │   ├── formula_indexer.py     # Per-chapter formula reference chunks
│   │   │   └── metadata_enricher.py   # book_title, chapter, section_path, page_number
│   │   ├── indexing/
│   │   │   ├── embedder.py          # Qwen3-Embedding-8B batch via SiliconFlow
│   │   │   └── qdrant_uploader.py   # Dense + BM25 sparse upload, scalar quantization
│   │   └── pipeline.py             # End-to-end ingestion orchestrator
│   ├── retrieval/           # ONLINE PIPELINE — no GPU, no batch jobs
│   │   ├── preprocessor.py  # Glossary lookup, query embedding with instruction prefix
│   │   ├── vector_search.py # Qdrant hybrid search (dense + BM25), metadata filter
│   │   └── reranker.py      # Qwen3-Reranker-8B top-k=20 → top-k=5
│   ├── tools/               # LangChain @tool wrappers (thin — delegate to retrieval/)
│   │   ├── vector_search_tool.py
│   │   └── reranker_tool.py
│   ├── agents/              # LangGraph state machine
│   │   ├── state.py         # GraphState schema
│   │   ├── nodes.py         # Retrieval node, generation node
│   │   └── graph.py         # Phase 1 graph: simple linear retrieve → generate
│   ├── generation/
│   │   ├── generator.py         # Bilingual response synthesis
│   │   └── citation_builder.py  # Format citations from chunk metadata
│   └── monitoring/
│       └── tracer.py            # Langfuse tracer (added in Phase 4 but stub now)
├── app/
│   └── main.py              # Streamlit UI entry point
├── scripts/
│   ├── ingest.py            # CLI: ingest all PDFs from data/raw/
│   └── test_query.py        # CLI: test retrieval + generation without UI
├── tests/
│   ├── test_parsing.py
│   ├── test_chunking.py
│   ├── test_retrieval.py
│   └── test_e2e.py
└── data/                    # gitignored
    ├── raw/                 # Source PDF textbooks
    ├── parsed/              # MinerU/Docling output (Markdown + HTML tables)
    ├── chunks/              # Serialized chunk JSON with metadata
    ├── llamaindex_store/    # HierarchicalNodeParser StorageContext
    └── lightrag_workdir/    # Reserved for Phase 2
```

### Pattern 1: MinerU Subprocess Isolation for VRAM Safety

**What:** Each textbook is parsed in a separate subprocess. The subprocess exits after parsing one book, causing the OS to reclaim all CUDA memory. This prevents VRAM fragmentation from accumulating across books.

**When to use:** Always for MinerU batch ingestion on GTX 1660 Ti. Never run multiple books in a single Python process.

**Example:**
```python
# Source: MinerU GitHub issue #3399 + PITFALLS.md
import subprocess
import sys

def parse_book_in_subprocess(pdf_path: str, output_dir: str) -> dict:
    """Parse one PDF in an isolated subprocess to prevent VRAM accumulation."""
    result = subprocess.run(
        [sys.executable, "-m", "src.ingestion.parsing.mineru_parser",
         "--input", pdf_path, "--output", output_dir],
        capture_output=True,
        text=True,
        timeout=3600  # 1 hour per book
    )
    if result.returncode != 0:
        raise RuntimeError(f"MinerU failed: {result.stderr}")
    return {"pdf": pdf_path, "status": "success"}
```

**Within a single subprocess, call VRAM cleanup after each document stage:**
```python
# Source: MinerU GitHub issue #3399 + PITFALLS.md
import gc
import torch

def vram_cleanup():
    """Full VRAM cleanup — call after every MinerU or Docling model operation."""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()

# Environment variable (set before importing torch):
# PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512,expandable_segments:True
```

### Pattern 2: Inline Page Markers for Accurate Citation Page Numbers

**What:** During PDF parsing, inject HTML comments at every page boundary in the Markdown output. After chunking, parse these markers to compute actual page_start and page_end for each chunk.

**When to use:** Always, in every parser (Docling and MinerU). Without this, all chunks from a multi-page section inherit the section's starting page number — the core value proposition breaks.

**Example:**
```python
# Source: PITFALLS.md (Pitfall 8)
import re

def inject_page_markers(markdown_text: str, page_map: list[tuple[int, int]]) -> str:
    """
    page_map: list of (char_offset, page_number) tuples from PDF parser.
    Inserts <!-- PAGE_START:N --> markers at each page boundary position.
    """
    result = []
    prev_offset = 0
    for char_offset, page_num in sorted(page_map, key=lambda x: x[0]):
        result.append(markdown_text[prev_offset:char_offset])
        result.append(f"\n<!-- PAGE_START:{page_num} -->\n")
        prev_offset = char_offset
    result.append(markdown_text[prev_offset:])
    return "".join(result)

def extract_page_range(chunk_text: str) -> tuple[int, int]:
    """Extract page_start and page_end from chunk text containing page markers."""
    pages = [int(m) for m in re.findall(r"<!-- PAGE_START:(\d+) -->", chunk_text)]
    if not pages:
        return (0, 0)  # Unknown page — triggers a warning in metadata_enricher
    return (pages[0], pages[-1])

def strip_page_markers(chunk_text: str) -> str:
    """Remove page markers before embedding — they corrupt semantic vectors."""
    return re.sub(r"\n?<!-- PAGE_START:\d+ -->\n?", "\n", chunk_text).strip()
```

### Pattern 3: Qdrant Collection Initialization (Dense + Sparse from Start)

**What:** Create the Qdrant collection with BOTH dense vector config and sparse vector config at collection creation time. Adding sparse vectors to an existing dense-only collection requires recreation.

**When to use:** At first collection creation, before any data is uploaded.

**Example:**
```python
# Source: Qdrant documentation + PITFALLS.md (Integration Gotchas)
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, SparseVectorParams, SparseIndexParams,
    ScalarQuantizationConfig, ScalarType, QuantizationConfig
)

def create_collection(client: QdrantClient, collection_name: str):
    """Create Qdrant collection with dense + sparse vectors and scalar quantization."""
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": VectorParams(
                size=1024,           # Qwen3-Embedding-8B MRL truncation to 1024
                distance=Distance.COSINE,
                quantization_config=QuantizationConfig(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        always_ram=True
                    )
                )
            )
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False),
                modifier="idf"       # IDF weighting for BM25-style sparse search
            )
        }
    )
```

### Pattern 4: SiliconFlow Client with Embedding Instruction Prefix

**What:** Use the OpenAI-compatible SiliconFlow client. Embed query text WITH instruction prefix. Embed document chunks WITHOUT prefix.

**Example:**
```python
# Source: Qwen3 Embedding official blog + PITFALLS.md (Pitfall 5)
from openai import OpenAI

# In config/settings.py — never inline:
EMBEDDING_QUERY_INSTRUCTION = (
    "Instruct: Retrieve English accounting textbook passages "
    "relevant to the Indonesian accounting query\nQuery: "
)
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
LLM_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"

# Client usage:
client = OpenAI(
    api_key=settings.siliconflow_api_key,
    base_url=settings.siliconflow_base_url
)

def embed_document(text: str) -> list[float]:
    """Embed document chunk — NO instruction prefix."""
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=1024  # MRL truncation
    )
    return response.data[0].embedding

def embed_query(query: str) -> list[float]:
    """Embed query — ALWAYS with instruction prefix for cross-lingual retrieval."""
    prefixed = settings.embedding_query_instruction + query
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=prefixed,
        dimensions=1024
    )
    return response.data[0].embedding
```

### Pattern 5: Phase 1 LangGraph Graph (Simplified — No CRAG yet)

**What:** Phase 1 uses a simple linear LangGraph graph: preprocess → retrieve → rerank → generate. The full CRAG loop and adaptive routing are Phase 3 work. Phase 1 validates the core retrieval quality before adding the quality gate.

**When to use:** Phase 1 only. The graph is intentionally simplified — it must be designed to accept CRAG and routing nodes in Phase 3 without full rewrite.

**Example:**
```python
# Source: LangGraph official documentation
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

class RAGState(TypedDict):
    query: str
    query_embedding: Optional[list[float]]
    retrieved_docs: Optional[list[dict]]
    reranked_docs: Optional[list[dict]]
    response: Optional[str]
    citations: Optional[list[dict]]

def build_phase1_graph() -> StateGraph:
    """
    Phase 1: Simple linear RAG — no complexity routing, no CRAG.
    Designed to accept CRAG node between rerank and generate in Phase 3.
    """
    graph = StateGraph(RAGState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", END)

    return graph.compile()
```

### Anti-Patterns to Avoid

- **Running MinerU and Docling in the same process without full process restart:** VRAM fragmentation compounds across parsers. Use subprocess isolation — one subprocess per book.
- **Using `--backend auto` with MinerU on GTX 1660 Ti:** Falls back to CPU silently. Always use `--backend pipeline` explicitly. Add assert to confirm.
- **Creating Qdrant collection with only dense vectors:** Adding sparse vectors later requires collection recreation. Configure both at creation time.
- **Hardcoding the embedding instruction prefix in multiple files:** Any instruction change requires grep-and-replace across many files. Single constant in `config/settings.py`.
- **Using RecursiveCharacterTextSplitter for all content types without an element classifier first:** Tables split mid-row, formulas split from explanations. Always classify content type before splitting.
- **Skipping page marker injection:** All chunks from a multi-page section inherit the starting page number. The core value proposition — exact page citations — breaks silently.
- **Not adding `.env` to `.gitignore` before first commit:** API keys in git history is unrecoverable.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF parsing (text-based) | Custom pdfplumber table extractor | Docling 2.81.0 | 97.9% table accuracy, F1 0.968 formulas, MIT license, GPU-accelerated |
| PDF parsing (scanned) | Custom OCR pipeline | MinerU 2.7.6 | YOLO layout + UniMERNet LaTeX + paddleocr2torch — 5 model pipeline tested on accounting textbooks |
| State machine with retry logic | Custom while-loop with flags | LangGraph | Conditional edges, interrupt_before, state persistence, streaming — built-in |
| Vector similarity search + BM25 | Custom FAISS + BM25 | Qdrant with sparse vectors | Hybrid search, metadata filtering, scalar quantization, cloud persistence — all built-in |
| Cross-lingual embedding | Query translation layer + separate embedder | Qwen3-Embedding-8B via SiliconFlow | Native #1 MTEB Multilingual; translation adds latency, cost, and a failure mode |
| Parent-child chunk hierarchy | Custom chunk linking dict | LlamaIndex HierarchicalNodeParser | AutoMergingRetriever pattern built-in; StorageContext persistence included |
| Late chunking | Custom contextual embedding | Chonkie LateChunker | Correct "embed full section, derive chunk embeddings" implementation |
| Retry on API rate limit | Custom try/except with sleep | tenacity | Exponential backoff, jitter, max attempts, logging — production-grade in 3 lines |

**Key insight:** The most tempting hand-roll traps in this stack are: (1) writing a custom table extractor instead of using Docling's structure-aware output, and (2) writing a custom state machine instead of using LangGraph. Both have been done many times and the edge cases (merged cells, multi-page tables, async state transitions) are where custom code fails.

---

## Common Pitfalls

### Pitfall 1: MinerU VRAM Fragmentation (GitHub Issue #3399)

**What goes wrong:** After MinerU processes a PDF, CUDA memory from its 5-model sequential pipeline is not fully released. Over multiple books, VRAM fills with fragmented unreleased memory, causing OOM on book 3-5 despite previous successes.

**Why it happens:** PyTorch's memory allocator caches freed memory by default. Fragmentation accumulates when blocks of different sizes are allocated and freed across model stages. No buffer on 6 GB VRAM.

**How to avoid:** Process each book in a separate subprocess (OS reclaims VRAM on process exit). Within any subprocess, call the full cleanup after every model operation: `del model; gc.collect(); torch.cuda.empty_cache(); torch.cuda.synchronize()`. Set `PYTORCH_CUDA_ALLOC_CONF='max_split_size_mb:512,expandable_segments:True'` before importing torch.

**Warning signs:** OOM errors start on book 3-5 but not book 1. `torch.cuda.memory_reserved()` climbs while `torch.cuda.memory_allocated()` is low. nvidia-smi shows VRAM as occupied after parsing completes.

### Pitfall 2: MinerU VLM Backend Silent CPU Fallback

**What goes wrong:** `--backend auto` on GTX 1660 Ti attempts VLM backends (need 8-10 GB), fails silently, falls back to CPU. Parsing takes 10-30x longer with no explicit error surfaced.

**How to avoid:** Always `--backend pipeline`. Add a startup assertion verifying the backend is `pipeline`. Monitor `nvidia-smi dmon` during first page to confirm GPU utilization is nonzero.

**Warning signs:** First page takes >30 seconds (GPU pipeline should take 1-3 seconds). nvidia-smi shows near-zero GPU utilization during parsing.

### Pitfall 3: Table Splitting Destroys Financial Data Context

**What goes wrong:** Naive RecursiveCharacterTextSplitter creates chunks with partial table rows and no column headers. A chunk starting with `| 48,500 | 47,200 | 1,300 |` is uninterpretable. Naive chunking on tables achieves only 30% accuracy vs 73.8% for structure-aware chunking (LangChain benchmark).

**How to avoid:** Element classifier detects Markdown tables BEFORE any text splitting. Tables ≤20 rows: keep as single atomic chunk (up to 1,024 tokens). Tables >20 rows: split per logical row group with column headers repeated at the start of every child chunk.

**Warning signs:** Test queries on table content return chunks starting with `|` delimiters but no recognizable headers. Manual inspection shows orphaned rows without column context.

### Pitfall 4: Citation Page Numbers Lost During Chunk Splitting

**What goes wrong:** LangChain TextSplitter and LlamaIndex HierarchicalNodeParser propagate parent metadata to children by copying the parent dict. This copies the *starting* page number. Child chunks from multi-page sections carry the wrong page number.

**How to avoid:** Inject `<!-- PAGE_START:N -->` markers into the Markdown text at parse time. After chunking, parse markers within each chunk to determine actual page_start and page_end. Strip markers before embedding.

**Warning signs:** All chunks from the same chapter share identical page numbers despite spanning 20+ pages. Manual spot-check shows page numbers off by 2-5 pages.

### Pitfall 5: Cross-Lingual Recall Degrades Without Instruction Prefix

**What goes wrong:** Qwen3-Embedding-8B cross-lingual performance degrades 1-5% without the task instruction prefix on queries. For domain-specific Indonesian queries against English textbooks this gap compounds.

**How to avoid:** Always wrap query embeddings (NOT document embeddings) with: `"Instruct: Retrieve English accounting textbook passages relevant to the Indonesian accounting query\nQuery: {user_query}"`. Store as constant in `config/settings.py`.

**Warning signs:** Correct retrieval sometimes and fails other times for the same query type. Semantic similarity for correct chunks hovers near threshold rather than clearly above it.

### Pitfall 6: SiliconFlow 50 RPD Default Limit Blocks Ingestion

**What goes wrong:** Default SiliconFlow accounts have 50 RPD. Embedding ~120,000 chunks requires thousands of API calls. The ingestion job will hit the rate limit within minutes and fail without retry logic.

**How to avoid:** Before any ingestion, purchase credits ($10+ triggers tier upgrade to 1,000 RPD). Implement tenacity retry on all SiliconFlow calls. Store ingestion checkpoints after every successful batch so rate limit interruptions do not restart from zero.

**Warning signs:** HTTP 429 within first 10 minutes of ingestion. Long unexplained gaps in embedding progress logs.

### Pitfall 7: Qdrant Free Tier Auto-Suspension

**What goes wrong:** Qdrant Cloud free tier auto-suspends after 1 week of inactivity and deletes the cluster after 4 weeks. The first query after suspension fails with a connection error. After 4 weeks, all vectors are lost.

**How to avoid:** Implement a health-check ping in the application startup sequence. Save all chunk texts and metadata to local SQLite before uploading to Qdrant — re-embedding costs ~$4-8 and is survivable only if chunk data is preserved locally.

**Warning signs:** Connection errors on first query after a break in usage.

---

## Code Examples

Verified patterns from the project's validated research:

### MinerU CLI Invocation (pipeline backend, correct flags)

```python
# Source: MinerU 2.7.6 docs + PITFALLS.md (Pitfall 2)
import subprocess
import os

env = os.environ.copy()
env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512,expandable_segments:True"

subprocess.run([
    "mineru",
    "--input", str(pdf_path),
    "--output", str(output_dir),
    "--backend", "pipeline",   # ALWAYS explicit — never "auto" on GTX 1660 Ti
    "--vram", "6",             # 6 GB VRAM limit
    "--device", "cuda",
], env=env, check=True)
```

### Docling Invocation (text-based PDFs, GTX 1660 Ti config)

```python
# Source: Docling 2.81.0 documentation + STACK.md
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice
)
from docling.backend.pypdfium2_backend import PyPdfium2DocumentBackend

pipeline_options = PdfPipelineOptions()
pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=4,
    device=AcceleratorDevice.CUDA
)
pipeline_options.ocr_options.use_gpu = True
# batch_size=4 tested within 6 GB VRAM for Granite-Docling-258M
pipeline_options.table_structure_options.mode = "accurate"

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfPipelineOptions(
            accelerator_options=pipeline_options.accelerator_options,
        )
    }
)
result = converter.convert(str(pdf_path))
markdown_text = result.document.export_to_markdown()
```

### PyMuPDF Triage Scan (text-based vs scanned)

```python
# Source: PyMuPDF 1.27.2.2 documentation + STACK.md
import pymupdf

def classify_pdf(pdf_path: str) -> str:
    """Returns 'text-based' or 'scanned' by sampling text density."""
    doc = pymupdf.open(pdf_path)
    sample_pages = min(5, len(doc))
    total_chars = 0
    for i in range(sample_pages):
        page = doc[i]
        total_chars += len(page.get_text())
    avg_chars_per_page = total_chars / sample_pages
    # Heuristic: text-based PDFs have >100 chars/page on average
    return "text-based" if avg_chars_per_page > 100 else "scanned"
```

### Table Chunk with Repeated Headers

```python
# Source: ARCHITECTURE.md + PITFALLS.md (Pitfall 3)
def split_large_table(markdown_table: str, max_rows: int = 20) -> list[str]:
    """
    Split a large Markdown table into chunks, repeating column headers
    at the start of each child chunk.
    """
    lines = markdown_table.strip().split("\n")
    if len(lines) < 3:
        return [markdown_table]

    header_line = lines[0]       # | Col1 | Col2 | ...
    separator_line = lines[1]    # | --- | --- | ...
    data_rows = lines[2:]

    chunks = []
    for i in range(0, len(data_rows), max_rows):
        row_group = data_rows[i:i + max_rows]
        chunk = "\n".join([header_line, separator_line] + row_group)
        chunks.append(chunk)
    return chunks
```

### Tenacity Retry Wrapper for SiliconFlow API

```python
# Source: tenacity documentation + PITFALLS.md (Pitfall 7)
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
import logging
import httpx

logger = logging.getLogger(__name__)

@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, Exception)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=60, max=300),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def call_siliconflow_embedding(client, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with automatic retry on rate limit."""
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=1024
    )
    return [item.embedding for item in response.data]
```

### Streamlit Chat UI (minimal Phase 1 structure)

```python
# Source: Streamlit documentation
import streamlit as st
from src.agents.graph import build_phase1_graph

st.title("Trusty RAG Akmen")
st.caption("Asisten akuntansi biaya dan manajemen berbasis textbook")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "graph" not in st.session_state:
    st.session_state.graph = build_phase1_graph()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ketik pertanyaan akuntansi Anda..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Mencari referensi..."):
            result = st.session_state.graph.invoke({"query": prompt})
            response = result["response"]
            citations = result.get("citations", [])

        st.markdown(response)

        if citations:
            with st.expander("Sumber Referensi"):
                for cit in citations:
                    st.write(
                        f"**{cit['book_title']}**, {cit['chapter']}, "
                        f"hal. {cit['page_start']}–{cit['page_end']}"
                    )

    st.session_state.messages.append({"role": "assistant", "content": response})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PaddlePaddle dependency for MinerU OCR | paddleocr2torch (pure PyTorch) | MinerU 2.x | Eliminates PaddlePaddle install complexity; single PyTorch dependency |
| SmolDocling VLM in Docling | Granite-Docling-258M (IBM) | Docling 2.x / March 2025 | Better accuracy, smaller model (258M), TEDS 0.97 table structure |
| LangChain as orchestrator | LangGraph as orchestrator, LangChain as toolbox | 2024 (LangGraph GA) | Explicit state machine semantics; CRAG loops are first-class citizens |
| LlamaIndex as primary RAG framework | LlamaIndex for HierarchicalNodeParser only | 2025 community consensus | Mixing LlamaIndex workflows with LangGraph creates unclear state ownership |
| LangSmith for LangGraph monitoring | Langfuse (MIT, self-hostable) | Project decision (pre-phase) | Accounting data privacy; self-hosting option; RAG-specific scoring |

**Deprecated/outdated:**
- `langgraph-supervisor` library: LangChain now recommends `create_react_agent` with tool binding for most use cases — lower overhead, simpler setup
- `cu128` PyTorch on GTX 1660 Ti: CC 7.5 is the minimum for cu128 and cu126 provides a documented safety margin
- LightRAG with Qdrant as internal storage: Built-in nano-vectordb is correct; Qdrant routing for LightRAG creates configuration conflicts at this scale

---

## Open Questions

1. **MinerU subprocess isolation for Windows (win32 shell)**
   - What we know: Subprocess isolation is the documented solution for VRAM fragmentation. The project runs on Windows 11 (based on env context).
   - What's unclear: Windows subprocess spawning behavior differs from Linux (no `fork`, only `spawn`). The `spawn` method on Windows requires module-level code to be protected with `if __name__ == "__main__"`.
   - Recommendation: Wrap all subprocess ingestion entry points with `if __name__ == "__main__"` guard. Test subprocess isolation on the actual Windows machine before committing to the ingestion architecture.

2. **SiliconFlow tier upgrade confirmation**
   - What we know: $10+ credit purchase should trigger 1,000 RPD. Documented in SiliconFlow rate limit docs.
   - What's unclear: Whether 1,000 RPD applies separately to each model (embedding, generation, reranking) or is shared across all models.
   - Recommendation: Purchase credits and verify the actual tier in the SiliconFlow dashboard before scheduling any large ingestion batch. Contact support if needed.

3. **Qdrant scalar quantization recall tradeoff at 1,024 dimensions**
   - What we know: Scalar quantization reduces memory 4x. Research estimates 500K-800K chunks in the free tier with quantization.
   - What's unclear: Exact recall degradation at 1,024 dimensions with INT8 quantization for this specific domain. Not empirically measured.
   - Recommendation: After first 5-book ingestion, benchmark recall on 20 test queries with and without quantization. If recall drops more than 3%, evaluate whether the free tier capacity trade-off is acceptable or if storage upgrade is needed.

4. **Bilingual glossary initial scope**
   - What we know: 200-500 EN↔ID accounting terms needed. Terms go into system prompt and BM25 index entries.
   - What's unclear: Which terms to prioritize first. Starting list is unspecified.
   - Recommendation: Bootstrap from the textbook table of contents terms (Horngren, Garrison, Hansen & Mowen) + standard IMA/CIMA term glossaries. Minimum viable list: ~100 terms covering cost types, costing methods, variance analysis terms, and common BEP/overhead calculation terminology.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed — Wave 0 gap) |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 |
| Quick run command | `pytest tests/ -x -q --timeout=30` |
| Full suite command | `pytest tests/ -v --timeout=120` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | Docling parses a text-based PDF and produces Markdown with table structure | unit | `pytest tests/test_parsing.py::test_docling_text_pdf -x` | Wave 0 |
| INGEST-02 | MinerU parses a scanned PDF with `--backend pipeline` and does not fall back to CPU | unit | `pytest tests/test_parsing.py::test_mineru_pipeline_backend -x` | Wave 0 |
| INGEST-03 | PyMuPDF triage correctly classifies text-based vs scanned sample PDFs | unit | `pytest tests/test_parsing.py::test_pdf_classifier -x` | Wave 0 |
| INGEST-04 | VRAM is fully released after MinerU subprocess exits (memory_reserved == 0) | integration | `pytest tests/test_parsing.py::test_vram_cleanup -x` | Wave 0 |
| INGEST-05 | VLM captioner returns a non-empty text description for a diagram image | unit | `pytest tests/test_parsing.py::test_vlm_captioner -x` | Wave 0 |
| CHUNK-01 | Element classifier returns correct type for narrative, table, formula, diagram, example inputs | unit | `pytest tests/test_chunking.py::test_element_classifier -x` | Wave 0 |
| CHUNK-03 | Large tables are split with column headers repeated in every child chunk | unit | `pytest tests/test_chunking.py::test_table_header_repeat -x` | Wave 0 |
| CHUNK-04 | HierarchicalNodeParser produces parent and child chunks with correct token size ranges | unit | `pytest tests/test_chunking.py::test_hierarchy_builder -x` | Wave 0 |
| CHUNK-06 | Every chunk has all required metadata fields: book_title, chapter, section_path, content_type, page_number | unit | `pytest tests/test_chunking.py::test_metadata_completeness -x` | Wave 0 |
| CHUNK-08 | page_start and page_end in chunk metadata match actual PDF pages (manual spot-check on 10 chunks) | manual | N/A — manual review of 10 chunks against source PDF | N/A |
| INDEX-01 | Chunks are uploaded to Qdrant with correct vector dimensions (1024) and scalar quantization | integration | `pytest tests/test_retrieval.py::test_qdrant_upload -x` | Wave 0 |
| INDEX-02 | Qdrant collection has both dense and sparse vector configs; hybrid search returns results | integration | `pytest tests/test_retrieval.py::test_hybrid_search -x` | Wave 0 |
| INDEX-05 | Query embedding with instruction prefix produces higher similarity score than without prefix for correct doc | unit | `pytest tests/test_retrieval.py::test_instruction_prefix_recall -x` | Wave 0 |
| RETR-01 | Hybrid search (dense + BM25) on a known query retrieves the expected chunk in top-5 | integration | `pytest tests/test_retrieval.py::test_hybrid_retrieval -x` | Wave 0 |
| RETR-02 | Reranker reorders top-k=20 candidates and returns top-k=5 with correct chunk at rank 1 | integration | `pytest tests/test_retrieval.py::test_reranker -x` | Wave 0 |
| LANG-01 | Indonesian query "apa itu break-even point" retrieves the BEP explanation chunk from English textbook | e2e | `pytest tests/test_e2e.py::test_cross_lingual_retrieval -x` | Wave 0 |
| LANG-03 | Generated response is in Indonesian prose with English technical terms in parentheses | unit | `pytest tests/test_e2e.py::test_bilingual_output_format -x` | Wave 0 |
| GEN-01 | Every generated response contains citation with book_title, chapter, page range | e2e | `pytest tests/test_e2e.py::test_citation_present -x` | Wave 0 |
| UI-01 | Streamlit app starts and accepts a query without error | smoke | `pytest tests/test_e2e.py::test_streamlit_smoke -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q --timeout=30 -k "not test_e2e"`
- **Per wave merge:** `pytest tests/ -v --timeout=120`
- **Phase gate:** Full suite green + manual citation spot-check (10 chunks, 3 textbooks) before `/gsd:verify-work`

### Wave 0 Gaps

All test files must be created in Wave 0 (setup wave) before implementation begins:

- [ ] `tests/test_parsing.py` — covers INGEST-01 through INGEST-05
- [ ] `tests/test_chunking.py` — covers CHUNK-01 through CHUNK-08
- [ ] `tests/test_retrieval.py` — covers INDEX-01, INDEX-02, INDEX-05, RETR-01, RETR-02
- [ ] `tests/test_e2e.py` — covers LANG-01, LANG-03, GEN-01, UI-01
- [ ] `tests/conftest.py` — shared fixtures (sample PDF fixtures, mock SiliconFlow client, Qdrant test collection)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — test configuration
- [ ] Framework install: `pip install pytest pytest-timeout` — not yet in project deps

---

## Sources

### Primary (HIGH confidence)

- `.planning/research/STACK.md` — all package versions verified via PyPI on 2026-03-22; technology choices with confidence assessments
- `.planning/research/ARCHITECTURE.md` — system architecture diagram, component responsibilities, data flow, project structure
- `.planning/research/PITFALLS.md` — 8 critical pitfalls with verified sources (GitHub issues, official docs, peer-reviewed benchmarks)
- `.planning/research/FEATURES.md` — feature dependency graph, MVP definition, feature prioritization matrix
- `.planning/research/SUMMARY.md` — executive summary consolidating all research findings
- `Trusty_RAG_Akmen.md` — master technical specification (524 lines) — hybrid chunking pipeline, parsing pipeline, architecture diagrams
- [MinerU VRAM issue #3399](https://github.com/opendatalab/MinerU/issues/3399) — confirmed VRAM retention bug
- [Qwen3 Embedding official blog](https://qwenlm.github.io/blog/qwen3-embedding/) — MTEB #1 rank, instruction prefix format, MRL truncation
- [LangGraph PyPI + Changelog](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available) — 1.1.3 production status
- [Qdrant Pricing](https://qdrant.tech/pricing/) — free tier limits, suspension/deletion policy, scalar quantization
- [Docling GitHub](https://github.com/docling-project/docling) — 97.9% table accuracy, Granite-Docling model, MIT license
- [SiliconFlow Rate Limits](https://docs.siliconflow.cn/en/userguide/rate-limits/rate-limit-and-upgradation) — 50 RPD default, tier upgrade policy

### Secondary (MEDIUM confidence)

- [Benchmarking RAG on tables (LangChain blog)](https://blog.langchain.com/benchmarking-rag-on-tables/) — 30% vs 73.8% table chunking accuracy
- [SiliconFlow Models pricing](https://www.siliconflow.com/models) — Qwen3 model catalog and pricing (USD conversion approximate)
- [ArtificialAnalysis Qwen3-30B-A3B-2507](https://artificialanalysis.ai/models/qwen3-30b-a3b-2507) — 86.1 tok/s throughput

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via PyPI records from project STACK.md (2026-03-22)
- Architecture: HIGH — project has detailed prior architecture research; offline/online separation is universal production practice; all major patterns validated
- Pitfalls: HIGH — all critical pitfalls sourced from official GitHub issues, production documentation, or peer-reviewed benchmarks; no speculation
- Code examples: MEDIUM-HIGH — patterns derived from official documentation and verified research; not yet tested against actual textbook corpus

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (30 days; stack is relatively stable; SiliconFlow pricing and tier limits may change)

**Critical pre-implementation actions before ingestion starts:**
1. Purchase SiliconFlow credits ($10+) to upgrade RPD tier — verify in dashboard before scheduling any batch
2. Test subprocess isolation on Windows 11 (`multiprocessing.set_start_method('spawn')` default on Windows)
3. Add `.env` to `.gitignore` before first `git commit`
4. Create Qdrant collection with BOTH dense and sparse vector config in the first Wave
