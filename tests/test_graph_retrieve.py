from unittest.mock import MagicMock, patch

import pytest

from src.agents.nodes import graph_retrieve_node
from src.agents.state import RAGState


class MockContext:
    """Mimics TContext dataclass with entities, relationships, chunks as List[Tuple[item, score]]."""
    def __init__(self, entities=None, relationships=None, chunks=None):
        self.entities = entities or []
        self.relationships = relationships or []
        self.chunks = chunks or []


class MockAnswer:
    def __init__(self, context):
        self.context = context
        self.response = ""


@pytest.fixture
def mock_graphrag():
    """Mock GraphRAG instance with query method."""
    mock_grag = MagicMock()
    mock_grag.query = MagicMock(
        return_value=MockAnswer(
            context=MockContext(
                entities=[("ABC Costing", 0.9), ("Cost Driver", 0.8)],
                relationships=[("ABC Costing -> REQUIRES -> Cost Driver", 0.85)],
                chunks=[("ABC costing requires cost drivers as prerequisite.", 0.7)],
            )
        )
    )
    return mock_grag


def test_graph_retrieve_returns_graph_docs(mock_graphrag):
    """graph_retrieve_node returns graph_docs list with text and metadata."""
    with patch("src.agents.nodes.get_graphrag", return_value=mock_graphrag):
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


def test_graph_retrieve_graceful_failure(mock_graphrag):
    """graph_retrieve_node returns empty graph_docs on exception, does not raise."""
    mock_graphrag.query = MagicMock(side_effect=Exception("API error"))
    with patch("src.agents.nodes.get_graphrag", return_value=mock_graphrag):
        state = {"query": "test", "error": None}
        result = graph_retrieve_node(state)
        assert result == {"graph_docs": []}


def test_graph_retrieve_none_graphrag_returns_empty():
    """graph_retrieve_node returns empty graph_docs when GraphRAG is None."""
    with patch("src.agents.nodes.get_graphrag", return_value=None):
        state = {"query": "test", "error": None}
        result = graph_retrieve_node(state)
        assert result == {"graph_docs": []}


def test_graph_retrieve_metadata_section_path(mock_graphrag):
    """graph_docs metadata section_path is 'GraphRAG/context'."""
    with patch("src.agents.nodes.get_graphrag", return_value=mock_graphrag):
        state = {"query": "apa itu overhead?", "error": None}
        result = graph_retrieve_node(state)
        assert result["graph_docs"][0]["metadata"]["section_path"] == "GraphRAG/context"


def test_ragstate_has_graph_docs_field():
    """RAGState TypedDict includes graph_docs field."""
    annotations = RAGState.__annotations__
    assert "graph_docs" in annotations


def test_graphrag_singleton_via_graph_service():
    """get_graphrag singleton is managed by graph_service, not nodes."""
    from src.services.graph_service import get_graphrag, set_graphrag

    original = get_graphrag()
    set_graphrag(None)
    assert get_graphrag() is None
    set_graphrag(original)
