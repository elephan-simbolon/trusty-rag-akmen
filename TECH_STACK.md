# Tech Stack — Trusty RAG Akmen

Dokumentasi lengkap teknologi, library, tools, dan services yang digunakan proyek ini.

---

## Backend (Python 3.11)

### Core Framework

| Teknologi | Versi | Kegunaan |
|---|---|---|
| Python | 3.11 (pinned `.python-version`) | Runtime utama |
| FastAPI | 0.135.2 | Web framework REST API |
| Uvicorn | 0.42.0 | ASGI server |
| SSE-Starlette | 3.3.3 | Server-Sent Events untuk streaming response |
| Pydantic Settings | 2.13.1 | Settings management dari `.env` |
| python-dotenv | 1.2.2 | Load environment variables |

### LLM & AI Framework

| Teknologi | Versi | Kegunaan |
|---|---|---|
| LangGraph | 1.1.3 | Agent orchestration — StateGraph untuk query pipeline |
| LangChain | 1.2.13 | LLM application framework |
| LightRAG (HKU) | 1.4.11 | Knowledge graph RAG — entity extraction & graph retrieval |
| OpenAI (client) | 2.29.0 | Client untuk SiliconFlow API (OpenAI-compatible) |

### Vector Database & Retrieval

| Teknologi | Versi | Kegunaan |
|---|---|---|
| Qdrant (client) | 1.17.1 | Vector database — dense (cosine) + sparse (BM25/IDF) |
| LightRAG nano-vectordb | built-in | File-based JSON storage untuk knowledge graph (terpisah dari Qdrant) |

### Document Processing

| Teknologi | Versi | Kegunaan |
|---|---|---|
| PyMuPDF | 1.27.2 | PDF triage & classification (text-based vs scanned) |
| Docling | 2.81.0 | PDF parsing untuk text-based PDF (PyPdfium2 backend) |
| MinerU | 2.7.6 | PDF parsing untuk scanned PDF (subprocess isolation) |

### Deep Learning & Compute

| Teknologi | Versi | Kegunaan |
|---|---|---|
| PyTorch | 2.10.0+cu126 | CUDA 12.6 — hanya untuk PDF parsing lokal (GTX 1660 Ti 6GB) |
| numpy | transitive | Array operations untuk LightRAG embedding (import langsung, bukan di pyproject.toml) |

### Utilities

| Teknologi | Versi | Kegunaan |
|---|---|---|
| httpx | 0.28.1 | HTTP client untuk reranker endpoint |
| Tenacity | 9.1.4 | Retry logic — 2 config: batch ingestion (5x) dan UI-facing (2x) |
| aiosqlite | 0.22.1 | Async SQLite untuk chat history (single-user local deployment) |

### Observability

| Teknologi | Versi | Kegunaan |
|---|---|---|
| Langfuse | 4.0.1 | LLM tracing, token usage tracking, cost monitoring |
| Python logging | stdlib | Logging standar di semua modul |
| Custom rate limit monitor | - | Logging khusus HTTP 429 dari SiliconFlow |

### Dead Dependencies (ada di pyproject.toml, tidak diimport)

| Teknologi | Versi | Catatan |
|---|---|---|
| chonkie[semantic] | 1.6.1 | Tidak ditemukan import di codebase |
| llama-index-core | 0.14.18 | Tidak ditemukan import di codebase |

---

## Frontend (React SPA)

### Core

| Teknologi | Versi | Kegunaan |
|---|---|---|
| React | 19.2.0 | UI library |
| Vite | 7.3.1 | Build tool & dev server (HMR) |
| TypeScript | 5.9.3 | Type-safe JavaScript (strict mode) |

### Styling

| Teknologi | Versi | Kegunaan |
|---|---|---|
| Tailwind CSS | 4.2.1 | Utility-first CSS (v4, CSS-first config via `@tailwindcss/vite`) |
| tw-animate-css | 1.4.0 | Animation utilities untuk Tailwind |
| autoprefixer | 10.4.27 | CSS vendor prefixes |
| PostCSS | 8.5.6 | CSS transformation |
| Plus Jakarta Sans | - | Google Font (400-800 weights, loaded via HTML `<link>`) |

### UI Components

| Teknologi | Versi | Kegunaan |
|---|---|---|
| shadcn/ui | 3.8.5 (CLI) | Component library (New York style, CSS variables) |
| Radix UI | 1.4.3 | Headless accessible primitives (Collapsible, Tooltip, DropdownMenu, Sidebar) |
| Lucide React | 0.575.0 | Icon library |
| class-variance-authority | 0.7.1 | Variant-based component class names |
| clsx + tailwind-merge | 2.1.1 / 3.5.0 | className utility (`cn()` function) |

### Content & UX

| Teknologi | Versi | Kegunaan |
|---|---|---|
| react-markdown | 10.1.0 | Render Markdown dari LLM response |
| Sonner | 2.0.7 | Toast notifications |

### Yang Tidak Digunakan (by design)

| Kategori | Catatan |
|---|---|
| State management | Tidak ada zustand/redux/jotai — murni React hooks (`useState`, `useRef`, `useCallback`) |
| Routing | Tidak ada react-router — single-page tanpa client-side routing |
| Form handling | Tidak ada react-hook-form/formik — plain controlled components |
| HTTP client | Tidak ada axios/ky — native browser `fetch` API |
| SSE library | Manual `ReadableStream` parsing (tanpa `eventsource` / `@microsoft/fetch-event-source`) |

---

## External Services (Cloud API)

### AI Model Providers

