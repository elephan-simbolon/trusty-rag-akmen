"""Tests for select_protocol() in src/retrieval/query_classifier.py — PROT-02.

Rule-based protocol selector: zero LLM calls, keyword matching with word-boundary
guard for short abbreviations (<=4 chars).
"""

import pytest
from src.retrieval.query_classifier import select_protocol, is_calculation_query


class TestSelectProtocolRouting:
    """Verify select_protocol() routes each query to the correct protocol."""

    def test_cvp_break_even(self):
        """'jelaskan break-even point' → 'cvp'."""
        assert select_protocol("jelaskan break-even point") == "cvp"

    def test_variance_analysis(self):
        """'hitung varians harga bahan baku' → 'variance_analysis'."""
        assert select_protocol("hitung varians harga bahan baku") == "variance_analysis"

    def test_abc_activity_based(self):
        """'apa itu activity-based costing?' → 'abc'."""
        assert select_protocol("apa itu activity-based costing?") == "abc"

    def test_transfer_pricing(self):
        """'bagaimana harga transfer ditetapkan?' → 'transfer_pricing'."""
        assert select_protocol("bagaimana harga transfer ditetapkan?") == "transfer_pricing"

    def test_relevant_costing_make_or_buy(self):
        """'biaya relevan dalam keputusan make or buy' → 'relevant_costing'."""
        assert select_protocol("biaya relevan dalam keputusan make or buy") == "relevant_costing"

    def test_product_profitability(self):
        """'profitabilitas produk lini A' → 'product_profitability'."""
        assert select_protocol("profitabilitas produk lini A") == "product_profitability"

    def test_budgeting_master_budget(self):
        """'bagaimana membuat master budget?' → 'budgeting'."""
        assert select_protocol("bagaimana membuat master budget?") == "budgeting"

    def test_cost_classification_fixed_variable(self):
        """'apa perbedaan biaya tetap dan biaya variabel?' → 'cost_classification'."""
        assert select_protocol("apa perbedaan biaya tetap dan biaya variabel?") == "cost_classification"

    def test_general_unknown_query(self):
        """'apa itu akuntansi manajemen?' → 'general' (no specific keyword match)."""
        assert select_protocol("apa itu akuntansi manajemen?") == "general"

    def test_general_empty_string(self):
        """Empty string → 'general'."""
        assert select_protocol("") == "general"


class TestSelectProtocolWordBoundaryGuard:
    """Short keywords (<=4 chars) must use word-boundary matching."""

    def test_abc_in_contract_context_no_match(self):
        """'kontrak ABC dengan vendor lainnya' must NOT match 'abc' protocol.

        'abc' is <=4 chars, so word-boundary check applies.
        However 'ABC' is uppercase in middle of sentence — it's an abbreviation
        in a non-accounting context. The guard prevents false positives.
        """
        assert select_protocol("kontrak ABC dengan vendor lainnya") != "abc"

    def test_bep_standalone_matches_cvp(self):
        """'titik bep optimal' should match 'cvp' (bep is a known CVP term)."""
        # 'bep' is <=4 chars, must appear as standalone word
        result = select_protocol("titik bep optimal")
        assert result == "cvp"

    def test_cvp_abbreviation_matches(self):
        """'analisis cvp dasar' should match 'cvp' protocol."""
        result = select_protocol("analisis cvp dasar")
        assert result == "cvp"


class TestSelectProtocolReturnType:
    """select_protocol() must always return a string protocol key."""

    def test_returns_string(self):
        """select_protocol always returns a str."""
        assert isinstance(select_protocol("apa itu biaya?"), str)

    def test_returns_valid_key(self):
        """Return value must be a valid PROTOCOL_REGISTRY key."""
        from config.protocols import PROTOCOL_REGISTRY
        result = select_protocol("varians harga bahan baku favorable")
        assert result in PROTOCOL_REGISTRY


class TestIsCalculationQueryUnchanged:
    """Verify is_calculation_query() behavior is unchanged after appending select_protocol()."""

    def test_still_works_with_number(self):
        """is_calculation_query still returns True for keyword + number."""
        assert is_calculation_query("hitung BEP dengan fixed cost 100000") is True

    def test_still_works_without_number(self):
        """is_calculation_query still returns False without number."""
        assert is_calculation_query("hitung BEP") is False

    def test_empty_string(self):
        """is_calculation_query still returns False for empty string."""
        assert is_calculation_query("") is False
