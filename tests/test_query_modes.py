"""Integration tests for query mode routing in graph_retrieve_node — RETR-03.

Verifies that the full state flow through graph_retrieve_node selects the
correct LightRAG query mode based on query content:
- Relational keywords (hubungan, prasyarat, relasi, etc.) trigger "local" mode
- Non-relational queries default to "hybrid" mode
- Returned state contains graph_docs with correct mode reflected in metadata
- Explicit query_mode in state is respected for non-relational queries
- Mode routing is deterministic across all defined relational keywords

These are integration-level tests that cover the full state flow through the
node, complementing the unit-level tests in test_graph_retrieve.py.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.agents.nodes import graph_retrieve_node
from src.agents.state import RAGState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_lightrag():
    """Mock LightRAG instance returning a deterministic graph result string."""
    rag = MagicMock()
    rag.aquery = AsyncMock(
        return_value=(
            "Activity-Based Costing uses cost drivers. "
            "Standard Costing is a prerequisite for variance analysis."
        )
    )
    return rag


def _run_node(query: str, extra_state: dict = None):
    """Helper: run graph_retrieve_node with a mocked LightRAG instance."""
    mock_rag = MagicMock()
    mock_rag.aquery = AsyncMock(return_value="Mock graph result.")

    state = {"query": query, "error": None}
    if extra_state:
        state.update(extra_state)

    with patch("src.agents.nodes._get_lightrag", return_value=mock_rag):
        with patch(
            "src.agents.nodes.asyncio.run",
            side_effect=lambda coro: "Mock graph result.",
        ):
            result = graph_retrieve_node(state)
    return result


# ---------------------------------------------------------------------------
# Mode routing — relational keywords select "local"
# ---------------------------------------------------------------------------

def test_relational_keyword_hubungan_triggers_local_mode():
    """Query containing 'hubungan' selects local mode in full node state flow."""
    result = _run_node("apa hubungan antara ABC costing dan cost driver?")
    assert result.get("query_mode") == "local"


def test_relational_keyword_prasyarat_triggers_local_mode():
    """Query containing 'prasyarat' selects local mode."""
    result = _run_node("apa prasyarat untuk memahami variance analysis?")
    assert result.get("query_mode") == "local"


def test_relational_keyword_prerequisite_triggers_local_mode():
    """Query containing English 'prerequisite' triggers local mode."""
    result = _run_node("what is the prerequisite for standard costing?")
    assert result.get("query_mode") == "local"


def test_relational_keyword_relasi_triggers_local_mode():
    """Query containing 'relasi' triggers local mode."""
    result = _run_node("jelaskan relasi antara overhead cost dan cost driver")
    assert result.get("query_mode") == "local"


def test_relational_keyword_sebelum_triggers_local_mode():
    """Query containing 'sebelum' (before) triggers local mode."""
    result = _run_node("konsep apa yang harus dipahami sebelum mempelajari ABC costing?")
    assert result.get("query_mode") == "local"


def test_relational_keyword_dasar_dari_triggers_local_mode():
    """Query containing 'dasar dari' triggers local mode."""
    result = _run_node("apa yang menjadi dasar dari alokasi overhead?")
    assert result.get("query_mode") == "local"


# ---------------------------------------------------------------------------
# Mode routing — non-relational queries default to "hybrid"
# ---------------------------------------------------------------------------

def test_non_relational_query_defaults_to_hybrid_mode():
    """Plain definition query defaults to hybrid mode."""
    result = _run_node("apa itu activity-based costing?")
    assert result.get("query_mode") == "hybrid"


def test_comparison_query_defaults_to_hybrid_mode():
    """Comparison query without relational keywords defaults to hybrid mode."""
    result = _run_node("bandingkan variable costing dan absorption costing")
    assert result.get("query_mode") == "hybrid"


def test_calculation_query_defaults_to_hybrid_mode():
    """Calculation query defaults to hybrid mode."""
    result = _run_node("hitung break-even point dengan fixed cost 100 juta")
    assert result.get("query_mode") == "hybrid"


# ---------------------------------------------------------------------------
# Explicit query_mode in state is respected for non-relational queries
# ---------------------------------------------------------------------------

def test_explicit_query_mode_local_respected_for_non_relational_query():
    """When state sets query_mode='local' and query is non-relational, local is used."""
    result = _run_node(
        "apa itu standard costing?",
        extra_state={"query_mode": "local"},
    )
    assert result.get("query_mode") == "local"


def test_explicit_query_mode_hybrid_respected():
    """When state sets query_mode='hybrid', hybrid mode is used for non-relational query."""
    result = _run_node(
        "apa itu overhead allocation?",
        extra_state={"query_mode": "hybrid"},
    )
    assert result.get("query_mode") == "hybrid"


# ---------------------------------------------------------------------------
# Full state flow: graph_docs shape and content after mode selection
# ---------------------------------------------------------------------------

def test_local_mode_query_returns_non_empty_graph_docs():
    """Relational query (local mode) returns non-empty graph_docs in state."""
    result = _run_node("apa hubungan ABC dengan cost driver?")
    assert "graph_docs" in result
    assert len(result["graph_docs"]) > 0


def test_local_mode_graph_docs_metadata_reflects_mode():
    """graph_docs metadata section_path reflects 'local' mode when local is selected."""
    result = _run_node("apa hubungan variance analysis dengan standard costing?")
    assert result["graph_docs"][0]["metadata"]["section_path"] == "LightRAG/local mode"


def test_hybrid_mode_graph_docs_metadata_reflects_mode():
    """graph_docs metadata section_path reflects 'hybrid' mode when hybrid is selected."""
    result = _run_node("jelaskan ABC costing secara singkat")
    assert result["graph_docs"][0]["metadata"]["section_path"] == "LightRAG/hybrid mode"


def test_graph_retrieve_node_returns_graph_context_text():
    """graph_docs[0]['text'] contains the string returned by LightRAG aquery."""
    result = _run_node("apa itu overhead allocation?")
    assert result["graph_docs"][0]["text"] == "Mock graph result."


def test_graph_docs_have_required_metadata_keys():
    """graph_docs entries contain all required metadata keys."""
    result = _run_node("apa itu standard costing?")
    meta = result["graph_docs"][0]["metadata"]
    required_keys = ["book_title", "chapter", "content_type", "page_start", "page_end", "section_path"]
    for key in required_keys:
        assert key in meta, f"Missing metadata key: {key}"


def test_graph_docs_content_type_is_graph_context():
    """graph_docs metadata content_type is always 'graph_context'."""
    result = _run_node("apa prasyarat ABC costing?")
    assert result["graph_docs"][0]["metadata"]["content_type"] == "graph_context"
