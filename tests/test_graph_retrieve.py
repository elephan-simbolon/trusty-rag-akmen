import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes import graph_retrieve_node
from src.agents.state import RAGState


@pytest.fixture
def mock_lightrag():
    """Mock LightRAG instance with aquery method."""
    mock_rag = MagicMock()
    mock_rag.aquery = AsyncMock(return_value="ABC costing requires cost drivers as prerequisite.")
    return mock_rag


def test_graph_retrieve_returns_graph_docs(mock_lightrag):
    """graph_retrieve_node returns graph_docs list with text and metadata."""
    with patch("src.agents.nodes.get_lightrag", return_value=mock_lightrag):
        state = {"query": "apa prerequisite ABC costing?", "error": None}
        result = asyncio.run(graph_retrieve_node(state))
        assert "graph_docs" in result
        assert len(result["graph_docs"]) == 1
        assert result["graph_docs"][0]["metadata"]["content_type"] == "graph_context"


def test_graph_retrieve_skips_on_error():
    """graph_retrieve_node returns empty dict when error is present."""
    state = {"query": "test", "error": "previous error"}
    result = asyncio.run(graph_retrieve_node(state))
    assert result == {}


def test_graph_retrieve_local_mode_for_relational_query(mock_lightrag):
    """Relational keywords trigger local mode."""
    with patch("src.agents.nodes.get_lightrag", return_value=mock_lightrag):
        state = {"query": "apa hubungan variance analysis dengan standard costing?", "error": None}
        result = asyncio.run(graph_retrieve_node(state))
        assert result.get("query_mode") == "local"


def test_graph_retrieve_hybrid_mode_default(mock_lightrag):
    """Non-relational queries default to hybrid mode."""
    with patch("src.agents.nodes.get_lightrag", return_value=mock_lightrag):
        state = {"query": "apa itu overhead cost allocation?", "error": None}
        result = asyncio.run(graph_retrieve_node(state))
        assert result.get("query_mode") == "hybrid"


def test_graph_retrieve_graceful_failure(mock_lightrag):
    """graph_retrieve_node returns empty graph_docs on exception, does not raise."""
    mock_lightrag.aquery = AsyncMock(side_effect=Exception("API error"))
    with patch("src.agents.nodes.get_lightrag", return_value=mock_lightrag):
        state = {"query": "test", "error": None}
        result = asyncio.run(graph_retrieve_node(state))
        assert result == {"graph_docs": []}


def test_ragstate_has_graph_docs_field():
    """RAGState TypedDict includes graph_docs field."""
    annotations = RAGState.__annotations__
    assert "graph_docs" in annotations
    assert "query_mode" in annotations


def test_lightrag_singleton_via_graph_service():
    """get_lightrag singleton is managed by graph_service, not nodes."""
    from src.services.graph_service import get_lightrag, set_lightrag

    original = get_lightrag()
    set_lightrag(None)
    assert get_lightrag() is None
    set_lightrag(original)
