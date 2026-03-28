"""Unit tests for Langfuse observability integration.

Tests cover:
- get_langfuse_handler() returns CallbackHandler when langfuse_enabled=True
- get_langfuse_handler() returns None when langfuse_enabled=False
- get_langfuse_handler() returns None gracefully when LANGFUSE_PUBLIC_KEY is empty
- update_token_usage() calls observation.update with correct usage_details keys
- Settings class has the required Langfuse configuration fields

No live Langfuse connection required — all langfuse imports are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Test 1: Handler is created when langfuse is enabled with valid keys
# ---------------------------------------------------------------------------

def test_handler_created():
    """get_langfuse_handler() returns a CallbackHandler instance when langfuse_enabled=True
    and a non-empty public key is present."""
    mock_handler_instance = MagicMock()
    mock_callback_cls = MagicMock(return_value=mock_handler_instance)
    mock_langfuse_langchain = MagicMock()
    mock_langfuse_langchain.CallbackHandler = mock_callback_cls

    with patch("src.monitoring.langfuse_client.settings") as mock_settings, \
         patch.dict("sys.modules", {"langfuse.langchain": mock_langfuse_langchain}):
        mock_settings.langfuse_enabled = True
        mock_settings.langfuse_public_key = "pk-lf-test-key"

        from src.monitoring import langfuse_client
        result = langfuse_client.get_langfuse_handler()

    assert result is mock_handler_instance


# ---------------------------------------------------------------------------
# Test 2: Handler returns None when langfuse is disabled
# ---------------------------------------------------------------------------

def test_handler_disabled():
    """get_langfuse_handler() returns None when langfuse_enabled=False."""
    with patch("src.monitoring.langfuse_client.settings") as mock_settings:
        mock_settings.langfuse_enabled = False
        mock_settings.langfuse_public_key = "pk-lf-test-key"

        from src.monitoring import langfuse_client
        import importlib
        importlib.reload(langfuse_client)

        result = langfuse_client.get_langfuse_handler()

    assert result is None


# ---------------------------------------------------------------------------
# Test 3: Handler returns None gracefully when public key is empty
# ---------------------------------------------------------------------------

def test_handler_graceful_when_no_keys():
    """get_langfuse_handler() returns None without raising when LANGFUSE_PUBLIC_KEY is empty."""
    with patch("src.monitoring.langfuse_client.settings") as mock_settings:
        mock_settings.langfuse_enabled = True
        mock_settings.langfuse_public_key = ""  # empty key — graceful degradation

        from src.monitoring import langfuse_client
        import importlib
        importlib.reload(langfuse_client)

        # Must not raise any exception
        result = langfuse_client.get_langfuse_handler()

    assert result is None


# ---------------------------------------------------------------------------
# Test 4: update_token_usage calls observation with correct keys
# ---------------------------------------------------------------------------

def test_update_token_usage_keys():
    """update_token_usage(input_tokens=100, output_tokens=50) calls obs.update with
    usage_details containing 'input' and 'output' keys."""
    mock_obs = MagicMock()
    mock_langfuse_client = MagicMock()
    mock_langfuse_client.get_current_observation.return_value = mock_obs

    mock_langfuse_module = MagicMock()
    mock_langfuse_module.get_client.return_value = mock_langfuse_client

    with patch.dict("sys.modules", {"langfuse": mock_langfuse_module}):
        from src.monitoring import langfuse_client
        import importlib
        importlib.reload(langfuse_client)

        langfuse_client.update_token_usage(input_tokens=100, output_tokens=50)

    mock_obs.update.assert_called_once()
    call_kwargs = mock_obs.update.call_args[1]
    assert "usage_details" in call_kwargs
    usage = call_kwargs["usage_details"]
    assert "input" in usage
    assert "output" in usage
    assert usage["input"] == 100
    assert usage["output"] == 50


# ---------------------------------------------------------------------------
# Test 5: Settings class has the required Langfuse fields
# ---------------------------------------------------------------------------

def test_settings_has_langfuse_fields():
    """Settings class exposes langfuse_public_key, langfuse_secret_key,
    langfuse_base_url, and langfuse_enabled fields."""
    from config.settings import Settings

    # Instantiate with no env vars — all should have defaults
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
    )

    assert hasattr(s, "langfuse_public_key"), "Missing field: langfuse_public_key"
    assert hasattr(s, "langfuse_secret_key"), "Missing field: langfuse_secret_key"
    assert hasattr(s, "langfuse_base_url"), "Missing field: langfuse_base_url"
    assert hasattr(s, "langfuse_enabled"), "Missing field: langfuse_enabled"

    # Verify types and non-None defaults (not values — .env may override)
    assert isinstance(s.langfuse_public_key, str)
    assert s.langfuse_base_url == "https://cloud.langfuse.com"
    assert s.langfuse_enabled is True


# ---------------------------------------------------------------------------
# Test 6: query_sse passes callbacks=[handler] to graph.ainvoke() (MON-04)
# ---------------------------------------------------------------------------

def test_query_sse_passes_callbacks_to_graph_ainvoke():
    """backend/main.py query_sse must pass callbacks=[handler] inside the config
    dict to graph.ainvoke().

    MON-04: Without this wiring, Langfuse receives no traces even when a
    CallbackHandler is created. This test:
    1. Stubs out all heavy dependencies (sse_starlette, FastAPI internals, LightRAG)
       so backend.main can be imported in the test environment.
    2. Patches get_langfuse_handler to return a sentinel handler object.
    3. Patches get_graph to return a mock whose ainvoke is an AsyncMock.
    4. Drives the inner event_stream() async generator from query_sse to completion.
    5. Asserts that graph.ainvoke() was called with config["callbacks"] == [sentinel_handler].
    """
    import asyncio
    import sys
    from unittest.mock import AsyncMock, MagicMock, patch

    sentinel_handler = MagicMock(name="langfuse_handler")

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "query": "test",
        "response": "Jawaban uji.",
        "citations": [],
        "query_type": "Simple",
        "crag_grade": "CORRECT",
        "error": None,
    })

    # Stub out sse_starlette if not available, so backend.main can be imported.
    # EventSourceResponse is replaced with a simple async-iterable wrapper.
    sse_stub_installed = False
    if "sse_starlette" not in sys.modules:
        class _FakeEventSourceResponse:
            """Minimal stand-in: wraps an async generator so tests can iterate it."""
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
        # Force fresh import of backend.main (remove cached version if it exists
        # from a previous run that may have used stubs).
        sys.modules.pop("backend.main", None)

        import backend.main as main_module
        from backend.models import QueryRequest

        async def _run():
            with patch("backend.main.get_langfuse_handler", return_value=sentinel_handler) as mock_get_handler, \
                 patch("backend.main.get_graph", return_value=mock_graph), \
                 patch("backend.main.save_history", new_callable=AsyncMock, return_value="hist-001"):

                request = QueryRequest(question="Apa itu BEP?", session_id="sess-test-001")

                # query_sse returns an EventSourceResponse (or stub) wrapping an async
                # generator. Drive the generator to completion to trigger ainvoke.
                response = await main_module.query_sse(request)
                async for _ in response:
                    pass

                # get_langfuse_handler must have been called with no arguments (v4 API)
                mock_get_handler.assert_called_once_with()

                # graph.ainvoke must have been called exactly once
                mock_graph.ainvoke.assert_called_once()

                # config kwarg must contain "callbacks" key with [sentinel_handler]
                ainvoke_call = mock_graph.ainvoke.call_args
                config_passed = ainvoke_call.kwargs.get("config")
                assert config_passed is not None, (
                    "graph.ainvoke() was not called with a 'config' keyword argument"
                )
                assert "callbacks" in config_passed, (
                    f"'callbacks' key missing from ainvoke config; "
                    f"got keys: {list(config_passed.keys())}"
                )
                assert config_passed["callbacks"] == [sentinel_handler], (
                    f"Expected callbacks=[sentinel_handler], "
                    f"got: {config_passed['callbacks']}"
                )
                assert "metadata" in config_passed, (
                    f"'metadata' key missing from ainvoke config; got keys: {list(config_passed.keys())}"
                )
                assert config_passed["metadata"]["langfuse_session_id"] == "sess-test-001"
                assert config_passed["metadata"]["langfuse_user_id"] == "default"

        asyncio.run(_run())

    finally:
        # Clean up the stubs and cached module so other tests are unaffected
        if sse_stub_installed:
            sys.modules.pop("sse_starlette", None)
            sys.modules.pop("sse_starlette.sse", None)
        sys.modules.pop("backend.main", None)
