# Requirements: Trusty RAG Akmen

**Defined:** 2026-03-22
**Core Value:** Mempercepat pencarian referensi dan penyusunan jawaban akuntansi dari 45-60 menit menjadi 5-10 menit, dengan source citation yang bisa dipertanggungjawabkan ke klien.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingestion Pipeline

- [x] **INGEST-01**: Sistem dapat mem-parsing PDF textbook text-based menggunakan Docling di GPU lokal (GTX 1660 Ti, batch_size=4, CUDA)
- [x] **INGEST-02**: Sistem dapat mem-parsing PDF textbook scanned/complex menggunakan MinerU pipeline backend di GPU lokal (--vram 6, sequential model loading)
- [x] **INGEST-03**: Sistem melakukan quick scan via PyMuPDF untuk menentukan PDF text-based vs scanned sebelum routing ke parser yang tepat
- [x] **INGEST-04**: Sistem menerapkan VRAM cleanup penuh (del model, gc.collect, torch.cuda.empty_cache, synchronize) antara setiap parser — Docling dan MinerU tidak boleh berjalan bersamaan
- [x] **INGEST-05**: Sistem mengekstrak diagram/flowchart sebagai gambar dan menghasilkan deskripsi tekstual via VLM captioning (Qwen-VL via SiliconFlow API)
- [x] **INGEST-06**: Sistem mendukung incremental ingestion — menambah textbook baru tanpa harus reindex seluruh corpus

### Chunking

- [x] **CHUNK-01**: Sistem mengklasifikasi setiap elemen parsed content ke dalam tipe: narrative_text, table, formula, diagram, example_problem
- [x] **CHUNK-02**: Sistem melakukan primary split berdasarkan heading hierarchy (Part → Chapter → Section → Subsection) dengan metadata breadcrumb
- [x] **CHUNK-03**: Sistem melakukan secondary split per tipe konten — naratif 512 token overlap 75, tabel kecil (≤20 baris) utuh, tabel besar split per kelompok baris dengan pengulangan column headers, rumus sebagai atomic unit + penjelasan (LaTeX + natural language), contoh soal utuh hingga 1024 token
- [x] **CHUNK-04**: Sistem membangun parent-child hierarchy menggunakan HierarchicalNodeParser (parent 1000-1500 token, child 200-512 token) dengan persistent StorageContext
- [x] **CHUNK-05**: Sistem melakukan late chunking enhancement via Qwen3-Embedding-8B API batch processing (bukan lokal)
- [x] **CHUNK-06**: Sistem menambahkan metadata pada setiap chunk: book_title, chapter, section_path, content_type, page_number
- [x] **CHUNK-07**: Sistem membuat formula index chunk per chapter — daftar semua rumus kunci dengan deskripsi LaTeX + natural language sebagai high-relevance retrieval target
- [x] **CHUNK-08**: Sistem menyisipkan inline page markers saat parsing untuk memastikan akurasi page_number pada setiap chunk (bukan hanya inherit dari parent)

### Indexing

- [x] **INDEX-01**: Sistem meng-embed semua chunks ke Qdrant Cloud menggunakan Qwen3-Embedding-8B via SiliconFlow (1024 dim, MRL truncation) dengan scalar quantization
- [x] **INDEX-02**: Sistem mengindeks sparse vectors (BM25) di Qdrant untuk hybrid search — menangkap terminologi Inggris eksak dari query Indonesia
- [x] **INDEX-03**: Sistem menyimpan metadata per chunk (book_title, chapter, section_path, content_type, page_number) sebagai payload di Qdrant untuk filtering
- [x] **INDEX-04**: Sistem mengekstrak entitas dan relasi ke LightRAG knowledge graph via Qwen3-30B-A3B menggunakan custom prompt untuk domain akuntansi — entity types: CostType, CostingMethod, CostDriver, AccountingStandard, ManagementTechnique, Formula, dll
- [x] **INDEX-05**: Sistem menggunakan instruction prefix pada embedding query: "Instruct: Retrieve English accounting textbook passages relevant to the Indonesian accounting query"

### Retrieval

