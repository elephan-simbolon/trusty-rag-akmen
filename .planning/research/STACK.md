# Stack Research

**Domain:** AI-powered RAG system for cost & management accounting textbooks (Indonesian-English bilingual)
**Researched:** 2026-03-22
**Confidence:** HIGH (core stack verified via PyPI + official docs), MEDIUM (pricing figures, GPU compatibility)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LangGraph | 1.1.3 | Agentic orchestration, CRAG loops, state machines | Production-stable (released 2026-03-18). The standard for stateful, cyclical agent workflows in Python as of 2025-2026. Native support for CRAG patterns, interrupt_before for human-in-the-loop, and node-level caching. No serious alternative for explicit state machine RAG. Requires Python 3.10+. |
| LangChain | 1.2.13 | Tool wrappers, retriever abstractions, TextSplitter | Production-stable (released 2026-03-19). Provides @tool decorators, Qdrant integrations, and TextSplitter that LangGraph nodes call. Do not use it as orchestrator — use LangGraph for that. LangChain is the toolbox; LangGraph is the engine. |
| LightRAG (lightrag-hku) | 1.4.11 | Knowledge graph extraction, graph-based retrieval | Released 2026-03-20. EMNLP 2025 paper. August 2025 update added reranker support. September 2025 update added specific optimizations for Qwen3-30B-A3B. Provides local/naive/hybrid/mix retrieval modes out of the box. Use built-in nano-vectordb for LightRAG's own storage; do not route it through Qdrant to avoid config conflicts. |
| Qdrant (qdrant-client) | 1.17.1 | Primary vector database for dense + sparse retrieval | Released 2026-03-13. Cloud Free Tier: 1 GB RAM, 4 GB disk, ~1M vectors at 768-dim. Scalar quantization reduces memory by 4x. With 1,024-dim Qwen3 embeddings via MRL truncation, estimate ~500K-800K chunks in free tier — sufficient for 20-30 textbooks. Auto-suspension after 1 week inactivity requires periodic ping. |
| Qwen3-30B-A3B-Instruct-2507 (via SiliconFlow) | 2507 release | LLM generation, routing, tool-calling | MoE architecture: 30.5B total params, only 3.3B active at inference. ~0.70 CNY input / ~2.80 CNY output per 1M tokens on SiliconFlow (approximately $0.10/$0.39 USD at current rates). Supports extended thinking mode for Complex/Calculation queries. 86.1 tokens/sec. Strong Chinese/Indonesian language capability inherited from base Qwen3. |
| Qwen3-Embedding-8B (via SiliconFlow) | latest | Multilingual dense embeddings | Rank #1 MTEB Multilingual (score 70.58, as of June 2025). 4096-dim native, use 1024-dim via MRL truncation to fit Qdrant free tier. Handles Indonesian query → English textbook retrieval natively with no translation layer. ~$0.04/1M tokens on SiliconFlow. Context window 32K. |
| Qwen3-Reranker-8B (via SiliconFlow) | latest | Cross-encoder reranking of retrieved candidates | ~$0.04/1M tokens. Top performer on MMTEB-R (72.94), CMTEB-R (77.45). Use after initial retrieval to rerank top-k=20 candidates to final top-k=5. Critical for cross-lingual retrieval quality (Indonesian query → English docs). |
| MinerU (mineru) | 2.7.6 | Primary PDF parser for scanned/complex textbooks | Released 2026-02-06. Uses YOLO + PaddleOCR + TableMaster. Handles scanned PDFs, complex layouts, LaTeX formulas. GPU flag `--vram 6` limits loading to fit GTX 1660 Ti. Sequential model loading by design: safe for 6 GB VRAM. Use for scanned/image-heavy textbook PDFs. |
| Docling | 2.81.0 | Secondary PDF parser for text-based PDFs | Released 2026-03-20. IBM Research / LF AI & Data Foundation. 97.9% accuracy on complex table extraction. MIT license. Use `batch_size=4` for GTX 1660 Ti. Granite-Docling (258M) model replaces SmolDocling as of March 2025. Faster than MinerU on text-native PDFs, better at table structure. |

