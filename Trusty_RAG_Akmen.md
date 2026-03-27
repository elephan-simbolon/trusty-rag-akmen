# Arsitektur RAG untuk Akuntansi Biaya dan Manajemen: Panduan Teknis Lengkap (Revisi)

**LightRAG + LangGraph + Qwen3 via SiliconFlow membentuk stack optimal** untuk sistem Retrieval-Augmented Generation di domain akuntansi biaya dan manajemen — dengan total biaya operasional hanya **$8–35/bulan** untuk 100 textbook dan ratusan query harian. Kombinasi ini memanfaatkan kemampuan multilingual Qwen3-Embedding-8B yang menduduki peringkat #1 di MTEB Multilingual Leaderboard (skor 70,58), sehingga retrieval cross-lingual Inggris–Indonesia dapat dilakukan *tanpa* translasi query. Proses ingestion dipercepat oleh **GPU lokal NVIDIA GTX 1660 Ti 6 GB** untuk parsing PDF, sementara embedding dan entity extraction tetap memanfaatkan SiliconFlow API yang jauh lebih efisien. Dokumen ini menyajikan rekomendasi arsitektur end-to-end lengkap dengan justifikasi teknis, system design, tech stack, dan draft PRD.

> **Catatan revisi:** Dokumen ini merupakan konsolidasi dari riset arsitektur awal dan riset pemanfaatan GPU GTX 1660 Ti 6 GB untuk pipeline ingestion. Perubahan utama meliputi: (1) revisi constraint "tidak memiliki GPU lokal", (2) penyesuaian pipeline parsing dengan MinerU sebagai parser primer, (3) koreksi estimasi waktu dan biaya ingestion, dan (4) diagram arsitektur ingestion yang memperhitungkan GPU lokal.

---

## A. Hybrid chunking sebagai strategi optimal untuk textbook akuntansi

Tidak ada satu strategi chunking yang cocok untuk semua tipe konten dalam textbook akuntansi. Textbook mengandung campuran teks naratif, tabel angka (cost sheet, variance analysis), rumus matematika (BEP, overhead rate), diagram (flowchart process costing), dan contoh soal — masing-masing memerlukan penanganan berbeda. Benchmark FloTorch 2026 menunjukkan recursive chunking pada **512 token** menghasilkan akurasi end-to-end **69%** (tertinggi di antara semua strategi), sementara studi peer-reviewed Vectara di NAACL 2025 mengonfirmasi bahwa konfigurasi chunking memengaruhi kualitas retrieval **sebesar atau lebih besar** dari pemilihan embedding model itu sendiri.

### Perbandingan strategi chunking

| Strategi | Akurasi Benchmark | Cocok untuk Akuntansi? | Kelemahan Utama |
|---|---|---|---|
| **Recursive character** (512t) | 69% (FloTorch), 88–89,5% recall (Chroma) | ✅ Baik untuk teks naratif | Tidak menangani tabel/rumus secara native |
| **Structure-aware** (heading-based) | 0,648 accuracy (NVIDIA) | ✅ Esensial — textbook punya hierarki jelas | Section bisa terlalu panjang atau pendek |
| **Semantic chunking** | 91,9% recall tetapi hanya 54% akurasi E2E | ⚠️ Selektif — baik untuk naratif panjang tanpa heading | Menghasilkan fragmen terlalu kecil (avg 43 token); mahal |
| **Late chunking** | Belum ada benchmark formal | ✅ Sangat direkomendasikan untuk textbook | Memerlukan pemrosesan full-section sekaligus |
| **Agentic/LLM chunking** | Di antara terburuk (FloTorch) | ❌ Terlalu mahal untuk 30–100 textbook | Nondeterministik, lambat |
| **Token-based** | N/A | ⚠️ Hanya sebagai enforcement step | Mengabaikan batas semantik |

### Rekomendasi: pipeline hybrid 7 langkah

Pipeline ini menggabungkan beberapa strategi berdasarkan tipe konten:

**Langkah 1 — PDF → Structured Markdown** via MinerU (primer) atau Docling (sekunder), keduanya berjalan di GPU lokal GTX 1660 Ti. Preservasi heading, tabel, dan rumus.

**Langkah 2 — Klasifikasi elemen:** `narrative_text | table | formula | diagram | example_problem`.

**Langkah 3 — Primary split** berdasarkan hierarki heading (Part → Chapter → Section → Subsection) dengan metadata breadcrumb.

**Langkah 4 — Secondary split per tipe konten:** teks naratif menggunakan RecursiveCharacterTextSplitter (512 token, overlap 75 token); tabel kecil (≤20 baris) dipertahankan utuh; tabel besar di-split per kelompok baris dengan **pengulangan column headers**; rumus dijadikan atomic unit bersama penjelasan; contoh soal dipertahankan utuh (hingga 1.024 token).

**Langkah 5 — Late chunking enhancement** menggunakan Qwen3-Embedding-8B **via SiliconFlow API** (bukan lokal — model 8B membutuhkan ~16 GB VRAM, jauh melebihi kapasitas GTX 1660 Ti 6 GB) untuk memproses seluruh section sebelum splitting. Proses dilakukan secara batch, bukan real-time, untuk efisiensi biaya.

**Langkah 6 — Parent-child hierarchy:** parent chunk 1.000–1.500 token (level section) dan child chunk 200–512 token (level paragraf), menggunakan LlamaIndex `HierarchicalNodeParser` + `AutoMergingRetriever`.

**Langkah 7 — Metadata enrichment:** `book_title`, `chapter`, `section_path`, `content_type`, `page_number`.

### Ukuran chunk optimal untuk Qwen3-Embedding-8B

Model ini memiliki context window **32.768 token** (official code menggunakan `max_length = 8192` sebagai batas praktis), dimensi embedding hingga **4.096** dengan MRL (truncation ke 1.024 mempertahankan ~95% performa retrieval). Rekomendasi spesifik:

