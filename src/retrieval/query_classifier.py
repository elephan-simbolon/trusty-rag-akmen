"""Rule-based query classifier for Phase 3 adaptive routing.

RETR-06: Detect Calculation queries using keyword + number pattern matching,
saving 1 LLM call compared to an LLM-based classifier for all query types.

Pattern: a query is Calculation if it contains BOTH a calculation keyword
AND at least one number. Queries with keywords but no numbers (e.g., "hitung BEP")
are NOT classified as Calculation — they are likely definitional questions.
"""

import re

_CALC_KEYWORDS = frozenset(
    [
        "hitung",
        "hitunglah",
        "berapa",
        "kalkulasi",
        "kalkulasikan",
        "bep",
        "break-even",
        "break even",
    ]
)

_NUMBER_PATTERN = re.compile(r"\d[\d.,]*")


def is_calculation_query(query: str) -> bool:
    """Return True if query contains calculation keywords AND at least one number.

    Rule-based pre-check (RETR-06) — zero LLM calls.
    Called by route_node before any LLM classifier to preserve Simple=2 budget.

    Examples:
        "hitung BEP dengan fixed cost 100000" → True  (keyword + number)
        "hitung BEP"                          → False (keyword, no number)
        "apa itu break-even point?"           → False (keyword 'break-even', no number)
        "berapa overhead rate jika cost 5000" → True  (keyword + number)
        "jelaskan variance analysis"          → False (no keyword, no number)
    """
    q_lower = query.lower()
    has_keyword = any(kw in q_lower for kw in _CALC_KEYWORDS)
    has_number = bool(_NUMBER_PATTERN.search(query))
    return has_keyword and has_number
