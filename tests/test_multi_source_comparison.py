"""Integration tests for multi-source comparison query flow — GEN-06.

Verifies that when graph_docs contains multi-source context:
1. generate_node merges multiple graph_docs entries into a single graph_context string
2. generate_response is called with non-empty graph_context (triggers synthesis path)
3. SYSTEM_PROMPT_SYNTHESIS (not SYSTEM_PROMPT_GENERATOR) is selected
4. User message contains both graph context and textbook passages blocks
5. Response includes attribution structure (comparison instruction visible in prompt)
6. Multiple graph_docs texts are joined correctly into one context block

No live API calls — all LightRAG and SiliconFlow interactions are mocked.
"""

from unittest.mock import patch

from src.agents.nodes import generate_node
from src.generation.generator import generate_response

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MULTI_SOURCE_GRAPH_DOCS = [
    {
        "text": (
            "[Source: Horngren, Cost Accounting, Chapter 5, page 168] "
            "Activity-Based Costing uses multiple activity cost pools and separate cost drivers."
        ),
        "metadata": {
            "book_title": "Knowledge Graph",
            "chapter": "Multi-source synthesis",
            "content_type": "graph_context",
            "page_start": 0,
            "page_end": 0,
            "section_path": "LightRAG/hybrid mode",
        },
        "score": 1.0,
    },
    {
        "text": (
            "[Source: Garrison, Managerial Accounting, Chapter 3, page 95] "
            "Traditional costing uses a single plant-wide overhead rate for all products."
        ),
        "metadata": {
            "book_title": "Knowledge Graph",
            "chapter": "Multi-source synthesis",
            "content_type": "graph_context",
            "page_start": 0,
            "page_end": 0,
            "section_path": "LightRAG/hybrid mode",
        },
        "score": 1.0,
    },
]

