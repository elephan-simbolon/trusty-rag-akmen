# Quality Checks

Panduan command untuk memeriksa kualitas RAG pipeline.

---

## 1. Quick Test (1 Query)

```bash
uv run python scripts/test_query.py "Apa itu break-even point?"
uv run python scripts/test_query.py "Apa itu break-even point?" -v   # tampilkan full state
```

Output: response, citations, query_type, crag_grade.

---

## 2. Citation Accuracy (20 Queries)

Mengukur apakah sumber yang dikutip sesuai ekspektasi. Target: **≥ 17/20 (85%)**.

```bash
# Jalankan evaluasi
uv run python scripts/evaluate_retrieval.py

# Verbose — tampilkan expected vs cited books per query
uv run python scripts/evaluate_retrieval.py -v

# Validasi struktur eval_queries.json saja (tanpa hit live services)
uv run python scripts/evaluate_retrieval.py --dry-run
```

Output: `data/eval/results.json`

---

## 3. RAGAS Evaluation (4 Metrik)

Evaluasi mendalam via LLM judge. Jalankan citation accuracy dulu sebelum ini.

```bash
# Step 1 — generate golden answers (sekali, hasilnya reusable)
uv run python scripts/evaluate_retrieval.py --generate-golden

# Step 2 — jalankan RAGAS
uv run python scripts/evaluate_retrieval.py --ragas

# Audit dulu (5 queries pertama)
uv run python scripts/evaluate_retrieval.py --ragas --batch-size 5

# Resume jika terputus
uv run python scripts/evaluate_retrieval.py --ragas --resume
```

Output: `data/eval/ragas_results.json`

| Metrik | Deskripsi |
|--------|-----------|
| Context Precision | Seberapa relevan chunks yang diambil |
| Context Recall | Apakah chunks mencakup isi golden answer |
| Answer Faithfulness | Apakah jawaban sesuai dengan sumber |
| Answer Relevance | Apakah jawaban menjawab pertanyaan |

---

## 4. Ranking Metrics (NDCG/MRR/Recall@K)

Evaluasi kualitas ranking hybrid search (pre-rerank, `retrieved_docs` top-20).
Membutuhkan `qrels.json` sebagai ground truth — generate sekali, reusable.

```bash
# Step 1 — generate qrels via LLM judge (sekali, seperti golden answers)
uv run python scripts/evaluate_retrieval.py --generate-qrels

# Audit dulu (3 queries)
uv run python scripts/evaluate_retrieval.py --generate-qrels --batch-size 3

# Step 2 — hitung ranking metrics
uv run python scripts/evaluate_retrieval.py --ranking

# Gabung dengan RAGAS dalam satu run
uv run python scripts/evaluate_retrieval.py --ragas --ranking
```

Output: `data/eval/ranking_results.json`

| Metrik | Mengukur |
|--------|----------|
| NDCG@5 | Kualitas ranking — doc relevan di posisi teratas |
| MRR@5 | Seberapa cepat doc relevan pertama muncul |
| Recall@5 | Coverage relevant docs di top-5 |
| Recall@10 | Coverage relevant docs di top-10 |

---

## 6. Unit Tests

```bash
uv run pytest          # semua test (pakai mock, tidak butuh live services)
uv run pytest -v       # verbose
uv run pytest tests/test_crag_evaluation.py   # test spesifik
```

---

## 7. Output Files

| File | Dibuat oleh | Isi |
|------|-------------|-----|
| `data/eval/results.json` | `evaluate_retrieval.py` | Citation pass/fail per query + summary accuracy |
| `data/eval/ragas_results.json` | `--ragas` | 4 metrik RAGAS per query + summary |
| `data/eval/ragas_results_partial.json` | `--ragas` | Checkpoint otomatis (untuk `--resume`) |
| `data/eval/golden_answers.json` | `--generate-golden` | Referensi jawaban untuk Context Recall |
| `data/eval/qrels.json` | `--generate-qrels` | Ground truth relevance per (query_id, doc_id) |
| `data/eval/ranking_results.json` | `--ranking` | Metrik NDCG/MRR/Recall@K |

---

## 8. Backend API (opsional)

Hasil RAGAS otomatis tersimpan ke DB jika backend berjalan saat evaluasi dijalankan.

```bash
# Jalankan backend
uv run uvicorn backend.main:app --reload --port 8000

# Ambil hasil eval terbaru
curl http://localhost:8000/api/eval/runs/latest

# List semua eval run
curl http://localhost:8000/api/eval/runs
```