### Chunking and Indexing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| LlamaIndex Core (llama-index-core) | 0.14.18 | HierarchicalNodeParser for parent-child chunk hierarchy | Released 2026-03-16. Use exclusively for HierarchicalNodeParser + parent-child storage. Do NOT use LlamaIndex as the orchestration framework — LangGraph owns that. Pairs with AutoMergingRetriever pattern where majority of child chunks triggers parent retrieval for broader context. |
| Chonkie | 1.6.1 | Late chunking (LateChunker) and semantic chunking | Released 2026-03-18. Install with `pip install chonkie[semantic]` to get LateChunker. LateChunker embeds the full document first, then derives contextually-enriched chunk embeddings — superior to naive chunk-then-embed for long accounting textbook passages. Default install is lightweight (~21 MB). |
| PyMuPDF (pymupdf) | 1.27.2.2 | Fast triage scan of PDFs before routing to MinerU/Docling | Released 2026-03-19. Use as "cheap scan" step: check if PDF is text-native (use Docling) or scanned/complex (use MinerU). Also useful for page count, metadata extraction, formula detection heuristics. Do not use as primary extractor — it lacks table structure and formula handling. |

### Monitoring and Observability

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Langfuse | latest | LLM observability, trace logging, RAG scoring | Open source MIT license. Self-hostable. Framework-agnostic via OpenTelemetry. Preferred over LangSmith for this project because: (1) SiliconFlow is not a LangChain-native provider, reducing LangSmith integration advantage; (2) Langfuse supports RAG-specific scoring (context relevance, groundedness); (3) full self-hosting option preserves accounting data privacy. |
| LangSmith | latest | Alternative: deep LangGraph integration, managed | Use only if Langfuse integration proves complex. LangSmith has native LangGraph tracing but is closed-source SaaS — no self-hosting on free tier. For a personal accounting tool with sensitive client data, Langfuse's self-hosting is preferable. |

### Configuration and Infrastructure

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x | Type-safe configuration from .env files | Standard for Python project config in 2025. Inherit from BaseSettings for all settings.py. Supports nested config, SecretStr for API keys, environment variable override. Eliminates boilerplate parsing code. |
| Streamlit | latest | Chat UI for query interface | Mature, fast to build, good for data-centric display (tables, citations, calculations). Preferred for v1 because accounting responses involve structured citation display. |
| Chainlit | latest | Alternative chat UI | Better for pure conversational flow; has async-first design. Note: as of May 2025, original team stepped back; now community-maintained. Recommend Streamlit for v1 given Chainlit's governance uncertainty. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| PyTorch (cu126 wheels) | GPU computation for MinerU and Docling | GTX 1660 Ti is Compute Capability 7.5 — minimum supported by cu128. Use cu126 for safety margin. Install: `pip install torch --index-url https://download.pytorch.org/whl/cu126` |
| pyproject.toml + uv | Dependency management | uv is the 2025 standard for Python project management: 10-100x faster than pip, lockfile support, virtual env management. Replace pip + requirements.txt entirely. |
| Docker / docker-compose | Container orchestration | Single Dockerfile for the app server. docker-compose for dev: app + any local services. Railway/Render/fly.io all accept Docker deployments. |

---

## Installation

