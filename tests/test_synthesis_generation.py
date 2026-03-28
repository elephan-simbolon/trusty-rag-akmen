from unittest.mock import patch

from src.generation.generator import generate_response

MOCK_VECTOR_DOCS = [
    {
        "text": "Overhead allocation uses cost drivers to assign indirect costs.",
        "metadata": {
            "book_title": "Horngren, Cost Accounting",
            "chapter": "Chapter 5",
            "page_start": 168,
            "page_end": 172,
            "section_path": "Part II > Chapter 5",
            "content_type": "narrative_text",
        },
        "score": 0.92,
    },
    {
        "text": "Departmental overhead rates provide more accuracy than plant-wide rates.",
        "metadata": {
            "book_title": "Garrison, Managerial Accounting",
            "chapter": "Chapter 3",
            "page_start": 95,
            "page_end": 97,
            "section_path": "Part I > Chapter 3",
            "content_type": "narrative_text",
        },
        "score": 0.88,
    },
]

MOCK_GRAPH_CONTEXT = (
    "[Source: Horngren, Cost Accounting, Chapter 5, page 168] "
    "Activity-Based Costing uses multiple cost drivers. "
    "[Source: Garrison, Managerial Accounting, Chapter 3, page 95] "
    "Traditional overhead allocation uses a single plant-wide rate."
)


@patch("src.generation.generator.generate")
def test_synthesis_uses_synthesis_prompt_when_graph_context_present(mock_generate):
    """When graph_context is non-empty, SYSTEM_PROMPT_SYNTHESIS is used."""
    mock_generate.return_value = "Menurut Horngren, ABC costing menggunakan cost drivers."
    generate_response(
        query="bandingkan overhead allocation",
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=MOCK_GRAPH_CONTEXT,
    )
    # Verify the system prompt used is the synthesis one (contains "textbook dan knowledge graph")
    call_args = mock_generate.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]
    assert "textbook dan knowledge graph" in system_msg


@patch("src.generation.generator.generate")
def test_synthesis_includes_graph_context_in_user_message(mock_generate):
    """User message includes knowledge graph context block."""
    mock_generate.return_value = "Response text."
    generate_response(
        query="test query",
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=MOCK_GRAPH_CONTEXT,
    )
    call_args = mock_generate.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    user_msg = messages[1]["content"]
    assert "Konteks dari knowledge graph:" in user_msg
    assert "Konteks dari textbook passages:" in user_msg
    assert "Instruksi: Sebutkan secara eksplisit sumber textbook" in user_msg


@patch("src.generation.generator.generate")
def test_fallback_to_phase1_prompt_without_graph_context(mock_generate):
    """When graph_context is empty, falls back to Phase 1 SYSTEM_PROMPT_GENERATOR."""
    mock_generate.return_value = "Standard response."
    generate_response(
        query="apa itu overhead?",
        context_docs=MOCK_VECTOR_DOCS,
        graph_context="",
    )
    call_args = mock_generate.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]
    # Phase 1 prompt does NOT contain "textbook dan knowledge graph" (synthesis marker)
    assert "textbook dan knowledge graph" not in system_msg
    # Phase 1 prompt contains the standard generator instruction
    assert "berdasarkan textbook" in system_msg


@patch("src.generation.generator.generate")
def test_default_graph_context_is_empty_string(mock_generate):
    """generate_response works with only two args (backward compatible)."""
    mock_generate.return_value = "Backward compatible response."
    result = generate_response(
        query="test",
        context_docs=MOCK_VECTOR_DOCS,
    )
    assert "response" in result
    assert "citations" in result


@patch("src.generation.generator.generate")
def test_citations_built_from_context_docs_not_graph(mock_generate):
    """Citations are built from context_docs metadata, not graph_docs."""
    mock_generate.return_value = "Response."
    result = generate_response(
        query="test",
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=MOCK_GRAPH_CONTEXT,
    )
    # Citations should reference Horngren and Garrison from vector docs
    formatted_citations = [c["formatted"] for c in result["citations"]]
    assert any("Horngren" in c for c in formatted_citations)
    assert any("Garrison" in c for c in formatted_citations)


def test_system_prompt_synthesis_exists():
    """SYSTEM_PROMPT_SYNTHESIS is importable from config.prompts."""
    from config.prompts import SYSTEM_PROMPT_SYNTHESIS

    assert "textbook dan knowledge graph" in SYSTEM_PROMPT_SYNTHESIS
    assert "{glossary_snippet}" in SYSTEM_PROMPT_SYNTHESIS
    assert "knowledge graph" in SYSTEM_PROMPT_SYNTHESIS


def test_system_prompt_synthesis_has_relational_instruction():
    """Synthesis prompt contains instruction for relational query handling."""
    from config.prompts import SYSTEM_PROMPT_SYNTHESIS

    assert "relasional" in SYSTEM_PROMPT_SYNTHESIS
    assert "hubungan konseptual" in SYSTEM_PROMPT_SYNTHESIS


def test_system_prompt_synthesis_has_comparison_instruction():
    """Synthesis prompt contains instruction for comparison query handling."""
    from config.prompts import SYSTEM_PROMPT_SYNTHESIS

    assert "perbandingan" in SYSTEM_PROMPT_SYNTHESIS
    assert "perspektif setiap sumber" in SYSTEM_PROMPT_SYNTHESIS


# --- generate_node integration tests ---

from src.agents.nodes import generate_node  # noqa: E402


@patch("src.agents.nodes.generate_response")
def test_generate_node_passes_graph_context(mock_gen_resp):
    """generate_node extracts graph_docs text and passes as graph_context."""
    mock_gen_resp.return_value = {"response": "Synthesis answer", "citations": []}
    state = {
        "query": "bandingkan overhead allocation",
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": [{"text": "Graph context about overhead.", "metadata": {}, "score": 1.0}],
        "error": None,
    }
    generate_node(state)
    mock_gen_resp.assert_called_once()
    call_kwargs = mock_gen_resp.call_args
    # Check graph_context was passed
    if call_kwargs[1]:
        assert call_kwargs[1].get("graph_context") == "Graph context about overhead."
    else:
        assert call_kwargs[0][2] == "Graph context about overhead."


@patch("src.agents.nodes.generate_response")
def test_generate_node_empty_graph_docs_passes_empty_string(mock_gen_resp):
    """When graph_docs is empty, graph_context is empty string."""
    mock_gen_resp.return_value = {"response": "Response", "citations": []}
    state = {
        "query": "test",
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": [],
        "error": None,
    }
    generate_node(state)
    call_kwargs = mock_gen_resp.call_args
    if call_kwargs[1]:
        assert call_kwargs[1].get("graph_context", "") == ""
    else:
        assert len(call_kwargs[0]) < 3 or call_kwargs[0][2] == ""


@patch("src.agents.nodes.generate_response")
def test_generate_node_no_graph_docs_key_backward_compat(mock_gen_resp):
    """When graph_docs key is missing from state (Phase 1), still works."""
    mock_gen_resp.return_value = {"response": "Phase 1 response", "citations": []}
    state = {
        "query": "test",
        "reranked_docs": MOCK_VECTOR_DOCS,
        "error": None,
    }
    result = generate_node(state)
    assert result["response"] == "Phase 1 response"
