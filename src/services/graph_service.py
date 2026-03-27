"""Singleton access to the compiled LangGraph RAG pipeline."""

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        from src.agents.graph import build_phase3_graph
        _graph = build_phase3_graph()
    return _graph
