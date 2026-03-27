"""Unit tests for contextual window embedding (CHUNK-05).

Tests for build_contextual_text() and use_contextual_window support in embed_chunks_batch().
Contextual window is an API-compatible alternative to true late chunking: each child chunk
is embedded with its parent section text prepended as context.
"""
import pytest
from unittest.mock import patch, MagicMock


# --- Tests for build_contextual_text ---

def test_contextual_text_prepend():
    """build_contextual_text returns string starting with '[Context: ...' and containing chunk text."""
    from src.ingestion.indexing.embedder import build_contextual_text

    chunk_text = "BEP formula..."
    parent_text = "Chapter 5 covers break-even analysis and cost-volume-profit relationships."
    result = build_contextual_text(chunk_text=chunk_text, parent_text=parent_text)

    assert result.startswith("[Context: Chapter 5 covers break-even")
    assert "BEP formula..." in result


def test_contextual_text_length():
    """build_contextual_text with 1000-word parent and max_context_words=256 truncates to at most 256 words."""
    from src.ingestion.indexing.embedder import build_contextual_text

    # Create a 1000-word parent text
    parent_text = " ".join([f"word{i}" for i in range(1000)])
    chunk_text = "The actual chunk content."
    result = build_contextual_text(chunk_text=chunk_text, parent_text=parent_text, max_context_words=256)

    # Extract the context part between "[Context: " and "]\n\n"
    context_start = len("[Context: ")
    context_end = result.index("]\n\n")
    context_words = result[context_start:context_end].split()
    assert len(context_words) <= 256


def test_contextual_text_empty_parent():
    """build_contextual_text with empty parent_text returns chunk_text unchanged."""
    from src.ingestion.indexing.embedder import build_contextual_text

    chunk_text = "The actual chunk content."
    result = build_contextual_text(chunk_text=chunk_text, parent_text="")

    assert result == chunk_text
    assert "[Context:" not in result


def test_contextual_text_whitespace_only_parent():
    """build_contextual_text with whitespace-only parent_text returns chunk_text unchanged."""
    from src.ingestion.indexing.embedder import build_contextual_text

    chunk_text = "The actual chunk content."
    result = build_contextual_text(chunk_text=chunk_text, parent_text="   \n  ")

    assert result == chunk_text
    assert "[Context:" not in result


# --- Tests for embed_chunks_batch with contextual window ---

def test_embed_chunks_batch_default_no_contextual():
    """embed_chunks_batch with use_contextual_window=False passes raw chunk texts to embed_batch."""
    from src.ingestion.indexing.embedder import embed_chunks_batch

    chunks = [
        {
            "text": "Break-even point formula...",
            "metadata": {
                "section_path": "Chapter 5 > BEP",
                "content_type": "formula",
            },
        },
        {
            "text": "Variable cost per unit is 20.",
            "metadata": {
                "section_path": "Chapter 5 > BEP",
                "content_type": "narrative_text",
            },
        },
    ]
    parent_texts = {"Chapter 5 > BEP": "Chapter 5 covers cost-volume-profit analysis."}

    captured_texts = []

    def mock_embed_batch(texts, is_query=False):
        captured_texts.extend(texts)
        return [[0.1] * 1024 for _ in texts]

    with patch("src.ingestion.indexing.embedder.embed_batch", side_effect=mock_embed_batch):
        result = embed_chunks_batch(
            chunks,
            use_contextual_window=False,
            parent_texts=parent_texts,
        )

    # Default behavior: raw texts passed without context prefix
    assert captured_texts[0] == "Break-even point formula..."
    assert captured_texts[1] == "Variable cost per unit is 20."
    assert "[Context:" not in captured_texts[0]
    assert result == 2
    assert "embedding" in chunks[0]


def test_embed_chunks_batch_contextual_window():
    """embed_chunks_batch with use_contextual_window=True passes contextual-prefixed texts to embed_batch."""
    from src.ingestion.indexing.embedder import embed_chunks_batch

    chunks = [
        {
            "text": "Break-even point formula...",
            "metadata": {
                "section_path": "Chapter 5 > BEP",
                "content_type": "formula",
            },
        },
        {
            "text": "Variable cost per unit is 20.",
            "metadata": {
                "section_path": "Chapter 5 > BEP",
                "content_type": "narrative_text",
            },
        },
    ]
    parent_texts = {"Chapter 5 > BEP": "Chapter 5 covers cost-volume-profit analysis and break-even relationships."}

    captured_texts = []

    def mock_embed_batch(texts, is_query=False):
        captured_texts.extend(texts)
        return [[0.1] * 1024 for _ in texts]

    with patch("src.ingestion.indexing.embedder.embed_batch", side_effect=mock_embed_batch):
        result = embed_chunks_batch(
            chunks,
            use_contextual_window=True,
            parent_texts=parent_texts,
        )

    # Contextual mode: texts are prefixed with parent context
    assert "[Context:" in captured_texts[0]
    assert "Break-even point formula..." in captured_texts[0]
    assert "[Context:" in captured_texts[1]
    assert "Variable cost per unit is 20." in captured_texts[1]
    assert result == 2
    assert "embedding" in chunks[0]


def test_embed_chunks_batch_contextual_missing_section():
    """embed_chunks_batch with use_contextual_window=True and missing section_path falls back to raw text."""
    from src.ingestion.indexing.embedder import embed_chunks_batch

    chunks = [
        {
            "text": "Some chunk without matching section path.",
            "metadata": {
                "section_path": "Chapter X > Unknown",
                "content_type": "narrative_text",
            },
        },
    ]
    # parent_texts has no entry for the chunk's section_path
    parent_texts = {"Chapter 5 > BEP": "Chapter 5 covers cost-volume-profit analysis."}

    captured_texts = []

    def mock_embed_batch(texts, is_query=False):
        captured_texts.extend(texts)
        return [[0.1] * 1024 for _ in texts]

    with patch("src.ingestion.indexing.embedder.embed_batch", side_effect=mock_embed_batch):
        result = embed_chunks_batch(
            chunks,
            use_contextual_window=True,
            parent_texts=parent_texts,
        )

    # No matching parent -> falls back to raw text (build_contextual_text with "" returns chunk_text)
    assert captured_texts[0] == "Some chunk without matching section path."
    assert "[Context:" not in captured_texts[0]
