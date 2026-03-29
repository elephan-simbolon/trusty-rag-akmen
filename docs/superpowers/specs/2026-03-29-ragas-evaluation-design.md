# Design Spec: RAGAS-style Evaluation System

**Tanggal:** 2026-03-29
**Status:** Approved
**Scope:** v1.1 milestone — evaluasi kualitas RAG end-to-end

---

## Context

Milestone v1.0 selesai dengan 40/40 requirements passed, tapi tidak ada cara untuk mengukur kualitas jawaban secara kuantitatif. Evaluasi yang ada (`scripts/evaluate_retrieval.py`) hanya mengecek apakah buku yang benar di-cite (binary PASS/FAIL), bukan kualitas jawaban sesungguhnya.

Kebutuhan: sistem evaluasi RAGAS-style yang mengukur 4 metrics standar RAG — context precision, context recall, answer faithfulness, answer relevance — menggunakan `ragas` library dengan SiliconFlow OpenAI-compatible client (dikonfirmasi dari dokumentasi resmi). Hasil evaluasi ditampilkan di dashboard UI React.

---

## Arsitektur

```
CLI Script  →  Backend API  →  Frontend Dashboard
(offline)      (REST)          (React SPA)
```

Tiga lapisan independen yang terhubung via REST:

1. **CLI** — `scripts/evaluate_retrieval.py --ragas` menjalankan evaluasi offline
2. **Backend** — 3 endpoint baru di FastAPI untuk menyimpan dan mengambil hasil
3. **Frontend** — tab "Evaluasi" baru di App.tsx (state-switching, tanpa react-router)

---

## Komponen Baru

### Python

| File | Deskripsi |
|------|-----------|
| `src/evaluation/__init__.py` | Package marker |
| `src/evaluation/golden_generator.py` | Generate & load golden answers satu kali |
| `src/evaluation/ragas_runner.py` | Orchestrator: 20 queries → 4 metrics via ragas library |
| `backend/eval_db.py` | SQLite CRUD untuk tabel `eval_runs` (pola persis `history_db.py`) |

### File Dimodifikasi

| File | Perubahan |
|------|-----------|
| `scripts/evaluate_retrieval.py` | Tambah `--ragas`, `--generate-golden`, `--resume`, `--batch-size`, delay flags |
| `backend/main.py` | Tambah 3 endpoint `/api/eval/*` |
| `pyproject.toml` | Tambah `ragas` ke dependencies |

### Frontend (TypeScript/React)

| File | Deskripsi |
|------|-----------|
| `frontend/src/types/eval.ts` | TypeScript interfaces untuk eval data |
| `frontend/src/hooks/useEvalData.ts` | Fetch hook untuk eval API (pola `useHistory.ts`) |
| `frontend/src/components/eval/MetricCard.tsx` | Card satu metric + progress bar CSS |
| `frontend/src/components/eval/RadarChart.tsx` | SVG radar chart 4-axis |
| `frontend/src/components/eval/DifficultyChart.tsx` | CSS bar chart per difficulty |
| `frontend/src/components/eval/QueryResultTable.tsx` | Tabel 20 query dengan color-coded scores |
| `frontend/src/components/EvalDashboard.tsx` | Container utama dashboard |
| `frontend/src/App.tsx` | Tambah `activeView` state + nav tab "Evaluasi" di header |

---

## RAGAS Library Integration

Menggunakan `ragas` library dengan SiliconFlow OpenAI-compatible client.
SiliconFlow dikonfirmasi OpenAI-compatible di `https://api.siliconflow.com/v1` (dari docs resmi).

```python
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    LLMContextPrecisionWithoutReference,
    ContextRecall,
    Faithfulness,
    AnswerRelevancy,
)
from config.settings import settings

client = AsyncOpenAI(
    api_key=settings.siliconflow_api_key.get_secret_value(),
    base_url=settings.siliconflow_base_url,  # https://api.siliconflow.com/v1
)
llm = llm_factory(settings.llm_model, client=client)
```

### Varian Metrics yang Dipilih

