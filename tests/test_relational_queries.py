"""Integration tests for relational query end-to-end flow — GEN-05.

Verifies that a relational query flows through the full pipeline:
1. graph_retrieve_node returns non-empty graph_docs in state
2. generate_node receives non-empty graph_context extracted from graph_docs
3. generate_response is called with non-empty graph_context
4. The synthesis prompt (SYSTEM_PROMPT_SYNTHESIS) is used, not SYSTEM_PROMPT_GENERATOR

No live API calls — all GraphRAG, SiliconFlow interactions are mocked.
"""

from unittest.mock import MagicMock, patch

from src.agents.nodes import generate_node, graph_retrieve_node

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

RELATIONAL_QUERY = "apa hubungan antara activity-based costing dan cost driver?"

MOCK_VECTOR_DOCS = [
    {
        "text": "Activity-Based Costing (ABC) assigns overhead using cost drivers.",
        "metadata": {
            "book_title": "Horngren, Cost Accounting",
            "chapter": "Chapter 5",
            "page_start": 168,
            "page_end": 172,
            "section_path": "Part II > Chapter 5",
            "content_type": "narrative_text",
        },
        "score": 0.90,
    },
]

class MockContext:
    """Mimics TContext dataclass with entities, relationships, chunks as List[Tuple[item, score]]."""
    def __init__(self, entities=None, relationships=None, chunks=None):
        self.entities = entities or []
        self.relationships = relationships or []
        self.chunks = chunks or []


MOCK_GRAPH_CONTEXT = MockContext(
    entities=[("ABC Costing", 0.9), ("Cost Driver", 0.8)],
    relationships=[("ABC Costing -> REQUIRES -> Cost Driver", 0.85)],
    chunks=[(
        "ABC Costing -> REQUIRES -> Cost Driver. "
        "Cost Driver is a prerequisite concept for Activity-Based Costing implementation.",
        0.7,
    )],
)


class MockAnswer:
    def __init__(self, context):
        self.context = context
        self.response = ""


# ---------------------------------------------------------------------------
# Stage 1: graph_retrieve_node returns non-empty graph_docs
# ---------------------------------------------------------------------------


def test_relational_query_graph_retrieve_returns_non_empty_graph_docs():
    """graph_retrieve_node returns non-empty graph_docs for relational query."""
    mock_grag = MagicMock()
    mock_grag.query = MagicMock(return_value=MockAnswer(context=MOCK_GRAPH_CONTEXT))

    with patch("src.agents.nodes.get_graphrag", return_value=mock_grag):
        state = {"query": RELATIONAL_QUERY, "error": None}
        result = graph_retrieve_node(state)

    assert "graph_docs" in result
    graph_docs = result["graph_docs"]
    assert len(graph_docs) >= 1
    assert "Cost Driver" in graph_docs[0]["text"]


def test_relational_query_graph_docs_contain_graph_result_text():
    """graph_docs[0]['text'] contains entity and relation info from graph context."""
    mock_grag = MagicMock()
    mock_grag.query = MagicMock(return_value=MockAnswer(context=MOCK_GRAPH_CONTEXT))

    with patch("src.agents.nodes.get_graphrag", return_value=mock_grag):
        state = {"query": RELATIONAL_QUERY, "error": None}
        result = graph_retrieve_node(state)

    assert "Cost Driver" in result["graph_docs"][0]["text"]


# ---------------------------------------------------------------------------
# Stage 2: generate_node receives non-empty graph_context from graph_docs
# ---------------------------------------------------------------------------


def test_generate_node_receives_non_empty_graph_context_for_relational_query():
    """generate_node passes non-empty graph_context to generate_response for relational query."""
    captured_kwargs = {}

    def capture_generate_response(query, context_docs, graph_context="", **kwargs):
        captured_kwargs["graph_context"] = graph_context
        return {"response": "Synthesis response.", "citations": []}

    state = {
        "query": RELATIONAL_QUERY,
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": [
            {
                "text": "Entities: ABC Costing; Cost Driver\n\nRelations: ABC Costing -> REQUIRES -> Cost Driver",
                "metadata": {
                    "book_title": "Knowledge Graph",
                    "chapter": "Multi-source synthesis",
                    "content_type": "graph_context",
                    "page_start": 0,
                    "page_end": 0,
                    "section_path": "GraphRAG/context",
                },
                "score": 1.0,
            }
        ],
        "error": None,
    }

    with patch("src.agents.nodes.generate_response", side_effect=capture_generate_response):
        generate_node(state)

    assert "graph_context" in captured_kwargs
    assert captured_kwargs["graph_context"] != ""
    assert len(captured_kwargs["graph_context"]) > 0


