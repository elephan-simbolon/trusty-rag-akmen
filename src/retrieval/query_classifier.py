"""Rule-based query classifier for Phase 3 adaptive routing.

RETR-06: Detect Calculation queries using keyword + number pattern matching,
saving 1 LLM call compared to an LLM-based classifier for all query types.

Pattern: a query is Calculation if it contains BOTH a calculation keyword
AND at least one number. Queries with keywords but no numbers (e.g., "hitung BEP")
are NOT classified as Calculation — they are likely definitional questions.
"""

import re

from config.protocols import PROTOCOL_REGISTRY

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


# Priority order: most-specific protocols first to prevent shadowing.
# variance_analysis before budgeting: "varians anggaran" matches variance, not budgeting.
# cost_classification before cvp: "biaya tetap/variabel" are broad terms caught here first.
# cvp last (before general): BEP/titik impas are CVP-specific but appear in general questions.
_PROTOCOL_PRIORITY = [
    "variance_analysis",
    "abc",
    "transfer_pricing",
    "relevant_costing",
    "product_profitability",
    "budgeting",
    "cost_classification",
    "cvp",
    "general",
]


def select_protocol(query: str) -> str:
    """Return protocol_key for query via rule-based keyword matching (PROT-02).

    Iterates protocols in _PROTOCOL_PRIORITY order. Returns 'general' if no match.
    Zero LLM calls — uses frozenset keyword matching with word-boundary guard
    for short abbreviations (≤4 chars) to prevent false positives.

    Examples:
        "jelaskan break-even point"    → "cvp"
        "hitung varians harga bahan"   → "variance_analysis"
        "apa itu activity-based cost?" → "abc"
        "bandingkan profitabilitas produk" → "product_profitability"
        "apa itu biaya?"               → "general"
        "kontrak ABC dengan vendor"    → not "abc" (word-boundary guard)
    """
    q_lower = query.lower()
    # Pad with spaces for word-boundary matching on short abbreviations
    q_padded = f" {q_lower} "

    for key in _PROTOCOL_PRIORITY:
        if key == "general":
            return "general"
        config = PROTOCOL_REGISTRY[key]
        all_keywords = config.keywords_id | config.keywords_en
        for kw in all_keywords:
            if len(kw) <= 4:
                # Short keywords require word-boundary: check padded string
                if f" {kw} " in q_padded:
                    return key
            else:
                if kw in q_lower:
                    return key
    return "general"