| Tipe Konten | Ukuran Chunk | Overlap | Rasional |
|---|---|---|---|
| Teks naratif | **512 token** | 75 token (15%) | Sweet spot tervalidasi benchmark |
| Tabel kecil | Hingga **1.024 token** | Tidak ada | Pertahankan utuh |
| Tabel besar | 512–768 per kelompok baris | Repeat headers | Headers memberikan konteks |
| Rumus + penjelasan | 200–512 token | 50 token | Atomic unit |
| Contoh soal + jawaban | 768–1.024 token | Tidak ada | Full problem + solution |
| Parent chunk | 1.000–1.500 token | N/A | Konteks level section |

### Penanganan khusus konten akuntansi

Untuk **tabel angka** (cost sheet, variance analysis): konversi ke Markdown format dengan headers, prepend setiap chunk tabel dengan judul section, caption, dan deskripsi singkat. Contoh: `[Section: Chapter 8 > Standard Costing > Material Variance Analysis] Table: Material Cost Variance Summary | Item | Std Qty | Act Qty | Price Var | Usage Var |`. Metadata yang disimpan: `type: "table"`, `table_title`, `row_range`, `column_names`.

Untuk **rumus matematika**: jangan pernah memisahkan rumus dari penjelasannya. Simpan dalam notasi LaTeX **dan** deskripsi natural language: `BEP (units) = FC / (P - VC)` disertai "Break-Even Point equals Fixed Costs divided by Contribution Margin per Unit." Buat juga formula index chunk per chapter — chunk khusus yang mendaftar rumus-rumus kunci dengan deskripsi, berfungsi sebagai high-relevance retrieval target.

Untuk **diagram/flowchart**: ekstrak sebagai gambar lalu gunakan Vision LLM (Qwen-VL) untuk menghasilkan deskripsi tekstual terstruktur. Flowchart process costing dikonversi menjadi: "WIP → [Dept 1: Materials $X, Conversion $Y] → Transfer to Dept 2 → Finished Goods."

---

## B. Supervisor with tool-calling adalah pola multi-agent terbaik

Dari lima pola multi-agent yang dievaluasi, **Supervisor with Tool-Calling + Adaptive Complexity Routing** menjadi pilihan optimal karena menghasilkan API call paling efisien (2–5 call per query vs 6+ untuk full supervisor atau 10+ untuk hierarchical), sekaligus mempertahankan fleksibilitas penuh untuk query kompleks lintas topik.

### Perbandingan pola arsitektur

| Pola | Cocok untuk Agentic RAG + GraphRAG | Efisiensi API | Penanganan Cross-topic | Skalabilitas |
|---|---|---|---|---|
| **Network (Peer-to-peer)** | Rendah — tidak ada koordinasi sentral | Sedang | Buruk | Buruk (O(n²)) |
| **Supervisor** | Tinggi — natural untuk routing vector + graph | Sedang (6+ call) | Baik | Baik |
| **Supervisor + Tool-Calling** | **Tertinggi** ⭐ | **Terbaik (2–5 call)** | **Excellent** | **Excellent** |
| **Hierarchical** | Tinggi tapi over-engineered | Terburuk (10+ call) | Excellent | Excellent |
| **Custom/Hybrid** | Bergantung desain | Bervariasi | Bervariasi | Bervariasi |

LangChain sendiri kini merekomendasikan pola tool-calling di atas library `langgraph-supervisor` untuk sebagian besar use case. Keunggulan utamanya: supervisor membuat **satu LLM call** yang dapat menginvoke multiple tools (`vector_search`, `graph_query`, `reranker`, `calculator`) secara sekuensial dalam satu reasoning loop, menghindari overhead multiple intermediate LLM call.

### Desain adaptive routing untuk efisiensi biaya

Karena mayoritas query akuntansi bersifat faktual/eksplanatif, adaptive routing menghemat **40–60% API call** dengan mengarahkan query sederhana langsung ke single-step RAG:

```
Query → Complexity Classifier (lightweight, 1 LLM call)
  ├── Simple   → Direct vector RAG → Generate             [2 LLM calls total]
  ├── Medium   → Vector + Reranker → Generate             [3 LLM calls total]
  ├── Complex  → Vector + Graph + Reranker + CRAG → Generate [4-5 LLM calls total]
  └── Calculation → Formula lookup + Calculator → Generate [2-3 LLM calls total]
```

### Workflow untuk query lintas topik

Untuk query seperti *"Bandingkan activity-based costing dengan traditional costing dalam konteks balanced scorecard"*, sistem melakukan: (1) **Query decomposition** — mengidentifikasi tiga konsep inti: ABC costing, traditional costing, balanced scorecard; (2) **Parallel retrieval** — `vector_search("activity-based costing")`, `vector_search("traditional costing")`, `graph_query("ABC → BSC relationships")`; (3) **Reranking** — Qwen3-Reranker-8B mengurutkan dan deduplikasi hasil gabungan; (4) **Synthesis** — Qwen3-30B-A3B menghasilkan jawaban komparatif dalam bahasa Indonesia dengan referensi ke textbook sumber.

---

## C. LangGraph untuk orkestrasi, LightRAG untuk graph retrieval

Stack orkestrasi menggunakan **LangGraph** (graph-based state machine) dan **LightRAG** (GraphRAG engine dengan native SiliconFlow integration). LightRAG memiliki demo resmi `lightrag_siliconcloud_demo.py` yang mengkonfirmasi kompatibilitas penuh dengan SiliconFlow API.

**LangGraph untuk orkestrasi** — menyediakan graph-based state machine dengan kontrol eksplisit atas alur kerja agent. Fitur `create_react_agent` dengan tool calling langsung mendukung pola Supervisor + Tool-Calling. Integrasi SiliconFlow dikonfirmasi bekerja melalui `ChatOpenAI(base_url="https://api.siliconflow.com/v1", model="Qwen/Qwen3-30B-A3B-Instruct-2507")`. Ekosistem terbesar (LangChain + LangGraph), dengan LangSmith untuk tracing/debugging.

