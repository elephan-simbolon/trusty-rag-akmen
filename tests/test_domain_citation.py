"""Unit tests for Phase 07: citation label differentiation (RETR-03).

Tests _build_context_block (generator.py) and build_citations (citation_builder.py).
Label convention: source_domain='consulting' -> [Kerangka N], else -> [Sumber N].
Both functions must produce consistent labels — no LLM/frontend mismatch.

Run: uv run pytest tests/test_domain_citation.py -x
"""


def test_accounting_citation_label():
    """_build_context_block emits [Sumber N:] for source_domain='accounting'."""
    from src.generation.generator import _build_context_block

    docs = [
        {
            "text": "Biaya tetap tidak berubah dengan volume produksi.",
            "metadata": {
                "book_title": "Akuntansi Biaya",
                "chapter": "Chapter 3",
                "page_start": 45,
                "source_domain": "accounting",
            },
        }
    ]
    result = _build_context_block(docs)
    assert result.startswith("[Sumber 1:"), f"Expected [Sumber 1:], got: {result[:30]}"
    assert "[Kerangka" not in result


def test_consulting_citation_label():
    """_build_context_block emits [Kerangka N:] for source_domain='consulting'."""
    from src.generation.generator import _build_context_block

    docs = [
        {
            "text": "Issue trees help structure complex problems.",
            "metadata": {
                "book_title": "McKinsey Way",
                "chapter": "Problem Structuring",
                "page_start": 22,
                "source_domain": "consulting",
            },
        }
    ]
    result = _build_context_block(docs)
    assert result.startswith("[Kerangka 1:"), f"Expected [Kerangka 1:], got: {result[:30]}"
    assert "[Sumber" not in result


def test_citations_include_source_domain():
    """build_citations includes 'source_domain' in every returned citation dict."""
    from src.generation.citation_builder import build_citations

    docs = [
        {
            "metadata": {
                "book_title": "McKinsey Way",
                "chapter": "Problem Structuring",
                "page_start": 22,
                "page_end": 25,
                "section_path": "McKinsey Way > Problem Structuring",
                "author": "Ethan Rasiel",
                "source_domain": "consulting",
            }
        }
    ]
    citations = build_citations(docs)
    assert len(citations) == 1
    assert "source_domain" in citations[0], "source_domain missing from build_citations output"
    assert citations[0]["source_domain"] == "consulting"
