"""Qdrant collection initialization and chunk upload for RAG indexing.

CRITICAL: Both dense and sparse vector configs MUST be set at collection creation time.
Adding sparse vectors later requires full collection recreation.
"""
import uuid
import logging
from collections import Counter

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    SparseVectorParams,
    SparseIndexParams,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    PointStruct,
    SparseVector,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)

from config.settings import settings

logger = logging.getLogger(__name__)


def create_collection(client: QdrantClient, collection_name: str | None = None):
    """
    Create Qdrant collection with dense + sparse vectors and scalar quantization.

    CRITICAL: Both vector types MUST be configured at creation time.
    Adding sparse vectors later requires collection recreation (Pitfall from RESEARCH.md).

    Dense: 1024 dimensions, cosine distance, INT8 scalar quantization in RAM.
    Sparse: IDF-weighted BM25-style for exact English terminology matching.
    """
    name = collection_name or settings.qdrant_collection_name

    if client.collection_exists(name):
        logger.info(f"Collection '{name}' already exists, skipping creation")
        return

    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": VectorParams(
                size=settings.embedding_dimensions,  # 1024
                distance=Distance.COSINE,
                quantization_config=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        always_ram=True,
                    )
                ),
            )
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False),
                modifier="idf",  # IDF weighting for BM25-style sparse search
            )
        },
    )

    # Create payload indices for filtering (required by Qdrant Cloud)
    from qdrant_client.models import PayloadSchemaType
    for field in ["book_title", "chapter", "content_type"]:
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD,
        )

    logger.info(f"Created collection '{name}' with dense(1024,cosine,INT8) + sparse(BM25,IDF)")


def compute_sparse_vector(text: str) -> SparseVector:
    """
    Compute a term-frequency sparse vector for BM25-style search.

    Uses word-level tokenization. Indices are hash-based for consistency.
    Captures exact English accounting terminology from Indonesian queries
    (cross-lingual exact match for terms like 'break-even', 'variable cost').
    """
    words = text.lower().split()
    word_counts = Counter(words)
    indices = []
    values = []
    for word, count in word_counts.items():
        # Use hash to get stable integer index for each word
        idx = abs(hash(word)) % (2**31)
        indices.append(idx)
        values.append(float(count))
    return SparseVector(indices=indices, values=values)


def upload_batch(client: QdrantClient, chunks: list[dict], collection_name: str | None = None):
    """Upload one batch of embedded chunks to Qdrant (dense + sparse vectors)."""
    name = collection_name or settings.qdrant_collection_name
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": chunk["embedding"],
                "sparse": compute_sparse_vector(chunk["text"]),
            },
            payload={"text": chunk["text"], **chunk.get("metadata", {})},
        )
        for chunk in chunks
    ]
    client.upsert(collection_name=name, points=points)


def health_check(client: QdrantClient) -> bool:
    """Ping Qdrant to verify connectivity. Returns True if healthy."""
    try:
        client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return False


def check_book_exists(
    client: QdrantClient,
    book_title: str,
    collection_name: str | None = None,
) -> bool:
    """Return True if any chunks for this book_title exist in Qdrant.

    Uses scroll with a filter on the book_title payload field.
    Limit=1 keeps the call fast — we only need to know existence, not count.
    """
    name = collection_name or settings.qdrant_collection_name
    results, _ = client.scroll(
        collection_name=name,
        scroll_filter=Filter(
            must=[FieldCondition(key="book_title", match=MatchValue(value=book_title))]
        ),
        limit=1,
        with_payload=False,
        with_vectors=False,
    )
    return len(results) > 0


def delete_book(
    client: QdrantClient,
    book_title: str,
    collection_name: str | None = None,
) -> None:
    """Delete all Qdrant points for a given book_title (for re-ingestion).

    Uses FilterSelector delete — targeted per-book deletion without
    affecting any other books in the collection (Anti-pattern: never use
    client.delete_collection() for incremental removes).
    """
    name = collection_name or settings.qdrant_collection_name
    client.delete(
        collection_name=name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="book_title", match=MatchValue(value=book_title))]
            )
        ),
    )
    logger.info(f"Deleted all chunks for book '{book_title}' from collection '{name}'")