**LightRAG untuk GraphRAG** — mendukung lima mode query (naive, local, global, hybrid, mix) dan incremental graph updates tanpa full reindexing. Dalam benchmark legal document QA, LightRAG Mix mode mencapai akurasi **0,887**.

---

## D. MinerU (primer) + Docling (sekunder) membentuk pipeline parsing optimal

Dari 10+ parser yang dievaluasi, **MinerU** (OpenDataLab) dan **Docling** (IBM, MIT license) muncul sebagai pasangan terbaik untuk textbook akuntansi, mengungguli solusi berbayar seperti Azure Document Intelligence untuk mayoritas use case. **MinerU direkomendasikan sebagai parser primer** karena pipeline backend-nya telah dioptimasi khusus untuk minimum 6 GB VRAM melalui sequential model loading (ModelSingleton pattern) dan parameter `--vram` di CLI — ideal untuk GTX 1660 Ti. Docling berfungsi sebagai fallback untuk dokumen yang gagal di MinerU, atau sebaliknya.

### Perbandingan kemampuan kritis

| Parser | Tabel Kompleks | Rumus → LaTeX | Multi-kolom | OCR Scanned | Kecepatan GPU (GTX 1660 Ti est.) | Lisensi | Biaya |
|---|---|---|---|---|---|---|---|
| **MinerU** | Baik (HTML output) | ✅ UniMERNet | ✅ | ✅ paddleocr2torch | **~0,3–0,8 hal/s** | AGPL-3.0 | **$0** |
| **Docling** | **97,9%** akurasi | F1 0,968 | ✅ | ✅ | **~1–2 hal/s** | MIT | **$0** |
| **Marker** | Sedang | Partial LaTeX | ✅ | ✅ Surya | ~0,5 hal/s | GPL-3.0 | $0 (research) |
| **PyMuPDF** | ❌ | ❌ | ❌ | ❌ | **~100+ hal/s** (CPU) | AGPL-3.0 | $0 |
| **pdfplumber** | Baik (dengan konfigurasi) | ❌ | ❌ | ❌ | ~100+ hal/s (CPU) | MIT | $0 |
| **Azure DI** | Excellent | Add-on | ✅ | ✅ | Cloud | Proprietary | $150–2.000 |
| **olmOCR** | Sedang | Basic | ✅ Excellent | ✅ VLM | Memerlukan ≥10 GB VRAM | Apache 2.0 | $0 + GPU |
| **Nougat** | Terbatas | **Excellent** | ✅ | ✅ VLM | Sangat lambat | MIT | $0 |

**MinerU** unggul sebagai parser primer karena: (1) pipeline backend telah sepenuhnya mengganti PaddlePaddle dengan **paddleocr2torch** (PP-OCRv5), menghilangkan dependency PaddlePaddle dan menyederhanakan instalasi ke PyTorch-only; (2) sequential model loading via ModelSingleton pattern (DocLayout-YOLO → YOLOv8-MFD → UniMERNet → PaddleOCR2Torch → RapidTable) memastikan peak VRAM hanya sebesar model terbesar, bukan total semua model; (3) output tabel dalam format HTML lebih baik untuk tabel akuntansi dengan merged cells; (4) konversi rumus ke LaTeX via UniMERNet.

**Docling** melengkapi sebagai parser sekunder dengan akurasi ekstraksi tabel **97,9%** (benchmark Procycons), formula recognition F1 **0,968**, dan lisensi MIT yang paling permisif. Granite-Docling-258M VLM berukuran hanya 258M parameter namun mencapai TEDS 0,97 untuk table structure recognition. Pada GTX 1660 Ti, total VRAM model Docling (layout Heron ~172 MB + TableFormer ~150 MB + RapidOCR ~200 MB) hanya **~0,5–1 GB** — sangat nyaman di 6 GB.

### Pipeline parsing yang direkomendasikan (dioptimasi untuk GTX 1660 Ti 6 GB)

```
Langkah 1: PyMuPDF → quick scan (CPU, ~0,12 s/halaman)
           Menentukan PDF text-based atau scanned

Langkah 2a: Text-based PDF → Docling di GPU lokal
            Config: AcceleratorDevice.CUDA, layout_batch_size=4,
            ocr_batch_size=4, RapidOcrOptions(backend="torch")
            Kecepatan: ~1–2 halaman/detik

Langkah 2b: Scanned/complex PDF → MinerU pipeline backend di GPU lokal
            Config: --vram 6, sequential model loading
            Kecepatan: ~0,3–0,8 halaman/detik

Langkah 3: Output gabungan → Structured Markdown + HTML tables + LaTeX formulas

Langkah 4: Diagram → ekstrak sebagai gambar → VLM captioning (Qwen-VL via SiliconFlow API)

Langkah 5: Post-processing cleanup (opsional LLM untuk edge case)
```

**Catatan kritis untuk 6 GB VRAM:** Jangan pernah menjalankan Docling dan MinerU secara bersamaan di GPU yang sama. Proses setiap stage secara berurutan dengan cleanup VRAM penuh di antaranya:

```python
del model
import gc; gc.collect()
torch.cuda.empty_cache()
torch.cuda.synchronize()
```

Gunakan `PYTORCH_CUDA_ALLOC_CONF='max_split_size_mb:512'` untuk mengurangi memory fragmentation, dan selalu gunakan FP16 (`model.half()`) karena GTX 1660 Ti mendapat ~2× throughput pada FP16 versus FP32.

**Batasan MinerU di GTX 1660 Ti:** Backend VLM-auto-engine membutuhkan ≥10 GB VRAM dan Hybrid-auto-engine membutuhkan ≥8 GB — keduanya tidak bisa dijalankan di GTX 1660 Ti. Hanya pipeline backend (accuracy score 82+ di OmniDocBench) yang tersedia. Untuk akurasi lebih tinggi pada dokumen tertentu, MinerU menyediakan opsi HTTP-client mode yang hanya membutuhkan 3 GB VRAM lokal dengan VLM berjalan di server remote.

