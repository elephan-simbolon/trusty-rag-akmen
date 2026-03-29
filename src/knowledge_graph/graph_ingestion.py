"""Ingestion pipeline: Phase 1 JSON chunks -> fast-graphrag knowledge graph.

Uses fast-graphrag's insert() with built-in checkpointing for crash safety.

Content-type filtering reduces volume by ~30%: only narrative_text and example_problem
chunks are sent to GraphRAG. Tables, formulas, formula_index, and diagrams are skipped
because they produce noisy or empty entity extractions.

Usage (via CLI):
    python scripts/ingest_graphrag.py data/chunks_backup.json
    python scripts/ingest_graphrag.py data/chunks_backup.json --full
"""

import json
import logging
from pathlib import Path

from src.knowledge_graph.fastgraphrag_client import build_graphrag_instance

logger = logging.getLogger(__name__)

GRAPHRAG_CONTENT_TYPES = {"narrative_text", "example_problem"}


def _build_document(chunk: dict) -> str:
    """Prepend source metadata to chunk text for GraphRAG insertion."""
    meta = chunk["metadata"]
    return (
        f"[Source: {meta['book_title']}, "
        f"{meta['chapter']}, "
        f"page {meta.get('page_start', '?')}]\n\n"
        f"{chunk['text']}"
    )


def _filter_chunks(chunks: list[dict]) -> list[dict]:
    """Keep only content types that produce useful accounting entities."""
    kept = [c for c in chunks if c["metadata"].get("content_type") in GRAPHRAG_CONTENT_TYPES]
    skipped = len(chunks) - len(kept)
    logger.info(
        "Content-type filter: %d kept, %d skipped (types kept: %s)",
        len(kept),
        skipped,
        GRAPHRAG_CONTENT_TYPES,
    )
    return kept


def ingest_chunks_to_graphrag(
    chunks_json_path: str,
    audit_mode: bool = True,
    llm_model: str | None = None,
    batch_size: int = 200,
) -> dict:
    """Load Phase 1 chunks and insert into fast-graphrag.

    Content-type filtering is applied before the audit_mode cap:
    - Only narrative_text and example_problem chunks are ingested.
    - audit_mode=True caps at 50 filtered chunks (default: verify quality first).
    - audit_mode=False processes all filtered chunks in batches.

    batch_size controls how many documents are sent per insert() call.
    Inserting in smaller batches limits the number of entities/edges accumulated
    per pass, preventing LLM output token overflow during graph building.
    Default 200 is safe for DeepSeek with EdgeUpsertPolicy_UpsertIfValidNodes.

    Returns dict with keys: total, ingested, failed.
    """
    grag = build_graphrag_instance(llm_model=llm_model)

    chunks = json.loads(Path(chunks_json_path).read_text(encoding="utf-8"))
    logger.info("Loaded %d chunks from %s", len(chunks), chunks_json_path)

    filtered = _filter_chunks(chunks)
    target = filtered[:50] if audit_mode else filtered
    total = len(target)

    logger.info(
        "%s mode: processing %d documents (%s)",
        "Audit" if audit_mode else "Full",
        total,
        "capped at 50" if audit_mode and len(filtered) > 50 else "all filtered",
    )

    ingested = 0
    failed = 0
    total_batches = (total + batch_size - 1) // batch_size
    for batch_num, batch_start in enumerate(range(0, total, batch_size), start=1):
        batch = target[batch_start : batch_start + batch_size]
        documents = [_build_document(c) for c in batch]
        metadata = [
            {
                "source": c["metadata"].get("book_title", "unknown"),
                "chapter": c["metadata"].get("chapter", "unknown"),
            }
            for c in batch
        ]
        logger.info("Batch %d/%d: inserting %d documents", batch_num, total_batches, len(batch))
        try:
            grag.insert(documents, metadata=metadata)
            ingested += len(batch)
        except Exception as exc:
            logger.error("Batch %d/%d failed: %s", batch_num, total_batches, exc)
            failed += len(batch)

    logger.info("Ingestion complete: %d documents processed", ingested)
    return {"total": total, "ingested": ingested, "failed": failed}
