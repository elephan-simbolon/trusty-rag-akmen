"""Run 20-query evaluation set against the RAG system and score citation relevance.

Measures retrieval accuracy (MON-02): target >= 85% (17/20 queries with correct citations).

Usage:
    python scripts/evaluate_retrieval.py
    python scripts/evaluate_retrieval.py --output data/eval/results.json
    python scripts/evaluate_retrieval.py --dry-run   # validate JSON structure only
    python scripts/evaluate_retrieval.py -v          # verbose per-query output
    python scripts/evaluate_retrieval.py --generate-golden  # generate golden answers
    python scripts/evaluate_retrieval.py --ragas     # full RAGAS evaluation (4 metrics)
    python scripts/evaluate_retrieval.py --generate-qrels  # generate qrels via LLM judge (sekali)
    python scripts/evaluate_retrieval.py --ranking   # hitung NDCG/MRR/Recall@K dari qrels
    python scripts/evaluate_retrieval.py --ragas --ranking  # gabung RAGAS + ranking metrics
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_QUERIES_PATH = Path(__file__).parent.parent / "data" / "eval" / "eval_queries.json"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "eval" / "results.json"

REQUIRED_FIELDS = {"id", "query", "expected_books", "expected_chapters", "difficulty"}
VALID_DIFFICULTIES = {"Simple", "Medium", "Complex", "Calculation"}

GOLDEN_PATH = Path(__file__).parent.parent / "data" / "eval" / "golden_answers.json"
DEFAULT_RAGAS_OUTPUT = Path(__file__).parent.parent / "data" / "eval" / "ragas_results.json"
DEFAULT_PARTIAL_PATH = Path(__file__).parent.parent / "data" / "eval" / "ragas_results_partial.json"
DEFAULT_QRELS_PATH = Path(__file__).parent.parent / "data" / "eval" / "qrels.json"
DEFAULT_RANKING_OUTPUT = Path(__file__).parent.parent / "data" / "eval" / "ranking_results.json"


# ---------------------------------------------------------------------------
# JSON Validation
# ---------------------------------------------------------------------------


def load_eval_queries(path: Path) -> list[dict]:
    """Load and return the evaluation query list from eval_queries.json."""
    if not path.exists():
        print(f"ERROR: eval_queries.json not found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("ERROR: eval_queries.json must be a JSON array", file=sys.stderr)
        sys.exit(1)
    return data


def validate_structure(queries: list[dict]) -> list[str]:
    """Validate query list structure. Returns list of error messages (empty = OK)."""
    errors = []

    if len(queries) != 20:
        errors.append(f"Expected 20 queries, found {len(queries)}")

    seen_ids = set()
    for i, q in enumerate(queries):
        label = q.get("id", f"index {i}")

        # Required fields
        missing = REQUIRED_FIELDS - set(q.keys())
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}")

        # ID uniqueness
        qid = q.get("id")
        if qid in seen_ids:
            errors.append(f"Duplicate id: {qid}")
        elif qid is not None:
            seen_ids.add(qid)

        # expected_books must be a non-empty list
        if not isinstance(q.get("expected_books"), list) or not q["expected_books"]:
            errors.append(f"{label}: expected_books must be a non-empty list")

        # expected_chapters must be a non-empty list
        if not isinstance(q.get("expected_chapters"), list) or not q["expected_chapters"]:
            errors.append(f"{label}: expected_chapters must be a non-empty list")

        # difficulty must be valid
        if q.get("difficulty") not in VALID_DIFFICULTIES:
            errors.append(
                f"{label}: difficulty '{q.get('difficulty')}' not in {VALID_DIFFICULTIES}"
            )

    return errors


def run_dry_run(queries: list[dict]) -> None:
    """Validate JSON structure and print summary. Exits with 0 on success."""
    errors = validate_structure(queries)
    if errors:
        print("VALIDATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    # Distribution summary
    dist: dict[str, int] = {}
    for q in queries:
        d = q.get("difficulty", "Unknown")
        dist[d] = dist.get(d, 0) + 1

    print(f"Validation PASSED: {len(queries)} queries loaded from {EVAL_QUERIES_PATH}")
    print("Difficulty distribution:")
    for diff in sorted(dist):
        print(f"  {diff}: {dist[diff]}")
    print("All required fields present. IDs unique. Structure OK.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Citation Scoring
# ---------------------------------------------------------------------------


def score_query(result: dict, expected_query: dict) -> dict:
    """Score a single query result against expected books.

    PASS: at least one citation book_title matches any expected_book.
    FAIL: no citation matches any expected_book.
    """
    citations = result.get("citations") or []
    expected_books = expected_query.get("expected_books", [])

    cited_books = {c.get("book_title", "") for c in citations}
    matched_books = [b for b in expected_books if b in cited_books]

    passed = len(matched_books) > 0
    return {
        "id": expected_query["id"],
        "query": expected_query["query"],
        "difficulty": expected_query["difficulty"],
        "expected_books": expected_books,
        "cited_books": sorted(cited_books),
        "matched_books": matched_books,
        "passed": passed,
        "citations": citations,
        "response_snippet": (result.get("response") or "")[:200],
        "query_type": result.get("query_type"),
        "crag_grade": result.get("crag_grade"),
    }


# ---------------------------------------------------------------------------
# Full Evaluation Run
# ---------------------------------------------------------------------------


def run_evaluation(
    queries: list[dict],
    output_path: Path,
    verbose: bool = False,
) -> dict:
    """Execute all 20 queries against the Phase 3 graph and score results."""
    # Lazy import: build_phase3_graph requires live services; not needed for --dry-run
    from src.agents.graph import build_phase3_graph  # noqa: PLC0415

    print("Building Phase 3 graph...")
    graph = build_phase3_graph()

    results = []
    pass_count = 0

    for i, eq in enumerate(queries, start=1):
        print(f"[{i:02d}/20] {eq['id']}: {eq['query'][:60]}...", end="", flush=True)
        t0 = time.time()

        try:
            result = graph.invoke(
                {
                    "query": eq["query"],
                    "conversation_history": [],
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={"configurable": {"thread_id": f"eval-{eq['id']}"}},
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - t0
            print(f" ERROR ({elapsed:.1f}s): {exc}")
            results.append(
                {
                    "id": eq["id"],
                    "query": eq["query"],
                    "difficulty": eq["difficulty"],
                    "passed": False,
                    "error": str(exc),
                }
            )
            continue

        elapsed = time.time() - t0
        scored = score_query(result, eq)
        results.append(scored)

        status = "PASS" if scored["passed"] else "FAIL"
        if scored["passed"]:
            pass_count += 1

        print(f" {status} ({elapsed:.1f}s)")
        if verbose:
            print(f"       Expected: {eq['expected_books']}")
            print(f"       Cited:    {scored['cited_books']}")
            print(f"       Response: {scored['response_snippet']}")
            print()

    accuracy_pct = round(pass_count / len(queries) * 100, 1)
    summary = {
        "total": len(queries),
        "passed": pass_count,
        "failed": len(queries) - pass_count,
        "accuracy_pct": accuracy_pct,
        "target_pct": 85.0,
        "meets_target": accuracy_pct >= 85.0,
        "results": results,
    }

    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print(f"Accuracy: {pass_count}/{len(queries)} ({accuracy_pct}%)")
    print(f"Target:   17/20 (85.0%) — {'MET' if summary['meets_target'] else 'NOT MET'}")
    print(f"Results saved to: {output_path}")

    return summary


# ---------------------------------------------------------------------------
# RAGAS Evaluation
# ---------------------------------------------------------------------------


def run_generate_golden(queries: list[dict], verbose: bool = False) -> None:
    """Generate golden answers dan simpan ke GOLDEN_PATH."""
    from src.agents.graph import build_phase3_graph  # noqa: PLC0415
    from src.evaluation.golden_generator import generate_golden_answers  # noqa: PLC0415

    print("Building Phase 3 graph untuk golden generation...")
    graph = build_phase3_graph()
    print(f"Generating golden answers untuk {len(queries)} queries...")
    answers = generate_golden_answers(
        queries=queries, graph=graph, output_path=GOLDEN_PATH, verbose=verbose
    )
    ok = sum(1 for v in answers.values() if v.get("golden_answer"))
    print(f"\nGolden answers: {ok}/{len(queries)} berhasil")
    print(f"Saved to: {GOLDEN_PATH}")


def run_ragas(
    queries: list[dict],
    output_path: Path,
    batch_size: int | None,
    resume: bool,
    inter_query_delay: float,
    inter_judge_delay: float,
    golden_file: Path | None,
    verbose: bool,
) -> None:
    """Jalankan RAGAS evaluation dan simpan hasil ke backend DB."""
    from src.agents.graph import build_phase3_graph  # noqa: PLC0415
    from src.evaluation.golden_generator import load_golden_answers  # noqa: PLC0415
    from src.evaluation.ragas_runner import run_ragas_evaluation  # noqa: PLC0415

    # Load golden answers
    golden_path = golden_file or GOLDEN_PATH
    golden_answers = load_golden_answers(golden_path)
    if not golden_answers:
        print("WARNING: golden_answers.json tidak ditemukan. Context Recall akan None.")
        print(f"  Jalankan dulu: python scripts/evaluate_retrieval.py --generate-golden")

    print("Building Phase 3 graph...")
    graph = build_phase3_graph()

    print(f"Menjalankan RAGAS evaluation ({batch_size or len(queries)} queries)...")
    result = asyncio.run(
        run_ragas_evaluation(
            queries=queries,
            golden_answers=golden_answers,
            graph=graph,
            output_path=output_path,
            partial_path=DEFAULT_PARTIAL_PATH,
            batch_size=batch_size,
            resume=resume,
            inter_query_delay=inter_query_delay,
            inter_judge_delay=inter_judge_delay,
            verbose=verbose,
        )
    )

    summary = result["summary"]
    print()
    print("=" * 50)
    print("RAGAS Evaluation Summary")
    print("=" * 50)
    cp = summary.get("context_precision")
    cr = summary.get("context_recall")
    af = summary.get("answer_faithfulness")
    ar = summary.get("answer_relevance")
    ra = summary.get("retrieval_accuracy", 0)
    print(f"Context Precision:    {cp:.3f}" if cp is not None else "Context Precision:    N/A")
    print(f"Context Recall:       {cr:.3f}" if cr is not None else "Context Recall:       N/A")
    print(f"Answer Faithfulness:  {af:.3f}" if af is not None else "Answer Faithfulness:  N/A")
    print(f"Answer Relevance:     {ar:.3f}" if ar is not None else "Answer Relevance:     N/A")
    print(f"Retrieval Accuracy:   {ra * 100:.1f}%")
    print(f"Results saved to:     {output_path}")

    # Simpan ke backend DB (opsional — backend harus berjalan)
    try:
        import httpx  # noqa: PLC0415
        from config.settings import settings  # noqa: PLC0415

        resp = httpx.post(
            "http://localhost:8000/api/eval/runs",
            json={
                "summary": summary,
                "results": result["results"],
                "model": settings.llm_model,
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            print("Results saved to backend DB (via /api/eval/runs)")
    except Exception:  # noqa: BLE001
        print("NOTE: Backend tidak berjalan — results tidak disimpan ke DB.")
        print("       Jalankan backend lalu POST manual dari ragas_results.json")


# ---------------------------------------------------------------------------
# Ranking Metrics
# ---------------------------------------------------------------------------


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
    output_path: Path = DEFAULT_RANKING_OUTPUT,
) -> dict:
    """Compute NDCG/MRR/Recall@K dari qrels yang sudah ada."""
    import json  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415

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

    target_queries = queries[:batch_size] if batch_size is not None else queries
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

    # Simpan ke file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "query_count": len(run_docs),
        "metrics": metrics,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Results saved to: {output_path}")

    return metrics


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate RAG retrieval accuracy on 20-query accounting evaluation set."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to save JSON results (default: data/eval/results.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate eval_queries.json structure only, do not run queries",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-query expected vs cited books and response snippet",
    )
    # RAGAS flags
    parser.add_argument(
        "--ragas",
        action="store_true",
        help="Jalankan full RAGAS evaluation (4 metrics via LLM judge)",
    )
    parser.add_argument(
        "--generate-golden",
        action="store_true",
        help="Generate golden answers sekali untuk Context Recall",
    )
    parser.add_argument(
        "--ragas-output",
        type=Path,
        default=DEFAULT_RAGAS_OUTPUT,
        help="Output path untuk RAGAS results (default: data/eval/ragas_results.json)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Hanya proses N queries pertama (untuk audit/test)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip queries yang sudah selesai (resume dari checkpoint)",
    )
    parser.add_argument(
        "--inter-query-delay",
        type=float,
        default=5.0,
        help="Detik jeda antar query (mitigasi rate limit, default: 5)",
    )
    parser.add_argument(
        "--inter-judge-delay",
        type=float,
        default=2.0,
        help="Detik jeda antar judge call (default: 2)",
    )
    parser.add_argument(
        "--golden-file",
        type=Path,
        default=None,
        help="Path ke golden answers JSON kustom",
    )
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
    args = parser.parse_args()

    queries = load_eval_queries(EVAL_QUERIES_PATH)

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


if __name__ == "__main__":
    main()
