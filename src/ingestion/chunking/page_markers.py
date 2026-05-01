import re

PAGE_MARKER_PATTERN = re.compile(r"<!-- PAGE_START:(\d+) -->")


def extract_page_range(chunk_text: str) -> tuple[int, int]:
    """Extract (page_start, page_end) from inline markers; returns (0, 0) if absent."""
    pages = [int(m) for m in PAGE_MARKER_PATTERN.findall(chunk_text)]
    if not pages:
        return (0, 0)
    return (pages[0], pages[-1])


def strip_page_markers(chunk_text: str) -> str:
    """Remove <!-- PAGE_START:N --> markers before embedding to avoid corrupting vectors."""
    return re.sub(r"\n?<!-- PAGE_START:\d+ -->\n?", "\n", chunk_text).strip()
