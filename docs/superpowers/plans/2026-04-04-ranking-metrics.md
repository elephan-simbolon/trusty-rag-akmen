# Ranking Metrics (NDCG/MRR/Recall@K) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambahkan NDCG@5, MRR@5, Recall@5, Recall@10 ke pipeline evaluasi RAG yang ada, menggunakan LLM-as-judge untuk generate ground truth qrels, dan `ranx` untuk compute metrics.

**Architecture:** (1) `qrels_generator.py` menjalankan LLM judge per-chunk dari `retrieved_docs` dan menyimpan `qrels.json` yang reusable. (2) `ranking_metrics.py` menggunakan `ranx` untuk compute metrik dari qrels. (3) `evaluate_retrieval.py` mendapat dua flag baru: `--generate-qrels` dan `--ranking`. Output ranking metrics ditambahkan ke `ragas_results.json` summary yang sudah ada.

**Tech Stack:** Python 3.11, `ranx` (ranking metrics), SiliconFlow LLM (judge), LangGraph Phase 3 graph, `src/llm/client.py:generate()`.

---

## File Map

| Action | Path | Tanggung Jawab |
|--------|------|---------------|
| **Create** | `src/evaluation/qrels_generator.py` | LLM judge per-chunk → qrels.json |
| **Create** | `src/evaluation/ranking_metrics.py` | Compute NDCG/MRR/Recall@K via ranx |
| **Create** | `tests/test_ranking_metrics.py` | Unit tests untuk kedua modul baru |
| **Modify** | `pyproject.toml` | Tambah `ranx` dependency |
| **Modify** | `scripts/evaluate_retrieval.py` | Tambah flag `--generate-qrels` dan `--ranking` |
| **Modify** | `src/evaluation/ragas_runner.py` | Tambah ranking metrics ke `_aggregate_metrics()` |
| **Modify** | `QUALITY_CHECKS.md` | Dokumentasi command baru |

---

## Task 1: Tambah `ranx` ke Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Tambah ranx ke dependencies**

Edit `pyproject.toml`, tambahkan `"ranx"` ke dalam list `dependencies` setelah baris `"ragas>=0.2"`:

```toml
    "ragas>=0.2",
    "ranx",
```

- [ ] **Step 2: Install dependency**

```bash
uv sync --dev
```

Expected: resolves dan install `ranx` tanpa error.

- [ ] **Step 3: Verifikasi import ranx**

```bash
uv run python -c "from ranx import Qrels, Run, evaluate; print('ranx OK')"
```

Expected output: `ranx OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add ranx dependency for ranking metrics evaluation"
```

---

## Task 2: Buat `qrels_generator.py`

**Files:**
- Create: `src/evaluation/qrels_generator.py`
- Test: `tests/test_ranking_metrics.py` (bagian pertama)

Modul ini bertanggung jawab: (a) menjalankan `graph.invoke()` per query untuk mendapat `retrieved_docs`, (b) memanggil LLM judge per chunk untuk menilai relevansi binary (0/1), (c) menyimpan qrels ke `qrels.json`.

- [ ] **Step 1: Tulis failing test untuk `_judge_chunk_relevance()`**

Buat file `tests/test_ranking_metrics.py`:

```python
"""Tests untuk qrels_generator dan ranking_metrics."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Tests: qrels_generator
# ---------------------------------------------------------------------------


def test_judge_chunk_relevance_returns_1_for_relevant():
    """_judge_chunk_relevance() mengembalikan 1 jika LLM menjawab '1'."""
    from src.evaluation.qrels_generator import _judge_chunk_relevance

    with patch("src.evaluation.qrels_generator.llm_generate", return_value="1"):
        result = _judge_chunk_relevance(query="Apa itu BEP?", chunk_text="BEP adalah titik impas.")
    assert result == 1


def test_judge_chunk_relevance_returns_0_for_irrelevant():
    """_judge_chunk_relevance() mengembalikan 0 jika LLM menjawab '0'."""
    from src.evaluation.qrels_generator import _judge_chunk_relevance

    with patch("src.evaluation.qrels_generator.llm_generate", return_value="0"):
        result = _judge_chunk_relevance(query="Apa itu BEP?", chunk_text="Bab ini membahas sejarah.")
    assert result == 0


def test_judge_chunk_relevance_returns_0_on_unexpected_output():
    """_judge_chunk_relevance() mengembalikan 0 jika LLM output tidak dikenali."""
    from src.evaluation.qrels_generator import _judge_chunk_relevance

    with patch("src.evaluation.qrels_generator.llm_generate", return_value="Ya, relevan"):
        result = _judge_chunk_relevance(query="Apa itu BEP?", chunk_text="Teks apapun.")
    assert result == 0
```

