import re
from typing import Optional

PAGE_MARKER_PATTERN = re.compile(r"<!-- PAGE_START:(\d+) -->")


def inject_page_markers(markdown_text: str, page_map: list[tuple[int, int]]) -> str:
    """
    Inject <!-- PAGE_START:N --> markers at each page boundary in markdown text.
    page_map: list of (char_offset, page_number) tuples from PDF parser.
    """
    result = []
    prev_offset = 0
    for char_offset, page_num in sorted(page_map, key=lambda x: x[0]):
        result.append(markdown_text[prev_offset:char_offset])
        result.append(f"\n<!-- PAGE_START:{page_num} -->\n")
        prev_offset = char_offset
    result.append(markdown_text[prev_offset:])
    return "".join(result)


def extract_page_range(chunk_text: str) -> tuple[int, int]:
    """
    Extract page_start and page_end from chunk text containing page markers.
    Returns (0, 0) if no markers found — triggers warning in metadata_enricher.
    """
    pages = [int(m) for m in PAGE_MARKER_PATTERN.findall(chunk_text)]
    if not pages:
        return (0, 0)
    return (pages[0], pages[-1])


def strip_page_markers(chunk_text: str) -> str:
    """
    Remove page markers before embedding — markers corrupt semantic vectors.
    """
    return re.sub(r"\n?<!-- PAGE_START:\d+ -->\n?", "\n", chunk_text).strip()
