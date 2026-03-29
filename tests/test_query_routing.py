"""Tests for Phase 3 query routing: RETR-05 (route_node) and RETR-06 (is_calculation_query).

Tests are pure-function unit tests — no mocks, no live services.
"""

from src.agents.state import RAGState
from src.retrieval.query_classifier import is_calculation_query

# ---------------------------------------------------------------------------
# RETR-06: Rule-based Calculation detection (is_calculation_query)
# ---------------------------------------------------------------------------


class TestIsCalculationQuery:
    """Requirement RETR-06: detect Calculation queries via rule (numbers + keywords),
    saving 1 LLM call compared to using an LLM classifier for all queries.
    """

    def test_hitung_bep_with_number_returns_true(self):
        """'hitung BEP dengan data ini: fixed cost 100000' has keyword + number."""
        assert is_calculation_query("hitung BEP dengan data ini: fixed cost 100000") is True

    def test_hitung_bep_without_number_returns_false(self):
        """'hitung BEP' has keyword but no number — should not be Calculation."""
        assert is_calculation_query("hitung BEP") is False

    def test_no_keyword_no_number_returns_false(self):
        """'apa itu break-even point?' contains 'break-even' keyword but no number."""
        assert is_calculation_query("apa itu break-even point?") is False

    def test_berapa_with_fixed_cost_and_units_returns_true(self):
        """'berapa overhead allocation rate jika fixed cost 50000 dan units 1000?' has keyword + numbers."""
        assert (
            is_calculation_query(
                "berapa overhead allocation rate jika fixed cost 50000 dan units 1000?"
            )
            is True
        )

    def test_jelaskan_variance_without_number_returns_false(self):
        """'jelaskan variance analysis' has no number."""
        assert is_calculation_query("jelaskan variance analysis") is False

    def test_kalkulasi_with_number_returns_true(self):
        """'kalkulasi biaya overhead 25000 per unit' has keyword + number."""
        assert is_calculation_query("kalkulasi biaya overhead 25000 per unit") is True

    def test_hitunglah_with_number_returns_true(self):
        """'hitunglah BEP jika fixed cost adalah 200.000' has keyword + number (with period separator)."""
        assert is_calculation_query("hitunglah BEP jika fixed cost adalah 200.000") is True

    def test_break_even_with_number_returns_true(self):
        """'break even point dengan fixed cost 500' has keyword + number."""
        assert is_calculation_query("break even point dengan fixed cost 500") is True

    def test_empty_string_returns_false(self):
        """Empty query should return False."""
        assert is_calculation_query("") is False

    def test_number_only_without_keyword_returns_false(self):
        """'100000 adalah biaya tetap' has number but no calculation keyword."""
        assert is_calculation_query("100000 adalah biaya tetap") is False


# ---------------------------------------------------------------------------
# RAGState: field completeness checks
# ---------------------------------------------------------------------------


class TestRAGStateFields:
    """Verify RAGState contains all expected fields from Phase 1, 2, and 3."""

    PHASE_1_FIELDS = {
        "query",
        "expanded_query",
        "query_embedding",
        "retrieved_docs",
        "reranked_docs",
        "response",
        "citations",
        "error",
    }

    PHASE_2_FIELDS = {
        "graph_docs",
    }

    PHASE_3_FIELDS = {
        "query_type",
        "crag_grade",
        "crag_iterations",
        "llm_call_count",
        "conversation_history",
    }

    def test_phase1_fields_present(self):
        """All Phase 1 fields must be preserved."""
        annotations = RAGState.__annotations__
        for field in self.PHASE_1_FIELDS:
            assert field in annotations, f"Phase 1 field '{field}' missing from RAGState"

    def test_phase2_fields_present(self):
        """All Phase 2 fields must be preserved."""
        annotations = RAGState.__annotations__
        for field in self.PHASE_2_FIELDS:
            assert field in annotations, f"Phase 2 field '{field}' missing from RAGState"

    def test_phase3_fields_present(self):
        """All Phase 3 fields must be present."""
        annotations = RAGState.__annotations__
        for field in self.PHASE_3_FIELDS:
            assert field in annotations, f"Phase 3 field '{field}' missing from RAGState"

    def test_total_field_count(self):
        """RAGState should have exactly 14 fields (8 Phase 1 + 1 Phase 2 + 5 Phase 3)."""
        annotations = RAGState.__annotations__
        assert len(annotations) == 14, (
            f"Expected 14 fields, got {len(annotations)}. Fields: {sorted(annotations.keys())}"
        )

    def test_conversation_history_uses_annotated_reducer(self):
        """conversation_history must use Annotated[list, operator.add] for MemorySaver accumulation."""
        import operator

        annotations = RAGState.__annotations__
        assert "conversation_history" in annotations
        ann = annotations["conversation_history"]
        # Annotated types have __metadata__ attribute
        assert hasattr(ann, "__metadata__"), (
            "conversation_history must be Annotated[list, operator.add], not plain list"
        )
        assert operator.add in ann.__metadata__, (
            "conversation_history Annotated metadata must include operator.add"
        )
