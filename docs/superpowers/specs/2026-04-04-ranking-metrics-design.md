# Design: Ranking Metrics (NDCG/MRR/Recall@K)

**Tanggal:** 2026-04-04
**Status:** Approved

## Konteks

Evaluasi retrieval yang ada (RAGAS) hanya mengukur kualitas konten (apakah chunk relevan?), tapi tidak mengukur **kualitas ranking** (apakah chunk relevan muncul di posisi teratas?). NDCG, MRR, dan Recall@K melengkapi RAGAS dengan mengukur posisi relatif hasil retrieval — metrik standar MTEB/BEIR untuk retrieval systems.

**Masalah**: `eval_queries.json` tidak punya ground truth per-chunk. Solusi: gunakan LLM-as-judge untuk generate qrels sekali, simpan sebagai `qrels.json` yang reusable.

## Pendekatan

**Scope**: `retrieved_docs` (20 docs pre-rerank) — bukan `reranked_docs`. Ini best practice MTEB/BEIR: evaluasi retrieval model secara terpisah dari reranker. RAGAS sudah mengukur `context_precision` dari reranked_docs, jadi keduanya saling melengkapi.

**Library**: `ranx` — fast, battle-tested, mendukung NDCG/MRR/Recall@K dengan API dict-based sederhana.

**Doc ID**: `str(doc["id"])` — Qdrant point ID, sudah ada di setiap doc, unik per chunk.

## Arsitektur & Data Flow

### Tahap 1: Qrels Generation (satu kali, reusable)

```
eval_queries.json
      ↓
graph.invoke() per query  →  retrieved_docs (20 docs per query)
      ↓
LLM judge per chunk       →  binary relevance (0=tidak relevan, 1=relevan)
      ↓
data/eval/qrels.json       ←  disimpan, dipakai ulang di semua run
```

LLM judge prompt:
```
Apakah teks berikut relevan untuk menjawab pertanyaan ini?
Query: {query}
Teks: {chunk_text}
Jawab: 1 (relevan) atau 0 (tidak relevan)
```

LLM: `settings.llm_model` (SiliconFlow) — tidak ada dependency baru.

Format `qrels.json`:
```json
{
  "generated_at": "2026-04-04T...",
  "model": "Qwen/Qwen3-30B-A3B-Instruct",
  "qrels": {
    "EVAL-01": {"12345": 1, "67890": 0, ...},
    "EVAL-02": {...}
  }
}
```

### Tahap 2: Compute Metrics (setiap eval run)

```
qrels.json  +  retrieved_docs dari run baru
      ↓
ranx.Qrels(qrels_dict)  +  ranx.Run(run_dict)
      ↓
ranx.evaluate(["ndcg@5", "mrr@5", "recall@5", "recall@10"])
      ↓
ranking_metrics → ragas_results.json (extended) + eval DB
```

`run_dict` menggunakan `score` (RRF fused score dari hybrid search) — bukan `rerank_score`. Ranking yang dievaluasi adalah output hybrid search, sebelum reranker mengubah urutan.

## Komponen

### File Baru

| File | Peran |
|------|-------|
| `src/evaluation/qrels_generator.py` | LLM judge per chunk → generate & simpan qrels.json |
| `src/evaluation/ranking_metrics.py` | Hitung NDCG/MRR/Recall@K dengan ranx dari qrels |

### File yang Dimodifikasi

| File | Perubahan |
|------|-----------|
| `scripts/evaluate_retrieval.py` | Tambah flag `--generate-qrels` dan `--ranking` |
| `src/evaluation/ragas_runner.py` | Tambah ranking metrics ke output summary dict |
| `backend/eval_db.py` | `summary_json` sudah JSON — ranking metrics masuk otomatis |
| `pyproject.toml` | Tambah `ranx` ke dependencies |
| `QUALITY_CHECKS.md` | Dokumentasi command baru |

## CLI Commands

```bash
# Step 1 — generate qrels (sekali, reusable seperti golden answers)
uv run python scripts/evaluate_retrieval.py --generate-qrels

# Step 2 — hitung ranking metrics
uv run python scripts/evaluate_retrieval.py --ranking

# Audit (5 queries pertama)
uv run python scripts/evaluate_retrieval.py --ranking --batch-size 5

# Gabung dengan RAGAS
uv run python scripts/evaluate_retrieval.py --ragas --ranking
```

## Output

**Tambahan di `ragas_results.json` summary:**
```json
{
  "summary": {
    "ndcg@5": 0.821,
    "mrr@5": 0.754,
    "recall@5": 0.700,
    "recall@10": 0.850,
    "context_precision": 0.959,
    ...
  }
}
```

**File baru:**
```
data/eval/qrels.json   ← ground truth relevance per (query, doc_id)
```

## Metrik yang Dihasilkan

| Metrik | Definisi | Mengukur |
|--------|----------|----------|
| NDCG@5 | Normalized Discounted Cumulative Gain | Kualitas ranking — doc relevan di posisi teratas |
| MRR@5 | Mean Reciprocal Rank | Seberapa cepat doc relevan pertama muncul |
| Recall@5 | Fraction of relevant docs in top-5 | Coverage relevant docs di 5 hasil teratas |
| Recall@10 | Fraction of relevant docs in top-10 | Coverage relevant docs di 10 hasil teratas |

## Verification

```bash
# 1. Install dependency baru
uv sync --dev

# 2. Generate qrels (audit 3 queries dulu)
uv run python scripts/evaluate_retrieval.py --generate-qrels --batch-size 3

# 3. Jalankan ranking metrics
uv run python scripts/evaluate_retrieval.py --ranking --batch-size 3

# 4. Cek output file
cat data/eval/qrels.json
cat data/eval/ragas_results.json | python -m json.tool | grep -E "ndcg|mrr|recall"

# 5. Unit tests
uv run pytest tests/test_ranking_metrics.py -v
```
