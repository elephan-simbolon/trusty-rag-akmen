import logging

logger = logging.getLogger(__name__)


def build_citation(metadata: dict) -> str:
    """
    Format a single citation from chunk metadata.
    Format: "Author, *Title*, Chapter X, hal. N-M"
    Source: GEN-01 in REQUIREMENTS.md — locked format.
    """
    book_title = metadata.get("book_title", "Unknown")
    chapter = metadata.get("chapter", "Unknown")
    page_start = metadata.get("page_start", 0)
    page_end = metadata.get("page_end", 0)

    if page_start and page_end and page_start != page_end:
        page_ref = f"hal. {page_start}-{page_end}"
    elif page_start:
        page_ref = f"hal. {page_start}"
    else:
        page_ref = "hal. tidak diketahui"

    return f"{book_title}, {chapter}, {page_ref}"


def build_citations(docs: list[dict]) -> list[dict]:
    """
    Build citations from a list of retrieved/reranked documents.
    Deduplicates by (book_title, chapter, page_start).
    Returns: list of dicts with 'formatted' (string) and raw metadata fields.
    """
    seen = set()
    citations = []

    for doc in docs:
        metadata = doc.get("metadata", {})
        key = (
            metadata.get("book_title", ""),
            metadata.get("chapter", ""),
            metadata.get("page_start", 0),
        )
        if key in seen:
            continue
        seen.add(key)

        formatted = build_citation(metadata)
        citations.append({
            "formatted": formatted,
            "book_title": metadata.get("book_title", ""),
            "chapter": metadata.get("chapter", ""),
            "page_start": metadata.get("page_start", 0),
            "page_end": metadata.get("page_end", 0),
            "section_path": metadata.get("section_path", ""),
        })

    logger.info(f"Built {len(citations)} citations from {len(docs)} docs")
    return citations