- [ ] **Step 2: Jalankan test, pastikan FAIL**

```bash
uv run pytest tests/test_ranking_metrics.py::test_judge_chunk_relevance_returns_1_for_relevant -v
```

Expected: `ModuleNotFoundError` atau `ImportError` — file belum ada.

- [ ] **Step 3: Buat `src/evaluation/qrels_generator.py`**

```python
"""Generate qrels (ground truth relevance) menggunakan LLM-as-judge.

Qrels di-generate SATU KALI dari retrieved_docs per query,
disimpan ke qrels.json, dan di-reuse di semua eval run selanjutnya.

Doc ID menggunakan str(doc["id"]) — Qdrant point ID, unik per chunk.
Relevance: binary (1=relevan, 0=tidak relevan).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_QRELS_PATH = Path(__file__).parent.parent.parent / "data" / "eval" / "qrels.json"

_JUDGE_SYSTEM = (
    "Kamu adalah evaluator sistem information retrieval. "
    "Tugasmu menilai apakah sebuah potongan teks relevan untuk menjawab pertanyaan. "
    "Jawab HANYA dengan angka: 1 jika relevan, 0 jika tidak relevan. "
    "Tidak ada penjelasan, tidak ada teks lain."
)


def _judge_chunk_relevance(query: str, chunk_text: str) -> int:
    """Panggil LLM judge untuk satu (query, chunk) pair. Return 1 atau 0.

    Lazy import llm_generate agar modul bisa di-import tanpa live services.
    """
    from src.llm.client import generate as llm_generate  # noqa: PLC0415

    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Pertanyaan: {query}\n\n"
                f"Potongan teks:\n{chunk_text[:1500]}\n\n"
                "Jawab 1 (relevan) atau 0 (tidak relevan):"
            ),
        },
    ]
    try:
        raw = llm_generate(messages, temperature=0.0, max_tokens=4)
        return 1 if raw.strip().startswith("1") else 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM judge failed, defaulting to 0: %s", exc)
        return 0


def load_qrels(path: Path = DEFAULT_QRELS_PATH) -> dict[str, dict[str, int]]:
    """Load qrels dari JSON file. Return {} jika file tidak ada."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("qrels", {})


def generate_qrels(
    queries: list[dict],
    graph,
    output_path: Path = DEFAULT_QRELS_PATH,
    batch_size: int | None = None,
    verbose: bool = False,
) -> dict[str, dict[str, int]]:
    """Generate qrels via LLM judge untuk semua (atau batch) queries.

    Args:
        queries: List query dicts dari eval_queries.json.
            Wajib punya: "id" (str), "query" (str).
        graph: Compiled LangGraph Phase 3 graph (sync .invoke()).
        output_path: Path untuk menyimpan qrels.json.
        batch_size: Jika diset, hanya proses N queries pertama.
        verbose: Print progress per query.

    Returns:
        Dict mapping query_id -> {doc_id: relevance_score (0|1)}
    """
    from config.settings import settings  # noqa: PLC0415

    target_queries = queries[:batch_size] if batch_size else queries
    qrels: dict[str, dict[str, int]] = {}

    for i, eq in enumerate(target_queries, start=1):
        qid = eq["id"]
        query = eq["query"]

        if verbose:
            print(f"  [{i:02d}/{len(target_queries)}] {qid}: invoking graph...", end="", flush=True)

        try:
            result = graph.invoke(
                {
                    "query": query,
                    "conversation_history": [],
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={"configurable": {"thread_id": f"qrels-{qid}"}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph invoke failed for %s: %s", qid, exc)
            qrels[qid] = {}
            if verbose:
                print(f" GRAPH ERROR: {exc}")
            continue

        retrieved = result.get("retrieved_docs") or []
        query_qrels: dict[str, int] = {}

        for doc in retrieved:
            doc_id = str(doc.get("id", ""))
            if not doc_id:
                continue
            chunk_text = doc.get("text") or doc.get("content") or ""
            relevance = _judge_chunk_relevance(query=query, chunk_text=chunk_text)
            query_qrels[doc_id] = relevance

        qrels[qid] = query_qrels
        n_relevant = sum(1 for v in query_qrels.values() if v == 1)

        if verbose:
            print(f" {len(query_qrels)} docs judged, {n_relevant} relevant")

    # Simpan ke file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.llm_model,
        "qrels": qrels,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Qrels saved to %s (%d queries)", output_path, len(qrels))
    return qrels
```