### Estimasi waktu pemrosesan untuk 100 textbook (~200.000 halaman)

| Skenario | Estimasi Waktu | Keterangan |
|---|---|---|
| MinerU pipeline backend di GTX 1660 Ti | ~70–185 jam (~3–8 hari) | 0,3–0,8 hal/s, full pipeline (layout + formula + OCR + table) |
| Docling di GTX 1660 Ti | ~28–56 jam (~1–2 hari) | 1–2 hal/s, standard pipeline tanpa heavy OCR |
| Kombinasi MinerU + Docling | ~40–80 jam (~2–4 hari) | Docling untuk mayoritas; MinerU untuk halaman kompleks |
| Docling CPU-only | ~172 jam (~7 hari) | Tanpa GPU, sebagai worst-case fallback |

---

## E. Router agentic RAG + CRAG + LightRAG hybrid sebagai arsitektur retrieval

Evaluasi tujuh pola arsitektur RAG mengarahkan pada kombinasi **Router Agentic RAG + Corrective RAG (CRAG) + Tool-Augmented + Hybrid Retrieval (vector + graph)** sebagai arsitektur paling seimbang untuk domain akuntansi.

### Mengapa kombinasi ini?

**Router** menghemat ~40% biaya API dengan mengklasifikasi query sebelum retrieval — query definisi sederhana tidak perlu melewati graph traversal dan CRAG loop. **CRAG** menambahkan quality gate kritis untuk domain akuntansi di mana kesalahan rumus atau standar akuntansi berdampak nyata; setiap dokumen yang di-retrieve dievaluasi relevansinya dan di-reformulasi jika di bawah threshold. **Tool augmentation** menangani query kalkulasi (break-even, variance analysis, overhead allocation) melalui calculator tool tanpa memerlukan LLM call tambahan. **Hybrid retrieval** (vector + graph + BM25) memastikan cakupan penuh: vector search untuk query semantik, BM25 untuk terminologi eksak (GAAP, IFRS, nomor standar), dan graph traversal untuk query relasional.

Riset HybridRAG menunjukkan kombinasi vector + graph mencapai faithfulness **0,96** vs vector-only **0,94** dan answer relevancy **0,96** vs **0,91**. LightRAG secara native mengintegrasikan vector dan graph retrieval dalam satu engine, mengeliminasi kebutuhan untuk membangun integration layer custom.

### Integrasi GraphRAG + vector search via LightRAG

LightRAG menangani integrasi ini secara built-in melalui arsitektur dual-level: (1) **Saat ingestion**, entitas dan relasi diekstrak dan disimpan di graph, sementara chunk teks di-embed di vector store; (2) **Saat query**, keywords diekstrak untuk graph entity matching, query di-embed untuk vector similarity search, graph neighborhood ditarik untuk konteks terhubung (1–2 hop), lalu hasil low-level (entity spesifik) dan high-level (tema) digabung dan dikirim ke LLM.

Untuk query routing optimal:

| Tipe Query | Mode LightRAG | Contoh | Est. API Calls |
|---|---|---|---|
| Definisi konsep | `local` | "Apa itu ABC costing?" | 2 |
| Penjelasan konseptual | `naive` (vector) | "Jelaskan konsep relevant cost" | 2 |
| Kalkulasi | Formula graph + calculator tool | "Hitung BEP jika FC=100rb" | 2–3 |
| Perbandingan | `hybrid` | "Bandingkan absorption vs variable costing" | 3–4 |
| Sintesis lintas textbook | `mix` | "Rangkum pendekatan variance analysis" | 4–5 |
| Lookup standar | BM25/exact | "IAS 2 tentang apa?" | 2 |

### Skema knowledge graph untuk domain akuntansi

Entity types: `CostType`, `CostingMethod`, `CostAllocationMethod`, `CostDriver`, `AccountingStandard`, `ManagementTechnique`, `Formula`, `FinancialStatement`, `Industry`, `DecisionType`. Relationship types yang kritis: `CostingMethod --USES→ CostDriver`, `CostingMethod --CONTRASTS_WITH→ CostingMethod`, `ManagementTechnique --USES_FORMULA→ Formula`, `Formula --HAS_VARIABLE→ CostType`, `AccountingStandard --GOVERNS→ CostingMethod`, `Concept --PREREQUISITE_OF→ Concept`. Contoh triplet: `(ABC_Costing, USES, Cost_Drivers)`, `(Break_Even_Point, FORMULA, "FC/(P-VC)")`, `(Absorption_Costing, CONTRASTS_WITH, Variable_Costing)`.

---

## F. Infrastruktur pendukung: vector DB, cross-lingual, GPU lokal, dan SiliconFlow

### Qdrant Cloud Free Tier sebagai vector database

Dari tujuh vector database yang dievaluasi, **Qdrant Cloud** menawarkan keseimbangan terbaik: **1 GB RAM + 4 GB disk gratis selamanya** tanpa kartu kredit, hybrid search (dense + sparse vectors), metadata filtering kaya, dan integrasi penuh dengan LangChain/LlamaIndex. Dengan scalar quantization (kompresi 4×), free tier dapat menyimpan **~500.000 vektor** pada dimensi 1.024 — lebih dari cukup untuk 100 textbook (~120.000 chunk). Alternatif kuat: **Supabase (pgvector)** dengan 500 MB gratis, ideal jika memerlukan relational data (user management, chat logs) dalam satu database.

### Strategi cross-lingual tanpa translasi query

Qwen3-Embedding-8B mendukung **100+ bahasa** termasuk bahasa Indonesia dan menduduki peringkat #1 di MTEB Multilingual Leaderboard. Strategi yang direkomendasikan: **direct multilingual embedding tanpa translasi query**. Embed chunk textbook Inggris dan query Indonesia langsung menggunakan model yang sama — cross-lingual matching terjadi otomatis dalam shared embedding space. Qwen3-Reranker-8B juga mendukung cross-lingual scoring dengan cross-attention yang lebih dalam. Untuk terminologi akuntansi yang sulit diterjemahkan, gunakan **bilingual glossary** (~200–500 istilah kunci) sebagai system prompt dan **hybrid search** (dense + BM25) agar keyword matching menangkap istilah Inggris meskipun query dalam bahasa Indonesia.

