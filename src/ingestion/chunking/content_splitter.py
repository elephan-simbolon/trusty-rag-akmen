import logging

from src.ingestion.chunking.classifier import ContentType, classify_element

logger = logging.getLogger(__name__)

# Token estimation: ~4 chars per token for English text
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def split_narrative(text: str, max_tokens: int = 512, overlap_tokens: int = 75) -> list[str]:
    """Split narrative text into chunks of max_tokens with overlap_tokens overlap."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    if estimate_tokens(text) <= max_tokens:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at sentence boundary
        segment = text[start:end]
        last_period = segment.rfind(". ")
        if last_period > max_chars * 0.5:
            end = start + last_period + 2

        chunks.append(text[start:end].strip())
        start = end - overlap_chars

    return [c for c in chunks if c.strip()]


def split_large_table(markdown_table: str, max_rows: int = 20) -> list[str]:
    """
    Split a large Markdown table into chunks with column headers repeated.
    Tables <= 20 rows are kept as atomic chunks.
    Source: RESEARCH.md Pitfall 3 + Table Chunk code.
    """
    lines = markdown_table.strip().split("\n")
    # Find header and separator
    table_lines = [line for line in lines if line.strip().startswith("|")]
    non_table_prefix = [
        line
        for line in lines
        if not line.strip().startswith("|")
        and lines.index(line) < (lines.index(table_lines[0]) if table_lines else 0)
    ]

    if len(table_lines) < 3:
        return [markdown_table]

    header_line = table_lines[0]
    separator_line = table_lines[1]
    data_rows = table_lines[2:]

    if len(data_rows) <= max_rows:
        return [markdown_table]

    prefix = "\n".join(non_table_prefix).strip()
    chunks = []
    for i in range(0, len(data_rows), max_rows):
        row_group = data_rows[i : i + max_rows]
        chunk = "\n".join([header_line, separator_line] + row_group)
        if prefix:
            chunk = prefix + "\n" + chunk
        chunks.append(chunk)
    return chunks


def split_content_by_type(text: str, content_type: ContentType | None = None) -> list[str]:
    """
    Apply content-type-specific splitting rules.
    - narrative_text: 512 tokens, 75 overlap
    - table: atomic if <=20 rows, split with repeated headers if >20
    - formula: atomic unit (up to 1024 tokens) — keep formula + explanation together
    - diagram: atomic (usually short captions)
    - example_problem: atomic up to 1024 tokens
    """
    if content_type is None:
        content_type = classify_element(text)

    if content_type == ContentType.NARRATIVE_TEXT:
        return split_narrative(text, max_tokens=512, overlap_tokens=75)

    elif content_type == ContentType.TABLE:
        return split_large_table(text, max_rows=20)

    elif content_type == ContentType.FORMULA:
        # Atomic — keep formula and explanation together
        if estimate_tokens(text) <= 1024:
            return [text]
        # If somehow very long, split at paragraph boundaries
        return split_narrative(text, max_tokens=1024, overlap_tokens=50)

    elif content_type == ContentType.DIAGRAM:
        return [text]  # Always atomic

    elif content_type == ContentType.EXAMPLE_PROBLEM:
        if estimate_tokens(text) <= 1024:
            return [text]
        return split_narrative(text, max_tokens=1024, overlap_tokens=50)

    return [text]