- [ ] **Step 4: Jalankan test, pastikan PASS**

```bash
uv run pytest tests/test_ranking_metrics.py::test_judge_chunk_relevance_returns_1_for_relevant tests/test_ranking_metrics.py::test_judge_chunk_relevance_returns_0_for_irrelevant tests/test_ranking_metrics.py::test_judge_chunk_relevance_returns_0_on_unexpected_output -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Tulis test untuk `load_qrels()`**

Tambahkan ke `tests/test_ranking_metrics.py`:

```python
def test_load_qrels_returns_dict(tmp_path):
    """load_qrels() mengembalikan dict qrels dari file JSON."""
    from src.evaluation.qrels_generator import load_qrels

    qrels_file = tmp_path / "qrels.json"
    data = {
        "generated_at": "2026-04-04T00:00:00Z",
        "model": "test",
        "qrels": {"EVAL-01": {"123": 1, "456": 0}},
    }
    qrels_file.write_text(json.dumps(data), encoding="utf-8")

    result = load_qrels(qrels_file)
    assert result["EVAL-01"]["123"] == 1
    assert result["EVAL-01"]["456"] == 0


def test_load_qrels_returns_empty_if_missing(tmp_path):
    """load_qrels() mengembalikan {} jika file tidak ada."""
    from src.evaluation.qrels_generator import load_qrels

    result = load_qrels(tmp_path / "nonexistent.json")
    assert result == {}
```

- [ ] **Step 6: Jalankan semua test qrels_generator, pastikan PASS**

```bash
uv run pytest tests/test_ranking_metrics.py -k "qrels" -v
```

Expected: 5 PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/evaluation/qrels_generator.py tests/test_ranking_metrics.py
git commit -m "feat(eval): add qrels_generator — LLM judge per-chunk for ranking metrics"
```

---

## Task 3: Buat `ranking_metrics.py`

**Files:**
- Create: `src/evaluation/ranking_metrics.py`
- Test: `tests/test_ranking_metrics.py` (lanjutan)

Modul ini bertanggung jawab: menerima qrels + retrieved_docs dari satu eval run, membangun `ranx.Qrels` dan `ranx.Run`, dan mengembalikan dict metrik.

- [ ] **Step 1: Tulis failing test untuk `compute_ranking_metrics()`**

Tambahkan ke `tests/test_ranking_metrics.py`:

