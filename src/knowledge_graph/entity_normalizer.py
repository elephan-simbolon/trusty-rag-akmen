"""Entity name normalizer for accounting knowledge graph deduplication.

Resolves the core entity deduplication problem: LightRAG's LLM-based extraction
creates separate graph nodes for semantically identical entities appearing in
different surface forms across textbooks (e.g., "ABC Costing", "Activity-Based
Costing", "ABC method" all become separate nodes without normalization).

Strategy (priority order):
1. Exact match in ACCOUNTING_CANONICAL
2. Case-insensitive match in ACCOUNTING_CANONICAL
3. Indonesian -> English lookup via GLOSSARY_REVERSE
4. Return raw name unchanged

Used by graph_ingestion.py post-extraction to clean up entity names before
they are written into the LightRAG nano-vectordb storage.
"""
from config.glossary import GLOSSARY, GLOSSARY_REVERSE  # noqa: F401 — re-exported

ACCOUNTING_CANONICAL: dict[str, str] = {
    "ABC Costing": "Activity-Based Costing",
    "ABC method": "Activity-Based Costing",
    "ABC system": "Activity-Based Costing",
    "activity based costing": "Activity-Based Costing",
    "Variable Costing": "Variable Costing",
    "Direct Costing": "Variable Costing",
    "Marginal Costing": "Variable Costing",
    "Absorption Costing": "Absorption Costing",
    "Full Costing": "Absorption Costing",
    "Full Cost Method": "Absorption Costing",
    "Standard Costing": "Standard Costing",
    "Standard Cost System": "Standard Costing",
    "Job Order Costing": "Job Order Costing",
    "Job Costing": "Job Order Costing",
    "Job-Order Costing": "Job Order Costing",
    "Process Costing": "Process Costing",
    "Process Cost System": "Process Costing",
    "BEP": "Break-Even Point",
    "Break Even Point": "Break-Even Point",
    "Breakeven Point": "Break-Even Point",
    "CVP Analysis": "Cost-Volume-Profit Analysis",
    "CVP": "Cost-Volume-Profit Analysis",
    "Cost Volume Profit": "Cost-Volume-Profit Analysis",
    "Overhead Allocation": "Overhead Cost Allocation",
    "OH Allocation": "Overhead Cost Allocation",
    "Variance Analysis": "Variance Analysis",
    "Budget Variance": "Variance Analysis",
}


def normalize_entity_name(raw_name: str) -> str:
    """Normalize an entity name to its canonical accounting form.

    Priority:
    1. Exact match in ACCOUNTING_CANONICAL -> return canonical
    2. Case-insensitive match in ACCOUNTING_CANONICAL -> return canonical
    3. Indonesian term in GLOSSARY_REVERSE -> return English term
    4. No match -> return raw_name unchanged

    Args:
        raw_name: Raw entity name as extracted by LightRAG LLM.

    Returns:
        Canonical entity name, or raw_name if no normalization applies.
    """
    # Step 1: Exact match
    if raw_name in ACCOUNTING_CANONICAL:
        return ACCOUNTING_CANONICAL[raw_name]

    # Step 2: Case-insensitive match
    for variant, canon in ACCOUNTING_CANONICAL.items():
        if raw_name.lower() == variant.lower():
            return canon

    # Step 3: Indonesian -> English lookup via GLOSSARY_REVERSE
    glossary_lower = {k.lower(): v for k, v in GLOSSARY_REVERSE.items()}
    if raw_name.lower() in glossary_lower:
        return glossary_lower[raw_name.lower()]

    # Step 4: No normalization applies
    return raw_name
