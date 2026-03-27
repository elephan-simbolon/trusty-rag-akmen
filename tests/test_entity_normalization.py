"""Unit tests for entity normalizer — accounting term deduplication.

Tests verify:
- Exact canonical match
- Case-insensitive matching
- Alias resolution for common accounting term variants
- Unknown terms pass through unchanged
- ACCOUNTING_CANONICAL has minimum 25 mappings
"""
from src.knowledge_graph.entity_normalizer import ACCOUNTING_CANONICAL, normalize_entity_name


def test_exact_match_abc_costing():
    assert normalize_entity_name("ABC Costing") == "Activity-Based Costing"


def test_case_insensitive_match():
    assert normalize_entity_name("abc costing") == "Activity-Based Costing"


def test_full_costing_maps_to_absorption():
    assert normalize_entity_name("Full Costing") == "Absorption Costing"


def test_variable_costing_alias_direct_costing():
    assert normalize_entity_name("Direct Costing") == "Variable Costing"


def test_bep_alias():
    assert normalize_entity_name("BEP") == "Break-Even Point"


def test_cvp_alias():
    assert normalize_entity_name("CVP") == "Cost-Volume-Profit Analysis"


def test_unknown_term_returns_unchanged():
    assert normalize_entity_name("SomeUnknownTerm") == "SomeUnknownTerm"


def test_job_order_variants():
    assert normalize_entity_name("Job Costing") == "Job Order Costing"
    assert normalize_entity_name("Job-Order Costing") == "Job Order Costing"


def test_canonical_count():
    assert len(ACCOUNTING_CANONICAL) >= 25
