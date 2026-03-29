"""fast-graphrag client with DeepSeek LLM + SiliconFlow embedding.

LLM backend: DeepSeek API (deepseek-chat / DeepSeek-V3.2) — no hard rate limit.
Falls back to SiliconFlow if DEEPSEEK_API_KEY is not set.
Embedding: SiliconFlow Qwen3-Embedding-8B (4096 dim native, 500K+ TPM separate from LLM).

Provides:
- ACCOUNTING_ENTITY_TYPES: 10 domain-specific entity categories
- DOMAIN: Natural language domain description for entity extraction guidance
- EXAMPLE_QUERIES: Sample queries to guide extraction accuracy
- build_graphrag_instance: Factory that creates and returns a configured GraphRAG instance
"""

import logging

from fast_graphrag import DefaultEmbeddingService, DefaultLLMService, EdgeUpsertPolicy_UpsertIfValidNodes, GraphRAG

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

DOMAIN = (
    "Analisis teks akuntansi biaya dan manajemen (cost & management accounting). "
    "Identifikasi konsep, metode kalkulasi, formula, standar akuntansi, "
    "dan hubungan antar konsep akuntansi. Teks menggunakan bahasa Inggris "
    "dengan istilah teknis akuntansi."
)

EXAMPLE_QUERIES = "\n".join(
    [
        "Apa itu break-even point dan bagaimana menghitungnya?",
        "Jelaskan perbedaan antara job order costing dan process costing.",
        "Bagaimana hubungan antara fixed cost dan variable cost terhadap BEP?",
        "Apa saja komponen dalam cost of goods manufactured?",
        "Jelaskan metode activity-based costing dan kapan digunakan.",
    ]
)


def build_graphrag_instance(llm_model: str | None = None) -> GraphRAG:
    """Create and return a configured fast-graphrag GraphRAG instance.

    LLM backend selection:
    - If DEEPSEEK_API_KEY is set: uses DeepSeek API (deepseek-chat, no hard rate limit)
    - If DEEPSEEK_API_KEY is empty: falls back to SiliconFlow (settings.llm_model)

    Model override: pass llm_model to override settings.graphrag_llm_model.

    Embedding: SiliconFlow Qwen3-Embedding-8B (4096 dim native output, 500K+ TPM).

    Config:
    - n_checkpoints=2: crash-safe ingestion with 2 recent checkpoints
    - entity_types: 10 domain-specific accounting entity categories
    - edge_upsert_policy: EdgeUpsertPolicy_UpsertIfValidNodes — skip LLM-based edge
      merging to prevent token overflow on large books (56K+ prompt tokens).
      Entity deduplication (node summarization) still runs normally.
    - Concurrency controlled via CONCURRENT_TASK_LIMIT env var (default: 16)
    """
    resolved_model = llm_model or settings.graphrag_llm_model
    use_deepseek = bool(settings.deepseek_api_key.get_secret_value())

    if use_deepseek:
        llm_base_url = settings.deepseek_base_url
        llm_api_key = settings.deepseek_api_key.get_secret_value()
        logger.info("GraphRAG LLM: DeepSeek (%s)", resolved_model)
    else:
        llm_base_url = settings.siliconflow_base_url
        llm_api_key = settings.siliconflow_api_key.get_secret_value()
        logger.info("GraphRAG LLM: SiliconFlow fallback (%s)", resolved_model)

    grag = GraphRAG(
        working_dir=settings.graphrag_working_dir,
        domain=DOMAIN,
        example_queries=EXAMPLE_QUERIES,
        entity_types=ACCOUNTING_ENTITY_TYPES,
        n_checkpoints=2,
        config=GraphRAG.Config(
            llm_service=DefaultLLMService(
                model=resolved_model,
                base_url=llm_base_url,
                api_key=llm_api_key,
            ),
            embedding_service=DefaultEmbeddingService(
                model=settings.embedding_model,
                base_url=settings.siliconflow_base_url,
                api_key=settings.siliconflow_api_key.get_secret_value(),
                embedding_dim=4096,
            ),
            edge_upsert_policy=EdgeUpsertPolicy_UpsertIfValidNodes(),
        ),
    )
    return grag