Instruksi embedding yang direkomendasikan (tulis dalam bahasa Inggris per rekomendasi Qwen): `"Instruct: Retrieve English accounting textbook passages relevant to the Indonesian accounting query\nQuery: [query]"`.

### GPU lokal GTX 1660 Ti 6 GB: strategi pemanfaatan optimal

GTX 1660 Ti (TU116, Compute Capability 7.5, arsitektur Turing) **sepenuhnya kompatibel** dengan PyTorch, Transformers, ONNX Runtime, dan CUDA 12.6+. Strategi pemanfaatannya bersifat **hybrid: GPU lokal untuk parsing, cloud API untuk kecerdasan** (embedding + entity extraction + generation).

**Komponen yang dijalankan di GPU lokal:**

| Komponen | VRAM Estimasi | Speedup vs CPU |
|---|---|---|
| Layout detection (Docling Heron / MinerU DocLayout-YOLO) | ~0,5–1 GB | 5–14× |
| OCR text extraction (RapidOCR torch / paddleocr2torch) | ~200–500 MB | ~8× |
| Table structure recognition (TableFormer / RapidTable) | ~300–500 MB | ~4× |
| Formula detection (YOLOv8-MFD) | ~200–500 MB | Signifikan |

**Komponen yang tetap di cloud API (SiliconFlow):**

| Komponen | Alasan | Biaya API |
|---|---|---|
| Embedding (Qwen3-Embedding-8B) | Model 8B butuh ~16 GB VRAM; lokal terlalu lambat (~33 hari untuk 200K halaman) | ~$4–8 total |
| Entity extraction LightRAG (Qwen3-30B-A3B) | Model 30B mustahil dijalankan lokal; model kecil (4B) menghasilkan ~50–70% success rate vs ~85–95% untuk 30B | ~$5–15 total |
| Generation (query-time) | Real-time inference memerlukan throughput tinggi | ~$3–15/bulan |
| VLM captioning diagram (Qwen-VL) | Model VLM besar membutuhkan VRAM signifikan | Pay-per-use |

**Keterbatasan hardware yang harus dipahami:**

- **Tidak memiliki Tensor Cores** — hanya RTX Turing (RTX 2060+) yang memilikinya. FP16 berjalan via dedicated FP16 cores dengan throughput ~11 TFLOPS (2× FP32), bukan 8×+ yang tersedia di RTX cards.
- **Tidak mendukung BF16** — selalu gunakan `torch.float16`, jangan pernah `torch.bfloat16`.
- **Flash Attention 2 tidak officially supported** — versi resmi Dao-AILab membutuhkan CC 8.0+ (Ampere). Ada community fork `flash-attention-2080ti` yang bekerja di Turing dengan FP16 only.
- **GTX 1660 Ti (CC 7.5) saat ini merupakan batas minimum** dukungan PyTorch cu128 — kompatibel sekarang, tetapi berisiko di-drop di versi mendatang.

**Setup yang direkomendasikan:**

| Komponen | Versi |
|---|---|
| CUDA Toolkit | 12.6 atau 12.8 |
| PyTorch | 2.7.x dengan cu126 wheels (lebih aman dari cu128 untuk longevity) |
| NVIDIA Driver | ≥560 (untuk CUDA 12.6+) |
| OS | Linux native preferred; WSL2 acceptable dengan ~10–33% overhead |
| Python | 3.10–3.12 |

Instalasi: `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126`

### SiliconFlow: biaya sangat terjangkau

| Model | Harga (per 1M token) | Catatan |
|---|---|---|
| Qwen3-Embedding-8B | **$0,04** (input) | 33K context, MRL hingga 4.096 dim |
| Qwen3-Reranker-8B | **~$0,04** | 33K context |
| Qwen3-30B-A3B-Instruct-2507 | **$0,10** input / **$0,39** output | 262K context, MoE (3B active) |

**Estimasi biaya ingestion (one-time):** embedding 100 textbook (~100M token) menggunakan Qwen3-Embedding-8B **~$4**. Entity extraction LightRAG via Qwen3-30B-A3B **~$5–15**. **Total one-time: ~$10–25** (revisi dari estimasi awal ≤$100 yang memperhitungkan GPU rental).

**Estimasi biaya operasional (bulanan):** per query ~**$0,001** (0,1 sen). Monthly: **$3–15** untuk 100–500 query/hari. API bersifat OpenAI-compatible, bekerja langsung dengan OpenAI SDK. Free credit $1 untuk user baru. Rate limit: 50 RPD (default), naik ke 1.000 RPD setelah pembelian ≥$10.

---

## Gambaran arsitektur sistem keseluruhan

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Chat Interface)                     │
│                    Bahasa Indonesia • Streamlit/Next.js               │
└────────────────────────────┬────────────────────────────────────────┘
                             │ User Query (Indonesian)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     QUERY PREPROCESSING LAYER                        │