- [x] **RETR-01**: Sistem melakukan hybrid search di Qdrant (dense vectors + sparse BM25 + metadata filtering) untuk setiap query
- [x] **RETR-02**: Sistem melakukan reranking hasil retrieval menggunakan Qwen3-Reranker-8B via SiliconFlow dengan cross-lingual scoring
- [x] **RETR-03**: Sistem mendukung LightRAG graph query dalam mode local, naive, hybrid, dan mix untuk query relasional dan perbandingan konsep
- [x] **RETR-04**: Sistem menerapkan CRAG quality gate — setiap retrieval dievaluasi CORRECT/AMBIGUOUS/INCORRECT; jika AMBIGUOUS atau INCORRECT, query di-reformulasi dan di-retrieve ulang (max 2 iterasi)
- [x] **RETR-05**: Sistem mengklasifikasi query ke 4 level kompleksitas (Simple/Medium/Complex/Calculation) via adaptive routing — Simple: 2 LLM calls, Medium: 3, Complex: 4-5, Calculation: 2-3
- [x] **RETR-06**: Sistem menerapkan rule-based pre-check untuk query Calculation (deteksi angka + keywords "hitung", "BEP", "berapa") sebelum LLM classifier untuk menghemat 1 LLM call

### Cross-lingual

- [x] **LANG-01**: User dapat mengetik query sepenuhnya dalam bahasa Indonesia dan mendapat retrieval akurat dari textbook berbahasa Inggris tanpa translasi query
- [x] **LANG-02**: Sistem menggunakan bilingual glossary (~200-500 istilah akuntansi EN↔ID) yang di-inject ke system prompt dan sebagai BM25 index entries
- [x] **LANG-03**: Sistem menghasilkan output dalam bahasa Indonesia dengan istilah teknis Inggris dalam tanda kurung, contoh: "alokasi biaya overhead (*overhead cost allocation*)"

### Generation

- [x] **GEN-01**: Setiap response menyertakan source citation: nama buku, chapter, halaman — format: "Horngren, *Cost Accounting*, Chapter 5, hal. 168-172"
- [x] **GEN-02**: Sistem dapat menghitung formula akuntansi: break-even point, variance analysis (material, labor, overhead), overhead allocation rate, contribution margin, ROI, residual income — dengan langkah perhitungan detail
- [x] **GEN-03**: Setiap response kalkulasi menyertakan disclaimer: "verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional"
- [x] **GEN-04**: Sistem dapat menyintesis pandangan dari multiple textbook untuk satu topik — mengidentifikasi konsensus dan perbedaan pendekatan antarpenulis, menyebutkan masing-masing sumber
- [x] **GEN-05**: Sistem dapat menjawab query relasional ("apa prerequisite ABC costing?", "apa hubungan variance analysis dengan standard costing?") menggunakan knowledge graph relationship traversal
- [x] **GEN-06**: Sistem menjawab query perbandingan ("bandingkan absorption vs variable costing untuk manufaktur") dengan menarik konteks dari multiple textbook dan knowledge graph relationships

### Interface

- [x] **UI-01**: User dapat berinteraksi melalui Streamlit chat UI — input query, lihat response, lihat citations, lihat langkah kalkulasi
- [x] **UI-02**: Sistem mempertahankan conversation memory dalam satu sesi — follow-up questions ("jelaskan lebih detail poin ke-3", "sekarang hitung dengan data ini") bekerja natural via LangGraph state
- [ ] **UI-03**: Citations ditampilkan di bagian bawah response dalam format expandable/collapsible

### Monitoring & Performance

- [x] **MON-01**: Sistem terintegrasi dengan Langfuse untuk tracing per-query: routing decision, retrieval results, generation, latency, token usage
- [x] **MON-02**: Retrieval accuracy ≥85% pada accounting-specific queries (diukur pada evaluation set)
- [x] **MON-03**: Response time ≤10 detik untuk query Simple, ≤20 detik untuk query Complex
- [x] **MON-04**: Biaya operasional ≤$35/bulan untuk 500 query/hari
- [x] **MON-05**: Sistem menerapkan request queuing/throttling untuk menangani SiliconFlow rate limit (50-1000 RPD bergantung tier)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Scale

- **SCALE-01**: Ingest full corpus hingga 100 textbook (~200.000 halaman) menggunakan GPU lokal — estimasi ~2-4 hari continuous processing
- **SCALE-02**: Semantic caching untuk query frequent — mengurangi API calls untuk pertanyaan berulang
- **SCALE-03**: Parent-child hierarchical retrieval optimization — AutoMergingRetriever threshold tuning untuk corpus besar

### Multi-user

