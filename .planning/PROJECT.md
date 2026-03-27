# Trusty RAG Akmen

## What This Is

AI-powered assistant untuk akuntansi biaya dan manajemen (cost & management accounting) yang menggunakan Retrieval-Augmented Generation untuk menjawab pertanyaan dari 20-30 textbook berbahasa Inggris, dalam bahasa Indonesia, dengan referensi buku dan halaman spesifik. Dibangun untuk seorang konsultan keuangan yang membutuhkan akses cepat ke knowledge base akuntansi untuk melayani klien.

## Core Value

Mempercepat proses pencarian referensi dan penyusunan jawaban akuntansi dari 45-60 menit menjadi 5-10 menit, dengan source citation (buku, chapter, halaman) yang bisa dipertanggungjawabkan ke klien.

## Requirements

### Validated

Validated in Phase 01 (Foundation):

- [x] PDF parsing pipeline — MinerU (primer) + Docling (sekunder) di GPU lokal GTX 1660 Ti 6 GB, menangani tabel, rumus LaTeX, dan diagram
- [x] Hybrid chunking 7 langkah — structure-aware + content-type specific + late chunking + parent-child hierarchy + metadata enrichment
- [x] Cross-lingual tanpa translasi — query bahasa Indonesia langsung di-retrieve terhadap textbook berbahasa Inggris via Qwen3-Embedding-8B multilingual
- [x] Source citation wajib — setiap response harus menyertakan referensi: nama buku, chapter, halaman
- [x] Chat UI sederhana — Streamlit interface untuk input query dan menampilkan response dengan citations (dark theme, bilingual copywriting)

### Validated

Validated in Phase 02 (Knowledge Graph):

- [x] Knowledge graph — LightRAG untuk entity/relationship extraction dan graph-based retrieval (local/naive/hybrid/mix modes). Validated in Phase 02: knowledge-graph
- [x] Perbandingan konsep lintas textbook — membandingkan metode costing (job order vs process vs ABC), pendekatan (absorption vs variable), dan teknik manajemen, menyintesis pandangan dari multiple textbook via SYSTEM_PROMPT_SYNTHESIS. Validated in Phase 02: knowledge-graph
- [x] Cross-reference textbook — menyajikan pandangan dari beberapa textbook untuk satu topik, mengidentifikasi konsensus dan perbedaan pendekatan antarpenulis via per-author attribution prompting. Validated in Phase 02: knowledge-graph

### Active

- [ ] Tanya jawab akuntansi cerdas — menjawab pertanyaan konseptual (definisi, penjelasan, prosedur) dengan referensi ke textbook sumber (nama buku, chapter, halaman), dalam bahasa Indonesia dengan istilah teknis Inggris dalam tanda kurung
- [ ] Kalkulasi otomatis — menghitung break-even point, variance analysis (material, labor, overhead), overhead allocation rate, contribution margin, ROI, residual income, dengan langkah perhitungan detail
- [ ] CRAG quality gate — setiap retrieval dievaluasi relevansinya (CORRECT/AMBIGUOUS/INCORRECT) dengan auto-reformulation jika di bawah threshold
- [ ] Adaptive complexity routing — query diklasifikasi ke 4 level (Simple/Medium/Complex/Calculation) untuk efisiensi API call (2-5 call per query)

### Out of Scope

- Navigasi berbasis topik / knowledge graph visual — kompleksitas UI tinggi, tidak kritis untuk v1
- Web search — hanya textbook yang di-ingest; tidak melakukan pencarian web untuk jawaban
- Multi-user / autentikasi — personal tool, satu pengguna
- Mobile app — web-first
- Real-time collaborative features — single user
- OAuth / social login — tidak ada autentikasi
- Notifikasi — tidak relevan untuk personal tool

## Context

**Pengguna:** Aris Simbolon — konsultan keuangan yang sehari-hari menjawab pertanyaan klien (manajer produksi, tim finance perusahaan manufaktur) soal akuntansi biaya dan manajemen. Referensi tersebar di 20-30 textbook berbahasa Inggris (Horngren, Garrison, Hansen & Mowen, dll). Saat ini: buka PDF satu per satu, Ctrl+F, baca, catat, pindah ke buku berikutnya, terjemahkan. Satu pertanyaan bisa makan waktu 30-60 menit hanya untuk mencari jawabannya.

