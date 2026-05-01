# Requirements: Trusty RAG Akmen

**Defined:** 2026-03-29
**Core Value:** Mempercepat pencarian referensi akuntansi dari 45-60 menit menjadi 5-10 menit, dengan source citation (buku, chapter, halaman) yang bisa dipertanggungjawabkan ke klien

## v1.1 Requirements

Requirements for Knowledge Protocol Engineering milestone. Each maps to roadmap phases.

### Protocol Engine

- [x] **PROT-01**: User mendapat respons terstruktur menggunakan framework analisis yang tepat (CVP, Variance, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General) berdasarkan topik query
- [x] **PROT-02**: User dapat mengirim query apapun dan sistem memilih protocol yang sesuai tanpa tambahan LLM call (rule-based keyword matching, fallback ke General)
- [x] **PROT-03**: User mendapat respons dengan section headers konsisten per protocol (## Jawaban Singkat, ## Analisis, ## Rekomendasi) dan few-shot format
- [x] **PROT-04**: User mendapat system prompt yang di-compose secara modular (persona + rules + protocol steps + synthesis block + glossary) menggantikan hardcoded prompts

### Domain Retrieval

- [x] **RETR-01**: User mendapat retrieval yang memfilter berdasarkan source_domain (accounting/consulting) sesuai konteks query
- [x] **RETR-02**: Semua existing Qdrant points di-backfill dengan source_domain="accounting" dan payload index dibuat sebelum domain filter aktif
- [x] **RETR-03**: User melihat [Sumber N] untuk referensi textbook akuntansi dan [Kerangka N] untuk referensi methodology consulting di setiap respons
- [x] **RETR-04**: Pipeline ingestion menerima --source-domain flag untuk menandai buku consulting vs accounting

### Consulting Ingestion

- [x] **INGEST-01**: 21 buku consulting/methodology di-ingest ke Qdrant dengan source_domain="consulting" melalui existing PDF parsing pipeline (Docling primary)
- [x] **INGEST-02**: Setiap chunk consulting memiliki metadata lengkap (book_title, chapter, page_start, page_end, author, source_domain) konsisten dengan format accounting chunks

## Future Requirements

None deferred for this milestone.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Consulting books ke fast-graphrag | Content mismatch — accounting entity types (CostType, CostDriver, Formula) tidak sesuai untuk procedural consulting knowledge; KPE protocols sudah encode framework selection |
| LLM-based protocol selection | Budget constraint ($8-35/bulan) — rule-based keyword matching mencapai 85-92% accuracy tanpa tambahan LLM call |
| Separate Qdrant collection per domain | Qdrant official recommendation: payload filter > collection sharding untuk logical domain separation; cross-domain query butuh single-collection RRF fusion |
| Knowledge graph visual / navigasi | Deferred dari v1.0 — kompleksitas UI tinggi, tidak kritis |
| Frontend UI changes untuk KPE | Protocol selection transparan ke user; respons format berubah tapi UI rendering (markdown) sudah handle section headers |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROT-01 | Phase 06 | Complete |
| PROT-02 | Phase 06 | Complete |
| PROT-03 | Phase 06 | Complete |
| PROT-04 | Phase 06 | Complete |
| RETR-01 | Phase 07 | Complete |
| RETR-02 | Phase 07 | Complete |
| RETR-03 | Phase 07 | Complete |
| RETR-04 | Phase 07 | Complete |
| INGEST-01 | Phase 08 | Complete |
| INGEST-02 | Phase 08 | Complete |

**Coverage:**
- v1.1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after roadmap creation*
