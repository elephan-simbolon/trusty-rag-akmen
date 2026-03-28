"""Tests for the 20-query accounting evaluation set structure (MON-02).

These are unit tests — they only validate the JSON file structure without
requiring any live services (no integration marker needed).
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

EVAL_QUERIES_PATH = Path(__file__).parent.parent / "data" / "eval" / "eval_queries.json"
REQUIRED_FIELDS = {"id", "query", "expected_books", "expected_chapters", "difficulty"}
VALID_DIFFICULTIES = {"Simple", "Medium", "Complex", "Calculation"}


@pytest.fixture(scope="module")
def eval_queries() -> list[dict]:
    """Load eval_queries.json once for all tests in this module."""
    assert EVAL_QUERIES_PATH.exists(), (
        f"eval_queries.json not found at {EVAL_QUERIES_PATH}. "
        "Run the evaluation set creation task first."
    )
    with open(EVAL_QUERIES_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_eval_queries_json_loads(eval_queries: list[dict]) -> None:
    """eval_queries.json loads as a list of exactly 20 dicts."""
    assert isinstance(eval_queries, list), "eval_queries.json must be a JSON array"
    assert len(eval_queries) == 20, (
        f"Expected 20 queries, found {len(eval_queries)}. "
        "MON-02 requires exactly 20 curated accounting queries."
    )
    for i, q in enumerate(eval_queries):
        assert isinstance(q, dict), f"Item at index {i} must be a dict, got {type(q)}"


@pytest.mark.e2e
def test_eval_queries_required_fields(eval_queries: list[dict]) -> None:
    """Each query has all required fields: id, query, expected_books, expected_chapters, difficulty."""
    for q in eval_queries:
        qid = q.get("id", f"<missing id at index {eval_queries.index(q)}>")
        missing = REQUIRED_FIELDS - set(q.keys())
        assert not missing, f"Query {qid} is missing required fields: {sorted(missing)}"

        # Type checks
        assert isinstance(q["id"], str), f"{qid}: 'id' must be a string"
        assert isinstance(q["query"], str) and q["query"].strip(), (
            f"{qid}: 'query' must be a non-empty string"
        )
        assert isinstance(q["expected_books"], list) and len(q["expected_books"]) > 0, (
            f"{qid}: 'expected_books' must be a non-empty list"
        )
        assert isinstance(q["expected_chapters"], list) and len(q["expected_chapters"]) > 0, (
            f"{qid}: 'expected_chapters' must be a non-empty list"
        )
        assert q["difficulty"] in VALID_DIFFICULTIES, (
            f"{qid}: 'difficulty' must be one of {VALID_DIFFICULTIES}, got '{q['difficulty']}'"
        )


@pytest.mark.e2e
def test_eval_queries_difficulty_distribution(eval_queries: list[dict]) -> None:
    """Distribution check: at least 4 Simple, 4 Medium/Complex combined, 4 Calculation queries.

    The plan specifies: 6 Simple, 4 Medium, 4 Complex, 4 Calculation, 2 cross-lingual.
    Cross-lingual queries can fall into any difficulty bucket, so we test the minimums.
    """
    dist: dict[str, int] = {}
    for q in eval_queries:
        d = q.get("difficulty", "Unknown")
        dist[d] = dist.get(d, 0) + 1

    simple_count = dist.get("Simple", 0)
    medium_count = dist.get("Medium", 0)
    complex_count = dist.get("Complex", 0)
    calc_count = dist.get("Calculation", 0)

    assert simple_count >= 4, (
        f"Expected at least 4 Simple queries, found {simple_count}. Distribution: {dist}"
    )
    assert medium_count + complex_count >= 4, (
        f"Expected at least 4 Medium+Complex queries, found {medium_count + complex_count}. "
        f"Distribution: {dist}"
    )
    assert calc_count >= 4, (
        f"Expected at least 4 Calculation queries, found {calc_count}. Distribution: {dist}"
    )


@pytest.mark.e2e
def test_eval_queries_unique_ids(eval_queries: list[dict]) -> None:
    """All 20 query IDs are unique and follow the EVAL-XX pattern."""
    ids = [q.get("id") for q in eval_queries]

    # Uniqueness check
    seen = set()
    duplicates = []
    for qid in ids:
        if qid in seen:
            duplicates.append(qid)
        seen.add(qid)
    assert not duplicates, f"Duplicate IDs found: {duplicates}"

    # Pattern check: EVAL-01 through EVAL-20
    for qid in ids:
        assert isinstance(qid, str) and qid.startswith("EVAL-"), (
            f"ID '{qid}' does not follow EVAL-XX naming pattern"
        )

    # Verify sequential range EVAL-01 to EVAL-20
    expected_ids = {f"EVAL-{i:02d}" for i in range(1, 21)}
    actual_ids = set(ids)
    missing_ids = expected_ids - actual_ids
    assert not missing_ids, f"Missing expected IDs: {sorted(missing_ids)}"