│  • Language detection                                                │
│  • Bilingual glossary lookup (accounting terms EN↔ID)                │
│  • Query embedding via Qwen3-Embedding-8B (SiliconFlow)             │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              LANGGRAPH ORCHESTRATION LAYER (Agentic RAG)             │
│                                                                      │
│  ┌──────────────────────────────────────────────┐                   │
│  │     QUERY ROUTER (Complexity Classifier)      │                   │
│  │     Qwen3-30B-A3B • 1 LLM call               │                   │
│  └───┬──────────┬──────────┬──────────┬─────────┘                   │
│      │          │          │          │                               │
│      ▼          ▼          ▼          ▼                               │
│  [Simple]   [Medium]   [Complex]  [Calculation]                      │
│  2 calls    3 calls    4-5 calls  2-3 calls                          │
│                                                                      │
│  TOOLS:                                                              │
│  ├── vector_search(query, top_k) → Qdrant hybrid search             │
│  ├── graph_query(entities, mode) → LightRAG dual-level retrieval    │
│  ├── rerank(query, docs) → Qwen3-Reranker-8B                       │
│  ├── calculator(expression) → Python eval untuk BEP/variance/etc    │
│  └── crag_grade(query, docs) → Relevance evaluation                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│   QDRANT CLOUD   │ │   LIGHTRAG   │ │   CALCULATOR TOOL    │
│   (Vector Store) │ │  (GraphRAG)  │ │   (Python Native)    │
│                  │ │              │ │                      │
│ • Dense vectors  │ │ • Entity     │ │ • BEP formula        │
│   (Qwen3-Emb)   │ │   graph      │ │ • Variance analysis  │
│ • Sparse vectors │ │ • Dual-level │ │ • Overhead allocation│
│   (BM25)         │ │   retrieval  │ │ • Contribution margin│
│ • Metadata filter│ │ • FAISS/     │ │ • ROI, Residual Inc  │
│ • 1GB free tier  │ │   nano-vecdb │ │                      │
└──────────────────┘ └──────────────┘ └──────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CRAG QUALITY GATE                               │
│  • Grade relevance: CORRECT / AMBIGUOUS / INCORRECT                  │
│  • If LOW → reformulate query & re-retrieve                          │
│  • If CORRECT → proceed to generation                                │
└────────────────────────────┬────────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   RESPONSE GENERATION                                │
│  • Qwen3-30B-A3B-Instruct-2507 via SiliconFlow                     │
│  • System prompt: bilingual glossary + domain expertise              │
│  • Output: Indonesian with English technical terms in parentheses    │
│  • Source citations: textbook name, chapter, page                    │
│  • Step-by-step working for calculations                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Data flow ingestion pipeline (dioptimasi untuk GTX 1660 Ti)

```
PDF Textbooks (30–100 buku, ~200.000 halaman)
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1: PDF PARSING — GPU LOKAL (GTX 1660 Ti 6 GB)            │
│                                                                   │
│  PyMuPDF (CPU, 0,12 s/hal) → quick scan text-based vs scanned   │
│                                                                   │
│  ┌─────────────────────┐    ┌──────────────────────────┐        │
│  │ Text-based PDF      │    │ Scanned/Complex PDF      │        │
│  │ → Docling (GPU)     │    │ → MinerU pipeline (GPU)  │        │
│  │ batch_size=4        │    │ --vram 6                 │        │
│  │ ~1–2 hal/s          │    │ sequential model loading │        │
│  │ VRAM: ~0,5–1 GB     │    │ ~0,3–0,8 hal/s          │        │
│  └─────────┬───────────┘    │ VRAM: ~3–5 GB peak      │        │
│            │                └────────────┬─────────────┘        │
│            └──────────┬─────────────────┘                       │
│                       ▼                                          │
│  Output: Structured Markdown + HTML tables + LaTeX formulas      │
│  Diagram → gambar → VLM captioning (Qwen-VL via SiliconFlow)    │
│                                                                   │
│  ⚠️ KRITIS: Jangan jalankan Docling & MinerU bersamaan!         │
│     Setelah selesai satu parser: del model → gc.collect()        │
│     → torch.cuda.empty_cache() → torch.cuda.synchronize()       │
│                                                                   │
│  Estimasi waktu: ~40–80 jam (~2–4 hari)                          │
└──────────────────────────┬───────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2: HYBRID CHUNKING — CPU (tidak memerlukan GPU)           │
│                                                                   │
│  Structure-aware split (heading hierarchy)                        │
│  → Content-type specific split (tabel/rumus/naratif/contoh soal) │
│  → Parent-child hierarchy (HierarchicalNodeParser)               │
│  → Metadata enrichment (book, chapter, section, content_type)    │
│                                                                   │
│  Output: ~120.000 chunks tersimpan sebagai JSON/pickle di disk   │
└──────────┬───────────────────────────┬───────────────────────────┘
           ▼                           ▼
┌──────────────────────┐    ┌──────────────────────────────────┐
│ STAGE 3a:            │    │ STAGE 3b:                        │
│ VECTOR INDEX         │    │ GRAPH INDEX                      │
│ CLOUD API            │    │ CLOUD API                        │
│                      │    │                                  │
│ Qwen3-Emb-8B        │    │ LightRAG entity/relation         │
│ via SiliconFlow      │    │ extraction via Qwen3-30B-A3B     │
│ → Qdrant Cloud       │    │ → graph store (built-in)         │
│ dense + sparse       │    │                                  │
│ + metadata           │    │ Estimasi: ~$5–15                 │
│                      │    │ Waktu: ~8–24 jam                 │
│ Estimasi: ~$4–8      │    │                                  │
│ Waktu: ~4–12 jam     │    │                                  │
└──────────────────────┘    └──────────────────────────────────┘

Late chunking (Langkah 5) dieksekusi sebagai sub-proses di Stage 3a:
  → Kirim full section ke Qwen3-Embedding-8B via API
  → Proses secara batch (bukan real-time) untuk efisiensi biaya
```

---

## Tech stack lengkap yang direkomendasikan

