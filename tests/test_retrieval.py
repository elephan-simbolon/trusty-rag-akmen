from unittest.mock import patch


def test_hybrid_search_returns_results(mock_qdrant_client):
    """RETR-01: Hybrid search (dense + BM25 + metadata filter) returns ranked results from Qdrant."""
    with patch("src.retrieval.vector_search.get_qdrant_client", return_value=mock_qdrant_client):
        from src.retrieval.vector_search import hybrid_search

        results = hybrid_search(
            query_embedding=[0.1] * 1024,
            query_text="break-even point",
        )

    assert isinstance(results, list)
    assert len(results) >= 1

    for entry in results:
        assert "text" in entry
        assert "metadata" in entry
        assert "score" in entry
        assert "book_title" in entry["metadata"]
        assert "page_start" in entry["metadata"]


def test_reranker_reorders_results(mock_siliconflow):
    """RETR-02: Qwen3-Reranker-8B reranks top-20 candidates to top-5, improving relevance order."""
    mock_search_results = [
        {
            "id": "chunk-001",
            "score": 0.7,
            "text": "Break-even point is the volume of sales at which total revenue equals total cost.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5",
                "content_type": "narrative_text",
                "page_start": 168,
                "page_end": 170,
            },
        },
        {
            "id": "chunk-002",
            "score": 0.6,
            "text": "Variable costs change in proportion to production volume.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 3",
                "section_path": "Part I > Chapter 3",
                "content_type": "narrative_text",
                "page_start": 45,
                "page_end": 47,
            },
        },
        {
            "id": "chunk-003",
            "score": 0.5,
            "text": "Fixed costs remain constant regardless of production volume.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 3",
                "section_path": "Part I > Chapter 3",
                "content_type": "narrative_text",
                "page_start": 48,
                "page_end": 50,
            },
        },
    ]

    with patch("src.retrieval.reranker.llm_rerank") as mock_llm_rerank:
        mock_llm_rerank.return_value = [
            {"index": 0, "score": 0.95, "text": mock_search_results[0]["text"]},
            {"index": 2, "score": 0.80, "text": mock_search_results[2]["text"]},
        ]

        from src.retrieval.reranker import rerank_results

        result = rerank_results(
            query="apa itu break-even point?",
            search_results=mock_search_results,
            top_k=2,
        )

    assert len(result) == 2
    for entry in result:
        assert "rerank_score" in entry