```python
# ---------------------------------------------------------------------------
# Tests: ranking_metrics
# ---------------------------------------------------------------------------


def test_compute_ranking_metrics_basic():
    """compute_ranking_metrics() mengembalikan dict dengan 4 metrik float."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    # qrels: EVAL-01 → doc "1" relevan, doc "2" tidak
    qrels = {"EVAL-01": {"1": 1, "2": 0, "3": 1}}

    # run_docs: retrieved_docs per query; doc "1" di posisi pertama (score tertinggi)
    run_docs = {
        "EVAL-01": [
            {"id": 1, "score": 0.9},  # doc "1", relevan, rank 1
            {"id": 2, "score": 0.7},  # doc "2", tidak relevan, rank 2
            {"id": 3, "score": 0.5},  # doc "3", relevan, rank 3
        ]
    }

    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    assert "ndcg@5" in result
    assert "mrr@5" in result
    assert "recall@5" in result
    assert "recall@10" in result
    # Semua metrik harus float dalam range [0, 1]
    for key, val in result.items():
        assert isinstance(val, float), f"{key} bukan float: {val}"
        assert 0.0 <= val <= 1.0, f"{key}={val} di luar range [0,1]"


def test_compute_ranking_metrics_perfect_ranking():
    """Jika doc relevan ada di rank 1, MRR@5 harus 1.0 dan NDCG@5 tinggi."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    qrels = {"EVAL-01": {"10": 1}}
    run_docs = {
        "EVAL-01": [
            {"id": 10, "score": 0.99},  # relevan, rank 1
            {"id": 20, "score": 0.50},
        ]
    }

    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    assert result["mrr@5"] == 1.0
    assert result["ndcg@5"] == 1.0
    assert result["recall@5"] == 1.0


def test_compute_ranking_metrics_no_relevant_docs():
    """Jika tidak ada doc relevan di qrels, semua metrik harus 0.0."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    qrels = {"EVAL-01": {"10": 0, "20": 0}}
    run_docs = {
        "EVAL-01": [
            {"id": 10, "score": 0.9},
            {"id": 20, "score": 0.5},
        ]
    }

    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    assert result["mrr@5"] == 0.0
    assert result["recall@5"] == 0.0


def test_compute_ranking_metrics_query_not_in_run():
    """Query yang ada di qrels tapi tidak di run_docs di-skip tanpa error."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    qrels = {"EVAL-01": {"1": 1}, "EVAL-02": {"2": 1}}
    run_docs = {
        "EVAL-01": [{"id": 1, "score": 0.9}],
        # EVAL-02 tidak ada di run_docs
    }

    # Tidak boleh raise exception
    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)
    assert "ndcg@5" in result
```

- [ ] **Step 2: Jalankan test, pastikan FAIL**

```bash
uv run pytest tests/test_ranking_metrics.py -k "ranking_metrics" -v
```

Expected: `ImportError` — modul belum ada.

- [ ] **Step 3: Buat `src/evaluation/ranking_metrics.py`**

```python
"""Compute ranking metrics (NDCG, MRR, Recall@K) menggunakan ranx.

Input:
    qrels: dict[query_id, dict[doc_id, relevance]] — binary (0|1)
    run_docs: dict[query_id, list[doc_dict]] — retrieved_docs dari graph.invoke()

Doc ID: str(doc["id"]) — Qdrant point ID.
Score untuk ranx.Run: doc["score"] (RRF-fused score dari hybrid search).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

METRICS = ["ndcg@5", "mrr@5", "recall@5", "recall@10"]


def compute_ranking_metrics(
    qrels: dict[str, dict[str, int]],
    run_docs: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    """Hitung ranking metrics dari qrels dan retrieved docs.

    Args:
        qrels: Ground truth relevance per (query_id, doc_id). Nilai 0 atau 1.
            Format: {"EVAL-01": {"12345": 1, "67890": 0}, ...}
        run_docs: Retrieved docs per query_id, berurutan dari score tertinggi.
            Format: {"EVAL-01": [{"id": 12345, "score": 0.9}, ...], ...}

    Returns:
        Dict metrik rata-rata: {"ndcg@5": 0.82, "mrr@5": 0.75, ...}
    """
    from ranx import Qrels, Run, evaluate  # noqa: PLC0415

    # Filter qrels: hanya query yang ada di run_docs dan punya minimal 1 doc relevan
    filtered_qrels: dict[str, dict[str, int]] = {}
    filtered_run: dict[str, dict[str, float]] = {}

    for qid, rel_dict in qrels.items():
        if qid not in run_docs:
            logger.debug("Query %s ada di qrels tapi tidak di run_docs, di-skip", qid)
            continue
        # Hanya sertakan qrels yang punya minimal 1 doc relevan
        relevant_docs = {doc_id: rel for doc_id, rel in rel_dict.items() if rel > 0}
        if not relevant_docs:
            logger.debug("Query %s tidak punya doc relevan di qrels, di-skip", qid)
            continue

        filtered_qrels[qid] = rel_dict  # simpan semua (0 dan 1) untuk ranx

        # Build run dict: {doc_id (str): score (float)}
        run_entry: dict[str, float] = {}
        for doc in run_docs[qid]:
            doc_id = str(doc.get("id", ""))
            if doc_id:
                run_entry[doc_id] = float(doc.get("score", 0.0))
        filtered_run[qid] = run_entry

    if not filtered_qrels:
        logger.warning("Tidak ada query valid untuk evaluasi ranking — semua di-skip")
        return {m.replace("@", "@"): 0.0 for m in METRICS}

    ranx_qrels = Qrels(filtered_qrels)
    ranx_run = Run(filtered_run)

    scores = evaluate(ranx_qrels, ranx_run, METRICS)

    # ranx evaluate() mengembalikan float jika single metric, dict jika multiple
    if isinstance(scores, dict):
        return {k: round(float(v), 4) for k, v in scores.items()}
    # Fallback untuk single metric (seharusnya tidak terjadi dengan list METRICS)
    return {METRICS[0]: round(float(scores), 4)}
```

