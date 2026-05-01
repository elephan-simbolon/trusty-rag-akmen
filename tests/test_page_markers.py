from src.ingestion.chunking.page_markers import (
    extract_page_range,
    strip_page_markers,
)


def test_extract_page_range():
    """CHUNK-08: Page range (page_start, page_end) is correctly extracted from inline markers."""
    text_with_markers = "Some text\n<!-- PAGE_START:5 -->\nMore text\n<!-- PAGE_START:7 -->\nEnd"
    assert extract_page_range(text_with_markers) == (5, 7)

    # Empty input returns (0, 0)
    assert extract_page_range("No markers here") == (0, 0)
    assert extract_page_range("") == (0, 0)


def test_strip_page_markers():
    """CHUNK-08: Page markers are stripped from text before embedding (clean text only)."""
    text = "<!-- PAGE_START:5 -->\nSome content\n<!-- PAGE_START:6 -->"
    result = strip_page_markers(text)
    assert "PAGE_START" not in result
    assert "Some content" in result
