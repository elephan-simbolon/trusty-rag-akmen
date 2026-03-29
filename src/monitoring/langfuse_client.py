"""Langfuse observability integration — CallbackHandler factory dan token usage tracking."""

import logging
import os

from config.settings import settings

logger = logging.getLogger(__name__)


def get_langfuse_handler():
    """Return a new Langfuse CallbackHandler per query session, or None if disabled."""
    if not settings.langfuse_enabled or not settings.langfuse_public_key:
        return None

    try:
        # Langfuse v4 membaca credentials dari os.environ
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key.get_secret_value())
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)

        from langfuse.langchain import CallbackHandler  # type: ignore[import]

        return CallbackHandler()
    except Exception:
        logger.debug("Langfuse handler creation failed — continuing without tracing")
        return None


def update_token_usage(input_tokens: int, output_tokens: int) -> None:
    """Inject SiliconFlow token counts into the active Langfuse generation span."""
    try:
        from langfuse import get_client  # type: ignore[import]

        get_client().update_current_generation(
            usage_details={
                "input": input_tokens,
                "output": output_tokens,
            }
        )
    except Exception:
        pass