- [ ] **Step 4: Jalankan semua test ranking_metrics, pastikan PASS**

```bash
uv run pytest tests/test_ranking_metrics.py -k "ranking_metrics" -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Jalankan semua test di file, pastikan tidak ada regresi**

```bash
uv run pytest tests/test_ranking_metrics.py -v
```

Expected: semua PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/evaluation/ranking_metrics.py tests/test_ranking_metrics.py
git commit -m "feat(eval): add ranking_metrics — NDCG/MRR/Recall@K via ranx"
```

---

## Task 4: Tambah Flag ke `evaluate_retrieval.py`

**Files:**
- Modify: `scripts/evaluate_retrieval.py`

Tambahkan dua fungsi baru dan dua flag CLI: `--generate-qrels` dan `--ranking`.

- [ ] **Step 1: Tambah import dan konstanta di bagian atas `evaluate_retrieval.py`**

Buka `scripts/evaluate_retrieval.py`. Setelah baris:
```python
GOLDEN_PATH = Path(__file__).parent.parent / "data" / "eval" / "golden_answers.json"
DEFAULT_RAGAS_OUTPUT = Path(__file__).parent.parent / "data" / "eval" / "ragas_results.json"
DEFAULT_PARTIAL_PATH = Path(__file__).parent.parent / "data" / "eval" / "ragas_results_partial.json"
```

Tambahkan:
```python
DEFAULT_QRELS_PATH = Path(__file__).parent.parent / "data" / "eval" / "qrels.json"
```

- [ ] **Step 2: Tambah fungsi `run_generate_qrels()` dan `run_ranking()`**

Tambahkan kedua fungsi ini sebelum fungsi `main()` di `scripts/evaluate_retrieval.py`:

