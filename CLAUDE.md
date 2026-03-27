# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Trusty RAG Akmen** — AI-powered cost & management accounting (Akuntansi Biaya dan Manajemen) assistant using Retrieval-Augmented Generation. Targets Indonesian accounting professionals with bilingual (Indonesian prose + English technical terms) responses. Built on Qwen3 models via SiliconFlow API, Qdrant vector DB, and LightRAG knowledge graph.

## Commands

```bash
# Install dependencies (uses uv with PyTorch CUDA 12.6 index)
uv sync --dev

# Run all tests (30s timeout per test, quiet output)
uv run pytest

# Run a single test file
uv run pytest tests/test_chunking.py

# Run tests by marker
uv run pytest -m "not integration and not gpu"  # skip live services and GPU tests

# Ingest PDF textbook(s) into RAG pipeline
uv run python scripts/ingest.py path/to/textbook.pdf
uv run python scripts/ingest.py data/pdfs/ --book-title "Cost Accounting"

# Ingest Phase 1 chunks into LightRAG knowledge graph (audit mode: 50 chunks)
uv run python scripts/ingest_lightrag.py data/chunks_backup.json
uv run python scripts/ingest_lightrag.py data/chunks_backup.json --full
uv run python scripts/ingest_lightrag.py data/chunks_backup.json --resume
uv run python scripts/ingest_lightrag.py data/chunks_backup.json --full --model deepseek-chat  # override model

# Test a query without UI
uv run python scripts/test_query.py "Apa itu break-even point?" -v

# Run React frontend (dev mode)
cd frontend && npm install && npm run dev  # port 5173

# Run FastAPI backend (dev mode)
uv run uvicorn backend.main:app --reload --port 8000

# Build frontend for production
cd frontend && npm run build  # outputs to frontend/dist/
```

## Architecture

### Data Flow

The system has two pipelines: **ingestion** (PDF → indexed chunks) and **query** (user question → cited answer).

**Ingestion pipeline** (`src/ingestion/pipeline.py` — 9 steps):
1. PDF triage via PyMuPDF (text-based → Docling, scanned → MinerU subprocess)
2. Diagram extraction + VLM captioning (Qwen2.5-VL-72B via SiliconFlow)
3. Split by Markdown heading hierarchy → `Section` dataclasses with breadcrumbs
4. Classify content type (narrative/table/formula/diagram/example) → type-specific splitting
5. Build parent-child chunk hierarchy (parents: 1000-1500 tokens, children: 200-512 tokens)
6. Create formula index chunks per chapter
7. Save chunks to JSON backup (enables re-embedding without re-parsing)
8. Embed via Qwen3-Embedding-8B (1024 dim, checkpoint resume)
9. Upload to Qdrant (dense cosine + sparse BM25/IDF vectors)

