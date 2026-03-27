from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agents.state import RAGState
from src.agents.nodes import (
    preprocess_node,
    retrieve_node,
    rerank_node,
    generate_node,
    graph_retrieve_node,
    route_node,
    crag_grade_node,
    crag_router,
    reformulate_node,
    generate_calc_node,
)


def build_phase1_graph():
    """
    Phase 1: Simple linear RAG graph.
    preprocess -> retrieve -> rerank -> generate -> END

    Intentionally simple. Designed to accept CRAG node between rerank and
    generate in Phase 3, and routing node after preprocess.
    """
    graph = StateGraph(RAGState)

    graph.add_node("preprocess", preprocess_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def build_phase2_graph():
    """
    Phase 2: RAG graph with knowledge graph retrieval.
    preprocess -> [retrieve, graph_retrieve] -> rerank -> generate -> END

    After preprocess, both vector retrieve and graph retrieve run.
    The graph is linear through: preprocess -> retrieve -> graph_retrieve -> rerank -> generate.
    LangGraph does not support true parallel execution in StateGraph without
    branching/joining complexity. Sequential is simpler and correct for Phase 2.
    Graph retrieve adds context but does not modify vector results.
    """
    graph = StateGraph(RAGState)

    graph.add_node("preprocess", preprocess_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("graph_retrieve", graph_retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "retrieve")
    graph.add_edge("retrieve", "graph_retrieve")
    graph.add_edge("graph_retrieve", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def build_phase3_graph():
    """
    Phase 3: Agentic RAG with CRAG quality gate and adaptive routing.
    route -> preprocess -> retrieve -> graph_retrieve -> rerank -> crag_grade ->
        [generate | generate_calc | reformulate]
    Reformulate loops back to retrieve (max 2 iterations).
    Compiled with MemorySaver for conversation memory (UI-02).

    NOTE: preprocess_node is wired between route and retrieve. The RESEARCH.md
    graph skeleton omits preprocess, but this is intentional — preprocess handles
    glossary expansion and query embedding required before retrieval.

    Preserves build_phase1_graph() and build_phase2_graph() for backward compatibility.
    """
    graph = StateGraph(RAGState)

    graph.add_node("route", route_node)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("graph_retrieve", graph_retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("crag_grade", crag_grade_node)
    graph.add_node("reformulate", reformulate_node)
    graph.add_node("generate", generate_node)
    graph.add_node("generate_calc", generate_calc_node)

    graph.set_entry_point("route")
    graph.add_edge("route", "preprocess")
    graph.add_edge("preprocess", "retrieve")
    graph.add_edge("retrieve", "graph_retrieve")
    graph.add_edge("graph_retrieve", "rerank")
    graph.add_edge("rerank", "crag_grade")
    graph.add_conditional_edges("crag_grade", crag_router, {
        "generate": "generate",
        "generate_calc": "generate_calc",
        "reformulate": "reformulate",
    })
    graph.add_edge("reformulate", "retrieve")  # CRAG loop back
    graph.add_edge("generate", END)
    graph.add_edge("generate_calc", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