MOCK_VECTOR_DOCS = [
    {
        "text": "ABC Costing assigns overhead based on activities that consume resources.",
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
        "text": "Traditional overhead allocation uses a single plant-wide rate.",
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

COMPARISON_QUERY = "bandingkan pendekatan ABC costing dari Horngren versus Garrison"


# ---------------------------------------------------------------------------
# Test: generate_node merges multiple graph_docs into single graph_context
# ---------------------------------------------------------------------------


def test_generate_node_merges_multiple_graph_docs_into_graph_context():
    """generate_node joins text from multiple graph_docs entries with double newline."""
    captured_kwargs = {}

    def capture_generate_response(query, context_docs, graph_context="", **kwargs):
        captured_kwargs["graph_context"] = graph_context
        return {"response": "Comparison answer.", "citations": []}

    state = {
        "query": COMPARISON_QUERY,
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": MULTI_SOURCE_GRAPH_DOCS,
        "error": None,
    }

    with patch("src.agents.nodes.generate_response", side_effect=capture_generate_response):
        generate_node(state)

    graph_context = captured_kwargs["graph_context"]
    # Both graph_docs texts should appear in the merged context
    assert MULTI_SOURCE_GRAPH_DOCS[0]["text"] in graph_context
    assert MULTI_SOURCE_GRAPH_DOCS[1]["text"] in graph_context


def test_generate_node_graph_context_non_empty_for_multi_source_docs():
    """generate_node passes non-empty graph_context when graph_docs is non-empty."""
    captured_kwargs = {}

    def capture_generate_response(query, context_docs, graph_context="", **kwargs):
        captured_kwargs["graph_context"] = graph_context
        return {"response": "Response.", "citations": []}

    state = {
        "query": COMPARISON_QUERY,
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": MULTI_SOURCE_GRAPH_DOCS,
        "error": None,
    }

    with patch("src.agents.nodes.generate_response", side_effect=capture_generate_response):
        generate_node(state)

    assert captured_kwargs.get("graph_context", "") != ""


def test_generate_node_multi_source_graph_context_joined_with_double_newline():
    """Multiple graph_docs texts are separated by double newline in graph_context."""
    captured_kwargs = {}

    def capture_generate_response(query, context_docs, graph_context="", **kwargs):
        captured_kwargs["graph_context"] = graph_context
        return {"response": "Response.", "citations": []}

    state = {
        "query": COMPARISON_QUERY,
        "reranked_docs": MOCK_VECTOR_DOCS,
        "graph_docs": MULTI_SOURCE_GRAPH_DOCS,
        "error": None,
    }

    with patch("src.agents.nodes.generate_response", side_effect=capture_generate_response):
        generate_node(state)

    graph_context = captured_kwargs["graph_context"]
    # Double newline separator between the two docs
    assert "\n\n" in graph_context


# ---------------------------------------------------------------------------
# Test: generate_response uses SYSTEM_PROMPT_SYNTHESIS with multi-source context
# ---------------------------------------------------------------------------


@patch("src.generation.generator.generate")
def test_synthesis_prompt_selected_for_multi_source_comparison(mock_llm):
    """generate_response uses SYSTEM_PROMPT_SYNTHESIS when graph_context is non-empty."""
    mock_llm.return_value = "Menurut Horngren, ABC costing menggunakan activity cost pools."

    graph_context = "\n\n".join(d["text"] for d in MULTI_SOURCE_GRAPH_DOCS)
    generate_response(
        query=COMPARISON_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context,
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]

    # SYSTEM_PROMPT_SYNTHESIS contains synthesis marker (not in SYSTEM_PROMPT_GENERATOR)
    assert "textbook dan knowledge graph" in system_msg


@patch("src.generation.generator.generate")
def test_comparison_instruction_present_in_synthesis_prompt_for_multi_source(mock_llm):
    """Synthesis prompt contains the comparison instruction when multi-source context used."""
    mock_llm.return_value = "Comparison answer."

    graph_context = "\n\n".join(d["text"] for d in MULTI_SOURCE_GRAPH_DOCS)
    generate_response(
        query=COMPARISON_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context,
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]

    # Comparison instruction: present each source separately, then synthesize
    assert "perbandingan" in system_msg
    assert "perspektif setiap sumber" in system_msg


@patch("src.generation.generator.generate")
def test_user_message_contains_both_graph_and_textbook_context_blocks(mock_llm):
    """User message contains both 'Konteks dari knowledge graph' and 'Konteks dari textbook passages'."""
    mock_llm.return_value = "Response."

    graph_context = "\n\n".join(d["text"] for d in MULTI_SOURCE_GRAPH_DOCS)
    generate_response(
        query=COMPARISON_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context,
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    user_msg = messages[1]["content"]

    assert "Konteks dari knowledge graph:" in user_msg
    assert "Konteks dari textbook passages:" in user_msg


@patch("src.generation.generator.generate")
def test_multi_source_graph_context_appears_in_user_message(mock_llm):
    """Both source texts from graph_docs appear in the user message sent to LLM."""
    mock_llm.return_value = "Response."

    graph_context = "\n\n".join(d["text"] for d in MULTI_SOURCE_GRAPH_DOCS)
    generate_response(
        query=COMPARISON_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context,
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    user_msg = messages[1]["content"]

    assert "Horngren" in user_msg
    assert "Garrison" in user_msg


@patch("src.generation.generator.generate")
def test_phase1_prompt_not_used_for_multi_source_comparison(mock_llm):
    """SYSTEM_PROMPT_GENERATOR (Phase 1) is NOT used when multi-source graph context present."""
    mock_llm.return_value = "Response."

    graph_context = "\n\n".join(d["text"] for d in MULTI_SOURCE_GRAPH_DOCS)
    generate_response(
        query=COMPARISON_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context,
    )

    call_args = mock_llm.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
    system_msg = messages[0]["content"]

    # Phase 1 prompt does NOT contain the per-source attribution rule
    # (SYSTEM_PROMPT_GENERATOR has rules 1-5 only; rule 6 is only in SYSTEM_PROMPT_SYNTHESIS)
    from config.glossary import GLOSSARY
    from config.prompts import SYSTEM_PROMPT_GENERATOR

    terms = list(GLOSSARY.items())[:50]
    glossary_snippet = "\n".join(f"- {en} = {id_}" for en, id_ in terms)
    phase1_prompt = SYSTEM_PROMPT_GENERATOR.format(glossary_snippet=glossary_snippet)
    # The system_msg should NOT be the Phase 1 prompt
    assert system_msg != phase1_prompt


# ---------------------------------------------------------------------------
# Test: citations are still built from vector docs, not from graph_docs
# ---------------------------------------------------------------------------


@patch("src.generation.generator.generate")
def test_citations_from_vector_docs_not_graph_for_comparison_query(mock_llm):
    """Citations reference Horngren and Garrison from vector docs, not graph metadata."""
    mock_llm.return_value = "Comparison response."

    graph_context = "\n\n".join(d["text"] for d in MULTI_SOURCE_GRAPH_DOCS)
    result = generate_response(
        query=COMPARISON_QUERY,
        context_docs=MOCK_VECTOR_DOCS,
        graph_context=graph_context,
    )

    formatted = [c["formatted"] for c in result["citations"]]
    assert any("Horngren" in c for c in formatted)
    assert any("Garrison" in c for c in formatted)