**Query pipeline** (`src/agents/graph.py` — LangGraph StateGraph):
- Phase 1: `preprocess → retrieve → rerank → generate → END`
- Phase 2 (current): `preprocess → retrieve → graph_retrieve → rerank → generate → END`
- State schema: `RAGState` in `src/agents/state.py`
- Each node is a function in `src/agents/nodes.py` that reads/writes to `RAGState`

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/llm/client.py` | SiliconFlow OpenAI-compatible client (embed, generate, rerank). Two retry configs: `_RETRY_CONFIG` (batch ingestion, 5 attempts) and `_UI_RETRY_CONFIG` (UI-facing, 2 attempts) |
| `src/retrieval/vector_search.py` | Hybrid search: dense + sparse BM25 fused via Reciprocal Rank Fusion (RRF) |
| `src/retrieval/preprocessor.py` | Glossary expansion (Indonesian→English) for BM25 + query embedding with instruction prefix |
| `src/retrieval/reranker.py` | Qwen3-Reranker-8B via SiliconFlow `/rerank` endpoint (httpx, not OpenAI client) |
| `src/generation/generator.py` | Bilingual response generation with two prompt modes: textbook-only (`SYSTEM_PROMPT_GENERATOR`) and multi-source synthesis (`SYSTEM_PROMPT_SYNTHESIS`) |
| `src/knowledge_graph/` | LightRAG integration: entity normalization, graph ingestion, DeepSeek LLM + SiliconFlow embedding |
| `config/settings.py` | Pydantic Settings loaded from `.env` — all API keys, model names, Qdrant config |
| `config/glossary.py` | Bidirectional English↔Indonesian accounting glossary (130+ terms) |
| `config/prompts.py` | System prompts for generation (3 variants: standard, calculation, synthesis) |
| `backend/main.py` | FastAPI backend with SSE streaming, wraps LangGraph pipeline |
| `frontend/` | React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui |

### Critical Design Patterns

- **Asymmetric embedding**: `embed_query()` prepends instruction prefix, `embed_document()` does not. Mixing these up loses 1-5% recall on cross-lingual retrieval.
- **VRAM isolation**: MinerU runs in a subprocess (`subprocess.run`) to prevent VRAM accumulation. Docling calls `vram_cleanup()` after every parse. GPU is only used for PDF parsing — all LLM/embedding inference is cloud API.
- **Qdrant dual vectors**: Collection MUST be created with both dense and sparse vector configs at creation time. Adding sparse later requires full collection recreation.
- **Checkpoint resume**: Embedding batches save progress to `data/checkpoints/` after each batch — rate limit interruptions don't restart from zero.
- **Content-type splitting**: Tables are atomic (≤20 rows) or split with repeated headers. Formulas are atomic (up to 1024 tokens) to keep formula + explanation together. Narrative text uses 512-token recursive split with 75-token overlap.

## Test Markers

```
integration  — requires live SiliconFlow/Qdrant services
e2e          — end-to-end tests
gpu          — requires NVIDIA GPU
```

Shared fixtures in `tests/conftest.py`: `mock_siliconflow`, `mock_qdrant_client`, `sample_markdown`, `sample_chunks`.

## LightRAG Ingestion Stack

LightRAG menggunakan 2 backend terpisah:
- **LLM**: DeepSeek API (`deepseek-chat`, no hard rate limit). Fallback SiliconFlow jika `DEEPSEEK_API_KEY` kosong.
- **Embedding**: SiliconFlow Qwen3-Embedding-8B (1024 dim, 500K+ TPM terpisah dari LLM rate limit).

Throughput realistis: ~2-3 jam per buku besar (1000+ filtered chunks). Bottleneck utama adalah LightRAG per-doc processing overhead (~47s/doc avg), bukan rate limit.

Filtered chunks = hanya `narrative_text` + `example_problem` (~30-50% dari total chunks).
Jalankan audit dulu (50 chunks, tanpa `--full`) sebelum full ingestion untuk memvalidasi kualitas entity extraction.

## Environment

- Python 3.11 (pinned in `.python-version`)
- `.env` file required (copy from `.env.example`): `SILICONFLOW_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `DEEPSEEK_API_KEY`
- Local GPU (GTX 1660 Ti 6GB) used only for PDF parsing; set `--vram 6` and `--backend pipeline` for MinerU
- PyTorch CUDA 12.6 installed from custom index (configured in `pyproject.toml` under `[tool.uv.sources]`)

## Language Convention

All documentation and user-facing content is in **Indonesian** (Bahasa Indonesia). English is used for technical terms, code identifiers, and API references. When generating responses or documentation, follow this bilingual pattern: Indonesian prose with English technical terms in parentheses where needed.

## Development Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | MVP: Basic RAG + Qdrant + Qwen3 API | Done |
| 2 | GraphRAG integration with LightRAG | Done |
| 3 | Agentic orchestration with LangGraph + CRAG | Planned |
| 4 | Scale to full corpus (100 textbooks) + optimization | Planned |
| 5 | Polish, documentation, beta launch | Planned |