**Pain points utama:**
1. Waktu cari referensi (30-60 menit per pertanyaan)
2. Sintesis antarbuku (mencocokkan perspektif Horngren vs Garrison vs Hansen & Mowen)
3. Kalkulasi manual yang rawan error (BEP, variance analysis, overhead rate)

**Skenario tipikal:** Klien bertanya "Apa bedanya traditional costing vs ABC costing untuk manufaktur menengah? Hitung juga BEP dengan data ini." — Trusty RAG harus menarik referensi dari multiple textbook, menyintesis, menghitung, dan menyajikan dalam bahasa Indonesia dengan citations.

**Komersial:** Personal tool dulu, tidak menutup kemungkinan menjadi produk komersial di masa depan — arsitektur harus cukup bersih untuk di-scale nanti.

**Dokumen arsitektur:** `Trusty_RAG_Akmen.md` (524 baris) berisi spesifikasi teknis lengkap — hybrid chunking pipeline, multi-agent architecture, LangGraph + LightRAG integration, PDF parsing optimization untuk GTX 1660 Ti, retrieval architecture, dan infrastructure planning.

## Constraints

- **GPU lokal:** NVIDIA GTX 1660 Ti 6 GB VRAM — cukup untuk PDF parsing (MinerU/Docling), **tidak cukup** untuk embedding/LLM inference lokal. Tidak ada Tensor Cores, tidak support BF16, Flash Attention 2 tidak officially supported (CC 7.5). Gunakan FP16 always.
- **Budget operasional:** $8-35/bulan untuk 100-500 query/hari via SiliconFlow API
- **Budget one-time:** ~$10-25 (embedding + entity extraction via API)
- **Sumber data:** Hanya textbook yang di-ingest, 20-30 buku untuk v1
- **Bahasa:** Input bahasa Indonesia, sumber bahasa Inggris, output bahasa Indonesia dengan istilah teknis Inggris
- **Rate limit SiliconFlow:** 50-1.000 RPD bergantung tier
- **Kompatibilitas GPU:** GTX 1660 Ti (CC 7.5) adalah batas minimum PyTorch cu128 — gunakan cu126 wheels untuk safety margin
- **Disclaimer wajib:** Untuk kalkulasi, sertakan "verifikasi hasil dengan sumber resmi" — bukan pengganti akuntan profesional

## Tech Stack

| Layer | Teknologi |
|-------|-----------|
| LLM Generation + Routing | Qwen3-30B-A3B-Instruct-2507 via SiliconFlow ($0,10/$0,39 per 1M token) |
| Embedding | Qwen3-Embedding-8B (1.024 dim via MRL truncation, $0,04/1M token) |
| Reranker | Qwen3-Reranker-8B ($0,04/1M token) |
| Orchestration | LangGraph + LangChain |
| GraphRAG | LightRAG (built-in nano-vectordb/NetworkX) |
| Vector DB | Qdrant Cloud Free Tier (1 GB RAM + 4 GB disk, scalar quantization) |
| PDF Parser (primer) | MinerU — scanned/complex PDFs, --vram 6 |
| PDF Parser (sekunder) | Docling — text-based PDFs, batch_size=4 |
| PDF Quick Scan | PyMuPDF |
| Chunking | LangChain TextSplitters + LlamaIndex HierarchicalNodeParser + Chonkie (LateChunker) |
| VLM (diagrams) | Qwen-VL via SiliconFlow |
| Frontend | Streamlit / Chainlit |
| Monitoring | LangSmith / Langfuse |
| Hosting | Railway / Render / fly.io |

## Project Structure

