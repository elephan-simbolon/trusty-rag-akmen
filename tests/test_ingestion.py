"""Tests for ingest_chunks_to_lightrag() and resume_lightrag_ingestion() — POLISH-02/03/04.

Verifies the enqueue/process two-phase ingestion pipeline:
- content-type filtering (only narrative_text + example_problem sent to LightRAG)
- enqueue/process split (apipeline_enqueue_documents + apipeline_process_enqueue_documents)
- per-batch finalize_storages flush for crash-safety
- audit_mode cap (50 filtered chunks max)
- resume path (process-only, no re-enqueue)
- failure handling (exception sets failed=total, finalize_storages still called)

All LightRAG calls are mocked — no live SiliconFlow API calls.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.knowledge_graph.graph_ingestion as graph_ingestion_module

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_chunks_json(tmp_path):
    """Write 60 chunks with mixed content types to a temp JSON file.

    Content types cycle: narrative_text, table, formula, example_problem, diagram, formula_index
    With 60 chunks and 6 types: each type appears 10 times.
    Filtered count: narrative_text (10) + example_problem (10) = 20 chunks.
    """
    content_types = [
        "narrative_text",
        "table",
        "formula",
        "example_problem",
        "diagram",
        "formula_index",
    ]
    chunks = []
    for i in range(60):
        ct = content_types[i % len(content_types)]
        chunks.append(
            {
                "text": f"Chunk {i}: overhead cost allocation discussion.",
                "metadata": {
                    "book_title": "Horngren, Cost Accounting",
                    "chapter": f"Chapter {(i % 5) + 1}",
                    "section_path": f"Part I > Chapter {(i % 5) + 1}",
                    "content_type": ct,
                    "page_start": 100 + i,
                    "page_end": 100 + i,
                },
            }
        )
    json_path = tmp_path / "chunks_backup.json"
    json_path.write_text(json.dumps(chunks), encoding="utf-8")
    return str(json_path)


@pytest.fixture
def large_chunks_json(tmp_path):
    """Write 300 chunks (all narrative_text) for audit-mode cap and batch-size testing.

    300 narrative_text chunks — after filter: 300. Audit cap: 50.
    """
    chunks = []
    for i in range(300):
        chunks.append(
            {
                "text": f"Chunk {i}: narrative text about cost allocation.",
                "metadata": {
                    "book_title": "Horngren, Cost Accounting",
                    "chapter": f"Chapter {(i % 10) + 1}",
                    "section_path": f"Part I > Chapter {(i % 10) + 1}",
                    "content_type": "narrative_text",
                    "page_start": 100 + i,
                    "page_end": 100 + i,
                },
            }
        )
    json_path = tmp_path / "large_chunks.json"
    json_path.write_text(json.dumps(chunks), encoding="utf-8")
    return str(json_path)


@pytest.fixture
def mock_rag_instance():
    """Mock LightRAG instance with enqueue/process pipeline methods."""
    rag = MagicMock()
    rag.apipeline_enqueue_documents = AsyncMock(return_value=None)
    rag.apipeline_process_enqueue_documents = AsyncMock(return_value=None)
    rag.finalize_storages = AsyncMock(return_value=None)
    rag.get_processing_status = AsyncMock(
        side_effect=[
            {"processed": 0, "failed": 0, "pending": 0},  # status_before
            {"processed": 20, "failed": 0, "pending": 0},  # status after processing
        ]
    )
    # Mock doc_status._data for dup-count check in resume path
    rag.doc_status._data = {}
    return rag


# ---------------------------------------------------------------------------
# Helper: patch context for ingest_chunks_to_lightrag
# ---------------------------------------------------------------------------


def _run_ingest(json_path, mock_rag, audit_mode=True):
    """Run ingest_chunks_to_lightrag with mocked build_lightrag_instance."""
    with patch.object(
        graph_ingestion_module,
        "build_lightrag_instance",
        new=AsyncMock(return_value=mock_rag),
    ):
        return asyncio.run(
            graph_ingestion_module.ingest_chunks_to_lightrag(json_path, audit_mode=audit_mode)
        )


def _run_resume(mock_rag):
    """Run resume_lightrag_ingestion with mocked build_lightrag_instance."""
    with patch.object(
        graph_ingestion_module,
        "build_lightrag_instance",
        new=AsyncMock(return_value=mock_rag),
    ):
        return asyncio.run(graph_ingestion_module.resume_lightrag_ingestion())


# ---------------------------------------------------------------------------
# Tests — ingest_chunks_to_lightrag
# ---------------------------------------------------------------------------


def test_content_type_filtering(sample_chunks_json, mock_rag_instance):
    """Only narrative_text and example_problem chunks are enqueued.

    60 chunks (10 of each of 6 types) → 20 filtered chunks sent to enqueue.
    """
    enqueued_texts = []

    async def capture_enqueue(batch):
        enqueued_texts.extend(batch)

    mock_rag_instance.apipeline_enqueue_documents = capture_enqueue

    result = _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=False)

    # 20 filtered chunks (10 narrative_text + 10 example_problem)
    assert len(enqueued_texts) == 20, (
        f"Expected 20 enqueued docs (after content filter) but got {len(enqueued_texts)}"
    )
    assert result["total"] == 20


def test_enqueue_process_split(sample_chunks_json, mock_rag_instance):
    """Uses apipeline_enqueue_documents (not ainsert), and calls apipeline_process_enqueue_documents once."""
    _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=False)

    # Must use enqueue, not ainsert
    mock_rag_instance.apipeline_enqueue_documents.assert_called()
    mock_rag_instance.apipeline_process_enqueue_documents.assert_called_once()

    # ainsert must NOT be called
    mock_rag_instance.ainsert.assert_not_called()


def test_finalize_called_per_enqueue_batch(sample_chunks_json, mock_rag_instance):
    """finalize_storages is called after each enqueue batch plus in the finally block.

    With 20 filtered chunks and ENQUEUE_BATCH_SIZE=50: 1 enqueue batch.
    finalize_storages should be called: 1 (after batch) + 1 (in finally) = at least 2 times.
    """
    _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=False)

    # At least 2 calls: 1 after enqueue batch + 1 in finally
    assert mock_rag_instance.finalize_storages.call_count >= 2, (
        f"Expected finalize_storages >= 2 calls but got {mock_rag_instance.finalize_storages.call_count}"
    )


def test_audit_mode_caps_at_50(large_chunks_json, mock_rag_instance):
    """audit_mode=True caps at 50 chunks even when 300 narrative_text chunks available."""
    result = _run_ingest(large_chunks_json, mock_rag_instance, audit_mode=True)

    assert result["total"] == 50, f"Expected audit mode to cap at 50 but got {result['total']}"


def test_full_mode_processes_all_filtered(sample_chunks_json, mock_rag_instance):
    """audit_mode=False processes all 20 filtered chunks (not just 50 cap)."""
    result = _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=False)

    # 60 total chunks, 20 pass filter (narrative_text + example_problem)
    assert result["total"] == 20


def test_returns_dict_with_required_keys(sample_chunks_json, mock_rag_instance):
    """Return dict must have total, ingested, failed, duplicates, real_failed keys."""
    result = _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=True)

    assert isinstance(result, dict)
    assert "total" in result
    assert "ingested" in result
    assert "failed" in result
    assert "duplicates" in result
    assert "real_failed" in result


def test_failure_sets_failed_counter(sample_chunks_json, mock_rag_instance):
    """When apipeline_process_enqueue_documents raises, failed == total."""
    mock_rag_instance.apipeline_process_enqueue_documents = AsyncMock(
        side_effect=RuntimeError("Simulated SiliconFlow error")
    )
    # Override: status_before is called once, then exception prevents status_after
    mock_rag_instance.get_processing_status = AsyncMock(
        return_value={"processed": 0, "failed": 0, "pending": 0}
    )

    result = _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=True)

    # 20 filtered chunks in audit mode (20 < 50 cap)
    assert result["failed"] == result["total"]
    assert result["ingested"] == 0


def test_finalize_called_on_exception(sample_chunks_json, mock_rag_instance):
    """finalize_storages is still called even when apipeline_process_enqueue_documents raises."""
    mock_rag_instance.apipeline_process_enqueue_documents = AsyncMock(
        side_effect=RuntimeError("Simulated failure")
    )
    # Override: status_before is called once, then exception prevents status_after
    mock_rag_instance.get_processing_status = AsyncMock(
        return_value={"processed": 0, "failed": 0, "pending": 0}
    )

    # Must not raise
    _run_ingest(sample_chunks_json, mock_rag_instance, audit_mode=True)

    # finalize_storages must be called (in finally block)
    mock_rag_instance.finalize_storages.assert_called()


def test_batch_enqueue_size(large_chunks_json, mock_rag_instance):
    """Each apipeline_enqueue_documents call receives at most ENQUEUE_BATCH_SIZE documents."""
    batch_sizes = []

    async def capture_enqueue(batch):
        batch_sizes.append(len(batch))

    mock_rag_instance.apipeline_enqueue_documents = capture_enqueue

    _run_ingest(large_chunks_json, mock_rag_instance, audit_mode=False)

    # Each batch must be <= ENQUEUE_BATCH_SIZE
    assert all(size <= graph_ingestion_module.ENQUEUE_BATCH_SIZE for size in batch_sizes), (
        f"Some batches exceeded ENQUEUE_BATCH_SIZE={graph_ingestion_module.ENQUEUE_BATCH_SIZE}: {batch_sizes}"
    )
    assert len(batch_sizes) >= 1, "Expected at least one enqueue batch call"


# ---------------------------------------------------------------------------
# Tests — resume_lightrag_ingestion
# ---------------------------------------------------------------------------


def test_resume_calls_process_only(sample_chunks_json, mock_rag_instance):
    """resume_lightrag_ingestion calls apipeline_process_enqueue_documents only — NOT apipeline_enqueue_documents."""
    _run_resume(mock_rag_instance)

    # Must call process
    mock_rag_instance.apipeline_process_enqueue_documents.assert_called_once()
    # Must NOT enqueue (Pitfall 1: re-enqueueing creates FAILED duplicate records)
    mock_rag_instance.apipeline_enqueue_documents.assert_not_called()


def test_resume_returns_status_dict(sample_chunks_json, mock_rag_instance):
    """resume_lightrag_ingestion returns dict with total, ingested, failed, duplicates, real_failed keys."""
    mock_rag_instance.get_processing_status = AsyncMock(
        side_effect=[
            {"processed": 15, "failed": 5, "pending": 0},  # before
            {"processed": 20, "failed": 0, "pending": 0},  # after
        ]
    )

    result = _run_resume(mock_rag_instance)

    assert isinstance(result, dict)
    assert "total" in result
    assert "ingested" in result
    assert "failed" in result
    assert "duplicates" in result
    assert "real_failed" in result
    # Delta: 20-15=5 newly processed, 0-5=-5 fewer failures
    assert result["ingested"] == 5
    assert result["failed"] == -5
