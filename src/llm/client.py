"""SiliconFlow OpenAI-compatible client for embeddings, generation, and reranking.

Dua retry strategy:
- _RETRY_CONFIG (5 attempts, 60-300s backoff): untuk batch ingestion (embed_document,
  embed_batch, rerank) — SiliconFlow rate limits nyata pada batch jobs.
- _UI_RETRY_CONFIG (2 attempts, 2-10s backoff): untuk fungsi UI-facing (embed_query,
  generate) — Streamlit single-threaded, freeze > 30s tidak dapat diterima.

Key asymmetry:
- embed_query: ALWAYS prepends instruction prefix (improves recall 1-5%)
- embed_document: NO prefix (documents are indexed as-is)
"""

import logging

import httpx
from openai import OpenAI
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings

logger = logging.getLogger(__name__)


def _log_rate_limit(retry_state) -> None:
    """Log 429 rate limit events specifically for MON-05 monitoring.

    When SiliconFlow returns HTTP 429 (Too Many Requests), log a targeted
    warning with retry timing. For all other exceptions, delegate to
    tenacity's standard before_sleep_log handler.
    """
    exc = retry_state.outcome.exception()
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        logger.warning(
            "SiliconFlow rate limit (429) hit — retrying in %.1fs (attempt %d)",
            retry_state.next_action.sleep,
            retry_state.attempt_number,
        )
    else:
        before_sleep_log(logger, logging.WARNING)(retry_state)


# Shared retry configuration for all SiliconFlow API calls
_RETRY_CONFIG = dict(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=60, max=300),
    before_sleep=_log_rate_limit,
    reraise=True,
)

# Fast-fail retry untuk fungsi yang dipanggil dari Streamlit UI (single-threaded).
# Streamlit memblokir seluruh UI thread selama tenacity menunggu — config ini
# memastikan error di-reraise dalam waktu di bawah 30 detik (2 x 10s max).
# Gunakan pada embed_query dan generate saja.
# Fungsi batch (embed_batch, embed_document) tetap pakai _RETRY_CONFIG karena
# SiliconFlow rate limiting nyata pada batch ingestion jobs.
_UI_RETRY_CONFIG = dict(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=_log_rate_limit,
    reraise=True,
)


def get_openai_client() -> OpenAI:
    """Return a configured OpenAI client pointed at SiliconFlow."""
    return OpenAI(
        api_key=settings.siliconflow_api_key.get_secret_value(),
        base_url=settings.siliconflow_base_url,
    )


@retry(**_RETRY_CONFIG)
def embed_document(text: str) -> list[float]:
    """Embed a document chunk — NO instruction prefix.

    Documents are indexed as-is. The asymmetric prefix strategy
    (query has prefix, document does not) is required for correct
    Qwen3-Embedding-8B cross-lingual retrieval.
    """
    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


@retry(**_UI_RETRY_CONFIG)
def embed_query(query: str) -> list[float]:
    """Embed a search query — ALWAYS with instruction prefix.

    The instruction prefix is critical: without it, Qwen3-Embedding-8B
    loses 1-5% recall on cross-lingual (Indonesian -> English) retrieval.
    """
    client = get_openai_client()
    prefixed = settings.embedding_query_instruction + query
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=prefixed,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


@retry(**_RETRY_CONFIG)
def embed_batch(texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Embed a batch of texts.

    Args:
        texts: List of strings to embed.
        is_query: If True, prepend instruction prefix to each text (query path).
                  If False, embed as-is (document path).

    Returns:
        List of embedding vectors, one per input text.
    """
    client = get_openai_client()
    if is_query:
        texts = [settings.embedding_query_instruction + t for t in texts]
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


@retry(**_UI_RETRY_CONFIG)
def generate(
    messages: list[dict], temperature: float = 0.3, return_usage: bool = False
) -> "str | dict":
    """Generate a response using the configured LLM.

    Args:
        messages: OpenAI-format message list (role + content dicts).
        temperature: Sampling temperature. Default 0.3 for factual accounting responses.
        return_usage: If True, return dict with 'text' and 'usage' keys instead of str.
                      Usage dict has 'prompt_tokens' and 'completion_tokens'.

    Returns:
        Generated text content (str), or dict with 'text' and 'usage' if return_usage=True.
        The tenacity _UI_RETRY_CONFIG retry wrapper is preserved for both return paths.
    """
    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
    )
    text = response.choices[0].message.content
    if return_usage and response.usage:
        return {
            "text": text,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        }
    return text


@retry(**_UI_RETRY_CONFIG)
def rerank(query: str, documents: list[str], top_k: int = 5) -> list[dict]:
    """Rerank documents against a query using Qwen3-Reranker-8B via SiliconFlow.

    Uses the SiliconFlow /rerank endpoint (not the OpenAI client, which
    lacks a rerank method). Returns results sorted by relevance score descending.

    Args:
        query: The search query (Indonesian or English).
        documents: Candidate document texts to rerank.
        top_k: Number of top results to return.

    Returns:
        List of dicts with keys: index, score, text — sorted by score descending.
    """
    response = httpx.post(
        f"{settings.siliconflow_base_url}/rerank",
        headers={"Authorization": f"Bearer {settings.siliconflow_api_key.get_secret_value()}"},
        json={
            "model": settings.reranker_model,
            "query": query,
            "documents": documents,
            "top_n": top_k,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    results = response.json()["results"]
    return [
        {
            "index": r["index"],
            "score": r["relevance_score"],
            "text": documents[r["index"]],
        }
        for r in sorted(results, key=lambda x: x["relevance_score"], reverse=True)
    ]