| Metric | Class ragas | Input | Butuh Golden? |
|--------|-------------|-------|---------------|
| Context Precision | `LLMContextPrecisionWithoutReference` | query + response + retrieved_contexts | Tidak |
| Context Recall | `ContextRecall` | query + retrieved_contexts + reference | Ya |
| Answer Faithfulness | `Faithfulness` | query + response + retrieved_contexts | Tidak |
| Answer Relevance | `AnswerRelevancy` | query + response + retrieved_contexts | Tidak |

`LLMContextPrecisionWithoutReference` dipilih untuk Context Precision karena tidak butuh golden answer — menilai relevansi chunk terhadap response yang dihasilkan, bukan reference eksternal.

---

## Golden Answers

Golden answers di-generate **satu kali** menggunakan LLM (`generate()` yang ada di `src/llm/client.py`) dari retrieved context (temperature=0.1), disimpan ke `data/eval/golden_answers.json`, dan di-reuse untuk semua run selanjutnya.

```bash
# Generate golden answers (jalankan sekali sebelum --ragas)
uv run python scripts/evaluate_retrieval.py --generate-golden
```

**Schema `data/eval/golden_answers.json`:**
```json
{
  "generated_at": "2026-03-29T10:00:00Z",
  "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
  "answers": {
    "EVAL-01": {
      "golden_answer": "Break-even point (BEP) adalah...",
      "source_docs": ["Cost Accounting/Chapter 3/hal. 85-87"]
    }
  }
}
```

**Caveat:** Golden answers di-generate dari context yang sama dengan yang diindeks — ini adalah self-referential grounding. Context Recall harus diinterpretasikan sebagai "seberapa cukup context RAG untuk menjawab query", bukan absolute ground truth. Flag `--golden-file <path>` disediakan untuk inject manual golden answers di masa depan.

---

## CLI Interface

```bash
# Step 1: Generate golden answers (jalankan sekali)
uv run python scripts/evaluate_retrieval.py --generate-golden

# Step 2: Full RAGAS evaluation
uv run python scripts/evaluate_retrieval.py --ragas

# Audit mode — 5 queries dulu sebelum full run
uv run python scripts/evaluate_retrieval.py --ragas --batch-size 5

# Resume jika interrupt (skip queries yang sudah selesai)
uv run python scripts/evaluate_retrieval.py --ragas --resume

# Custom delays (default: --inter-query-delay 5 --inter-judge-delay 2)
uv run python scripts/evaluate_retrieval.py --ragas --inter-query-delay 10 --inter-judge-delay 3

# Inject golden answers eksternal
uv run python scripts/evaluate_retrieval.py --ragas --golden-file path/to/golden.json

# Mode lama tetap berfungsi
uv run python scripts/evaluate_retrieval.py           # citation scoring saja
uv run python scripts/evaluate_retrieval.py --dry-run
```

---

## Rate Limiting

SiliconFlow tidak publish angka pasti RPM/TPM (dikonfirmasi dari docs — tidak terdokumentasi publik). Mitigasi berlapis:

1. **Sequential** — 4 judge calls per query dijalankan sequential, tidak parallel
2. **Inter-query delay** — default 5s antar query (`--inter-query-delay`)
3. **Inter-judge delay** — default 2s antar metric dalam satu query (`--inter-judge-delay`)
4. **Retry** — ragas library punya retry built-in; dikonfigurasi via `max_retries`
5. **Checkpoint/resume** — partial results disimpan ke `ragas_results_partial.json` setelah tiap query; `--resume` skip yang sudah selesai

Estimasi durasi full run (20 queries × ~4 judge calls × ~15s per call + delays): **~10–15 menit**.

---

## Storage

### File JSON

```
data/eval/
├── eval_queries.json              # existing — 20 queries
├── golden_answers.json            # NEW — generated once, re-used
├── results.json                   # existing — citation PASS/FAIL
├── ragas_results.json             # NEW — latest full RAGAS run
└── ragas_results_partial.json     # NEW — checkpoint untuk resume
```

### SQLite (tabel baru di `backend/history.db`)

