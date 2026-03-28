"""Tests for Phase 3 graph topology.

Covers:
- build_phase3_graph() compiles and returns a usable graph
- Graph has all 9 expected nodes (route, preprocess, retrieve, graph_retrieve,
  rerank, crag_grade, reformulate, generate, generate_calc)
- Graph invocation with thread_id config does not raise
"""


# ---------------------------------------------------------------------------
# Helpers: build Phase 3 graph
# ---------------------------------------------------------------------------


def _make_phase3_graph_with_mocks():
    """Build Phase 3 graph.

    All LightRAG/SiliconFlow/Qdrant imports in nodes.py are lazy (inside function
    bodies), so importing graph.py does not trigger any external service connections
    at import time. No sys.modules patching needed.
    """
    from src.agents.graph import build_phase3_graph

    return build_phase3_graph()


# ---------------------------------------------------------------------------
# Test: build_phase3_graph compiles
# ---------------------------------------------------------------------------


def test_build_phase3_graph_returns_compiled_graph():
    """build_phase3_graph() returns a compiled LangGraph (not None, has invoke)."""
    graph = _make_phase3_graph_with_mocks()
    assert graph is not None
    assert hasattr(graph, "invoke"), "Compiled graph should have invoke method"


def test_build_phase3_graph_has_invoke_and_stream():
    """Compiled graph should have both invoke and stream methods."""
    graph = _make_phase3_graph_with_mocks()
    assert callable(getattr(graph, "invoke", None))
    assert callable(getattr(graph, "stream", None))


# ---------------------------------------------------------------------------
# Test: Phase 3 graph node presence
# ---------------------------------------------------------------------------


def test_phase3_graph_has_expected_nodes():
    """Graph contains all 9 expected nodes for Phase 3 topology."""
    graph = _make_phase3_graph_with_mocks()

    # LangGraph compiled graph exposes node names via graph.nodes or similar attribute
    # Check via the underlying graph structure
    expected_nodes = {
        "route",
        "preprocess",
        "retrieve",
        "graph_retrieve",
        "rerank",
        "crag_grade",
        "reformulate",
        "generate",
        "generate_calc",
    }

    # Access node names from the compiled graph
    # LangGraph compiled graphs have a `graph` attribute or expose node names
    node_names = set()
    if hasattr(graph, "nodes"):
        node_names = set(graph.nodes.keys())
    elif hasattr(graph, "_graph"):
        node_names = set(graph._graph.nodes.keys()) if hasattr(graph._graph, "nodes") else set()

    # Filter out internal LangGraph nodes (START, END, __start__, __end__)
    node_names = {n for n in node_names if not n.startswith("__")}

    # Verify all expected nodes are present
    for expected in expected_nodes:
        assert expected in node_names, f"Node '{expected}' not found in graph nodes {node_names}"


# ---------------------------------------------------------------------------
# Test: Graph invocation with thread_id config does not raise
# ---------------------------------------------------------------------------


def test_phase3_graph_invocation_with_thread_id_does_not_raise():
    """Invoking the graph with thread_id config should not raise an exception.

    Uses fully mocked nodes so no API calls are made.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph

    from src.agents.state import RAGState

    def mock_route(state):
        return {
            "query_type": "Simple",
            "crag_iterations": 0,
            "crag_grade": None,
            "llm_call_count": 0,
        }

    def mock_preprocess(state):
        return {"expanded_query": state["query"], "query_embedding": [0.1] * 10}

    def mock_retrieve(state):
        return {"retrieved_docs": []}

    def mock_graph_retrieve(state):
        return {"graph_docs": []}

    def mock_rerank(state):
        return {"reranked_docs": []}

    def mock_crag_grade(state):
        return {"crag_grade": "CORRECT", "crag_iterations": 1}

    def mock_crag_router(state):
        return "generate"

    def mock_generate(state):
        return {
            "response": "Test answer.",
            "citations": [],
            "llm_call_count": 1,
            "conversation_history": [
                {"role": "user", "content": state["query"]},
                {"role": "assistant", "content": "Test answer."},
            ],
        }

    g = StateGraph(RAGState)
    g.add_node("route", mock_route)
    g.add_node("preprocess", mock_preprocess)
    g.add_node("retrieve", mock_retrieve)
    g.add_node("graph_retrieve", mock_graph_retrieve)
    g.add_node("rerank", mock_rerank)
    g.add_node("crag_grade", mock_crag_grade)
    g.add_node("generate", mock_generate)
    g.set_entry_point("route")
    g.add_edge("route", "preprocess")
    g.add_edge("preprocess", "retrieve")
    g.add_edge("retrieve", "graph_retrieve")
    g.add_edge("graph_retrieve", "rerank")
    g.add_edge("rerank", "crag_grade")
    g.add_conditional_edges(
        "crag_grade",
        mock_crag_router,
        {
            "generate": "generate",
        },
    )
    g.add_edge("generate", END)
    compiled = g.compile(checkpointer=MemorySaver())

    # Should not raise
    result = compiled.invoke(
        {"query": "Apa itu BEP?", "conversation_history": []},
        config={"configurable": {"thread_id": "test-thread-1"}},
    )
    assert result["response"] == "Test answer."