| Layer | Komponen | Teknologi | Biaya |
|---|---|---|---|
| **LLM Provider** | Inference API | SiliconFlow (OpenAI-compatible) | ~$3–15/bulan |
| **Query Model** | Generation + Routing | Qwen3-30B-A3B-Instruct-2507 | $0,10/$0,39 per 1M token |
| **Embedding** | Vector encoding | Qwen3-Embedding-8B (1.024 dim via MRL) | $0,04 per 1M token |
| **Reranker** | Cross-encoder reranking | Qwen3-Reranker-8B | ~$0,04 per 1M token |
| **Orchestration** | Agent workflow | LangGraph + LangChain | Gratis (MIT) |
| **GraphRAG** | Graph + vector hybrid | LightRAG (HKUDS) | Gratis (MIT) |
| **Vector DB** | Dense + sparse storage | Qdrant Cloud Free Tier (1 GB) | **$0** |
| **Graph Store** | Entity-relationship | LightRAG built-in (nano-vectordb/NetworkX) | **$0** |
| **PDF Parser (primer)** | Scanned/complex PDFs | MinerU (OpenDataLab) — dioptimasi untuk 6 GB VRAM | Gratis (AGPL-3.0) |
| **PDF Parser (sekunder)** | Text-based PDFs | Docling (IBM) | Gratis (MIT) |
| **PDF Quick Scan** | Type detection | PyMuPDF (fitz) | Gratis (AGPL-3.0) |
| **GPU Lokal** | PDF parsing acceleration | NVIDIA GTX 1660 Ti 6 GB (CC 7.5, Turing) | **$0** (sudah dimiliki) |
| **Chunking** | Text splitting | LangChain TextSplitters + Chonkie (LateChunker) | Gratis |
| **Hierarchical Index** | Parent-child retrieval | LlamaIndex HierarchicalNodeParser | Gratis (MIT) |
| **VLM (diagrams)** | Image captioning | Qwen-VL via SiliconFlow | Pay-per-use |
| **Frontend** | Chat UI | Streamlit / Chainlit / Next.js | Gratis |
| **Hosting** | Application server | Railway / Render / fly.io | $5–20/bulan |
| **Monitoring** | Tracing & eval | LangSmith (free tier) / Langfuse (OSS) | $0 |
| **TOTAL ESTIMASI** | | | **$8–35/bulan** |

---

## Draft PRD (Product Requirements Document)

### 1. Tujuan produk

**Nama produk**: Trusty RAG Akmen — AI-Powered Cost & Management Accounting Assistant

**Visi**: Menyediakan asisten AI berbasis RAG yang mampu menjawab pertanyaan akuntansi biaya dan manajemen secara akurat, dengan referensi langsung ke textbook sumber, dalam bahasa Indonesia.

**Target pengguna**: Akuntan profesional, mahasiswa akuntansi tingkat lanjut, dan praktisi cost accounting di Indonesia yang memerlukan akses cepat ke pengetahuan dari 30–100 textbook berbahasa Inggris tanpa harus membaca seluruh buku.

**Problem statement**: Praktisi akuntansi memerlukan waktu signifikan untuk mencari informasi spesifik di antara puluhan textbook. Terminologi Inggris menjadi barrier tambahan. Kalkulasi manual rentan kesalahan. Tidak ada sistem yang mengintegrasikan knowledge base akuntansi dengan kemampuan kalkulasi dan cross-reference.

**Success metrics**: Retrieval accuracy ≥85% pada accounting-specific queries; response time ≤10 detik untuk query sederhana, ≤20 detik untuk query kompleks; user satisfaction score ≥4,0/5,0; biaya operasional ≤$35/bulan untuk 500 query/hari.

### 2. Fitur utama

**F1 — Tanya Jawab Akuntansi Cerdas**: Menjawab pertanyaan konseptual (definisi, penjelasan, prosedur) dengan referensi ke textbook sumber (nama buku, chapter, halaman). Mendukung query bahasa Indonesia meskipun sumber bahasa Inggris. Menampilkan istilah teknis Inggris dalam tanda kurung untuk kejelasan.

**F2 — Kalkulasi Otomatis**: Menghitung break-even point, variance analysis (material, labor, overhead), overhead allocation rate, contribution margin, ROI, residual income, dan formula akuntansi lainnya. Menampilkan langkah-langkah perhitungan secara detail.

**F3 — Perbandingan Konsep**: Membandingkan metode costing (job order vs process vs ABC), pendekatan (absorption vs variable costing), dan teknik manajemen. Menggunakan knowledge graph untuk mengidentifikasi relasi antarkonsep lintas textbook.

**F4 — Cross-Reference Textbook**: Menyajikan pandangan dari multiple textbook untuk satu topik. Mengidentifikasi konsensus dan perbedaan pendekatan antarpenulis.

**F5 — Navigasi Berbasis Topik**: Memungkinkan pengguna menelusuri topik melalui knowledge graph visual (opsional). Menampilkan prerequisite concepts dan related topics.

### 3. Persyaratan teknis

**PT1 — Arsitektur**: Agentic RAG + GraphRAG menggunakan LangGraph (orkestrasi), LightRAG (graph retrieval), Qdrant (vector storage). Pattern: Supervisor with Tool-Calling + Adaptive Complexity Routing.

**PT2 — Model AI**: Semua model inference diakses via SiliconFlow API (OpenAI-compatible). Qwen3-30B-A3B untuk generation/routing, Qwen3-Embedding-8B untuk encoding, Qwen3-Reranker-8B untuk reranking.

**PT3 — Data Pipeline**: PDF parsing via MinerU (primer) + Docling (sekunder) di **GPU lokal GTX 1660 Ti 6 GB**. Hybrid chunking (structure-aware + content-type specific + late chunking via API). Parent-child indexing. Incremental ingestion (tambah textbook tanpa reindex seluruhnya).

**PT4 — Cross-lingual**: Direct multilingual embedding tanpa translasi query. Bilingual glossary (200–500 istilah akuntansi EN↔ID) sebagai system prompt. Hybrid search (dense + BM25) untuk menangkap terminologi Inggris dari query Indonesia.

**PT5 — Quality Assurance**: CRAG quality gate untuk setiap retrieval. Source citation wajib di setiap response. Disclaimer untuk kalkulasi ("verifikasi hasil dengan sumber resmi").

### 4. Batasan (constraints)