```python
def run_generate_qrels(
    queries: list[dict],
    batch_size: int | None = None,
    verbose: bool = False,
) -> None:
    """Generate qrels via LLM judge dan simpan ke DEFAULT_QRELS_PATH."""
    from src.agents.graph import build_phase3_graph  # noqa: PLC0415
    from src.evaluation.qrels_generator import generate_qrels  # noqa: PLC0415

    print("Building Phase 3 graph untuk qrels generation...")
    graph = build_phase3_graph()
    n = batch_size or len(queries)
    print(f"Generating qrels untuk {n} queries via LLM judge...")
    qrels = generate_qrels(
        queries=queries,
        graph=graph,
        output_path=DEFAULT_QRELS_PATH,
        batch_size=batch_size,
        verbose=verbose,
    )
    ok = sum(1 for v in qrels.values() if v)
    print(f"\nQrels: {ok}/{len(qrels)} queries punya minimal 1 doc relevan")
    print(f"Saved to: {DEFAULT_QRELS_PATH}")


def run_ranking(
    queries: list[dict],
    batch_size: int | None = None,
    verbose: bool = False,
    qrels_file: Path | None = None,
) -> dict:
    """Compute NDCG/MRR/Recall@K dari qrels yang sudah ada."""
    from src.agents.graph import build_phase3_graph  # noqa: PLC0415
    from src.evaluation.qrels_generator import load_qrels  # noqa: PLC0415
    from src.evaluation.ranking_metrics import compute_ranking_metrics  # noqa: PLC0415

    qrels_path = qrels_file or DEFAULT_QRELS_PATH
    qrels = load_qrels(qrels_path)
    if not qrels:
        print(f"ERROR: qrels.json tidak ditemukan di {qrels_path}")
        print("  Jalankan dulu: python scripts/evaluate_retrieval.py --generate-qrels")
        sys.exit(1)

    print("Building Phase 3 graph...")
    graph = build_phase3_graph()

    target_queries = queries[:batch_size] if batch_size else queries
    run_docs: dict[str, list[dict]] = {}

    for i, eq in enumerate(target_queries, start=1):
        qid = eq["id"]
        print(f"  [{i:02d}/{len(target_queries)}] {qid}...", end="", flush=True)
        try:
            result = graph.invoke(
                {
                    "query": eq["query"],
                    "conversation_history": [],
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={"configurable": {"thread_id": f"ranking-{qid}"}},
            )
            run_docs[qid] = result.get("retrieved_docs") or []
            print(f" {len(run_docs[qid])} docs")
        except Exception as exc:  # noqa: BLE001
            print(f" ERROR: {exc}")
            run_docs[qid] = []

    metrics = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    print()
    print("=" * 40)
    print("Ranking Metrics")
    print("=" * 40)
    for k, v in metrics.items():
        print(f"  {k:12s}: {v:.4f}")

    return metrics
```

- [ ] **Step 3: Tambah argumen CLI ke `main()`**

Di dalam fungsi `main()`, setelah blok argumen `--golden-file`, tambahkan:

```python
    # Ranking metrics flags
    parser.add_argument(
        "--generate-qrels",
        action="store_true",
        help="Generate qrels via LLM judge (sekali, hasilnya reusable)",
    )
    parser.add_argument(
        "--ranking",
        action="store_true",
        help="Hitung NDCG/MRR/Recall@K dari qrels yang sudah ada",
    )
    parser.add_argument(
        "--qrels-file",
        type=Path,
        default=None,
        help="Path ke qrels JSON kustom (default: data/eval/qrels.json)",
    )
```

- [ ] **Step 4: Tambah routing di `main()` sebelum `else` default**

Ubah blok `if/elif/else` di akhir `main()` dari:

```python
    if args.dry_run:
        run_dry_run(queries)
    elif args.generate_golden:
        run_generate_golden(queries, verbose=args.verbose)
    elif args.ragas:
        run_ragas(...)
    else:
        run_evaluation(queries, args.output, verbose=args.verbose)
```

Menjadi:

```python
    if args.dry_run:
        run_dry_run(queries)
    elif args.generate_golden:
        run_generate_golden(queries, verbose=args.verbose)
    elif args.generate_qrels:
        run_generate_qrels(queries, batch_size=args.batch_size, verbose=args.verbose)
    elif args.ranking:
        run_ranking(
            queries=queries,
            batch_size=args.batch_size,
            verbose=args.verbose,
            qrels_file=args.qrels_file,
        )
    elif args.ragas:
        run_ragas(
            queries=queries,
            output_path=args.ragas_output,
            batch_size=args.batch_size,
            resume=args.resume,
            inter_query_delay=args.inter_query_delay,
            inter_judge_delay=args.inter_judge_delay,
            golden_file=args.golden_file,
            verbose=args.verbose,
        )
    else:
        run_evaluation(queries, args.output, verbose=args.verbose)
```

- [ ] **Step 5: Verifikasi CLI help menampilkan flag baru**

```bash
uv run python scripts/evaluate_retrieval.py --help
```

