from qdrant_client.models import ScalarQuantization, ScalarType

from src.ingestion.indexing.qdrant_uploader import create_collection, upload_batch


def test_collection_has_dense_and_sparse(mock_qdrant_client):
    """INDEX-01, INDEX-02: Qdrant collection is created with both dense (1024-dim) and sparse (BM25) vector configs."""
    mock_qdrant_client.collection_exists.return_value = False
    create_collection(mock_qdrant_client)

    assert mock_qdrant_client.create_collection.called

    call_kwargs = mock_qdrant_client.create_collection.call_args.kwargs

    # Dense vector config must be present
    vectors_config = call_kwargs["vectors_config"]
    assert "dense" in vectors_config
    assert vectors_config["dense"].size == 1024

    # Sparse vector config must be present with IDF modifier
    sparse_config = call_kwargs["sparse_vectors_config"]
    assert "sparse" in sparse_config
    assert sparse_config["sparse"].modifier == "idf"


def test_payload_contains_metadata(mock_qdrant_client):
    """INDEX-03: Each Qdrant point payload contains book_title, chapter, section_path, content_type, page_start, page_end."""
    chunks = [
        {
            "text": "Break-even point is the volume of sales where total revenue equals total cost.",
            "embedding": [0.1] * 1024,
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5 > Break-Even Analysis",
                "content_type": "narrative_text",
                "page_start": 168,
                "page_end": 170,
            },
        },
        {
            "text": "Variable cost per unit is the cost that changes with production volume.",
            "embedding": [0.2] * 1024,
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5 > Variable Costs",
                "content_type": "narrative_text",
                "page_start": 171,
                "page_end": 172,
            },
        },
    ]

    upload_batch(mock_qdrant_client, chunks)

    assert mock_qdrant_client.upsert.called

    call_kwargs = mock_qdrant_client.upsert.call_args.kwargs
    points = call_kwargs["points"]
    assert len(points) == 2

    required_fields = {
        "book_title",
        "chapter",
        "section_path",
        "content_type",
        "page_start",
        "page_end",
        "text",
    }
    for point in points:
        for field in required_fields:
            assert field in point.payload, f"Missing field '{field}' in payload"


def test_scalar_quantization_config(mock_qdrant_client):
    """INDEX-01: Qdrant collection uses scalar quantization to reduce memory usage on free tier."""
    mock_qdrant_client.collection_exists.return_value = False
    create_collection(mock_qdrant_client)

    call_kwargs = mock_qdrant_client.create_collection.call_args.kwargs
    vectors_config = call_kwargs["vectors_config"]
    dense_config = vectors_config["dense"]

    # Scalar quantization must be ScalarQuantization with INT8 type
    quant = dense_config.quantization_config
    assert quant is not None
    assert isinstance(quant, ScalarQuantization)
    assert quant.scalar is not None
    assert quant.scalar.type == ScalarType.INT8
