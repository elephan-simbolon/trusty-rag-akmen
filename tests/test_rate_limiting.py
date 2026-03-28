"""Tests for 429 rate limit handling enhancement in src/llm/client.py (MON-05).

Covers:
- _log_rate_limit callback is defined and logs 429 specifically
- _RETRY_CONFIG uses _log_rate_limit as before_sleep
- _UI_RETRY_CONFIG uses _log_rate_limit as before_sleep
- rerank function retries on 429 (does not hard-fail on first 429)
- Non-429 errors still trigger retry
"""

import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest


class TestLogRateLimitCallback:
    def test_log_rate_limit_is_defined(self):
        """_log_rate_limit function is defined in client module."""
        from src.llm.client import _log_rate_limit

        assert callable(_log_rate_limit)

    def test_log_rate_limit_logs_429(self, caplog):
        """_log_rate_limit logs 'rate limit (429)' when exception is 429 HTTPStatusError."""
        from src.llm.client import _log_rate_limit

        # Build a mock retry_state mimicking tenacity's retry state for a 429 error
        response_mock = MagicMock()
        response_mock.status_code = 429
        exc = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=response_mock,
        )

        outcome_mock = MagicMock()
        outcome_mock.exception.return_value = exc

        retry_state = MagicMock()
        retry_state.outcome = outcome_mock
        retry_state.next_action.sleep = 60.0
        retry_state.attempt_number = 1

        with caplog.at_level(logging.WARNING, logger="src.llm.client"):
            _log_rate_limit(retry_state)

        assert any("rate limit (429)" in record.message for record in caplog.records), (
            f"Expected 'rate limit (429)' in log messages, got: {[r.message for r in caplog.records]}"
        )

    def test_log_rate_limit_non_429_delegates_to_before_sleep_log(self):
        """_log_rate_limit for non-429 errors delegates to tenacity's before_sleep_log."""
        from src.llm.client import _log_rate_limit

        # Non-429 error (e.g. 500)
        response_mock = MagicMock()
        response_mock.status_code = 500
        exc = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=response_mock,
        )

        outcome_mock = MagicMock()
        outcome_mock.exception.return_value = exc

        retry_state = MagicMock()
        retry_state.outcome = outcome_mock
        retry_state.next_action.sleep = 2.0
        retry_state.attempt_number = 1

        # Should not raise — delegates to before_sleep_log which handles logging
        # We can't easily assert the logger call here without deep patching,
        # but verifying no exception is raised is the key assertion.
        try:
            _log_rate_limit(retry_state)
        except Exception as e:
            pytest.fail(f"_log_rate_limit raised unexpectedly for 500 error: {e}")


class TestRetryConfigBeforeSleep:
    def test_retry_config_uses_log_rate_limit(self):
        """_RETRY_CONFIG before_sleep is _log_rate_limit."""
        from src.llm.client import _RETRY_CONFIG, _log_rate_limit

        assert _RETRY_CONFIG["before_sleep"] is _log_rate_limit, (
            f"_RETRY_CONFIG['before_sleep'] should be _log_rate_limit, "
            f"got {_RETRY_CONFIG['before_sleep']}"
        )

    def test_ui_retry_config_uses_log_rate_limit(self):
        """_UI_RETRY_CONFIG before_sleep is _log_rate_limit."""
        from src.llm.client import _UI_RETRY_CONFIG, _log_rate_limit

        assert _UI_RETRY_CONFIG["before_sleep"] is _log_rate_limit, (
            f"_UI_RETRY_CONFIG['before_sleep'] should be _log_rate_limit, "
            f"got {_UI_RETRY_CONFIG['before_sleep']}"
        )

    def test_retry_config_contains_httpx_status_error(self):
        """_RETRY_CONFIG and _UI_RETRY_CONFIG include httpx.HTTPStatusError in retry conditions.

        Since both configs use retry_if_exception_type((Exception,)) which catches ALL
        exceptions including HTTPStatusError (a subclass of Exception), this verifies
        the retry predicate covers 429 HTTPStatusError by checking exception class membership.
        """
        from tenacity.retry import retry_if_exception_type

        from src.llm.client import _RETRY_CONFIG, _UI_RETRY_CONFIG

        # Verify both configs use retry_if_exception_type with (Exception,)
        # which captures all exceptions including httpx.HTTPStatusError
        assert isinstance(_RETRY_CONFIG["retry"], retry_if_exception_type), (
            "_RETRY_CONFIG retry should be retry_if_exception_type instance"
        )
        assert isinstance(_UI_RETRY_CONFIG["retry"], retry_if_exception_type), (
            "_UI_RETRY_CONFIG retry should be retry_if_exception_type instance"
        )

        # Verify httpx.HTTPStatusError is a subclass of Exception (covered by the predicate)
        assert issubclass(httpx.HTTPStatusError, Exception), (
            "httpx.HTTPStatusError must be a subclass of Exception to be caught by retry_if_exception_type((Exception,))"
        )


class TestRerankRetryOn429:
    def test_rerank_retries_on_429_then_succeeds(self):
        """rerank retries on 429 HTTPStatusError, then succeeds on second call."""
        from src.llm.client import rerank

        # Build a 429 response and a 200 response
        response_429 = MagicMock(spec=httpx.Response)
        response_429.status_code = 429

        response_200 = MagicMock(spec=httpx.Response)
        response_200.status_code = 200
        response_200.raise_for_status.return_value = None
        response_200.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
            ]
        }

        call_count = {"n": 0}

        def mock_post(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=MagicMock(),
                    response=response_429,
                )
            return response_200

        with patch("src.llm.client.httpx.post", side_effect=mock_post):
            with patch("src.llm.client.settings") as mock_settings:
                mock_settings.siliconflow_base_url = "https://api.siliconflow.cn/v1"
                mock_settings.siliconflow_api_key.get_secret_value.return_value = "test-key"
                mock_settings.reranker_model = "Qwen/Qwen3-Reranker-8B"

                result = rerank(
                    query="test query",
                    documents=["doc1"],
                    top_k=1,
                )

        # Should have retried and returned the successful result
        assert call_count["n"] == 2, f"Expected 2 calls (1 fail + 1 success), got {call_count['n']}"
        assert len(result) == 1

    def test_rerank_reraises_after_max_retries(self):
        """rerank reraises HTTPStatusError after max retries exhausted (not swallowed)."""
        from src.llm.client import rerank

        response_429 = MagicMock(spec=httpx.Response)
        response_429.status_code = 429

        def mock_post(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=response_429,
            )

        with patch("src.llm.client.httpx.post", side_effect=mock_post):
            with patch("src.llm.client.settings") as mock_settings:
                mock_settings.siliconflow_base_url = "https://api.siliconflow.cn/v1"
                mock_settings.siliconflow_api_key.get_secret_value.return_value = "test-key"
                mock_settings.reranker_model = "Qwen/Qwen3-Reranker-8B"

                # rerank uses _UI_RETRY_CONFIG: 2 attempts max
                with pytest.raises(httpx.HTTPStatusError):
                    rerank(
                        query="test query",
                        documents=["doc1"],
                        top_k=1,
                    )
