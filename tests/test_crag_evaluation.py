"""Tests for CRAG quality gate nodes and generate_calc_node.

Covers:
- crag_grade_node grading thresholds (CORRECT/AMBIGUOUS/INCORRECT)
- crag_grade_node increments crag_iterations
- crag_router routing logic with cap at 2 iterations
- reformulate_node overwrites query key and increments llm_call_count
- generate_calc_node returns response with disclaimer text
- generate_response accepts query_type stub without TypeError
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# crag_grade_node tests
# ---------------------------------------------------------------------------

class TestCragGradeNode:
    def test_grade_correct_high_score(self):
        """reranked_docs with max rerank_score=0.7 → CORRECT."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [
                {"text": "doc1", "rerank_score": 0.7},
                {"text": "doc2", "rerank_score": 0.4},
            ],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "CORRECT"

    def test_grade_ambiguous_mid_score(self):
        """reranked_docs with max rerank_score=0.35 → AMBIGUOUS."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [
                {"text": "doc1", "rerank_score": 0.35},
                {"text": "doc2", "rerank_score": 0.1},
            ],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "AMBIGUOUS"

    def test_grade_incorrect_low_score(self):
        """reranked_docs with max rerank_score=0.1 → INCORRECT."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [
                {"text": "doc1", "rerank_score": 0.1},
            ],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "INCORRECT"

    def test_grade_incorrect_empty_docs(self):
        """Empty reranked_docs → INCORRECT."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "INCORRECT"

    def test_grade_increments_iterations(self):
        """crag_grade_node increments crag_iterations by 1."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [{"text": "doc", "rerank_score": 0.8}],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_iterations"] == 1

    def test_grade_increments_from_existing(self):
        """crag_grade_node increments from existing iteration count."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [{"text": "doc", "rerank_score": 0.8}],
            "crag_iterations": 1,
        }
        result = crag_grade_node(state)
        assert result["crag_iterations"] == 2

    def test_grade_none_reranked_docs(self):
        """None reranked_docs (not set) → INCORRECT."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": None,
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "INCORRECT"

    def test_grade_threshold_boundary_correct(self):
        """Score exactly at 0.5 → CORRECT (inclusive lower bound)."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [{"text": "doc", "rerank_score": 0.5}],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "CORRECT"

    def test_grade_threshold_boundary_ambiguous(self):
        """Score exactly at 0.2 → AMBIGUOUS (inclusive lower bound)."""
        from src.agents.nodes import crag_grade_node

        state = {
            "query": "apa itu BEP?",
            "reranked_docs": [{"text": "doc", "rerank_score": 0.2}],
            "crag_iterations": 0,
        }
        result = crag_grade_node(state)
        assert result["crag_grade"] == "AMBIGUOUS"


# ---------------------------------------------------------------------------
# crag_router tests
# ---------------------------------------------------------------------------

class TestCragRouter:
    def test_route_correct_simple_to_generate(self):
        """CORRECT grade + Simple query_type → 'generate'."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "CORRECT",
            "crag_iterations": 1,
            "query_type": "Simple",
        }
        assert crag_router(state) == "generate"

    def test_route_correct_calculation_to_generate_calc(self):
        """CORRECT grade + Calculation query_type → 'generate_calc'."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "CORRECT",
            "crag_iterations": 1,
            "query_type": "Calculation",
        }
        assert crag_router(state) == "generate_calc"

    def test_route_ambiguous_under_cap_to_reformulate(self):
        """AMBIGUOUS grade + iterations < 2 → 'reformulate'."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "AMBIGUOUS",
            "crag_iterations": 1,
            "query_type": "Simple",
        }
        assert crag_router(state) == "reformulate"

    def test_route_ambiguous_at_cap_to_generate(self):
        """AMBIGUOUS grade + iterations >= 2 (cap hit) → 'generate'."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "AMBIGUOUS",
            "crag_iterations": 2,
            "query_type": "Simple",
        }
        assert crag_router(state) == "generate"

    def test_route_incorrect_under_cap_to_reformulate(self):
        """INCORRECT grade + iterations < 2 → 'reformulate'."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "INCORRECT",
            "crag_iterations": 1,
            "query_type": "Simple",
        }
        assert crag_router(state) == "reformulate"

    def test_route_incorrect_at_cap_to_generate(self):
        """INCORRECT grade + iterations >= 2 (cap hit, graceful degradation) → 'generate'."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "INCORRECT",
            "crag_iterations": 2,
            "query_type": "Simple",
        }
        assert crag_router(state) == "generate"

    def test_route_incorrect_at_cap_calculation_to_generate_calc(self):
        """INCORRECT grade + iterations >= 2 + Calculation → 'generate_calc' (graceful degradation, calc path)."""
        from src.agents.nodes import crag_router

        state = {
            "crag_grade": "INCORRECT",
            "crag_iterations": 2,
            "query_type": "Calculation",
        }
        assert crag_router(state) == "generate_calc"


# ---------------------------------------------------------------------------
# reformulate_node tests
# ---------------------------------------------------------------------------

class TestReformulateNode:
    def test_reformulate_overwrites_query_key(self):
        """reformulate_node writes to 'query' key (not a different key)."""
        from src.agents.nodes import reformulate_node

        with patch("src.agents.nodes.llm_generate") as mock_generate:
            mock_generate.return_value = "pertanyaan yang lebih spesifik tentang BEP"
            state = {
                "query": "apa itu BEP?",
                "llm_call_count": 0,
            }
            result = reformulate_node(state)
            assert "query" in result
            assert result["query"] == "pertanyaan yang lebih spesifik tentang BEP"

    def test_reformulate_increments_llm_call_count(self):
        """reformulate_node increments llm_call_count by 1."""
        from src.agents.nodes import reformulate_node

        with patch("src.agents.nodes.llm_generate") as mock_generate:
            mock_generate.return_value = "reformulated query"
            state = {
                "query": "apa itu BEP?",
                "llm_call_count": 2,
            }
            result = reformulate_node(state)
            assert result["llm_call_count"] == 3

    def test_reformulate_on_failure_keeps_original_query(self):
        """If LLM call fails, reformulate_node keeps original query and doesn't increment count."""
        from src.agents.nodes import reformulate_node

        with patch("src.agents.nodes.llm_generate") as mock_generate:
            mock_generate.side_effect = Exception("API error")
            state = {
                "query": "apa itu BEP?",
                "llm_call_count": 1,
            }
            result = reformulate_node(state)
            assert result["query"] == "apa itu BEP?"
            assert result["llm_call_count"] == 1

    def test_reformulate_strips_whitespace(self):
        """reformulate_node strips whitespace from reformulated query."""
        from src.agents.nodes import reformulate_node

        with patch("src.agents.nodes.llm_generate") as mock_generate:
            mock_generate.return_value = "  reformulated query with spaces  "
            state = {
                "query": "apa itu BEP?",
                "llm_call_count": 0,
            }
            result = reformulate_node(state)
            assert result["query"] == "reformulated query with spaces"


