"""Run 20-query evaluation set against the RAG system and score citation relevance.

Measures retrieval accuracy (MON-02): target >= 85% (17/20 queries with correct citations).

Usage:
    python scripts/evaluate_retrieval.py
    python scripts/evaluate_retrieval.py --output data/eval/results.json
    python scripts/evaluate_retrieval.py --dry-run   # validate JSON structure only
    python scripts/evaluate_retrieval.py -v          # verbose per-query output
"""

import argparse
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
    args = parser.parse_args()

    queries = load_eval_queries(EVAL_QUERIES_PATH)

    if args.dry_run:
        run_dry_run(queries)
    else:
        run_evaluation(queries, args.output, verbose=args.verbose)


if __name__ == "__main__":
    main()
