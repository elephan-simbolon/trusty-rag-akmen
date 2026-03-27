"""Unit tests for incremental ingestion guard (INGEST-06).

Tests:
  1. check_book_exists returns False when scroll returns empty list
  2. check_book_exists returns True when scroll returns results
  3. delete_book calls client.delete with the correct FilterSelector
  4. run_ingestion_pipeline raises ValueError when book exists and replace_existing=False
  5. run_ingestion_pipeline calls delete_book when book exists and replace_existing=True
"""
import pytest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch, call


COLLECTION = "trusty_rag_akmen"


# ---------------------------------------------------------------------------
# Tests for check_book_exists
# ---------------------------------------------------------------------------

def test_check_book_not_exists():
    """check_book_exists returns False when scroll returns empty list."""
    from src.ingestion.indexing.qdrant_uploader import check_book_exists

    client = MagicMock()
    # scroll returns (results, next_page_offset); empty results means not found
    client.scroll.return_value = ([], None)

    result = check_book_exists(client, "Unknown Book", COLLECTION)

    assert result is False
    client.scroll.assert_called_once()


def test_check_book_exists():
    """check_book_exists returns True when scroll returns at least one result."""
    from src.ingestion.indexing.qdrant_uploader import check_book_exists

    client = MagicMock()
    # scroll returns a non-empty list — book is present
    mock_point = MagicMock()
    client.scroll.return_value = ([mock_point], None)

    result = check_book_exists(client, "Cost Accounting", COLLECTION)

    assert result is True
    client.scroll.assert_called_once()


# ---------------------------------------------------------------------------
# Test for delete_book
# ---------------------------------------------------------------------------

def test_delete_book_by_filter():
    """delete_book calls client.delete with FilterSelector containing book_title match."""
    from src.ingestion.indexing.qdrant_uploader import delete_book
    from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue

    client = MagicMock()

    delete_book(client, "Cost Accounting", COLLECTION)

    client.delete.assert_called_once()
    call_kwargs = client.delete.call_args

    # Verify collection_name is correct
    assert call_kwargs.kwargs.get("collection_name") == COLLECTION or \
           call_args_positional_contains(call_kwargs, COLLECTION), \
           "delete() was not called with the expected collection_name"

    # Verify points_selector contains the expected filter structure
    points_selector = call_kwargs.kwargs.get("points_selector")
    assert points_selector is not None, "points_selector not passed to client.delete()"
    assert isinstance(points_selector, FilterSelector), \
        f"Expected FilterSelector, got {type(points_selector)}"

    # Check that the filter targets book_title field with the correct value
    filt = points_selector.filter
    assert filt is not None
    must_conditions = filt.must
    assert must_conditions and len(must_conditions) == 1
    condition = must_conditions[0]
    assert isinstance(condition, FieldCondition)
    assert condition.key == "book_title"
    assert condition.match == MatchValue(value="Cost Accounting")


def call_args_positional_contains(call_kwargs, value):
    """Helper: check if a value appears in positional args."""
    if call_kwargs.args:
        return value in call_kwargs.args
    return False


# ---------------------------------------------------------------------------
# Tests for run_ingestion_pipeline incremental guard
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


def test_pipeline_skips_when_book_exists_no_replace(tmp_path):
    """run_ingestion_pipeline returns skipped result when book already exists and replace_existing=False."""
    from src.ingestion.pipeline import run_ingestion_pipeline

    # Create a dummy PDF path so Path(pdf_path).stem works
    pdf = tmp_path / "cost_accounting.pdf"
    pdf.write_bytes(b"dummy")

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    patches = _make_pipeline_mocks()

    with ExitStack() as stack:
        stack.enter_context(patch("src.ingestion.pipeline.get_qdrant_client", return_value=mock_client))
        stack.enter_context(patch("src.ingestion.pipeline.health_check", return_value=True))
        mock_check = stack.enter_context(patch("src.ingestion.pipeline.check_book_exists", return_value=True))
        for target, val in patches.items():
            stack.enter_context(patch(target, val))

        result = run_ingestion_pipeline(
            pdf_path=str(pdf),
            output_dir=str(tmp_path / "parsed"),
            chunks_dir=str(tmp_path / "chunks"),
            book_title="Cost Accounting",
            replace_existing=False,
        )

        assert result.get("skipped") is True, "Pipeline should return skipped=True when book exists"
        mock_check.assert_called_once_with(mock_client, "Cost Accounting")


def test_pipeline_deletes_when_book_exists_with_replace(tmp_path):
    """run_ingestion_pipeline calls delete_book when book already exists and replace_existing=True."""
    from src.ingestion.pipeline import run_ingestion_pipeline

    pdf = tmp_path / "cost_accounting.pdf"
    pdf.write_bytes(b"dummy")

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    patches = _make_pipeline_mocks()

    with ExitStack() as stack:
        stack.enter_context(patch("src.ingestion.pipeline.get_qdrant_client", return_value=mock_client))
        stack.enter_context(patch("src.ingestion.pipeline.health_check", return_value=True))
        mock_check = stack.enter_context(patch("src.ingestion.pipeline.check_book_exists", return_value=True))
        mock_delete = stack.enter_context(patch("src.ingestion.pipeline.delete_book"))
        for target, val in patches.items():
            stack.enter_context(patch(target, val))

        result = run_ingestion_pipeline(
            pdf_path=str(pdf),
            output_dir=str(tmp_path / "parsed"),
            chunks_dir=str(tmp_path / "chunks"),
            book_title="Cost Accounting",
            replace_existing=True,
        )

        mock_check.assert_called_once_with(mock_client, "Cost Accounting")
        mock_delete.assert_called_once_with(mock_client, "Cost Accounting")

        # Pipeline should complete successfully (no exception)
        assert isinstance(result, dict)
