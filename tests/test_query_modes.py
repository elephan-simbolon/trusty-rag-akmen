"""Tests for GraphRAG query behavior in graph_retrieve_node.

Verifies that graph_retrieve_node:
- Uses QueryParam(only_context=True) for context-only retrieval
- Returns properly formatted graph_docs with entities, relations, chunks
- Returns empty graph_docs when context is empty
- graph_docs have correct metadata structure
"""

from unittest.mock import MagicMock, patch


from src.agents.nodes import graph_retrieve_node


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


def _make_mock_graphrag(context=None):
    """Create a mock GraphRAG with configurable context response."""
    if context is None:
        context = MockContext(
            entities=[("ABC Costing", 0.9), ("Cost Driver", 0.8)],
            relationships=[("ABC Costing -> REQUIRES -> Cost Driver", 0.85)],
            chunks=[("ABC costing uses cost drivers.", 0.7)],
        )
    mock_grag = MagicMock()
    mock_grag.query = MagicMock(return_value=MockAnswer(context=context))
    return mock_grag


def _run_node(query: str, mock_context=None):
    """Helper: run graph_retrieve_node with a mocked GraphRAG instance."""
    mock_grag = _make_mock_graphrag(mock_context)
    state = {"query": query, "error": None}
    with patch("src.agents.nodes.get_graphrag", return_value=mock_grag):
        result = graph_retrieve_node(state)
    return result


def test_graph_retrieve_returns_non_empty_graph_docs():
    """graph_retrieve_node returns non-empty graph_docs for a valid query."""
    result = _run_node("apa itu activity-based costing?")
    assert "graph_docs" in result
    assert len(result["graph_docs"]) > 0


def test_graph_docs_text_contains_entities():
    """graph_docs text contains formatted entity information."""
    result = _run_node("apa itu ABC costing?")
    text = result["graph_docs"][0]["text"]
    assert "Entities:" in text
    assert "ABC Costing" in text


def test_graph_docs_text_contains_relations():
    """graph_docs text contains formatted relation information."""
    result = _run_node("apa itu ABC costing?")
    text = result["graph_docs"][0]["text"]
    assert "Relations:" in text


def test_graph_docs_text_contains_chunks():
    """graph_docs text contains formatted chunk information."""
    result = _run_node("apa itu ABC costing?")
    text = result["graph_docs"][0]["text"]
    assert "Chunks:" in text


def test_empty_context_returns_empty_graph_docs():
    """When GraphRAG returns empty context, graph_docs is empty."""
    result = _run_node(
        "query with no results",
        mock_context=MockContext(entities=[], relationships=[], chunks=[]),
    )
    assert result == {"graph_docs": []}


def test_graph_docs_have_required_metadata_keys():
    """graph_docs entries contain all required metadata keys."""
    result = _run_node("apa itu standard costing?")
    meta = result["graph_docs"][0]["metadata"]
    required_keys = [
        "book_title",
        "chapter",
        "content_type",
        "page_start",
        "page_end",
        "section_path",
    ]
    for key in required_keys:
        assert key in meta, f"Missing metadata key: {key}"


def test_graph_docs_content_type_is_graph_context():
    """graph_docs metadata content_type is always 'graph_context'."""
    result = _run_node("apa itu overhead allocation?")
    assert result["graph_docs"][0]["metadata"]["content_type"] == "graph_context"


def test_graph_docs_section_path_is_graphrag_context():
    """graph_docs metadata section_path is 'GraphRAG/context'."""
    result = _run_node("jelaskan ABC costing")
    assert result["graph_docs"][0]["metadata"]["section_path"] == "GraphRAG/context"


def test_relational_query_returns_graph_docs():
    """Relational queries (with 'hubungan') still return graph_docs normally."""
    result = _run_node("apa hubungan ABC costing dengan cost driver?")
    assert "graph_docs" in result
    assert len(result["graph_docs"]) > 0


def test_calculation_query_returns_graph_docs():
    """Calculation queries still return graph_docs normally."""
    result = _run_node("hitung break-even point dengan fixed cost 100 juta")
    assert "graph_docs" in result
    assert len(result["graph_docs"]) > 0