# ---------------------------------------------------------------------------
# generate_calc_node tests
# ---------------------------------------------------------------------------

class TestGenerateCalcNode:
    def test_generate_calc_returns_disclaimer(self):
        """generate_calc_node returns response containing disclaimer text."""
        from src.agents.nodes import generate_calc_node

        with patch("src.agents.nodes.generate_response") as mock_gen:
            mock_gen.return_value = {
                "response": "Langkah 1: BEP = FC / CM\n\nVerifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional.",
                "citations": [],
            }
            state = {
                "query": "hitung BEP jika fixed cost 100000 dan CM per unit 30000",
                "reranked_docs": [{"text": "BEP formula", "rerank_score": 0.8, "metadata": {}}],
                "graph_docs": [],
                "llm_call_count": 0,
                "error": None,
            }
            result = generate_calc_node(state)
            assert "Verifikasi hasil dengan sumber resmi" in result["response"]

    def test_generate_calc_calls_generate_response_with_calculation_type(self):
        """generate_calc_node calls generate_response with query_type='Calculation'."""
        from src.agents.nodes import generate_calc_node

        with patch("src.agents.nodes.generate_response") as mock_gen:
            mock_gen.return_value = {
                "response": "Calculation response\nVerifikasi hasil dengan sumber resmi",
                "citations": [],
            }
            state = {
                "query": "hitung BEP",
                "reranked_docs": [{"text": "formula", "rerank_score": 0.7, "metadata": {}}],
                "graph_docs": [],
                "llm_call_count": 0,
                "error": None,
            }
            generate_calc_node(state)
            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args
            assert call_kwargs.kwargs.get("query_type") == "Calculation" or \
                   (len(call_kwargs.args) >= 4 and call_kwargs.args[3] == "Calculation")

    def test_generate_calc_increments_llm_call_count(self):
        """generate_calc_node increments llm_call_count."""
        from src.agents.nodes import generate_calc_node

        with patch("src.agents.nodes.generate_response") as mock_gen:
            mock_gen.return_value = {
                "response": "Calculation response",
                "citations": [],
            }
            state = {
                "query": "hitung BEP",
                "reranked_docs": [{"text": "formula", "rerank_score": 0.7, "metadata": {}}],
                "graph_docs": [],
                "llm_call_count": 1,
                "error": None,
            }
            result = generate_calc_node(state)
            assert result["llm_call_count"] == 2

    def test_generate_calc_error_state(self):
        """generate_calc_node returns error message if state has error."""
        from src.agents.nodes import generate_calc_node

        state = {
            "query": "hitung BEP",
            "reranked_docs": [],
            "error": "Retrieval failed",
        }
        result = generate_calc_node(state)
        assert "Terjadi kesalahan" in result["response"]
        assert result["citations"] == []

    def test_generate_calc_no_docs(self):
        """generate_calc_node returns 'tidak ditemukan' message if no docs."""
        from src.agents.nodes import generate_calc_node

        state = {
            "query": "hitung BEP",
            "reranked_docs": [],
            "graph_docs": [],
            "llm_call_count": 0,
            "error": None,
        }
        result = generate_calc_node(state)
        assert "Tidak ditemukan" in result["response"]
        assert result["citations"] == []

    def test_generate_calc_adds_conversation_history(self):
        """generate_calc_node adds conversation_history with user/assistant turns."""
        from src.agents.nodes import generate_calc_node

        with patch("src.agents.nodes.generate_response") as mock_gen:
            mock_gen.return_value = {
                "response": "Calculation response",
                "citations": [],
            }
            state = {
                "query": "hitung BEP",
                "reranked_docs": [{"text": "formula", "rerank_score": 0.7, "metadata": {}}],
                "graph_docs": [],
                "llm_call_count": 0,
                "error": None,
            }
            result = generate_calc_node(state)
            assert "conversation_history" in result
            assert len(result["conversation_history"]) == 2
            assert result["conversation_history"][0]["role"] == "user"
            assert result["conversation_history"][1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# generate_response stub parameter test
# ---------------------------------------------------------------------------

class TestGenerateResponseQueryTypeStub:
    def test_generate_response_accepts_query_type_kwarg(self):
        """generate_response accepts query_type kwarg without TypeError (stub test)."""
        from src.generation.generator import generate_response
        import inspect

        sig = inspect.signature(generate_response)
        assert "query_type" in sig.parameters, (
            "generate_response must have query_type parameter (backward-compatible stub)"
        )

    def test_generate_response_query_type_has_default(self):
        """generate_response query_type has default value of 'Simple'."""
        from src.generation.generator import generate_response
        import inspect

        sig = inspect.signature(generate_response)
        param = sig.parameters["query_type"]
        assert param.default == "Simple", (
            f"query_type default should be 'Simple', got {param.default!r}"
        )

    def test_generate_response_query_type_noop_with_mock(self):
        """generate_response with query_type='Calculation' produces same result as without (no-op stub)."""
        from src.generation.generator import generate_response

        with patch("src.generation.generator.generate") as mock_generate, \
             patch("src.generation.generator.build_citations") as mock_citations:
            mock_generate.return_value = "Test response"
            mock_citations.return_value = []

            docs = [{"text": "some doc", "metadata": {"book_title": "Test", "chapter": "Ch1", "page_start": 1}}]

            result_default = generate_response(
                query="test query",
                context_docs=docs,
            )
            result_calc = generate_response(
                query="test query",
                context_docs=docs,
                query_type="Calculation",
            )

            # Both should call generate with the same arguments (no-op: query_type ignored)
            assert result_default["response"] == result_calc["response"]
