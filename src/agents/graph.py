from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.nodes import (
    crag_grade_node,
    crag_router,
    generate_calc_node,
    generate_node,
    graph_retrieve_node,
    preprocess_node,
    reformulate_node,
    rerank_node,
    retrieve_node,
    route_node,
)
from src.agents.state import RAGState


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
    graph.add_conditional_edges(
        "crag_grade",
        crag_router,
        {
            "generate": "generate",
            "generate_calc": "generate_calc",
            "reformulate": "reformulate",
        },
    )
    graph.add_edge("reformulate", "retrieve")  # CRAG loop back
    graph.add_edge("generate", END)
    graph.add_edge("generate_calc", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
