# Knowledge Protocol Engineering (KPE) untuk Trusty RAG Akmen

## Context

Trusty RAG Akmen saat ini merespons pertanyaan akuntansi manajemen dengan gaya "textbook answer" — retrieve, rerank, generate plain text. Respons sudah akurat dan ber-sitasi, tapi tidak terstruktur seperti analisis konsultan.

**Problem:** User membutuhkan respons yang mengadopsi cara berpikir, framework, dan gaya respons seperti konsultan McKinsey/BCG — structured problem solving, bukan sekadar retrieval-and-answer.

**Solution:** Two complementary layers:

1. **Knowledge Protocol Engineering (KPE)** — encode management accounting analytical frameworks sebagai executable reasoning templates (HOW to reason). Hardcoded di system prompts. Terinspirasi dari riset KPE (arXiv 2507.02760, Juli 2025).
2. **Consulting Book Ingestion** — ingest 21 buku consulting frameworks ke Qdrant (WHAT to reason about). Case studies, nuance, examples yang terlalu kaya untuk di-hardcode.

Dipilih karena:
- KPE alone: Qwen3 reliable untuk constrained completion, tapi hanya bisa encode step-by-step ringkas. 21 buku berisi ribuan case studies, decision trees, dan nuance yang tidak muat di prompt.
- Ingestion alone: retrieved chunks tanpa reasoning scaffold menghasilkan "textbook answer" — bukan structured analysis.
- **KPE + Ingestion**: protocol template provide structure, retrieved chunks provide evidence and nuance. Seperti konsultan yang tahu framework (dari training) dan punya data (dari research).

## Architecture Overview

### Pipeline Flow (Before vs After)

**Before (Phase 3):**
```
route → preprocess → retrieve → graph_retrieve → rerank → crag_grade → [generate | generate_calc | reformulate]
```
- `route_node` hanya classify: Simple | Calculation
- Generation menggunakan 3 generic prompt templates

**After (Phase 3 + KPE + Consulting Ingestion):**
```
route → preprocess → retrieve (with source_domain filter) → graph_retrieve → rerank → crag_grade → [generate | generate_calc | reformulate]
```
- `route_node` classify: Simple | Medium | Complex | Calculation
- `route_node` juga select protocol + determine retrieval domain
- `retrieve_node` applies `source_domain` filter when appropriate
- Generation: KPE template as reasoning scaffold + accounting context `[Sumber N]` + consulting context `[Kerangka N]`
- **Graph topology TIDAK berubah** — protocol selection embedded di `route_node`

### Key Design Decision: Protocol in State, Not Config

Protocol selection result (`selected_protocol`) masuk ke `RAGState` karena:
1. Protocol bisa berubah jika query di-reformulate (CRAG loop)
2. Protocol perlu accessible di `generate_node` yang sudah baca state
3. Ini bukan per-session config (seperti thread_id) — ini per-query computed value

## Protocol Registry

### Structure

File baru: `config/protocols.py`

Setiap protocol berisi:
```python
@dataclass
class Protocol:
    name: str              # e.g., "CVP Analysis"
    name_id: str           # Indonesian name, e.g., "Analisis Biaya-Volume-Laba"
    trigger_keywords: list[str]  # keyword matching
    query_types: list[str]       # applicable query types
    steps: list[str]       # reasoning steps (injected into prompt)
    output_sections: list[str]   # required Markdown headers
    few_shot_example: str  # 1 concrete example
```

### Protocol List (8 protocols)

| # | Protocol | Trigger Keywords | Query Types |
|---|----------|-----------------|-------------|
| 1 | CVP / Break-Even Analysis | "break-even", "BEP", "titik impas", "contribution margin", "margin kontribusi" | Simple, Medium, Calculation |
| 2 | Variance Analysis | "selisih", "variance", "anggaran vs realisasi", "varians" | Medium, Complex, Calculation |
| 3 | Activity-Based Costing | "ABC", "activity-based", "cost driver", "pemicu biaya" | Simple, Medium, Complex |
| 4 | Transfer Pricing | "transfer pricing", "harga transfer", "divisi" | Medium, Complex |
| 5 | Relevant Costing | "biaya relevan", "keputusan khusus", "make or buy", "buat atau beli", "special order" | Medium, Complex |
| 6 | Product Profitability | "profitabilitas", "lini produk", "margin produk", "product mix" | Medium, Complex |
| 7 | Budgeting & Planning | "anggaran", "budget", "perencanaan", "master budget" | Simple, Medium |
| 8 | Cost Classification & Behavior | "klasifikasi biaya", "fixed cost", "variable cost", "biaya tetap", "biaya variabel", "overhead" | Simple, Medium |

