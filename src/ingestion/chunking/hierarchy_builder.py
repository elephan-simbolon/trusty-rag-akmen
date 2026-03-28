import logging
from dataclasses import dataclass

from src.ingestion.chunking.content_splitter import estimate_tokens

logger = logging.getLogger(__name__)


@dataclass
class ChunkNode:
    text: str
    node_type: str  # "parent" or "child"
    parent_id: str | None
    chunk_id: str
    metadata: dict


def build_hierarchy(
    chunks: list[dict],
    parent_min_tokens: int = 1000,
    parent_max_tokens: int = 1500,
    child_min_tokens: int = 200,
    child_max_tokens: int = 512,
) -> list[ChunkNode]:
    """
    Build parent-child hierarchy from flat chunk list.
    Parent chunks: 1000-1500 tokens (aggregated from children).
    Child chunks: 200-512 tokens (the actual retrieval units).

    Uses a simple grouping strategy: consecutive child chunks are grouped
    under a parent. When the accumulated tokens exceed parent_max_tokens,
    a new parent is started.

    Each chunk dict must have: 'text', 'metadata'.
    """
    nodes: list[ChunkNode] = []
    parent_counter = 0
    child_counter = 0

    current_parent_children: list[dict] = []
    current_parent_tokens = 0

    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk["text"])

        # If adding this chunk would exceed parent max, flush current parent
        if current_parent_tokens + chunk_tokens > parent_max_tokens and current_parent_children:
            parent_id = f"parent-{parent_counter:04d}"
            parent_text = "\n\n".join(c["text"] for c in current_parent_children)
            parent_metadata = {**current_parent_children[0].get("metadata", {})}
            parent_metadata["node_type"] = "parent"

            nodes.append(
                ChunkNode(
                    text=parent_text,
                    node_type="parent",
                    parent_id=None,
                    chunk_id=parent_id,
                    metadata=parent_metadata,
                )
            )

            for child_chunk in current_parent_children:
                child_id = f"child-{child_counter:04d}"
                child_metadata = {**child_chunk.get("metadata", {})}
                child_metadata["node_type"] = "child"
                nodes.append(
                    ChunkNode(
                        text=child_chunk["text"],
                        node_type="child",
                        parent_id=parent_id,
                        chunk_id=child_id,
                        metadata=child_metadata,
                    )
                )
                child_counter += 1

            parent_counter += 1
            current_parent_children = []
            current_parent_tokens = 0

        current_parent_children.append(chunk)
        current_parent_tokens += chunk_tokens

    # Flush remaining
    if current_parent_children:
        parent_id = f"parent-{parent_counter:04d}"
        parent_text = "\n\n".join(c["text"] for c in current_parent_children)
        parent_metadata = {**current_parent_children[0].get("metadata", {})}
        parent_metadata["node_type"] = "parent"

        nodes.append(
            ChunkNode(
                text=parent_text,
                node_type="parent",
                parent_id=None,
                chunk_id=parent_id,
                metadata=parent_metadata,
            )
        )

        for child_chunk in current_parent_children:
            child_id = f"child-{child_counter:04d}"
            child_metadata = {**child_chunk.get("metadata", {})}
            child_metadata["node_type"] = "child"
            nodes.append(
                ChunkNode(
                    text=child_chunk["text"],
                    node_type="child",
                    parent_id=parent_id,
                    chunk_id=child_id,
                    metadata=child_metadata,
                )
            )
            child_counter += 1

    logger.info(f"Built hierarchy: {parent_counter + 1} parents, {child_counter} children")
    return nodes
