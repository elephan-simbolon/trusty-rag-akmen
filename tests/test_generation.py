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
                "author": "Horngren",
            },
        }
    ]

    result = build_citations(mock_docs)

    assert len(result) >= 1
    formatted = result[0]["formatted"]
    assert formatted.startswith("Horngren, ")
    assert "Cost Accounting" in formatted
    assert "Chapter 5" in formatted
    assert "hal. 168-170" in formatted


def test_citation_format_without_author():
    """GEN-01: Citation gracefully omits author prefix when author is absent."""
    from src.generation.citation_builder import build_citation

    metadata = {
        "book_title": "Cost Accounting",
        "chapter": "Chapter 5",
        "page_start": 168,
        "page_end": 170,
    }

    formatted = build_citation(metadata)

    assert not formatted.startswith(", ")
    assert "Cost Accounting, Chapter 5, hal. 168-170" == formatted


def test_citation_format_empty_author():
    """GEN-01: Citation treats empty string author as absent — no leading comma."""
    from src.generation.citation_builder import build_citation

    metadata = {
        "book_title": "Cost Accounting",
        "chapter": "Chapter 5",
        "page_start": 168,
        "page_end": 170,
        "author": "",
    }

    formatted = build_citation(metadata)

    assert not formatted.startswith(", ")
    assert "Cost Accounting, Chapter 5, hal. 168-170" == formatted


def test_build_citations_includes_author_field():
    """GEN-01: build_citations returns dicts with 'author' key populated from metadata."""
    from src.generation.citation_builder import build_citations

    mock_docs = [
        {
            "text": "Sample text.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 5",
                "page_start": 168,
                "page_end": 170,
                "author": "Horngren",
            },
        }
    ]

    result = build_citations(mock_docs)

    assert len(result) >= 1
    assert result[0]["author"] == "Horngren"


def test_no_citation_text_block_in_response():
    """GEN-01: generate_response output does NOT contain '**Sumber Referensi:**' text block."""
    from unittest.mock import patch, MagicMock
    from src.generation.generator import generate_response

    mock_llm_result = {"text": "Test response about BEP.", "usage": {"prompt_tokens": 10, "completion_tokens": 20}}
    mock_citations = [
        {
            "formatted": "Horngren, Cost Accounting, Chapter 5, hal. 168-170",
            "book_title": "Cost Accounting",
            "chapter": "Chapter 5",
            "page_start": 168,
            "page_end": 170,
            "section_path": "",
            "author": "Horngren",
        }
    ]

    with patch("src.generation.generator.generate", return_value=mock_llm_result), \
         patch("src.generation.generator.build_citations", return_value=mock_citations), \
         patch("src.generation.generator.update_token_usage", return_value=None):

        result = generate_response(query="test", context_docs=[{"text": "doc", "metadata": {}}])

    assert "**Sumber Referensi:**" not in result["response"]
    assert result["response"] == "Test response about BEP."


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