### Default Protocol

Jika tidak ada protocol yang match: gunakan **General Consulting Protocol** — Pyramid Principle format (jawaban singkat dulu, lalu penjelasan terstruktur).

## Query Classification Enhancement

### Current State (query_classifier.py)

Hanya 2 type:
- `Calculation`: keyword + number pattern
- `Simple`: everything else

### Enhanced Classification

4 type, rule-based (zero LLM calls):

```python
# Priority order (first match wins):
1. Calculation: existing rule (calc keyword + number)
2. Complex: application/strategy keywords ("bagaimana menerapkan", "strategi",
   "analisis kasus", "evaluasi", "rekomendasikan", "implementasi")
3. Medium: comparison/relationship keywords ("bandingkan", "perbedaan", "vs",
   "hubungan", "pengaruh", "dibandingkan", "perbandingan")
4. Simple: default
```

### Output Depth per Query Type

| Type | Output Format | Section Count |
|------|---------------|---------------|
| Simple | Jawaban Singkat → Penjelasan (poin-poin) → Contoh (optional) | 2-3 sections |
| Medium | Jawaban Singkat → Perbandingan/Analisis (table/MECE) → Implikasi | 3 sections |
| Complex | Konteks → Tantangan → Analisis (framework steps) → Rekomendasi → Langkah Implementasi | 4-5 sections |
| Calculation | Jawaban → Data yang Diketahui → Langkah Perhitungan → Verifikasi → Disclaimer | 4-5 sections |

## Prompt Architecture

### Prompt Assembly

```
System Prompt = Base Rules + Protocol Template + Output Format + Few-Shot Example + Glossary
```

- **Base Rules**: bilingual convention, citation rules `[Sumber N]`, no hallucination (existing)
- **Protocol Template**: framework-specific reasoning steps (NEW)
- **Output Format**: required Markdown sections per query_type (NEW)
- **Few-Shot Example**: 1 short example showing expected output structure (NEW)
- **Glossary**: existing glossary snippet

### Prompt Selection Matrix

| query_type | graph_context? | Protocol? | Prompt Used |
|------------|---------------|-----------|-------------|
| Calculation | any | any | `PROMPT_CALCULATION + protocol steps` |
| Simple | no | yes | `PROMPT_PROTOCOL_SIMPLE + protocol` |
| Simple | no | no | `PROMPT_GENERAL_SIMPLE` (fallback) |
| Simple | yes | any | `PROMPT_SYNTHESIS_SIMPLE + protocol` |
| Medium | no | yes | `PROMPT_PROTOCOL_MEDIUM + protocol` |
| Medium | yes | any | `PROMPT_SYNTHESIS_MEDIUM + protocol` |
| Complex | no | yes | `PROMPT_PROTOCOL_COMPLEX + protocol` |
| Complex | yes | any | `PROMPT_SYNTHESIS_COMPLEX + protocol` |

**Implementation: composable template builder, NOT 12 separate prompts.**
Satu fungsi `build_system_prompt(query_type, protocol, graph_context, glossary)` yang compose dari 3 base templates (Simple, Medium/Complex, Calculation) + optional protocol block + optional synthesis block. Matrix di atas hanya menunjukkan kombinasi logis, bukan file/variabel terpisah.

### Base Template Structure (example: Medium/Complex)

```
Kamu adalah konsultan akuntansi manajemen senior yang menganalisis masalah secara terstruktur.

Aturan:
1. Jawab dalam bahasa Indonesia. Gunakan istilah teknis Inggris dalam tanda kurung.
2. Setiap klaim HARUS disertai [Sumber N] inline.
3. JANGAN tulis nama pengarang di teks — gunakan HANYA [Sumber N].
4. Jika konteks tidak cukup, katakan dengan jujur.
5. Jangan mengarang informasi yang tidak ada di konteks.

{protocol_block}

Format jawaban:
{output_format}

{synthesis_block}

{few_shot_block}

Glosarium istilah:
{glossary_snippet}
```

### Protocol Block (example: CVP Analysis)

