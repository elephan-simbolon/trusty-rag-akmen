"""Unit tests for Phase 08 consulting ingestion pipeline extensions (INGEST-01 VLM gate, INGEST-02 author field)."""

import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Mock helper (copied verbatim from tests/test_incremental_ingestion.py)
# ---------------------------------------------------------------------------


def _make_pipeline_mocks():
    """Return a dict of patches needed to run run_ingestion_pipeline without I/O."""
    return {
        "src.ingestion.pipeline.route_and_parse": MagicMock(
            return_value={"markdown_text": "# Chapter\nText", "parser_used": "docling"}
        ),
        "src.ingestion.pipeline.extract_and_caption_diagrams": MagicMock(return_value=[]),
        "src.ingestion.pipeline.split_by_headings": MagicMock(return_value=[]),
        "src.ingestion.pipeline.build_hierarchy": MagicMock(return_value=[]),
        "src.ingestion.pipeline.create_formula_index": MagicMock(return_value=None),
        "src.ingestion.pipeline.embed_chunks_batch": MagicMock(return_value=[]),
        "src.ingestion.pipeline.create_collection": MagicMock(),
        "src.ingestion.pipeline.upload_batch": MagicMock(return_value=0),
    }


def _make_mock_section():
    """Return a MagicMock Section with one text chunk for author/domain stamp tests."""
    section = MagicMock()
    section.breadcrumb = ["Book", "Chapter 1"]
    section.title = "Chapter 1"
    section.content = "# Chapter\n[p.1] Some text [/p.1]"
    return section


def _run_pipeline_with_chunk(tmp_path, **kwargs):
    """Helper: run run_ingestion_pipeline with one mock section flowing through Step 4."""
    from src.ingestion.pipeline import run_ingestion_pipeline

    pdf = tmp_path / "test_book.pdf"
    pdf.write_bytes(b"dummy")

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    patches = _make_pipeline_mocks()
    # Override split_by_headings to return one section so Step 4 runs
    section = _make_mock_section()
    patches["src.ingestion.pipeline.split_by_headings"] = MagicMock(return_value=[section])
    # Override split_content_by_type to return one sub-chunk
    patches["src.ingestion.pipeline.split_content_by_type"] = MagicMock(
        return_value=["[p.1] Some text [/p.1]"]
    )
    # Override classify_element (not in default mocks) — needed for Step 4
    patches["src.ingestion.pipeline.classify_element"] = MagicMock(
        return_value=MagicMock(value="narrative_text")
    )
    # enrich_metadata returns a chunk dict
    patches["src.ingestion.pipeline.enrich_metadata"] = MagicMock(
        return_value={
            "text": "[p.1] Some text [/p.1]",
            "metadata": {
                "book_title": "Test Book",
                "chapter": "Chapter 1",
                "section_path": "Book > Chapter 1",
                "content_type": "narrative_text",
                "page_start": 1,
                "page_end": 1,
            },
        }
    )

    captured_chunks = []

    original_build_hierarchy = MagicMock(return_value=[])

    def capture_hierarchy(chunks):
        captured_chunks.extend(chunks)
        return []

    patches["src.ingestion.pipeline.build_hierarchy"] = MagicMock(side_effect=capture_hierarchy)

    with ExitStack() as stack:
        stack.enter_context(
            patch("src.ingestion.pipeline.get_qdrant_client", return_value=mock_client)
        )
        stack.enter_context(patch("src.ingestion.pipeline.health_check", return_value=True))
        for target, val in patches.items():
            stack.enter_context(patch(target, val))

        run_ingestion_pipeline(
            pdf_path=str(pdf),
            output_dir=str(tmp_path / "parsed"),
            chunks_dir=str(tmp_path / "chunks"),
            book_title="Test Book",
            **kwargs,
        )

    return captured_chunks


# ===========================================================================
# INGEST-01: VLM gate tests (4 tests)
# ===========================================================================


def test_no_vlm_skips_captioning(tmp_path):
    """run_ingestion_pipeline with use_vlm=False must NOT call extract_and_caption_diagrams."""
    from src.ingestion.pipeline import run_ingestion_pipeline

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"dummy")

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    patches = _make_pipeline_mocks()
    mock_captioner = patches["src.ingestion.pipeline.extract_and_caption_diagrams"]

    with ExitStack() as stack:
        stack.enter_context(
            patch("src.ingestion.pipeline.get_qdrant_client", return_value=mock_client)
        )
        stack.enter_context(patch("src.ingestion.pipeline.health_check", return_value=True))
        for target, val in patches.items():
            stack.enter_context(patch(target, val))

        run_ingestion_pipeline(
            pdf_path=str(pdf),
            output_dir=str(tmp_path / "parsed"),
            chunks_dir=str(tmp_path / "chunks"),
            use_vlm=False,
        )

    mock_captioner.assert_not_called()


