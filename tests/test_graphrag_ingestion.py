"""Tests for fast-graphrag ingestion pipeline.

Covers:
- Content-type filtering (only narrative_text and example_problem)
- Audit mode caps at 50 chunks
- Full mode processes all filtered chunks
- insert() is called with documents and metadata
- Returns dict with total, ingested, failed keys
- Failure handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge_graph.graph_ingestion import (
    GRAPHRAG_CONTENT_TYPES,
    _build_document,
    _filter_chunks,
)


def _make_chunks(n, content_type="narrative_text"):
    """Create n test chunks with specified content type."""
    return [
        {
            "text": f"Chunk {i} text about accounting.",
            "metadata": {
                "book_title": "Test Book",
                "chapter": "Chapter 1",
                "page_start": i,
                "page_end": i + 1,
                "content_type": content_type,
            },
        }
        for i in range(n)
    ]


def test_content_type_filter_keeps_narrative_text():
    """_filter_chunks keeps narrative_text chunks."""
    chunks = _make_chunks(5, "narrative_text")
    result = _filter_chunks(chunks)
    assert len(result) == 5


def test_content_type_filter_keeps_example_problem():
    """_filter_chunks keeps example_problem chunks."""
    chunks = _make_chunks(3, "example_problem")
    result = _filter_chunks(chunks)
    assert len(result) == 3


def test_content_type_filter_skips_table():
    """_filter_chunks skips table content type."""
    chunks = _make_chunks(5, "table")
    result = _filter_chunks(chunks)
    assert len(result) == 0


def test_content_type_filter_skips_formula():
    """_filter_chunks skips formula content type."""
    chunks = _make_chunks(3, "formula")
    result = _filter_chunks(chunks)
    assert len(result) == 0


def test_content_type_filter_mixed():
    """_filter_chunks correctly filters mixed content types."""
    chunks = (
        _make_chunks(3, "narrative_text")
        + _make_chunks(2, "table")
        + _make_chunks(1, "example_problem")
    )
    result = _filter_chunks(chunks)
    assert len(result) == 4  # 3 narrative + 1 example


def test_build_document_prepends_metadata():
    """_build_document prepends source metadata to chunk text."""
    chunk = {
        "text": "Accounting content.",
        "metadata": {
            "book_title": "Horngren",
            "chapter": "Chapter 5",
            "page_start": 168,
        },
    }
    doc = _build_document(chunk)
    assert "[Source: Horngren, Chapter 5, page 168]" in doc
    assert "Accounting content." in doc


def test_graphrag_content_types():
    """GRAPHRAG_CONTENT_TYPES contains exactly narrative_text and example_problem."""
    assert GRAPHRAG_CONTENT_TYPES == {"narrative_text", "example_problem"}


@patch("src.knowledge_graph.graph_ingestion.build_graphrag_instance")
def test_ingest_audit_mode_caps_at_50(mock_build, tmp_path):
    """Audit mode caps at 50 chunks."""
    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_graphrag

    mock_grag = MagicMock()
    mock_build.return_value = mock_grag

    chunks = _make_chunks(100, "narrative_text")
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")

    result = ingest_chunks_to_graphrag(str(chunks_path), audit_mode=True)
    assert result["total"] == 50


@patch("src.knowledge_graph.graph_ingestion.build_graphrag_instance")
def test_ingest_full_mode_processes_all(mock_build, tmp_path):
    """Full mode processes all filtered chunks."""
    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_graphrag

    mock_grag = MagicMock()
    mock_build.return_value = mock_grag

    chunks = _make_chunks(80, "narrative_text")
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")

    result = ingest_chunks_to_graphrag(str(chunks_path), audit_mode=False)
    assert result["total"] == 80


@patch("src.knowledge_graph.graph_ingestion.build_graphrag_instance")
def test_ingest_calls_insert_with_documents_and_metadata(mock_build, tmp_path):
    """ingest_chunks_to_graphrag calls grag.insert() with documents and metadata."""
    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_graphrag

    mock_grag = MagicMock()
    mock_build.return_value = mock_grag

    chunks = _make_chunks(3, "narrative_text")
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")

    ingest_chunks_to_graphrag(str(chunks_path), audit_mode=True)
    mock_grag.insert.assert_called_once()
    call_args = mock_grag.insert.call_args
    documents = call_args[0][0]
    metadata = call_args[1]["metadata"]
    assert len(documents) == 3
    assert len(metadata) == 3
    assert metadata[0]["source"] == "Test Book"


@patch("src.knowledge_graph.graph_ingestion.build_graphrag_instance")
def test_ingest_returns_dict_with_required_keys(mock_build, tmp_path):
    """ingest_chunks_to_graphrag returns dict with total, ingested, failed keys."""
    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_graphrag

    mock_grag = MagicMock()
    mock_build.return_value = mock_grag

    chunks = _make_chunks(5, "narrative_text")
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")

    result = ingest_chunks_to_graphrag(str(chunks_path), audit_mode=True)
    assert "total" in result
    assert "ingested" in result
    assert "failed" in result


@patch("src.knowledge_graph.graph_ingestion.build_graphrag_instance")
def test_ingest_failure_sets_failed_counter(mock_build, tmp_path):
    """When insert() raises, failed counter equals total."""
    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_graphrag

    mock_grag = MagicMock()
    mock_grag.insert.side_effect = Exception("API error")
    mock_build.return_value = mock_grag

    chunks = _make_chunks(5, "narrative_text")
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")

    result = ingest_chunks_to_graphrag(str(chunks_path), audit_mode=True)
    assert result["failed"] == 5
    assert result["ingested"] == 0