```
Framework Analisis: Cost-Volume-Profit (CVP) Analysis

Langkah analisis yang HARUS kamu ikuti:
1. Identifikasi komponen: biaya tetap (fixed cost), biaya variabel per unit (variable cost per unit), harga jual per unit (selling price per unit)
2. Hitung contribution margin per unit = harga jual - biaya variabel per unit
3. Hitung contribution margin ratio = CM per unit / harga jual
4. Tentukan break-even point: BEP (unit) = biaya tetap / CM per unit; BEP (Rp) = biaya tetap / CM ratio
5. Jika ada target laba: unit yang dibutuhkan = (biaya tetap + target laba) / CM per unit
6. Analisis sensitivitas: apa yang terjadi jika variabel berubah?
7. Berikan rekomendasi berdasarkan hasil analisis
```

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `config/protocols.py` | NEW | Protocol registry — 8 protocols + General fallback |
| `config/prompts.py` | MODIFY | Replace 3 flat prompts with 3 template builders + protocol injection |
| `src/retrieval/query_classifier.py` | MODIFY | Add `classify_query()` returning (query_type, protocol_name) |
| `src/agents/state.py` | MODIFY | Add `selected_protocol: Optional[str]` field |
| `src/agents/nodes.py` | MODIFY | Update `route_node` to use new classifier + set protocol. Update `generate_node`/`generate_calc_node` to pass protocol to generator |
| `src/generation/generator.py` | MODIFY | Accept `protocol` param, use prompt builder instead of flat prompt selection |

## Consulting Book Ingestion

### Strategy: Single Collection + source_domain Metadata

21 buku consulting di-ingest ke **collection Qdrant yang sama** (bukan collection terpisah):
- Setiap chunk mendapat `source_domain: "consulting"` di payload metadata
- Existing accounting chunks mendapat `source_domain: "accounting"` (backfill via script)
- Create payload index on `source_domain` untuk O(1) filtering

### Retrieval with Domain Awareness

`retrieve_node` membaca `selected_protocol` dari state:
- **No protocol matched** → retrieve tanpa filter (semua domain)
- **Accounting protocol matched** (CVP, variance, ABC, dll) → retrieve `source_domain: "accounting"` only
- **Framework analysis detected** (Complex queries) → retrieve tanpa filter (cross-domain, agar accounting data + consulting framework muncul bersama)

Implementasi: tambah optional `domain_filter` parameter ke `hybrid_search()` di `vector_search.py`.

### Citation Differentiation

Saat ini semua sitasi menggunakan `[Sumber N]`. Dengan dua domain:
- **Accounting sources** → `[Sumber N]` (factual reference) — format existing
- **Consulting sources** → `[Kerangka N]` (methodology reference) — format baru

`citation_builder.py` membedakan berdasarkan `source_domain` di metadata chunk.

Prompt instruction tambahan: "Referensi kerangka `[Kerangka N]` adalah alat analisis, bukan bukti empiris. Gunakan untuk struktur penalaran, bukan sebagai sumber fakta."

### Ingestion Pipeline

Existing `scripts/ingest.py` sudah support PDF ingestion. Perubahan:
- Tambah `--source-domain` CLI flag (default: "accounting")
- Pass `source_domain` ke metadata setiap chunk
- Backfill script untuk existing accounting chunks

**Note on `generate_calc_node`:** This node already uses `query_type="Calculation"` hardcoded. With KPE, it will also pass `selected_protocol` to `generate_response()`, so calculation queries get protocol-specific steps (e.g., CVP protocol for break-even calculations, Variance protocol for variance calculations). If no specific protocol matches, the existing calculation prompt serves as fallback.

| `src/retrieval/vector_search.py` | MODIFY | Add optional `domain_filter` param to `hybrid_search()` |
| `src/agents/nodes.py` (retrieve_node) | MODIFY | Pass `domain_filter` based on `selected_protocol` |
| `src/generation/citation_builder.py` | MODIFY | Differentiate `[Sumber N]` vs `[Kerangka N]` by `source_domain` |
| `scripts/ingest.py` | MODIFY | Add `--source-domain` CLI flag, pass to chunk metadata |
| `scripts/backfill_source_domain.py` | NEW | One-time script to add `source_domain: "accounting"` to existing Qdrant points |

**Zero changes:** `graph.py`, `backend/main.py`, `frontend/`

## Verification Plan

### Unit Tests

1. **Query Classifier** — test `classify_query()` with 20+ example queries covering all 4 types
2. **Protocol Matching** — test keyword matching returns correct protocol for representative queries
3. **Prompt Assembly** — test that prompt builder correctly injects protocol, output format, and few-shot for each query_type × protocol combination

### Integration Tests

4. **End-to-end pipeline** — run 5 representative queries (1 per type + 1 no-protocol-match) through full pipeline, verify:
   - Correct query_type classification
   - Correct protocol selection
   - Response contains expected Markdown sections
   - Citations still work correctly

### Manual Quality Check

5. **20 representative queries** (5 per type) — compare old vs new response quality:
   - Does the response follow the protocol structure?
   - Is the analysis more consultant-like?
   - Are citations preserved and accurate?
   - Is the bilingual convention maintained?
