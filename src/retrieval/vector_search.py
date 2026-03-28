import logging

from qdrant_client.models import (
    Fusion,
    FusionQuery,
    NearestQuery,
    Prefetch,
    SparseVector,
)

from config.settings import settings
from src.ingestion.indexing.qdrant_uploader import compute_sparse_vector
from src.services.qdrant_service import get_qdrant_client

logger = logging.getLogger(__name__)


def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    top_k: int = 20,
    collection_name: str | None = None,
    book_filter: str | None = None,
) -> list[dict]:
    """
    Hybrid search combining dense vector similarity and sparse BM25 on Qdrant.
    Uses Reciprocal Rank Fusion (RRF) to merge dense and sparse results.

    Args:
        query_embedding: Dense vector from embed_query (with instruction prefix)
        query_text: Expanded query text for BM25 sparse matching
        top_k: Number of results to return (default 20 for reranker input)
        collection_name: Optional override for collection name
        book_filter: Optional book_title filter
    Returns: list of dicts with 'text', 'metadata', 'score'
    """
    client = get_qdrant_client()
    name = collection_name or settings.qdrant_collection_name

    sparse_vec = compute_sparse_vector(query_text)

    # Build prefetch for dense and sparse, then fuse with RRF
    results = client.query_points(
        collection_name=name,
        prefetch=[
            Prefetch(
                query=NearestQuery(nearest=query_embedding),
                using="dense",
                limit=top_k,
            ),
            Prefetch(
                query=NearestQuery(
                    nearest=SparseVector(
                        indices=sparse_vec.indices,
                        values=sparse_vec.values,
                    )
                ),
                using="sparse",
                limit=top_k,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
    )

    search_results = []
    for point in results.points:
        payload = point.payload or {}
        search_results.append(
            {
                "id": point.id,
                "score": point.score if hasattr(point, "score") else 0.0,
                "text": payload.get("text", ""),
                "metadata": {
                    "book_title": payload.get("book_title", ""),
                    "chapter": payload.get("chapter", ""),
                    "section_path": payload.get("section_path", ""),
                    "content_type": payload.get("content_type", ""),
                    "page_start": payload.get("page_start", 0),
                    "page_end": payload.get("page_end", 0),
                },
            }
        )

    logger.info(f"Hybrid search returned {len(search_results)} results for: {query_text[:80]}")
    return search_results