| Service | Model | Kegunaan |
|---|---|---|
| SiliconFlow | Qwen3-30B-A3B-Instruct-2507 | LLM utama (generation, routing, grading) |
| SiliconFlow | Qwen3-Embedding-8B (1024 dim) | Embedding (asymmetric: query vs document) |
| SiliconFlow | Qwen3-Reranker-8B | Reranking via `/rerank` endpoint (httpx) |
| SiliconFlow | Qwen2.5-VL-72B-Instruct | VLM untuk diagram captioning |
| DeepSeek | deepseek-chat (V3.2) | LLM untuk LightRAG entity extraction (primary, fallback ke SiliconFlow) |

### Infrastructure Services

| Service | Kegunaan |
|---|---|
| Qdrant Cloud | Vector database (hosted) |
| Langfuse | LLM observability & tracing (optional, graceful degradation) |
| Vercel | Frontend hosting (deployment via GitHub Actions) |
| Codecov | Code coverage reporting |

---

## Build System & Package Management

| Tool | Kegunaan |
|---|---|
| uv | Python package manager (dengan `uv.lock` untuk reproducible installs) |
| Hatchling | Python build backend |
| npm | Frontend package manager |
| Vite | Frontend bundler & dev server |
| tsc | TypeScript compiler (type-check sebelum build) |

---

## CI/CD & DevOps

### GitHub Actions

| Workflow | Jobs | Detail |
|---|---|---|
| `ci.yml` | 3 parallel jobs | Unit tests (pytest + coverage), lint (ruff), frontend build (npm) |
| `deploy.yml` | Manual dispatch | Frontend → Vercel; backend deployment commented out (Docker+VPS atau Railway) |

### GitHub Actions Dependencies

| Action | Versi |
|---|---|
| actions/checkout | v5 |
| astral-sh/setup-uv | v7 |
| actions/setup-node | v4 (Node.js 20) |
| codecov/codecov-action | v4 |
| actions/upload-artifact | v4 |
| actions/download-artifact | v4 |
| amondnet/vercel-action | v25 |

### Automated Maintenance

| Tool | Kegunaan |
|---|---|
| Dependabot | Weekly dependency updates (pip, npm, github-actions) |

### Yang Belum Ada

| Item | Catatan |
|---|---|
| Dockerfile | Belum dibuat — template Docker+VPS di deploy.yml masih commented out |
| docker-compose.yml | Belum dibuat |
| Git hooks | Tidak ada `.husky/` atau `.pre-commit-config.yaml` — linting hanya di CI |
| Authentication | Tidak ada auth — desain single-user local deployment |

---

## Linting & Testing

### Python

| Tool | Versi | Config |
|---|---|---|
| Ruff | 0.15.8 | Line length 100, target py311, rules: E, F, I (ignore E501) |
| pytest | 9.0.2 | Config di `pytest.ini` |
| pytest-timeout | 2.4.0 | 30s default timeout |
| pytest-asyncio | 1.3.0 | Async test support |
| pytest-cov | 7.1.0 | Coverage reporting |

Test markers: `integration` (live services), `e2e` (end-to-end), `gpu` (NVIDIA GPU).

### Frontend

| Tool | Versi | Config |
|---|---|---|
| ESLint | 9.39.1 | Flat config (`eslint.config.js`) |
| typescript-eslint | 8.48.0 | TS parser & rules |
| eslint-plugin-react-hooks | 7.0.1 | React hooks rules |
| eslint-plugin-react-refresh | 0.4.24 | Fast Refresh validation |

---

## Data Formats

| Format | Kegunaan |
|---|---|
| JSON | Chunks, checkpoints, eval queries, LightRAG cache, API payloads, SSE events |
| Markdown | Parsed PDF content (intermediate format dari Docling/MinerU) |
| PDF | Source documents (textbook) |
| TOML | `pyproject.toml` project config |
| YAML | GitHub Actions workflows, Dependabot config |
| SQLite | Chat history (`backend/history.db`) |
| CSS | Tailwind directives (`frontend/src/index.css`) |

---

## Storage & Database

| Storage | Teknologi | Lokasi | Kegunaan |
|---|---|---|---|
| Vector DB | Qdrant Cloud | Remote | Dense + sparse vectors untuk retrieval |
| Knowledge Graph | LightRAG nano-vectordb | `./lightrag_storage/` (lokal, file-based JSON) | Entity & relationship storage |
| Chat History | SQLite | `backend/history.db` | Query history, feedback, titles |
| Chunk Backup | JSON files | `data/chunks/` | Serialized chunks per buku |
| Embedding Checkpoints | JSON files | `data/checkpoints/` | Resume-safe embedding progress |
| Parsed PDFs | Markdown files | `data/parsed/` | Intermediate parsed content |

---

## Environment Variables

### Required

| Variable | Kegunaan |
|---|---|
| `SILICONFLOW_API_KEY` | SiliconFlow API (embedding, LLM, reranker, VLM) |
| `QDRANT_URL` | Qdrant vector database endpoint |
| `QDRANT_API_KEY` | Qdrant authentication |
| `DEEPSEEK_API_KEY` | DeepSeek API untuk LightRAG (kosong = fallback SiliconFlow) |

### Optional

| Variable | Kegunaan |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | Langfuse observability |
| `LANGFUSE_SECRET_KEY` | Langfuse observability |
| `LANGFUSE_BASE_URL` | Langfuse endpoint |
| `PYTORCH_CUDA_ALLOC_CONF` | CUDA memory config |
| `LIGHTRAG_LLM_MODEL` | Override model untuk LightRAG (default: `deepseek-chat`) |
| `VITE_API_BASE_URL` | Frontend API endpoint (default: `http://localhost:8000`) |
