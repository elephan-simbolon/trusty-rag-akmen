"""Tests for session_id stability and Langfuse v4 metadata wiring (Phase 05.2)."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import QueryRequest
from src.monitoring.langfuse_client import get_langfuse_handler


def test_query_request_has_no_history_id():
    """QueryRequest must not have history_id field (dead weight removed)."""
    assert "history_id" not in QueryRequest.model_fields


def test_query_request_accepts_session_id():
    req = QueryRequest(question="test", session_id="abc-123")
    assert req.session_id == "abc-123"


def test_query_request_session_id_defaults_none():
    req = QueryRequest(question="test")
    assert req.session_id is None


def test_langfuse_handler_no_args_signature():
    """get_langfuse_handler() must accept zero parameters (v4 API — no session_id/user_id)."""
    sig = inspect.signature(get_langfuse_handler)
    assert len(sig.parameters) == 0, (
        f"Expected 0 params, got {len(sig.parameters)}: {list(sig.parameters.keys())}"
    )


@pytest.mark.asyncio
async def test_query_sse_uses_session_id_as_thread_id():
    """Backend must wire session_id → config[configurable][thread_id] for MemorySaver."""
    import sys

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "response": "test response",
            "citations": [],
            "query_type": "Simple",
            "crag_grade": "CORRECT",
            "error": None,
        }
    )

    sse_stub_installed = False
    if "sse_starlette" not in sys.modules:

        class _FakeEventSourceResponse:
            def __init__(self, gen, *args, **kwargs):
                self._gen = gen

            def __aiter__(self):
                return self._gen.__aiter__()

        sse_sse_stub = MagicMock()
        sse_sse_stub.EventSourceResponse = _FakeEventSourceResponse
        sse_pkg_stub = MagicMock()
        sys.modules["sse_starlette"] = sse_pkg_stub
        sys.modules["sse_starlette.sse"] = sse_sse_stub
        sse_stub_installed = True

    try:
        sys.modules.pop("backend.main", None)
        import backend.main as main_module

        with (
            patch("backend.main.get_graph", return_value=mock_graph),
            patch("backend.main.get_langfuse_handler", return_value=None),
            patch("backend.main.save_history", new_callable=AsyncMock, return_value="hist-1"),
        ):
            request = QueryRequest(question="test question", session_id="my-session-123")
            response = await main_module.query_sse(request)
            async for _ in response:
                pass

            assert mock_graph.ainvoke.called
            _, kwargs = mock_graph.ainvoke.call_args
            config = kwargs.get("config", {})
            assert config.get("configurable", {}).get("thread_id") == "my-session-123", (
                f"thread_id should be 'my-session-123', got: {config}"
            )
    finally:
        if sse_stub_installed:
            sys.modules.pop("sse_starlette", None)
            sys.modules.pop("sse_starlette.sse", None)
        sys.modules.pop("backend.main", None)


@pytest.mark.asyncio
async def test_query_sse_passes_metadata_with_langfuse_keys():
    """Backend must include langfuse_session_id in ainvoke metadata for Langfuse v4 attribution."""
    import sys

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "response": "test response",
            "citations": [],
            "query_type": "Simple",
            "crag_grade": "CORRECT",
            "error": None,
        }
    )

    sse_stub_installed = False
    if "sse_starlette" not in sys.modules:

        class _FakeEventSourceResponse:
            def __init__(self, gen, *args, **kwargs):
                self._gen = gen

            def __aiter__(self):
                return self._gen.__aiter__()

        sse_sse_stub = MagicMock()
        sse_sse_stub.EventSourceResponse = _FakeEventSourceResponse
        sse_pkg_stub = MagicMock()
        sys.modules["sse_starlette"] = sse_pkg_stub
        sys.modules["sse_starlette.sse"] = sse_sse_stub
        sse_stub_installed = True

    try:
        sys.modules.pop("backend.main", None)
        import backend.main as main_module

        with (
            patch("backend.main.get_graph", return_value=mock_graph),
            patch("backend.main.get_langfuse_handler", return_value=None),
            patch("backend.main.save_history", new_callable=AsyncMock, return_value="hist-1"),
        ):
            request = QueryRequest(question="test question", session_id="my-session-123")
            response = await main_module.query_sse(request)
            async for _ in response:
                pass

            assert mock_graph.ainvoke.called
            _, kwargs = mock_graph.ainvoke.call_args
            config = kwargs.get("config", {})
            metadata = config.get("metadata", {})
            assert "langfuse_session_id" in metadata, (
                f"'langfuse_session_id' missing from ainvoke config metadata; got: {metadata}"
            )
            assert metadata["langfuse_session_id"] == "my-session-123"
    finally:
        if sse_stub_installed:
            sys.modules.pop("sse_starlette", None)
            sys.modules.pop("sse_starlette.sse", None)
        sys.modules.pop("backend.main", None)