def test_generate_node_graph_context_contains_graph_docs_text():
    """The graph_context passed to generate_response contains the graph_docs text."""
    captured_kwargs = {}

    def capture_generate_response(query, context_docs, graph_context="", **kwargs):
        captured_kwargs["graph_context"] = graph_context
        return {"response": "Response.", "citations": []}

    graph_text = "Entities: ABC Costing; Cost Driver"
    state = {
        "query": RELATIONAL_QUERY,
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": [
            {
                "text": graph_text,
                "metadata": {"content_type": "graph_context"},
                "score": 1.0,
            }
        ],
        "error": None,
    }

    with patch("src.agents.nodes.generate_response", side_effect=capture_generate_response):
        generate_node(state)

    assert graph_text in captured_kwargs["graph_context"]


# ---------------------------------------------------------------------------
# Stage 3: generate_response uses synthesis prompt for relational query context
# ---------------------------------------------------------------------------


@patch("src.generation.generator.generate")
def test_synthesis_prompt_used_when_graph_context_non_empty_for_relational_query(mock_llm):
    """generate_response uses SYSTEM_PROMPT_SYNTHESIS (not SYSTEM_PROMPT_GENERATOR)
    when called with non-empty graph_context from a relational query."""
    mock_llm.return_value = "Hubungan ABC costing dengan cost driver adalah..."

    from src.generation.generator import generate_response

    generate_response(
        query=RELATIONAL_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context="Entities: ABC Costing; Cost Driver\n\nRelations: ABC Costing -> REQUIRES -> Cost Driver",
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]

    assert "textbook dan knowledge graph" in system_msg
    assert "relasional" in system_msg
    assert "hubungan konseptual" in system_msg


@patch("src.generation.generator.generate")
def test_user_message_contains_graph_context_for_relational_query(mock_llm):
    """User message to LLM contains the knowledge graph context for relational queries."""
    mock_llm.return_value = "Answer."

    from src.generation.generator import generate_response

    graph_context_text = "Entities: ABC Costing; Cost Driver"
    generate_response(
        query=RELATIONAL_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context_text,
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    user_msg = messages[1]["content"]

    assert "Konteks dari knowledge graph:" in user_msg
    assert graph_context_text in user_msg


# ---------------------------------------------------------------------------
# Full pipeline integration: graph_retrieve -> generate (chained state)
# ---------------------------------------------------------------------------


def test_full_relational_pipeline_graph_context_reaches_generate_response():
    """Full pipeline: relational query state flows from graph_retrieve_node output
    into generate_node, which passes non-empty graph_context to generate_response."""
    captured_kwargs = {}

    def capture_generate_response(query, context_docs, graph_context="", **kwargs):
        captured_kwargs["graph_context"] = graph_context
        return {"response": "Final synthesis.", "citations": []}

    # Step 1: simulate graph_retrieve_node output
    mock_grag = MagicMock()
    mock_grag.query = MagicMock(return_value=MockAnswer(context=MOCK_GRAPH_CONTEXT))

    with patch("src.agents.nodes.get_graphrag", return_value=mock_grag):
        graph_result = graph_retrieve_node({"query": RELATIONAL_QUERY, "error": None})

    # Step 2: merge graph_retrieve output into state for generate_node
    full_state = {
        "query": RELATIONAL_QUERY,
        "reranked_docs": MOCK_VECTOR_DOCS,
        "error": None,
        **graph_result,
    }

    # Step 3: run generate_node with merged state
    with patch("src.agents.nodes.generate_response", side_effect=capture_generate_response):
        final_result = generate_node(full_state)

    # Verify graph_context was non-empty
    assert captured_kwargs.get("graph_context") != ""
    assert "Cost Driver" in captured_kwargs["graph_context"]
    # Verify final result is present
    assert final_result["response"] == "Final synthesis."
