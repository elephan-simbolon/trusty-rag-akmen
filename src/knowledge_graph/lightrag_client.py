"""LightRAG client with DeepSeek LLM + SiliconFlow embedding.

LLM backend: DeepSeek API (deepseek-chat / DeepSeek-V3.2) — no hard rate limit.
Falls back to SiliconFlow if DEEPSEEK_API_KEY is not set.
Embedding: SiliconFlow Qwen3-Embedding-8B (1024 dim, 500K+ TPM separate from LLM).

Provides:
- ACCOUNTING_ENTITY_TYPES: 10 domain-specific entity categories
- embedding_func: Embedding function for LightRAG (Qwen3-Embedding-8B, 1024 dim)
- build_lightrag_instance: Factory that initializes and returns a ready LightRAG instance
"""
import logging

import numpy as np
from lightrag import LightRAG, QueryParam  # noqa: F401 — re-exported for callers
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import wrap_embedding_func_with_attrs

from config.settings import settings

logger = logging.getLogger(__name__)

ACCOUNTING_ENTITY_TYPES: list[str] = [
    "CostType",
    "CostingMethod",
    "CostAllocationMethod",
    "CostDriver",
    "AccountingStandard",
    "ManagementTechnique",
    "Formula",
    "FinancialStatement",
    "DecisionType",
    "Concept",
]


@wrap_embedding_func_with_attrs(
    embedding_dim=settings.embedding_dimensions,
    max_token_size=8192,
    model_name=settings.embedding_model,
)
async def embedding_func(texts: list[str]) -> np.ndarray:
    """Qwen3-Embedding-8B via SiliconFlow; 1024 dim, 500K+ TPM (separate from LLM rate limit)."""
    return await openai_embed.func(
        texts=texts,
        model=settings.embedding_model,
        embedding_dim=settings.embedding_dimensions,
        base_url=settings.siliconflow_base_url,
        api_key=settings.siliconflow_api_key.get_secret_value(),
    )


async def build_lightrag_instance(llm_model: str | None = None) -> LightRAG:
    """Initialize and return a ready LightRAG instance.

    LLM backend selection:
    - If DEEPSEEK_API_KEY is set: uses DeepSeek API (deepseek-chat, no hard rate limit)
    - If DEEPSEEK_API_KEY is empty: falls back to SiliconFlow (settings.llm_model)

    Model override: pass llm_model to override settings.lightrag_llm_model.

    Embedding: SiliconFlow Qwen3-Embedding-8B (1024 dim, 500K+ TPM).
    Embedding rate limit is separate from LLM rate limit on SiliconFlow.

    Config:
    - llm_model_max_async=16: supports high concurrency on DeepSeek (no rate limit)
    - max_parallel_insert=4: controls concurrent document processing (recommended: max_async/4)
    - entity_extract_max_gleaning=0: eliminates second gleaning LLM call per chunk
    - Built-in nano-vectordb (file-based) instead of Qdrant — locked decision
    """
    resolved_model = llm_model or settings.lightrag_llm_model
    use_deepseek = bool(settings.deepseek_api_key.get_secret_value())

    if use_deepseek:
        llm_base_url = settings.deepseek_base_url
        llm_api_key = settings.deepseek_api_key.get_secret_value()
        logger.info(f"LightRAG LLM: DeepSeek ({resolved_model})")
    else:
        llm_base_url = settings.siliconflow_base_url
        llm_api_key = settings.siliconflow_api_key.get_secret_value()
        logger.info(f"LightRAG LLM: SiliconFlow fallback ({resolved_model})")

    async def _llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list = [],
        keyword_extraction: bool = False,
        **kwargs,
    ) -> str:
        kwargs.pop("response_format", None)  # safety net
        return await openai_complete_if_cache(
            model=resolved_model,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            base_url=llm_base_url,
            api_key=llm_api_key,
            keyword_extraction=False,  # DeepSeek tidak mendukung structured output
            **kwargs,
        )

    rag = LightRAG(
        working_dir=settings.lightrag_working_dir,
        llm_model_func=_llm_model_func,
        embedding_func=embedding_func,
        llm_model_max_async=16,
        embedding_func_max_async=8,
        max_parallel_insert=4,
        entity_extract_max_gleaning=0,
        addon_params={
            "language": "English",
            "entity_types": ACCOUNTING_ENTITY_TYPES,
        },
    )
    return rag
