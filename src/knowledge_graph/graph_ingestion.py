"""Async ingestion pipeline: Phase 1 JSON chunks -> LightRAG knowledge graph.

Uses two-phase enqueue/process pipeline for crash-safe ingestion:
- Phase 1: apipeline_enqueue_documents in batches with finalize_storages per batch
- Phase 2: apipeline_process_enqueue_documents to extract entities from all enqueued docs

Content-type filtering reduces volume by ~30%: only narrative_text and example_problem
chunks are sent to LightRAG. Tables, formulas, formula_index, and diagrams are skipped
because they produce noisy or empty entity extractions.

Usage (via CLI):
    python scripts/ingest_lightrag.py data/chunks_backup.json
    python scripts/ingest_lightrag.py data/chunks_backup.json --full
    python scripts/ingest_lightrag.py data/chunks_backup.json --resume
"""

import json
import logging
from pathlib import Path

from src.knowledge_graph.lightrag_client import build_lightrag_instance

logger = logging.getLogger(__name__)

# Content types that produce useful accounting entities in LightRAG.
# Tables, formulas, formula_index, and diagrams are excluded — they produce
# noisy or empty entity extractions that inflate graph size without quality gain.
LIGHTRAG_CONTENT_TYPES = {"narrative_text", "example_problem"}

# Documents per apipeline_enqueue_documents call. After each batch, finalize_storages
# flushes doc_status to disk so a crash mid-enqueue can resume without loss.
ENQUEUE_BATCH_SIZE = 50


def _build_document(chunk: dict) -> str:
    """Prepend source metadata to chunk text for LightRAG insertion."""
    meta = chunk["metadata"]
    return (
        f"[Source: {meta['book_title']}, "
        f"{meta['chapter']}, "
        f"page {meta.get('page_start', '?')}]\n\n"
        f"{chunk['text']}"
    )


def _filter_chunks_for_lightrag(chunks: list[dict]) -> list[dict]:
    """Keep only content types that produce useful accounting entities."""
    kept = [c for c in chunks if c["metadata"].get("content_type") in LIGHTRAG_CONTENT_TYPES]
    skipped = len(chunks) - len(kept)
    logger.info(
        f"Content-type filter: {len(kept)} kept, {skipped} skipped "
        f"(types kept: {LIGHTRAG_CONTENT_TYPES})"
    )
    return kept


async def ingest_chunks_to_lightrag(
    chunks_json_path: str,
    audit_mode: bool = True,
    llm_model: str | None = None,
) -> dict:
    """Load Phase 1 chunks and batch-insert into LightRAG using enqueue/process split.

    Content-type filtering is applied before the audit_mode cap:
    - Only narrative_text and example_problem chunks are ingested.
    - audit_mode=True caps at 50 filtered chunks (default: verify quality first).
    - audit_mode=False processes all filtered chunks.

    Returns dict with keys: total, ingested, failed.
    """
    rag = await build_lightrag_instance(llm_model=llm_model)

    chunks = json.loads(Path(chunks_json_path).read_text(encoding="utf-8"))
    logger.info(f"Loaded {len(chunks)} chunks from {chunks_json_path}")

    # Filter to content types that produce useful entities (Step 1: filter, then cap)
    filtered = _filter_chunks_for_lightrag(chunks)
    target = filtered[:50] if audit_mode else filtered
    documents = [_build_document(c) for c in target]
    total = len(documents)

    logger.info(
        f"{'Audit' if audit_mode else 'Full'} mode: processing {total} documents "
        f"({'capped at 50' if audit_mode and len(filtered) > 50 else 'all filtered'})"
    )

    ingested = 0
    failed = total  # default to all-failed; updated on success

    try:
        status_before = await rag.get_processing_status()

        # Phase 1: Enqueue in batches with per-batch disk flush (crash-safe)
        for i in range(0, total, ENQUEUE_BATCH_SIZE):
            batch = documents[i : i + ENQUEUE_BATCH_SIZE]
            await rag.apipeline_enqueue_documents(batch)
            await rag.finalize_storages()  # flush doc_status to disk after each batch
            logger.info(f"Enqueued {min(i + ENQUEUE_BATCH_SIZE, total)}/{total}")

        # Phase 2: Process all enqueued docs (PENDING + FAILED → entity extraction)
        await rag.apipeline_process_enqueue_documents()

        status = await rag.get_processing_status()
        logger.info(f"Final status: {status}")

        # Delta = this run only (not cumulative across all runs)
        ingested = status.get("processed", 0) - status_before.get("processed", 0)
        failed = status.get("failed", 0) - status_before.get("failed", 0)

        # Break down failures: dup- prefix = duplicate content (not real errors)
        duplicates = sum(1 for k in rag.doc_status._data if k.startswith("dup-"))
        real_failed = max(0, status.get("failed", 0) - duplicates)

    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}")
        ingested = 0
        failed = total
        duplicates = 0
        real_failed = total
    finally:
        await rag.finalize_storages()

    return {
        "total": total,
        "ingested": ingested,
        "failed": failed,
        "duplicates": duplicates,
        "real_failed": real_failed,
    }


async def resume_lightrag_ingestion(llm_model: str | None = None) -> dict:
    """Resume processing of already-enqueued docs without re-enqueuing.

    Called via --resume CLI flag. Only calls apipeline_process_enqueue_documents()
    to process PENDING/FAILED docs. Does NOT call apipeline_enqueue_documents()
    (which would create FAILED duplicate records for already-PROCESSED docs).

    No chunks_path needed — reprocessing works directly from LightRAG's doc_status
    storage, consistent with LightRAG's /documents/reprocess_failed pattern.

    See Pitfall 1 in 04.1-RESEARCH.md: re-enqueueing creates [DUPLICATE] FAILED records.

    Returns dict with keys: total, ingested, failed.
    """
    rag = await build_lightrag_instance(llm_model=llm_model)
    try:
        status_before = await rag.get_processing_status()
        logger.info(f"Resuming ingestion. Status before: {status_before}")

        await rag.apipeline_process_enqueue_documents()

        status_after = await rag.get_processing_status()
        logger.info(f"Resume complete. Status after: {status_after}")

        # Break down failures: dup- prefix = duplicate content (not real errors)
        duplicates = sum(1 for k in rag.doc_status._data if k.startswith("dup-"))
        real_failed = max(0, status_after.get("failed", 0) - duplicates)

        # Delta = this resume run only (not cumulative across all runs)
        return {
            "total": sum(status_after.values()),
            "ingested": status_after.get("processed", 0) - status_before.get("processed", 0),
            "failed": status_after.get("failed", 0) - status_before.get("failed", 0),
            "duplicates": duplicates,
            "real_failed": real_failed,
        }
    finally:
        await rag.finalize_storages()


async def clean_duplicate_doc_status() -> int:
    """Remove dup- prefixed FAILED records from doc_status (created by re-enqueue).

    LightRAG creates dup- records when apipeline_enqueue_documents() is called
    for documents already in doc_status (see lightrag.py:1396-1439). These inflate
    the failed count without representing real processing failures.
    """
    rag = await build_lightrag_instance()
    try:
        dup_ids = [doc_id for doc_id in rag.doc_status._data if doc_id.startswith("dup-")]
        if dup_ids:
            await rag.doc_status.delete(dup_ids)
            await rag.doc_status.index_done_callback()  # flush deletion to disk
            logger.info(f"Cleaned {len(dup_ids)} duplicate doc_status records")
        else:
            logger.info("No duplicate (dup-) records found in doc_status")
        return len(dup_ids)
    finally:
        await rag.finalize_storages()