Expected: tampil `--generate-qrels`, `--ranking`, `--qrels-file` di output.

- [ ] **Step 6: Commit**

```bash
git add scripts/evaluate_retrieval.py
git commit -m "feat(eval): add --generate-qrels and --ranking CLI flags"
```

---

## Task 5: Integrasikan Ranking Metrics ke `ragas_runner.py`

**Files:**
- Modify: `src/evaluation/ragas_runner.py`

Ketika `--ragas --ranking` dijalankan bersamaan, ranking metrics ditambahkan ke summary output. Ini dilakukan dengan mengekstend `_aggregate_metrics()` agar menerima optional ranking metrics dict.

- [ ] **Step 1: Ubah signature `_aggregate_metrics()` di `ragas_runner.py`**

Ubah:
```python
def _aggregate_metrics(results: list[dict]) -> dict:
    """Hitung summary metrics dari per-query results."""
```

Menjadi:
```python
def _aggregate_metrics(results: list[dict], ranking_metrics: dict | None = None) -> dict:
    """Hitung summary metrics dari per-query results.

    Args:
        results: Per-query RAGAS results.
        ranking_metrics: Optional dict dari compute_ranking_metrics() —
            jika diset, ranking metrics di-merge ke dalam summary.
    """
```

- [ ] **Step 2: Tambah merge ranking_metrics di akhir `_aggregate_metrics()`**

Di dalam `_aggregate_metrics()`, sebelum `return overall`, tambahkan:

```python
    # Merge ranking metrics jika tersedia
    if ranking_metrics:
        overall.update(ranking_metrics)

    return overall
```

- [ ] **Step 3: Update signature `run_ragas_evaluation()` untuk menerima ranking_metrics**

Ubah signature fungsi dari:
```python
async def run_ragas_evaluation(
    queries: list[dict],
    golden_answers: dict[str, dict],
    graph: Any,
    output_path: Path = DEFAULT_RAGAS_OUTPUT,
    partial_path: Path = DEFAULT_PARTIAL_OUTPUT,
    batch_size: int | None = None,
    resume: bool = False,
    inter_query_delay: float = 5.0,
    inter_judge_delay: float = 2.0,
    verbose: bool = False,
) -> dict:
```

Menjadi:
```python
async def run_ragas_evaluation(
    queries: list[dict],
    golden_answers: dict[str, dict],
    graph: Any,
    output_path: Path = DEFAULT_RAGAS_OUTPUT,
    partial_path: Path = DEFAULT_PARTIAL_OUTPUT,
    batch_size: int | None = None,
    resume: bool = False,
    inter_query_delay: float = 5.0,
    inter_judge_delay: float = 2.0,
    verbose: bool = False,
    ranking_metrics: dict | None = None,
) -> dict:
```

- [ ] **Step 4: Pass `ranking_metrics` ke `_aggregate_metrics()` di dalam `run_ragas_evaluation()`**

Temukan baris:
```python
    summary = _aggregate_metrics(results)
```

Ubah menjadi:
```python
    summary = _aggregate_metrics(results, ranking_metrics=ranking_metrics)
```

- [ ] **Step 5: Verifikasi test `_aggregate_metrics` masih PASS**

```bash
uv run pytest tests/test_ragas_runner.py -v
```

Expected: semua PASSED — perubahan backward compatible karena `ranking_metrics=None` default.

- [ ] **Step 6: Commit**

```bash
git add src/evaluation/ragas_runner.py
git commit -m "feat(eval): integrate ranking metrics into ragas_runner summary output"
```

---

## Task 6: Update `QUALITY_CHECKS.md`

**Files:**
- Modify: `QUALITY_CHECKS.md`

- [ ] **Step 1: Tambah section ranking metrics ke QUALITY_CHECKS.md**

Di `QUALITY_CHECKS.md`, tambahkan section baru setelah "## 3. RAGAS Evaluation":