```
trusty-rag-akmen/
├── .env / .env.example
├── pyproject.toml
├── Dockerfile / docker-compose.yml
├── langgraph.json
├── config/                           # Settings, glossary, prompts
│   ├── settings.py                   # Pydantic BaseSettings
│   ├── glossary.py                   # Bilingual EN↔ID (~200-500 istilah)
│   └── prompts.py                    # Semua system prompts terpusat
├── src/
│   ├── llm/                          # SiliconFlow client + model registry
│   ├── ingestion/                    # Offline batch pipeline
│   │   ├── parsing/                  # MinerU, Docling, PyMuPDF, VLM, GPU utils
│   │   ├── chunking/                 # Classifier, splitters, hierarchy, late chunking, formula index
│   │   ├── indexing/                 # Embedder, Qdrant uploader, LightRAG graph builder
│   │   └── pipeline.py              # End-to-end orchestrator
│   ├── retrieval/                    # Online per-query: router, vector, graph, reranker, CRAG
│   ├── tools/                        # LangChain @tool wrappers
│   ├── agents/                       # LangGraph: state, supervisor, nodes, edges, graph
│   ├── generation/                   # Response generator, formatter, citation builder
│   └── monitoring/                   # LangSmith/Langfuse tracer + metrics
├── data/                             # Gitignored: raw PDFs, parsed, chunks, LlamaIndex store, LightRAG workdir
├── scripts/                          # CLI: ingest, ingest_single, test_query, build_formula_index
├── app/                              # Streamlit/Chainlit UI
└── tests/                            # Per-concern: parsing, chunking, retrieval, router, CRAG, calculator, e2e
```

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SiliconFlow sebagai satu-satunya LLM provider | OpenAI-compatible, harga sangat murah ($0,10/$0,39 per 1M token untuk Qwen3-30B), semua model Qwen3 tersedia dalam satu platform | — Pending |
| LightRAG pakai built-in nano-vectordb, bukan Qdrant | Simplicity — Qdrant hanya untuk direct vector search via LangChain, LightRAG tetap self-contained. Menghindari konflik konfigurasi | — Pending |
| GPU lokal hanya untuk parsing, cloud API untuk intelligence | GTX 1660 Ti 6 GB cukup untuk MinerU/Docling tapi tidak cukup untuk model 8B+. Embedding lokal butuh ~33 hari vs ~4-12 jam via API ($2-8) | — Pending |
| Cross-lingual tanpa translasi query | Qwen3-Embedding-8B #1 MTEB Multilingual (skor 70,58) — menghilangkan layer kompleksitas translation service | — Pending |
| Hybrid chunking 7 langkah, bukan satu strategi tunggal | Textbook akuntansi mengandung campuran teks, tabel, rumus, diagram — masing-masing butuh penanganan berbeda. Studi Vectara NAACL 2025 mengonfirmasi chunking configuration memengaruhi kualitas retrieval setara pemilihan embedding model | — Pending |
| MinerU primer + Docling sekunder (bukan salah satu saja) | MinerU unggul untuk scanned/complex PDFs (sequential model loading, --vram 6). Docling unggul untuk text-based PDFs (97,9% akurasi tabel, MIT license, lebih cepat). Komplementer | — Pending |
| Supervisor + Tool-Calling pattern (bukan full supervisor atau hierarchical) | 2-5 API calls per query vs 6+ (full supervisor) atau 10+ (hierarchical). Satu LLM call menginvoke multiple tools secara sekuensial dalam satu reasoning loop | — Pending |
| Personal tool dulu, arsitektur bersih untuk scale nanti | Fokus v1: memecahkan masalah sendiri. Tapi config/prompts terpusat, modular structure, workspace isolation di LightRAG — siap di-extend jika komersial | — Pending |
| cu126 PyTorch wheels, bukan cu128 | GTX 1660 Ti CC 7.5 adalah batas minimum cu128 — cu126 memberikan safety margin untuk longevity | — Pending |

---
## Current State

Phase 02 (Knowledge Graph) complete — 2026-03-22. LightRAG knowledge graph terintegrasi dengan LangGraph pipeline — graph_retrieve_node, multi-textbook synthesis via SYSTEM_PROMPT_SYNTHESIS, dan per-author attribution. Siap untuk Phase 03 (Agentic Orchestration dengan LangGraph + CRAG).

---
*Last updated: 2026-03-22 after Phase 02 completion*
