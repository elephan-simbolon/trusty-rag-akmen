import logging

from src.ingestion.chunking.classifier import classify_element
from src.ingestion.chunking.page_markers import extract_page_range, strip_page_markers

logger = logging.getLogger(__name__)

REQUIRED_METADATA_FIELDS = [
    "book_title",
    "chapter",
    "section_path",
    "content_type",
    "page_start",
    "page_end",
]


def enrich_metadata(
    chunk_text: str,
    book_title: str,
    chapter: str,
    section_path: str,
    content_type: str | None = None,
) -> dict:
    """Enrich chunk with metadata fields; extracts page range from markers and strips them."""
    page_start, page_end = extract_page_range(chunk_text)
    if page_start == 0:
        logger.warning(
            f"No page markers found in chunk from {book_title}/{chapter}. "
            "Citation page numbers will be inaccurate."
        )

    clean_text = strip_page_markers(chunk_text)

    if content_type is None:
        content_type = classify_element(clean_text).value

    metadata = {
        "book_title": book_title,
        "chapter": chapter,
        "section_path": section_path,
        "content_type": content_type,
        "page_start": page_start,
        "page_end": page_end,
    }

    return {
        "text": clean_text,
        "metadata": metadata,
    }


def validate_metadata(chunk: dict) -> list[str]:
    """Return list of missing required metadata field names (empty list = valid)."""
    metadata = chunk.get("metadata", {})
    missing = [f for f in REQUIRED_METADATA_FIELDS if f not in metadata or metadata[f] is None]
    return missing
