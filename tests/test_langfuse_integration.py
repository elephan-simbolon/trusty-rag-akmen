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
        result = langfuse_client.get_langfuse_handler(session_id="test-session")

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

        result = langfuse_client.get_langfuse_handler(session_id="test-session")

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
        result = langfuse_client.get_langfuse_handler(session_id="test-session")

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

    # Verify defaults
    assert s.langfuse_public_key == ""
    assert s.langfuse_base_url == "https://cloud.langfuse.com"
    assert s.langfuse_enabled is True
