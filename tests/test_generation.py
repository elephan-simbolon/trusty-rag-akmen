import pytest


def test_citation_format_in_response():
    """GEN-01: Generated response includes citation in format: Author, Title, Chapter N, hal. X-Y."""
    from src.generation.citation_builder import build_citations

    mock_docs = [
        {
            "text": "Break-even point is the volume of sales at which total revenue equals total cost.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5 > Break-Even Analysis",
                "content_type": "narrative_text",
                "page_start": 168,
                "page_end": 170,
            },
        }
    ]

    result = build_citations(mock_docs)

    assert len(result) >= 1
    formatted = result[0]["formatted"]
    assert "Cost Accounting" in formatted
    assert "Chapter 5" in formatted
    assert "hal. 168-170" in formatted


def test_citation_contains_required_fields():
    """GEN-01: Citation includes all required fields: book_title, chapter, page_start, page_end."""
    from src.generation.citation_builder import build_citations

    mock_docs = [
        {
            "text": "Sample text.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5",
                "content_type": "narrative_text",
                "page_start": 168,
                "page_end": 170,
            },
        }
    ]

    result = build_citations(mock_docs)

    assert len(result) >= 1
    citation = result[0]
    required_keys = {"formatted", "book_title", "chapter", "page_start", "page_end", "section_path"}
    for key in required_keys:
        assert key in citation, f"Missing key: {key}"