Pola identik dengan `history_db.py`: satu koneksi per operasi, `aiosqlite`, `row_factory = aiosqlite.Row`.

```sql
CREATE TABLE IF NOT EXISTS eval_runs (
  id TEXT PRIMARY KEY,
  run_at TEXT NOT NULL,
  summary_json TEXT NOT NULL,   -- JSON: 4 overall metrics + per_difficulty
  results_json TEXT NOT NULL,   -- JSON array: per-query scores
  model TEXT NOT NULL,
  query_count INTEGER NOT NULL DEFAULT 20
);
```

---

## Backend Endpoints Baru

```
GET  /api/eval/runs/latest    → run terbaru lengkap (summary + per-query results)
GET  /api/eval/runs           → list semua runs (metadata saja, tanpa results)
POST /api/eval/runs           → simpan hasil dari CLI script
```

**`GET /api/eval/runs/latest` response schema:**
```json
{
  "id": "run-2026-03-29T10:00:00",
  "run_at": "2026-03-29T10:00:00Z",
  "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
  "summary": {
    "context_precision": 0.82,
    "context_recall": 0.75,
    "answer_faithfulness": 0.91,
    "answer_relevance": 0.88,
    "retrieval_accuracy": 0.85,
    "total_queries": 20
  },
  "per_difficulty": {
    "Simple":      { "context_precision": 0.9, "context_recall": 0.85, "answer_faithfulness": 0.95, "answer_relevance": 0.92 },
    "Medium":      { "context_precision": 0.8, "context_recall": 0.75, "answer_faithfulness": 0.90, "answer_relevance": 0.85 },
    "Complex":     { "context_precision": 0.75, "context_recall": 0.70, "answer_faithfulness": 0.88, "answer_relevance": 0.80 },
    "Calculation": { "context_precision": 0.85, "context_recall": 0.80, "answer_faithfulness": 0.92, "answer_relevance": 0.88 }
  },
  "results": [
    {
      "id": "EVAL-01",
      "query": "Apa itu break-even point...",
      "difficulty": "Simple",
      "context_precision": 0.8,
      "context_recall": 0.9,
      "answer_faithfulness": 1.0,
      "answer_relevance": 0.85,
      "retrieval_pass": true
    }
  ]
}
```

---

## Frontend Dashboard

### Routing

State-switching di `App.tsx` — konsisten dengan SPA tanpa react-router:

```tsx
const [activeView, setActiveView] = useState<"chat" | "eval">("chat");
```

Nav tab di header (sejajar dengan theme toggle), render kondisional `<EvalDashboard />` vs chat view.

### Layout Dashboard

```
┌─────────────────────────────────────────────────────┐
│  Run terakhir: 29 Mar 2026               [Refresh]  │
├──────────────┬──────────────┬──────────┬────────────┤
│ Ctx Precision│ Ctx Recall   │ Faith.   │ Relevance  │
│    0.82      │    0.75      │   0.91   │   0.88     │
│ ████████░░   │ ███████░░░   │ █████████ │ ████████░  │
├─────────────────────────────────────────────────────┤
│              SVG Radar Chart (4-axis)               │
├─────────────────────────────────────────────────────┤
│       Score per Difficulty (CSS bar chart)          │
│  Simple ████  Medium ███  Complex ██  Calc ████     │
├─────────────────────────────────────────────────────┤
│  Tabel 20 Queries                  Filter: [All ▾]  │
│  ID      Query         Prec  Rec  Faith  Rel  Pass  │
│  EVAL-01 Apa itu BEP   0.8   0.9  1.0   0.85  ✓   │
└─────────────────────────────────────────────────────┘
```

### Charts (SVG/CSS native — tidak install library baru)

- **MetricCard**: score besar + progress bar CSS (`width: score*100%`), color-coded
- **RadarChart**: SVG polygon 4-axis, `viewBox="0 0 200 200"`, koordinat polar
- **DifficultyChart**: CSS flexbox bars, grouped per difficulty
- Color coding: hijau ≥0.8, kuning 0.6–0.8, merah <0.6

