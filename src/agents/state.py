import operator
from typing import Annotated, Optional, TypedDict


class RAGState(TypedDict):
    """Phase 3 LangGraph state schema.
    Backward-compatible: all Phase 1 + 2 fields preserved.
    New in Phase 3: query_type, crag_grade, crag_iterations, llm_call_count,
    conversation_history.
    """

    # Phase 1 fields (unchanged)
    query: str
    expanded_query: Optional[str]
    query_embedding: Optional[list[float]]
    retrieved_docs: Optional[list[dict]]  # Qdrant hybrid search results
    reranked_docs: Optional[list[dict]]
    response: Optional[str]
    citations: Optional[list[dict]]
    error: Optional[str]
    # Phase 2 fields (unchanged)
    graph_docs: Optional[list[dict]]  # LightRAG graph results
    query_mode: Optional[str]  # "local" or "hybrid" (default: "hybrid")
    # Phase 3 additions
    query_type: Optional[str]  # "Simple"|"Medium"|"Complex"|"Calculation"
    crag_grade: Optional[str]  # "CORRECT"|"AMBIGUOUS"|"INCORRECT"
    crag_iterations: Optional[int]  # initialized to 0 in route_node, caps at 2
    llm_call_count: Optional[int]  # logged per query for budget verification
    conversation_history: Annotated[list, operator.add]  # accumulates across turns