```markdown
## 4. Ranking Metrics (NDCG/MRR/Recall@K)

Evaluasi kualitas ranking hybrid search (pre-rerank, retrieved_docs top-20).
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

Output: ditambahkan ke `data/eval/ragas_results.json` summary.

| Metrik | Mengukur |
|--------|----------|
| NDCG@5 | Kualitas ranking — doc relevan di posisi teratas |
| MRR@5  | Seberapa cepat doc relevan pertama muncul |
| Recall@5 | Coverage relevant docs di top-5 |
| Recall@10 | Coverage relevant docs di top-10 |
```

- [ ] **Step 2: Update nomor section berikutnya**

Ubah section yang sebelumnya `## 4. Output Files` menjadi `## 5. Output Files`, dan seterusnya hingga `## 6. Backend API` menjadi `## 6. Backend API`, `## 4. Unit Tests` (lama) menjadi `## 7. Unit Tests`.

Perhatikan urutan section akhir:
```
## 5. Output Files
## 6. Backend API (opsional)
## 7. Unit Tests
```

Tambahkan juga baris qrels.json ke tabel output:
```markdown
| `data/eval/qrels.json` | `--generate-qrels` | Ground truth relevance per (query_id, doc_id) |
```

- [ ] **Step 3: Commit**

```bash
git add QUALITY_CHECKS.md
git commit -m "docs: update QUALITY_CHECKS.md with ranking metrics commands"
```

---

## Task 7: Smoke Test End-to-End (Dry Run)

Verifikasi bahwa semua komponen terhubung benar tanpa menjalankan live services.

- [ ] **Step 1: Jalankan seluruh test suite**

```bash
uv run pytest tests/test_ranking_metrics.py tests/test_ragas_runner.py -v
```

Expected: semua PASSED.

- [ ] **Step 2: Verifikasi `--dry-run` masih bekerja**

```bash
uv run python scripts/evaluate_retrieval.py --dry-run
```

Expected: `Validation PASSED: 20 queries loaded` — tidak ada regresi pada existing code.

- [ ] **Step 3: Verifikasi help text lengkap**

```bash
uv run python scripts/evaluate_retrieval.py --help
```

Expected: tampil `--generate-qrels`, `--ranking`, `--qrels-file` di samping flag yang sudah ada.

- [ ] **Step 4: Verifikasi import semua modul baru**

```bash
uv run python -c "
from src.evaluation.qrels_generator import load_qrels, generate_qrels, _judge_chunk_relevance
from src.evaluation.ranking_metrics import compute_ranking_metrics, METRICS
print('All imports OK')
print('METRICS:', METRICS)
"
```

Expected:
```
All imports OK
METRICS: ['ndcg@5', 'mrr@5', 'recall@5', 'recall@10']
```

- [ ] **Step 5: Commit final**

```bash
git add .
git commit -m "feat(eval): complete ranking metrics implementation — NDCG/MRR/Recall@K"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task yang mengimplementasikan |
|-----------------|-------------------------------|
| LLM judge per-chunk → binary qrels | Task 2: `qrels_generator.py` |
| Simpan qrels.json (reusable) | Task 2: `generate_qrels()` |
| Compute NDCG@5, MRR@5, Recall@5, Recall@10 | Task 3: `ranking_metrics.py` |
| Flag `--generate-qrels` | Task 4: `evaluate_retrieval.py` |
| Flag `--ranking` | Task 4: `evaluate_retrieval.py` |
| Merge ke ragas_results.json summary | Task 5: `_aggregate_metrics()` |
| Dokumentasi QUALITY_CHECKS.md | Task 6 |
| Dependency `ranx` | Task 1 |

**Placeholder scan:** Tidak ada TBD/TODO di plan.

**Type consistency:**
- `qrels`: selalu `dict[str, dict[str, int]]` — konsisten antara Task 2, 3, 4, 5.
- `run_docs`: selalu `dict[str, list[dict]]` — konsisten antara Task 3 dan 4.
- `doc["id"]` → `str(doc.get("id", ""))` — konsisten di `qrels_generator.py` dan `ranking_metrics.py`.
- `ranking_metrics` parameter di `_aggregate_metrics()` dan `run_ragas_evaluation()` — konsisten `dict | None`.