```bash
# Core RAG stack
pip install langgraph==1.1.3 langchain==1.2.13 lightrag-hku==1.4.11 qdrant-client==1.17.1

# Parsing pipeline
pip install mineru==2.7.6 docling==2.81.0 pymupdf==1.27.2.2

# Chunking
pip install llama-index-core==0.14.18 "chonkie[semantic]==1.6.1"

# Configuration and UI
pip install pydantic-settings streamlit

# Monitoring (choose one; Langfuse recommended)
pip install langfuse
# OR: pip install langsmith

# PyTorch for local GPU (GTX 1660 Ti cu126)
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

Using uv (recommended):
```bash
uv init trusty-rag-akmen
uv add langgraph langchain lightrag-hku qdrant-client
uv add mineru docling pymupdf
uv add llama-index-core "chonkie[semantic]"
uv add pydantic-settings streamlit langfuse
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| LangGraph | LlamaIndex Workflows | If the entire pipeline is already LlamaIndex-native and you have no need for explicit state machine semantics. LlamaIndex Workflows (0.14.x) have improved but LangGraph has wider production adoption and better CRAG pattern support. |
| LangGraph | CrewAI | For multi-agent collaboration tasks (multiple autonomous agents with roles). Overkill for this project — single-user, single-session RAG with deterministic routing. |
| LangGraph | AutoGen | Microsoft framework; good for multi-agent conversation. Not a fit for deterministic graph-based RAG with explicit CRAG loops. |
| Qdrant Cloud Free | Pinecone Free | Pinecone's free tier: 2M vectors but 1 index, serverless with cold-start latency. Qdrant free tier has 1 GB RAM limit but no cold-start and better scalar quantization. For 20-30 textbooks, Qdrant free tier is sufficient. |
| Qdrant Cloud Free | Weaviate Cloud Free | Weaviate's free: 1 sandbox, auto-pauses. Less mature scalar quantization. Qdrant has better Rust-native performance and first-class Python client. |
| Qdrant Cloud Free | ChromaDB (local) | Use ChromaDB only if you want zero cloud dependency and don't care about horizontal scale. Qdrant Cloud is better for eventual productization. |
| MinerU (primary) | Unstructured.io | Unstructured is excellent but more expensive at scale. MinerU is free/open-source, GPU-optimized, handles formulas via StructEqTable. For a local ingestion pipeline on GTX 1660 Ti, MinerU is the right choice. |
| Docling (secondary) | LlamaParse | LlamaParse (cloud API, paid after 1000 pages/day) gives excellent results but adds API cost and data privacy concerns for accounting textbooks. Docling (local, MIT, 97.9% table accuracy) is preferable for this use case. |
| Qwen3-30B-A3B (via SiliconFlow) | GPT-4o (OpenAI) | GPT-4o costs ~$5/$15 per 1M tokens vs ~$0.10/$0.39 for Qwen3-30B-A3B-2507. For 500 queries/day budget of $8-35/month, GPT-4o is 30-50x more expensive. Qwen3's multilingual capability is comparable for Indonesian/English tasks. |
| Qwen3-Embedding-8B | text-embedding-3-large (OpenAI) | OpenAI embedding is $0.13/1M tokens vs $0.04/1M for Qwen3-Embedding-8B. More importantly, Qwen3-Embedding-8B outperforms on MTEB Multilingual (#1 rank, score 70.58) which is the critical benchmark for Indonesian↔English retrieval. |
| Langfuse | LangSmith | Use LangSmith if you want zero-config LangGraph tracing and are comfortable with SaaS data storage. LangSmith's native LangGraph integration is genuinely excellent, but Langfuse's self-hosting and MIT license are preferable for a personal accounting tool. |
| Streamlit | Chainlit | Use Chainlit if conversational UX is the primary concern and community-maintenance governance is acceptable. Streamlit is preferred for v1 because citation display (table + page references) benefits from Streamlit's data-centric display components. |
| uv | pip + requirements.txt | Use pip only if uv is unavailable in the deployment environment. Railway, Render, and fly.io all support uv natively. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Microsoft GraphRAG (msft/graphrag) | Requires GPT-4 class models for entity extraction; cost at scale is prohibitive ($100+ for full corpus ingestion). Complex setup, slow iteration. | LightRAG — simpler API, self-contained, compatible with Qwen3 via SiliconFlow, September 2025 update specifically optimized for Qwen3-30B-A3B. |
| LlamaIndex as primary orchestrator | Mixing LlamaIndex Workflows with LangGraph creates dependency conflicts and unclear ownership of graph state. LlamaIndex's strength is document parsing/indexing, not stateful agent orchestration. | Use LlamaIndex only for HierarchicalNodeParser; route orchestration through LangGraph. |
| cu128 PyTorch wheels | GTX 1660 Ti (CC 7.5) is the minimum compatibility threshold for cu128. Edge of support means potential silent failures in future PyTorch releases. | cu126 wheels provide stable support for CC 7.5 with confirmed longevity. |
| Local LLM inference (Ollama / vLLM) | GTX 1660 Ti 6 GB VRAM cannot run 8B+ models at useful throughput. Qwen3-Embedding-8B alone needs ~16 GB VRAM at FP16. Inference latency would make the tool unusable. Embedding a 20-30 book corpus locally would take ~33 days vs 4-12 hours via API. | SiliconFlow API for all embedding, reranking, and LLM inference. GPU is for PDF parsing only (MinerU/Docling). |
| OpenAI Assistants API / Threads API | Vendor lock-in, 30-day thread expiry, opaque retrieval, no custom chunking control. Incompatible with the hybrid 7-step chunking requirement. | LangGraph + Qdrant for full control over retrieval pipeline. |
| sentence-transformers for embedding | Popular but its multilingual models do not match Qwen3-Embedding-8B on MTEB Multilingual. Local inference also requires GPU VRAM budget better saved for parsing. | Qwen3-Embedding-8B via SiliconFlow API. |
| Naive RAG (single retrieve → generate) | Unsuitable for cross-textbook synthesis and calculation tasks that require multi-hop reasoning. No quality gate means hallucinations pass through unchecked. | Agentic RAG with CRAG quality gate (CORRECT/AMBIGUOUS/INCORRECT grading) in LangGraph. |
| Pinecone as primary vector store | Cold-start latency on serverless tier; index limit on free tier; no scalar quantization as mature as Qdrant. | Qdrant Cloud with scalar quantization. |

---

## Stack Patterns by Variant

**If query is Simple (definition, single-concept lookup):**
- Router classifies as Simple
- Single vector retrieval from Qdrant (top-k=5)
- Qwen3-Reranker-8B on candidates
- Direct generation — 2 API calls total

**If query is Complex (cross-textbook synthesis, compare costing methods):**
- Router classifies as Complex
- Parallel retrieval: Qdrant vector search + LightRAG hybrid/mix mode
- CRAG grading loop (up to 2 reformulations)
- Qwen3-30B-A3B in extended thinking mode if needed
- Multi-source citation builder — 4-6 API calls total

**If query is Calculation (BEP, variance analysis, overhead rate):**
- Router classifies as Calculation
- Retrieve formula/definition chunks + example chunks
- Qwen3-30B-A3B performs structured step-by-step calculation
- Mandatory disclaimer appended: "verifikasi hasil dengan sumber resmi"
- 3-5 API calls total

**If ingestion pipeline is running (offline batch):**
- PyMuPDF triage scan → route to MinerU or Docling
- MinerU: `--vram 6` flag, sequential model loading
- Docling: `batch_size=4` for GTX 1660 Ti
- HierarchicalNodeParser: parent (1024 tokens) → child (256 tokens)
- Chonkie LateChunker for contextual embedding
- SiliconFlow embedding API for batch embedding (not local)

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| LangGraph 1.1.3 | LangChain 1.2.13 | Same release cadence; always upgrade together. |
| LightRAG 1.4.11 | LangChain 1.2.13 | LightRAG is standalone; LangChain integration via custom tool wrapper. |
| MinerU 2.7.6 | PyTorch cu126 + CUDA 12.6 | Tested with cu126 wheels. Do NOT use cu128 on GTX 1660 Ti (CC 7.5 is minimum). |
| Docling 2.81.0 | PyTorch cu126 | Granite-Docling model requires PyTorch. Batch_size=4 tested within 6 GB VRAM. |
| llama-index-core 0.14.18 | LangChain 1.2.13 | Use only for HierarchicalNodeParser. Avoid mixing LlamaIndex query engines with LangGraph graph execution. |
| Chonkie 1.6.1 [semantic] | llama-index-core 0.14.18 | Chonkie's LlamaIndex integration via ChonkieNodeParser. Compatible with current versions. |
| qdrant-client 1.17.1 | LangChain 1.2.13 | LangChain Qdrant integration is stable via `langchain-qdrant` package. |
| pydantic-settings 2.x | Pydantic v2 | Do NOT use pydantic-settings 1.x (incompatible with Pydantic v2 BaseModel). |

---

## Validated Design Decisions

The following decisions from PROJECT.md were validated by research:

**CONFIRMED: Qwen3-Embedding-8B cross-lingual approach**
MTEB Multilingual #1 (score 70.58, June 2025) is verified via official Qwen blog. Cross-lingual Indonesian↔English retrieval without a translation layer is sound. Confidence: HIGH.

**CONFIRMED: MinerU primary + Docling secondary parser split**
MinerU 2.7.6 has `--vram 6` GPU flag confirmed for 6 GB VRAM constraint. Docling 2.81.0 (97.9% table accuracy) confirmed for text-native PDFs. Complementary split is the correct architecture. Confidence: HIGH.

**CONFIRMED: LightRAG built-in nano-vectordb (not Qdrant) for graph storage**
LightRAG 1.4.11 is self-contained and the September 2025 update specifically added Qwen3-30B-A3B entity extraction support. Using Qdrant for LightRAG storage introduces config complexity with no retrieval benefit at this scale. Confidence: HIGH.

**CONFIRMED: cu126 over cu128 PyTorch wheels**
GTX 1660 Ti CC 7.5 is documented minimum for cu128. cu126 provides explicit safety margin. Confidence: HIGH.

**NEEDS MONITORING: Chainlit governance**
As of May 2025, original Chainlit team stepped back; project is community-maintained. Streamlit is the safer choice for v1. If Chainlit stabilizes under new governance, reconsider for v2 conversational UX. Confidence: MEDIUM.

**NEEDS MONITORING: Qdrant free tier inactivity suspension**
Qdrant Cloud free tier auto-suspends after 1 week of inactivity and deletes after 4 weeks. For a personal tool with irregular usage, implement a periodic "ping" (weekly keepalive request) to prevent suspension. Confidence: HIGH (documented behavior).

---

## Sources

- PyPI langgraph — verified version 1.1.3, released 2026-03-18
- PyPI langchain — verified version 1.2.13, released 2026-03-19
- PyPI lightrag-hku — verified version 1.4.11, released 2026-03-20
- PyPI qdrant-client — verified version 1.17.1, released 2026-03-13
- PyPI mineru — verified version 2.7.6, released 2026-02-06
- PyPI docling — verified version 2.81.0, released 2026-03-20
- PyPI llama-index-core — verified version 0.14.18, released 2026-03-16
- PyPI chonkie — verified version 1.6.1, released 2026-03-18
- PyPI pymupdf — verified version 1.27.2.2, released 2026-03-19
- [Qwen3 Embedding official blog](https://qwenlm.github.io/blog/qwen3-embedding/) — MTEB #1 rank, 70.58 score, language support, MRL truncation — HIGH confidence
- [LightRAG GitHub HKUDS](https://github.com/HKUDS/LightRAG) — EMNLP 2025, Qwen3 optimization confirmed — HIGH confidence
- [Qdrant Pricing](https://qdrant.tech/pricing/) — free tier limits (1 GB RAM, 4 GB disk, 1M vectors at 768-dim, inactivity policy) — HIGH confidence
- [SiliconFlow Models](https://www.siliconflow.com/models) — Qwen3 model catalog, pricing in CNY — MEDIUM confidence (USD conversion approximate)
- [LangGraph PyPI](https://pypi.org/project/langgraph/) + [Changelog](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available) — version, production status — HIGH confidence
- [Docling GitHub](https://github.com/docling-project/docling) — IBM/LF AI & Data, table accuracy benchmark — HIGH confidence
- [Chonkie GitHub](https://github.com/chonkie-inc/chonkie) — LateChunker availability in `[semantic]` extras — HIGH confidence
- [Langfuse vs LangSmith comparison, ZenML Blog](https://www.zenml.io/blog/langfuse-vs-langsmith) — OSS status, governance, RAG scoring — MEDIUM confidence
- WebSearch "Chainlit governance 2025" — community-maintained since May 2025 — MEDIUM confidence (single-source finding)
- [Qwen3-30B-A3B HuggingFace](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507) — MoE params (30.5B total, 3.3B active) — HIGH confidence
- [ArtificialAnalysis Qwen3-30B-A3B-2507](https://artificialanalysis.ai/models/qwen3-30b-a3b-2507) — throughput 86.1 tok/s — MEDIUM confidence

---

*Stack research for: AI-powered RAG system, cost & management accounting, bilingual Indonesian/English*
*Researched: 2026-03-22*
