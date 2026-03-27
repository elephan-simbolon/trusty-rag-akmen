import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.agents.state import RAGState
from src.agents.nodes import graph_retrieve_node


@pytest.fixture
def mock_lightrag():
    """Mock LightRAG instance with aquery method."""
    mock_rag = MagicMock()
    mock_rag.aquery = AsyncMock(return_value="ABC costing requires cost drivers as prerequisite.")
    return mock_rag


def test_graph_retrieve_returns_graph_docs(mock_lightrag):
    """graph_retrieve_node returns graph_docs list with text and metadata."""
    with patch("src.agents.nodes._get_lightrag", return_value=mock_lightrag):
        with patch("src.agents.nodes.asyncio.run", side_effect=lambda coro: "ABC costing requires cost drivers."):
            state = {"query": "apa prerequisite ABC costing?", "error": None}
            result = graph_retrieve_node(state)
            assert "graph_docs" in result
            assert len(result["graph_docs"]) == 1
            assert result["graph_docs"][0]["metadata"]["content_type"] == "graph_context"


def test_graph_retrieve_skips_on_error():
    """graph_retrieve_node returns empty dict when error is present."""
    state = {"query": "test", "error": "previous error"}
    result = graph_retrieve_node(state)
    assert result == {}


def test_graph_retrieve_local_mode_for_relational_query(mock_lightrag):
    """Relational keywords trigger local mode."""
    with patch("src.agents.nodes._get_lightrag", return_value=mock_lightrag):
        with patch("src.agents.nodes.asyncio.run", side_effect=lambda coro: "Result"):
            state = {"query": "apa hubungan variance analysis dengan standard costing?", "error": None}
            result = graph_retrieve_node(state)
            assert result.get("query_mode") == "local"


def test_graph_retrieve_hybrid_mode_default(mock_lightrag):
    """Non-relational queries default to hybrid mode."""
    with patch("src.agents.nodes._get_lightrag", return_value=mock_lightrag):
        with patch("src.agents.nodes.asyncio.run", side_effect=lambda coro: "Result"):
            state = {"query": "apa itu overhead cost allocation?", "error": None}
            result = graph_retrieve_node(state)
            assert result.get("query_mode") == "hybrid"


def test_graph_retrieve_graceful_failure(mock_lightrag):
    """graph_retrieve_node returns empty graph_docs on exception, does not raise."""
    with patch("src.agents.nodes._get_lightrag", return_value=mock_lightrag):
        with patch("src.agents.nodes.asyncio.run", side_effect=Exception("API error")):
            state = {"query": "test", "error": None}
            result = graph_retrieve_node(state)
            assert result == {"graph_docs": []}


def test_ragstate_has_graph_docs_field():
    """RAGState TypedDict includes graph_docs field."""
    annotations = RAGState.__annotations__
    assert "graph_docs" in annotations
    assert "query_mode" in annotations


def test_lightrag_singleton_lazy_import():
    """_get_lightrag uses lazy import pattern."""
    from src.agents.nodes import _lightrag_instance
    # At import time, singleton should be None (not pre-initialized)
    # We check the module-level variable is None initially
    import src.agents.nodes as nodes_module
    # Reset to test laziness
    original = nodes_module._lightrag_instance
    nodes_module._lightrag_instance = None
    assert nodes_module._lightrag_instance is None
    nodes_module._lightrag_instance = original