---

## Urutan Implementasi

### Phase A — Backend Foundation
1. Tambah `ragas` ke `pyproject.toml` + `uv sync`
2. Buat `backend/eval_db.py` (pola persis `history_db.py`)
3. Buat `src/evaluation/__init__.py` + `src/evaluation/golden_generator.py`
4. Buat `src/evaluation/ragas_runner.py` (orchestrator + checkpointing)
5. Extend `scripts/evaluate_retrieval.py` dengan flags baru
6. **Validasi early**: `--generate-golden` dengan 3 queries, lalu `--ragas --batch-size 3`

### Phase B — Backend API
7. Tambah 3 endpoint `/api/eval/*` ke `backend/main.py` + import `eval_db`
8. Test: POST hasil dari CLI → GET `/api/eval/runs/latest`

### Phase C — Frontend Dashboard
9. Buat `frontend/src/types/eval.ts`
10. Buat `frontend/src/hooks/useEvalData.ts`
11. Buat komponen eval: MetricCard → RadarChart → DifficultyChart → QueryResultTable
12. Buat `frontend/src/components/EvalDashboard.tsx`
13. Modifikasi `frontend/src/App.tsx` — nav tab + conditional render

### Phase D — Validasi
14. Jalankan full eval run (20 queries), simpan ke DB
15. Buka dashboard, verifikasi semua metrics tampil dengan data nyata
16. Tulis tests: `tests/test_eval_db.py` + `tests/test_ragas_runner.py`

---

## Keputusan Arsitektur

| Keputusan | Pilihan | Alasan |
|-----------|---------|--------|
| Judge implementation | `ragas` library | Battle-tested prompts, OpenAI-compatible confirmed dengan SiliconFlow |
| Context Precision variant | `LLMContextPrecisionWithoutReference` | Tidak butuh golden answer tambahan |
| Frontend routing | State-switching | Konsisten dengan SPA existing, hanya 2 views, zero refactor |
| Chart library | SVG/CSS native | Tidak perlu dependency baru; mudah swap ke recharts nanti |
| Golden storage | JSON file | Versionable di git, mudah inspect manual |
| Eval run storage | SQLite tabel baru di `history.db` | Pola identik `history_db.py`, tidak perlu infrastruktur baru |
| CLI vs API trigger | CLI primer | Eval butuh akses filesystem + graph; lebih aman dan predictable |
| Rate limit strategy | Sequential + configurable delay | SiliconFlow tidak publish RPM limit; conservative default |

---

## Risiko

| Risiko | Mitigasi |
|--------|----------|
| Rate limit SiliconFlow saat ~80 LLM calls | Sequential + delay default konservatif (5s/2s) + `--resume` |
| `ragas` tidak kompatibel dengan SiliconFlow model ID format | Validasi early: test 3 queries sebelum full run |
| Golden answer bias (self-referential) | Dokumentasikan caveat; `--golden-file` untuk inject eksternal |
| `ragas` version conflict dengan `openai` yang sudah terinstall | Pin versi ragas yang kompatibel; test di `uv sync` |

---

## Verification

```bash
# 1. Generate golden answers
uv run python scripts/evaluate_retrieval.py --generate-golden
# Expected: data/eval/golden_answers.json tercipta dengan 20 entries

# 2. Audit run (5 queries)
uv run python scripts/evaluate_retrieval.py --ragas --batch-size 5 -v
# Expected: 5 queries scored, 4 metrics per query tampil di output

# 3. Full RAGAS run
uv run python scripts/evaluate_retrieval.py --ragas
# Expected: data/eval/ragas_results.json, 4 summary metrics tersedia

# 4. Backend API
curl http://localhost:8000/api/eval/runs/latest
# Expected: JSON dengan summary + 20 per-query results

# 5. Frontend dashboard
# Buka http://localhost:5173, klik tab "Evaluasi"
# Expected: 4 MetricCards, RadarChart, DifficultyChart, QueryResultTable semua render

# 6. Tests
uv run pytest tests/test_eval_db.py tests/test_ragas_runner.py -v
```
