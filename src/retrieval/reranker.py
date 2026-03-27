import logging
from src.llm.client import rerank as llm_rerank
from config.settings import settings

logger = logging.getLogger(__name__)


def rerank_results(
    query: str,
    search_results: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """
    Rerank search results using Qwen3-Reranker-8B via SiliconFlow.
    Takes top_k_input (20) candidates and returns top_k_output (5).

    Preserves metadata from search results through the reranking.
    """
    top_k = top_k or settings.reranker_top_k_output

    if not search_results:
        return []

    documents = [r["text"] for r in search_results]

    reranked = llm_rerank(
        query=query,
        documents=documents,
        top_k=top_k,
    )

    # Map reranked results back to original search results with metadata
    results = []
    for r in reranked:
        original_idx = r["index"]
        if original_idx < len(search_results):
            original = search_results[original_idx]
            results.append({
                **original,
                "rerank_score": r["score"],
            })

    logger.info(f"Reranked {len(search_results)} -> {len(results)} results")
    return results