- **Budget**: Operasional ≤$35/bulan; one-time setup ~$10–25 (embedding + entity extraction via API — GPU rental tidak diperlukan karena tersedia GPU lokal).
- **GPU lokal terbatas**: GTX 1660 Ti 6 GB VRAM cukup untuk parsing PDF (Docling + MinerU), tetapi **tidak cukup** untuk menjalankan embedding model 8B atau LLM generation secara lokal. Semua inference LLM tetap via SiliconFlow API.
- **Sumber data tertutup**: Hanya textbook yang di-ingest; tidak melakukan web search untuk jawaban.
- **Bukan pengganti akuntan profesional**: Sistem memberikan informasi referensial, bukan advice profesional.
- **Bahasa**: Input bahasa Indonesia; sumber bahasa Inggris; output bahasa Indonesia dengan istilah teknis Inggris.
- **Rate limit SiliconFlow**: 50–1.000 RPD bergantung tier; perlu request queuing untuk peak usage.
- **Kompatibilitas GPU**: GTX 1660 Ti (CC 7.5) saat ini merupakan batas minimum PyTorch cu128 — perlu dipantau untuk versi mendatang. Gunakan cu126 wheels untuk margin keamanan.

### 5. Milestone pengembangan

**Phase 1 — Foundation (Minggu 1–3)**

Scope: MVP dengan basic RAG pipeline. Setup SiliconFlow API integration + LangChain. PDF parsing 5–10 textbook kunci via MinerU/Docling **di GPU lokal**. Recursive chunking 512 token + embedding ke Qdrant via Qwen3-Embedding-8B API. Simple vector RAG: query → embed → retrieve → rerank → generate. Chat UI sederhana (Streamlit/Chainlit). **Validasi kualitas parsing** — terutama untuk tabel variance analysis dan rumus overhead allocation yang merupakan konten paling menantang.

Deliverable: Sistem Q&A dasar yang berfungsi untuk query sederhana.

**Phase 2 — GraphRAG Integration (Minggu 4–6)**

Scope: Menambahkan knowledge graph. Setup LightRAG dengan SiliconFlow API. Entity/relationship extraction dari chunk yang sudah ada. Custom prompt engineering untuk domain akuntansi. Hybrid retrieval: vector (Qdrant) + graph (LightRAG). Query routing sederhana (dua jalur: simple vs hybrid).

Deliverable: Sistem mampu menjawab query relasional dan perbandingan konsep.

**Phase 3 — Agentic Orchestration (Minggu 7–9)**

Scope: Multi-agent dengan LangGraph. Implement Supervisor + Tool-Calling pattern. Adaptive complexity routing (simple/medium/complex/calculation). Calculator tool untuk formula akuntansi. CRAG quality gate. Bilingual glossary integration.

Deliverable: Sistem lengkap dengan routing cerdas dan kalkulasi otomatis.

**Phase 4 — Scale & Optimize (Minggu 10–12)**

Scope: Scaling ke full corpus + optimasi. **Ingest remaining textbook (hingga 100 buku) menggunakan GPU lokal** — estimasi ~2–4 hari continuous processing. Late chunking implementation via API batch. Parent-child hierarchical indexing. Semantic caching untuk query frequent. Monitoring via LangSmith/Langfuse. Performance benchmarking dan tuning.

Deliverable: Sistem production-ready untuk 100 textbook.

**Phase 5 — Polish & Launch (Minggu 13–14)**

Scope: UI/UX refinement, documentation, soft launch. Improved chat UI dengan source citations. User feedback collection mechanism. Dokumentasi teknis dan user guide. Soft launch ke kelompok beta tester (5–10 akuntan profesional).

Deliverable: Beta release siap untuk validasi pengguna.

---

## Insight kunci dan pertimbangan strategis

Keputusan arsitektural paling berdampak dalam sistem ini bukanlah pemilihan model atau framework, melainkan **kualitas pipeline parsing dan chunking**. Studi Vectara (NAACL 2025) mengonfirmasi bahwa konfigurasi chunking memengaruhi kualitas retrieval setidaknya sebesar pemilihan embedding model. Investasikan waktu terbanyak di Phase 1 untuk memvalidasi bahwa MinerU + Docling menghasilkan output bersih dari textbook akuntansi target — terutama untuk tabel variance analysis dan rumus overhead allocation yang merupakan konten paling menantang.

**LightRAG adalah enabler kritis** yang membuat arsitektur ini feasible dengan budget minimal. Native SiliconFlow demo dalam repository LightRAG mengeliminasi risiko kompatibilitas.

**Risiko utama** terletak pada kualitas entity extraction Qwen3-30B-A3B untuk knowledge graph construction. Riset E²GraphRAG menunjukkan model Qwen lebih lambat dalam menghasilkan structured JSON. Mitigasi: gunakan custom prompt yang lebih simpel dalam LightRAG, set retry mechanism, dan proses indexing textbook secara incremental satu per satu.

**Strategi cross-lingual tanpa translasi** dimungkinkan sepenuhnya oleh Qwen3-Embedding-8B yang merupakan #1 di MTEB Multilingual — sebuah keunggulan yang menghilangkan satu layer kompleksitas (translation service) dan mengurangi latency serta biaya. Kombinasikan dengan bilingual glossary dan hybrid search untuk memastikan terminologi akuntansi spesifik tetap tertangkap dengan baik meskipun query disampaikan sepenuhnya dalam bahasa Indonesia.

**GPU lokal sebagai akselerator parsing** mengubah ekonomi pipeline ingestion secara signifikan. Biaya one-time setup turun dari estimasi awal ≤$100 (yang memperhitungkan GPU rental) menjadi ~$10–25 (hanya biaya API embedding + entity extraction). Waktu parsing 200.000 halaman turun dari ~172 jam (CPU-only) menjadi ~40–80 jam. Namun, untuk embedding dan entity extraction, **cloud API tetap jauh lebih efisien** — menjalankan Qwen3-Embedding-8B secara lokal di GTX 1660 Ti akan memerlukan ~33 hari versus ~4–12 jam via API dengan biaya hanya $2–8. Prinsipnya jelas: **GPU lokal untuk compute-intensive parsing, cloud API untuk intelligence-intensive tasks**.
