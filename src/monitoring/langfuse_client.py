"""Langfuse observability integration for Trusty RAG Akmen.

Provides:
- get_langfuse_handler(): CallbackHandler factory for LangGraph tracing (MON-01, MON-03)
- update_token_usage(): Token usage injection for cost tracking (MON-04)

Design decisions:
- Lazy imports (langfuse imported inside function body) — avoids authentication errors
  when env vars are absent in test environments (see Anti-Pattern in RESEARCH.md).
- New CallbackHandler() instance per call — prevents trace bleed between Streamlit reruns
  (Pitfall 7 in RESEARCH.md).
- Graceful degradation when LANGFUSE_PUBLIC_KEY is empty or langfuse_enabled=False:
  returns None without raising so the system operates normally.
"""
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


def get_langfuse_handler():
    """Return a Langfuse CallbackHandler for one query session, or None if disabled.

    Creates a new CallbackHandler instance per call (not a module-level singleton)
    to prevent trace bleed between query sessions (Pitfall 7).

    Session and user attribution are passed via metadata in graph.ainvoke() config
    (Langfuse v4 pattern: metadata["langfuse_session_id"] / metadata["langfuse_user_id"]),
    not via CallbackHandler constructor args.

    Returns:
        CallbackHandler instance if Langfuse is enabled and keys are present.
        None if disabled or public key is empty (graceful degradation).
    """
    if not settings.langfuse_enabled:
        return None

    if not settings.langfuse_public_key:
        return None

    try:
        # Lazy import — avoids auth errors when env vars absent in test environments
        from langfuse.langchain import CallbackHandler  # type: ignore[import]
        return CallbackHandler()
    except Exception:
        logger.debug("Langfuse handler creation failed — continuing without tracing")
        return None


def update_token_usage(input_tokens: int, output_tokens: int) -> None:
    """Update the current Langfuse observation with token usage details.

    Injects usage_details into the active Langfuse span so that SiliconFlow
    token counts are recorded for cost tracking (MON-04). SiliconFlow is not
    a natively supported Langfuse provider, so usage_details must be passed
    manually (Pitfall 2 in RESEARCH.md).

    Args:
        input_tokens: Number of prompt/input tokens from the LLM response.
        output_tokens: Number of completion/output tokens from the LLM response.

    Note:
        Silently no-ops when no active Langfuse observation is present
        (e.g., when Langfuse is disabled or keys are absent).
    """
    try:
        # Lazy import — avoids auth errors when env vars absent in test environments
        from langfuse import get_client  # type: ignore[import]
        langfuse = get_client()
        obs = langfuse.get_current_observation()
        if obs is not None:
            obs.update(
                usage_details={
                    "input": input_tokens,
                    "output": output_tokens,
                }
            )
    except Exception:
        pass  # Token usage tracking is best-effort; never block the query pipeline