def test_vlm_enabled_by_default(tmp_path):
    """run_ingestion_pipeline without use_vlm kwarg must call extract_and_caption_diagrams."""
    from src.ingestion.pipeline import run_ingestion_pipeline

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"dummy")

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    patches = _make_pipeline_mocks()
    mock_captioner = patches["src.ingestion.pipeline.extract_and_caption_diagrams"]

    with ExitStack() as stack:
        stack.enter_context(
            patch("src.ingestion.pipeline.get_qdrant_client", return_value=mock_client)
        )
        stack.enter_context(patch("src.ingestion.pipeline.health_check", return_value=True))
        for target, val in patches.items():
            stack.enter_context(patch(target, val))

        run_ingestion_pipeline(
            pdf_path=str(pdf),
            output_dir=str(tmp_path / "parsed"),
            chunks_dir=str(tmp_path / "chunks"),
        )

    mock_captioner.assert_called_once()


def test_no_vlm_flag_exists():
    """Parsing ['dummy.pdf', '--no-vlm'] must set args.no_vlm = True."""
    import scripts.ingest as ingest_module

    parser = ingest_module.create_parser()
    args = parser.parse_args(["dummy.pdf", "--no-vlm"])
    assert args.no_vlm is True


def test_vlm_default_true():
    """Parsing ['dummy.pdf'] without --no-vlm must set args.no_vlm = False (VLM enabled)."""
    import scripts.ingest as ingest_module

    parser = ingest_module.create_parser()
    args = parser.parse_args(["dummy.pdf"])
    assert args.no_vlm is False


# ===========================================================================
# INGEST-02: Author field tests (5 tests)
# ===========================================================================


def test_pipeline_stamps_author(tmp_path):
    """run_ingestion_pipeline with author='Ethan Rasiel' must stamp author on every chunk."""
    chunks = _run_pipeline_with_chunk(tmp_path, author="Ethan Rasiel")
    assert len(chunks) >= 1, "Expected at least one chunk to flow through Step 4"
    for chunk in chunks:
        assert chunk["metadata"].get("author") == "Ethan Rasiel", (
            f"Expected author='Ethan Rasiel', got {chunk['metadata'].get('author')!r}"
        )


def test_pipeline_stamps_empty_author(tmp_path):
    """run_ingestion_pipeline without author kwarg must stamp author='' on every chunk."""
    chunks = _run_pipeline_with_chunk(tmp_path)
    assert len(chunks) >= 1, "Expected at least one chunk to flow through Step 4"
    for chunk in chunks:
        assert chunk["metadata"].get("author") == "", (
            f"Expected author='', got {chunk['metadata'].get('author')!r}"
        )


def test_author_flag_forwarded(tmp_path):
    """main() with --author 'Barbara Minto' must forward author='Barbara Minto' to run_ingestion_pipeline."""
    pdf = tmp_path / "barbara_minto.pdf"
    pdf.write_bytes(b"dummy")

    import scripts.ingest as ingest_module

    with patch.object(
        sys, "argv", ["ingest.py", str(pdf), "--author", "Barbara Minto"]
    ), patch(
        "scripts.ingest.run_ingestion_pipeline", return_value={"skipped": False}
    ) as mock_pipeline:
        ingest_module.main()

    mock_pipeline.assert_called_once()
    call_kwargs = mock_pipeline.call_args
    assert call_kwargs.kwargs.get("author") == "Barbara Minto", (
        f"Expected author='Barbara Minto', got {call_kwargs.kwargs.get('author')!r}"
    )


def test_author_default_empty():
    """Parsing ['dummy.pdf'] without --author must set args.author = ''."""
    import scripts.ingest as ingest_module

    parser = ingest_module.create_parser()
    args = parser.parse_args(["dummy.pdf"])
    assert args.author == ""


def test_consulting_chunk_has_author_and_domain(tmp_path):
    """Chunk from consulting ingestion must have author='McKinsey' and source_domain='consulting'."""
    chunks = _run_pipeline_with_chunk(
        tmp_path,
        author="McKinsey",
        source_domain="consulting",
        use_vlm=False,
    )
    assert len(chunks) >= 1, "Expected at least one chunk to flow through Step 4"
    for chunk in chunks:
        assert chunk["metadata"].get("author") == "McKinsey", (
            f"Expected author='McKinsey', got {chunk['metadata'].get('author')!r}"
        )
        assert chunk["metadata"].get("source_domain") == "consulting", (
            f"Expected source_domain='consulting', got {chunk['metadata'].get('source_domain')!r}"
        )
