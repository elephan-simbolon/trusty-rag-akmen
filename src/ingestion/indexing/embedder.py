"""Batch embedder with checkpoint resume — embed + upload per batch."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from src.llm.client import embed_batch

logger = logging.getLogger(__name__)


def build_contextual_text(chunk_text: str, parent_text: str, max_context_words: int = 256) -> str:
    """Prepend truncated parent context to child chunk text (CHUNK-05)."""
    if not parent_text or not parent_text.strip():
        return chunk_text
    context = " ".join(parent_text.split()[:max_context_words])
    return f"[Context: {context}]\n\n{chunk_text}"


def embed_chunks_batch(
    chunks: list[dict],
    batch_size: int = 16,
    checkpoint_path: str | None = None,
    upload_fn: Callable | None = None,
    use_contextual_window: bool = False,
    parent_texts: dict[str, str] | None = None,
) -> int:
    """Embed chunks in batches, upload each batch immediately. Return total processed."""
    start_idx = 0
    if checkpoint_path:
        cp = Path(checkpoint_path)
        if cp.exists():
            checkpoint = json.loads(cp.read_text(encoding="utf-8"))
            start_idx = checkpoint.get("last_completed_idx", 0) + 1
            logger.info(f"Resuming from index {start_idx}")

    total = 0
    for i in range(start_idx, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]

        if use_contextual_window and parent_texts:
            texts = [
                build_contextual_text(
                    c["text"],
                    parent_texts.get(c.get("metadata", {}).get("section_path", ""), ""),
                )
                for c in batch
            ]
        else:
            texts = [c["text"] for c in batch]

        embeddings = embed_batch(texts, is_query=False)
        for chunk, emb in zip(batch, embeddings):
            chunk["embedding"] = emb

        if upload_fn:
            upload_fn(batch)

        if checkpoint_path:
            Path(checkpoint_path).write_text(
                json.dumps({"last_completed_idx": i + len(batch) - 1}),
                encoding="utf-8",
            )

        total += len(batch)
        logger.info(f"Embedded batch {i}-{i + len(batch)} / {len(chunks)}")

    return total
