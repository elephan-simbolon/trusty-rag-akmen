import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    NARRATIVE_TEXT = "narrative_text"
    TABLE = "table"
    FORMULA = "formula"
    DIAGRAM = "diagram"
    EXAMPLE_PROBLEM = "example_problem"


# Regex patterns for content type detection
TABLE_PATTERN = re.compile(r"^\|.*\|$", re.MULTILINE)
TABLE_SEPARATOR = re.compile(r"^\|[\s\-:|]+\|$", re.MULTILINE)
FORMULA_PATTERN = re.compile(r"\$\$.*?\$\$", re.DOTALL)
INLINE_FORMULA = re.compile(r"(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)")
DIAGRAM_KEYWORDS = re.compile(
    r"(?:diagram|flowchart|figure|gambar|bagan|grafik)\s*\d*", re.IGNORECASE
)
EXAMPLE_KEYWORDS = re.compile(
    r"(?:example|contoh|soal|exercise|illustration|ilustrasi|problem)\s*\d*[.:]", re.IGNORECASE
)


def classify_element(text: str) -> ContentType:
    """
    Classify a text element into one of five content types.
    Priority: table > formula > example_problem > diagram > narrative_text.
    """
    text_stripped = text.strip()

    # Check for Markdown table (| delimiters + separator row)
    table_rows = TABLE_PATTERN.findall(text_stripped)
    separator_rows = TABLE_SEPARATOR.findall(text_stripped)
    if len(table_rows) >= 3 and len(separator_rows) >= 1:
        return ContentType.TABLE

    # Check for display math ($$...$$)
    if FORMULA_PATTERN.search(text_stripped):
        # If the block is primarily a formula (>50% of content is math)
        formula_matches = FORMULA_PATTERN.findall(text_stripped)
        formula_chars = sum(len(m) for m in formula_matches)
        if formula_chars > len(text_stripped) * 0.3:
            return ContentType.FORMULA

    # Check for example/exercise pattern
    lines = text_stripped.split("\n")
    first_lines = "\n".join(lines[:3])
    if EXAMPLE_KEYWORDS.search(first_lines):
        return ContentType.EXAMPLE_PROBLEM

    # Check for diagram reference
    if DIAGRAM_KEYWORDS.search(first_lines) and len(text_stripped) < 500:
        return ContentType.DIAGRAM

    return ContentType.NARRATIVE_TEXT


def classify_elements(elements: list[str]) -> list[tuple[str, ContentType]]:
    """Classify a list of text elements. Returns list of (text, content_type) tuples."""
    return [(elem, classify_element(elem)) for elem in elements]