- **MULTI-01**: Multi-user support dengan workspace isolation
- **MULTI-02**: Authentication dan session management
- **MULTI-03**: Per-user query history dan bookmarks

### UI Enhancement

- **UIX-01**: Visual knowledge graph navigation — browse topics via interactive graph
- **UIX-02**: Cross-session conversation history persistence
- **UIX-03**: Export/share — generate PDF report dari jawaban untuk dikirim ke klien

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web search / live internet data | Destroys trust — tool's value is citations from authoritative textbooks. Mixing unvetted web content makes citations unreliable |
| Fine-tuned / locally-hosted LLM | GTX 1660 Ti 6 GB cannot run 8B+ models for inference. No labeled data for fine-tuning |
| Visual knowledge graph navigation (v1) | High UI complexity for low immediate value — consultant uses tool to answer specific questions, not to explore |
| Hierarchical multi-agent pattern | 10+ LLM calls per query — budget-incompatible at $0.001/query target |
| Real-time corpus updates | LightRAG entity extraction takes hours per book. Incremental batch ingestion is sufficient |
| Mobile app | Web-first, single user. Mobile later if commercialized |
| Social login / OAuth | Personal tool, no authentication needed |
| Automatic answer correction | Creates liability — tool is reference, not professional advice |
| Cross-session chat persistence (v1) | Over-engineering for personal tool. LangGraph session-level state is sufficient for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 1 — Foundation | Complete |
| INGEST-02 | Phase 1 — Foundation | Complete |
| INGEST-03 | Phase 1 — Foundation | Complete |
| INGEST-04 | Phase 1 — Foundation | Complete |
| INGEST-05 | Phase 1 — Foundation | Complete |
| INGEST-06 | Phase 4 — Scale and Observability | Complete |
| CHUNK-01 | Phase 1 — Foundation | Complete |
| CHUNK-02 | Phase 1 — Foundation | Complete |
| CHUNK-03 | Phase 1 — Foundation | Complete |
| CHUNK-04 | Phase 1 — Foundation | Complete |
| CHUNK-05 | Phase 4 — Scale and Observability | Complete |
| CHUNK-06 | Phase 1 — Foundation | Complete |
| CHUNK-07 | Phase 1 — Foundation | Complete |
| CHUNK-08 | Phase 1 — Foundation | Complete |
| INDEX-01 | Phase 1 — Foundation | Complete |
| INDEX-02 | Phase 1 — Foundation | Complete |
| INDEX-03 | Phase 1 — Foundation | Complete |
| INDEX-04 | Phase 2 — Knowledge Graph | Complete |
| INDEX-05 | Phase 1 — Foundation | Complete |
| RETR-01 | Phase 1 — Foundation | Complete |
| RETR-02 | Phase 1 — Foundation | Complete |
| RETR-03 | Phase 2 — Knowledge Graph | Complete |
| RETR-04 | Phase 3 — Agentic Orchestration | Complete |
| RETR-05 | Phase 3 — Agentic Orchestration | Complete |
| RETR-06 | Phase 3 — Agentic Orchestration | Complete |
| LANG-01 | Phase 1 — Foundation | Complete |
| LANG-02 | Phase 1 — Foundation | Complete |
| LANG-03 | Phase 1 — Foundation | Complete |
| GEN-01 | Phase 1 — Foundation | Complete |
| GEN-02 | Phase 3 — Agentic Orchestration | Complete |
| GEN-03 | Phase 3 — Agentic Orchestration | Complete |
| GEN-04 | Phase 2 — Knowledge Graph | Complete |
| GEN-05 | Phase 2 — Knowledge Graph | Complete |
| GEN-06 | Phase 2 — Knowledge Graph | Complete |
| UI-01 | Phase 1 — Foundation | Complete |
| UI-02 | Phase 3 — Agentic Orchestration | Complete |
| UI-03 | Phase 5 — Polish | Pending |
| MON-01 | Phase 4 — Scale and Observability | Complete |
| MON-02 | Phase 4 — Scale and Observability | Complete |
| MON-03 | Phase 4 — Scale and Observability | Complete |
| MON-04 | Phase 4 — Scale and Observability | Complete |
| MON-05 | Phase 3 — Agentic Orchestration | Complete |

**Coverage:**
- v1 requirements: 40 total
- Mapped to phases: 40
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after Plan 01-06 — UI-01 marked complete; Phase 1 Foundation all requirements fulfilled*
