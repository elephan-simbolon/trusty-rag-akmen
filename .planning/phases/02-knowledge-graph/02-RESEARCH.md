# Phase 2: Knowledge Graph - Research

**Researched:** 2026-03-22
**Domain:** LightRAG knowledge graph integration, graph-based retrieval, multi-textbook synthesis generation
**Confidence:** HIGH (LightRAG API patterns verified against PyPI 1.4.11 and GitHub source), MEDIUM (entity normalization strategies and accounting-specific extraction patterns)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INDEX-04 | Extract entities and relations into LightRAG knowledge graph via Qwen3-30B-A3B using custom prompt for accounting domain — entity types: CostType, CostingMethod, CostDriver, AccountingStandard, ManagementTechnique, Formula, etc. | LightRAG 1.4.11 supports `addon_params` for custom `entity_types`; async `ainsert` / `ainsert_batch` for ingestion; SiliconFlow custom `base_url` via `openai_complete_if_cache` |
| RETR-03 | System supports LightRAG graph query in local, naive, hybrid, and mix modes for relational and concept comparison queries | `QueryParam(mode=...)` accepts "local", "naive", "global", "hybrid", "mix"; each mode differs in graph traversal depth; `aquery` is async |
| GEN-04 | System can synthesize views from multiple textbooks for one topic — identify consensus and differences between authors, cite each source | LightRAG graph stores `source_id` per entity and relation; synthesis prompt must explicitly instruct multi-source attribution |
| GEN-05 | System can answer relational queries ("what is prerequisite of ABC costing?") using knowledge graph relationship traversal | LightRAG `local` mode returns entity neighborhood (1-2 hops); `PREREQUISITE_OF` relation type must be in custom entity_types |
| GEN-06 | System answers comparison queries ("compare absorption vs variable costing") drawing context from multiple textbooks and knowledge graph relationships | LightRAG `hybrid` or `mix` mode combines vector search + graph traversal; combined context from Qdrant (Phase 1) + LightRAG |
</phase_requirements>

---

## Summary

Phase 2 adds LightRAG as a second retrieval layer alongside the Qdrant vector store built in Phase 1. The core architectural decision — already locked — is that LightRAG uses its own built-in `nano-vectordb` (file-based JSON storage) rather than routing through Qdrant, avoiding configuration conflicts between LightRAG's internal vector operations and the project's Qdrant instance.

The work in Phase 2 splits into two independent tracks: (1) an offline ingestion script that extracts accounting entities and relations from the already-chunked Phase 1 data into a LightRAG knowledge graph via Qwen3-30B-A3B, and (2) an online retrieval integration that adds a new `graph_retrieve_node` to the existing LangGraph state machine so that relational and comparative queries draw from the knowledge graph in addition to Qdrant.

The most critical technical risk for this phase is entity deduplication: LightRAG's LLM-based extraction creates separate graph nodes for semantically identical entities appearing in different surface forms across textbooks (e.g., "ABC Costing", "Activity-Based Costing", "ABC method" all become separate nodes). A post-extraction normalization pass using the existing bilingual glossary in `config/glossary.py` is required before the graph is usable for relational queries.

**Primary recommendation:** Install `lightrag-hku==1.4.11` with a custom async embedding function wrapping the existing `embed_batch()` infrastructure; configure `addon_params` with accounting-specific entity types; run the ingestion script against the existing 5-textbook Phase 1 corpus with a 50-chunk sample audit before full ingestion; then add a `graph_retrieve_node` to the existing `build_phase1_graph()` that queries LightRAG in `local` or `hybrid` mode and merges results with Qdrant retrieval.

---

## Standard Stack

### Core (Phase 2 additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| lightrag-hku | 1.4.11 | Knowledge graph extraction + graph-based retrieval | Already locked in project spec. EMNLP2025 paper. September 2025 update specifically optimized for Qwen3-30B-A3B entity extraction. Built-in nano-vectordb avoids Qdrant configuration conflict (locked decision). |
| nest-asyncio | latest | Allow asyncio.run() inside Streamlit's existing event loop | Streamlit runs in a sync context; LightRAG's `aquery` / `ainsert` are async. `nest_asyncio.apply()` at startup avoids "Event loop is closed" errors on Windows and Streamlit. |

### Already Present (Phase 1 — reused without changes)

| Library | Version | Purpose |
|---------|---------|---------|
| langgraph | 1.1.2 | Orchestration — Phase 2 adds nodes to existing graph |
| langchain | 1.2.12 | LangChain tooling reused in graph nodes |
| qdrant-client | 1.17.1 | Primary vector store — Phase 2 queries run in parallel with graph queries |
| openai | latest | SiliconFlow client — reused for LightRAG LLM/embedding functions |
| tenacity | latest | Retry logic — applies to LightRAG API calls via SiliconFlow |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| lightrag-hku nano-vectordb | LightRAG with Qdrant backend | Qdrant backend requires `LIGHTRAG_VECTOR_STORAGE=qdrant` env configuration and creates a second Qdrant collection. Adds config complexity with no retrieval benefit at this scale. Locked decision: use nano-vectordb. |
| lightrag-hku | Microsoft GraphRAG (msft/graphrag) | GraphRAG requires GPT-4 class models for entity extraction — cost at scale is prohibitive ($100+ for full corpus). LightRAG was specifically optimized for Qwen3-30B-A3B in September 2025. |
| LightRAG entity types only | Full custom prompt rewrite | LightRAG allows `addon_params["entity_types"]` for lightweight customization without modifying source files. Full prompt rewrite via `PROMPTS` dict is possible but creates upgrade maintenance burden. |

**Installation (Phase 2 additions only):**
```bash
uv add lightrag-hku==1.4.11 nest-asyncio
```

Or with pip:
```bash
pip install lightrag-hku==1.4.11 nest-asyncio
```

**Version verification (confirmed 2026-03-22):**
- `lightrag-hku` — 1.4.11, released 2026-03-20 (PyPI verified)
- `nest-asyncio` — standard Python async utility, no version constraints

---

## Architecture Patterns

### Recommended Project Structure (additions to existing src/)

```
src/
├── agents/
│   ├── graph.py              # MODIFIED: build_phase2_graph() added
│   ├── nodes.py              # MODIFIED: graph_retrieve_node added
│   └── state.py              # MODIFIED: graph_docs field added to RAGState
├── knowledge_graph/          # NEW module
│   ├── __init__.py
│   ├── lightrag_client.py    # LightRAG initialization + async wrappers
│   ├── entity_normalizer.py  # Post-extraction entity deduplication
│   └── graph_ingestion.py    # Offline ingestion script (not part of online path)
scripts/
└── ingest_lightrag.py        # CLI script: reads Phase 1 chunks, inserts to LightRAG
```

### Pattern 1: LightRAG Initialization with SiliconFlow

LightRAG requires async initialization and must use custom async functions for LLM and embedding that point to SiliconFlow.

```python
# src/knowledge_graph/lightrag_client.py
import asyncio
import numpy as np
from functools import partial
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from config.settings import settings

LIGHTRAG_WORKING_DIR = "./lightrag_storage"

async def _llm_model_func(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """Async LLM function using SiliconFlow/Qwen3-30B-A3B via OpenAI-compatible API."""
    return await openai_complete_if_cache(
        model=settings.llm_model,  # "Qwen/Qwen3-30B-A3B-Instruct-2507"
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        base_url=settings.siliconflow_base_url,
        api_key=settings.siliconflow_api_key.get_secret_value(),
        **kwargs,
    )

async def _embedding_func(texts: list[str]) -> np.ndarray:
    """Async embedding function using SiliconFlow/Qwen3-Embedding-8B.

    NOTE: LightRAG uses embeddings for its internal nano-vectordb.
    Do NOT use the instruction prefix here — LightRAG embeds entities/relations
    as documents, not queries. Prefix is for query-time only.
    """
    return await openai_embed(
        texts=texts,
        model=settings.embedding_model,  # "Qwen/Qwen3-Embedding-8B"
        embedding_dim=settings.embedding_dimensions,  # 1024
        base_url=settings.siliconflow_base_url,
        api_key=settings.siliconflow_api_key.get_secret_value(),
    )

ACCOUNTING_ENTITY_TYPES = [
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

embedding_func = EmbeddingFunc(
    embedding_dim=settings.embedding_dimensions,  # 1024
    max_token_size=8192,
    func=_embedding_func,
)

async def build_lightrag_instance() -> LightRAG:
    """Initialize LightRAG with SiliconFlow backend and accounting entity types."""
    rag = LightRAG(
        working_dir=LIGHTRAG_WORKING_DIR,
        llm_model_func=_llm_model_func,
        embedding_func=embedding_func,
        # Concurrency: tuned for SiliconFlow 1000 RPD tier
        llm_model_max_async=4,      # Keep low — SiliconFlow rate limits
        embedding_func_max_async=8,
        # Accounting-domain configuration
        addon_params={
            "language": "English",          # Textbooks are English; entity names in English
            "entity_types": ACCOUNTING_ENTITY_TYPES,
            "insert_batch_size": 10,        # Small batches for rate limit safety
        },
    )
    await rag.initialize_storages()
    return rag
```

**Key constraints on this pattern:**
- `language` must be `"English"` — textbooks are English-language; entity extraction output in English; queries will do cross-lingual matching via embedding, not LightRAG's language parameter
- `llm_model_max_async=4` is intentionally conservative for SiliconFlow 1000 RPD limit; can be raised to 8 after confirming tier
- `EmbeddingFunc` wrapper is required — it attaches `.embedding_dim` and `.max_token_size` attributes that LightRAG reads internally
- `initialize_storages()` must be awaited before any insert or query

### Pattern 2: Offline Ingestion from Phase 1 Chunks

Phase 1 already created chunks with metadata (book_title, chapter, page_number). The ingestion script feeds those chunks to LightRAG's `ainsert` method with rate-limit-safe batching.

```python
# scripts/ingest_lightrag.py
import asyncio
import json
import logging
from pathlib import Path
from src.knowledge_graph.lightrag_client import build_lightrag_instance

logger = logging.getLogger(__name__)

async def ingest_chunks_to_lightrag(chunks_json_path: str) -> None:
    """
    Load Phase 1 chunks from JSON backup and insert into LightRAG.
    Chunks backup created by Phase 1 Plan 04 (before embedding step).

    Rate limit: SiliconFlow 1000 RPD. At ~3 LLM calls per chunk for entity
    extraction, we can process ~330 chunks/day. For 5 textbooks (~5000 chunks),
    plan for 15-20 day ingestion window OR negotiate higher tier with SiliconFlow.
    """
    rag = await build_lightrag_instance()

    chunks = json.loads(Path(chunks_json_path).read_text(encoding="utf-8"))
    logger.info(f"Loaded {len(chunks)} chunks for LightRAG ingestion")

    # Sample audit: first 50 chunks, then full run
    AUDIT_MODE = True  # Set to False for full ingestion
    target_chunks = chunks[:50] if AUDIT_MODE else chunks

    for i, chunk in enumerate(target_chunks):
        try:
            # Prepend source metadata for entity extraction context
            text_with_context = (
                f"[Source: {chunk['metadata']['book_title']}, "
                f"{chunk['metadata']['chapter']}, "
                f"page {chunk['metadata'].get('page_start', '?')}]\n\n"
                f"{chunk['text']}"
            )
            await rag.ainsert(text_with_context)

            if (i + 1) % 10 == 0:
                logger.info(f"Ingested {i + 1}/{len(target_chunks)} chunks")

        except Exception as e:
            logger.error(f"Failed to insert chunk {i}: {e}")
            # Do NOT re-raise — zombie task pollution (see Pitfall 2)
            continue

    await rag.finalize_storages()

if __name__ == "__main__":
    asyncio.run(ingest_chunks_to_lightrag("data/chunks_backup.json"))
```

### Pattern 3: Graph Retrieve Node for LangGraph

Phase 2 adds a `graph_retrieve_node` that calls LightRAG asynchronously and merges results with Qdrant results already in state.

```python
# src/agents/nodes.py (addition)
import asyncio
import nest_asyncio
from src.knowledge_graph.lightrag_client import build_lightrag_instance
from lightrag import QueryParam

nest_asyncio.apply()  # Allow asyncio.run() in Streamlit's event loop

_lightrag_instance = None

def _get_lightrag() -> "LightRAG":
    """Lazy singleton — avoid initializing at import time (heavy async startup)."""
    global _lightrag_instance
    if _lightrag_instance is None:
        _lightrag_instance = asyncio.run(build_lightrag_instance())
    return _lightrag_instance

def graph_retrieve_node(state: RAGState) -> dict:
    """
    Retrieve context from LightRAG knowledge graph.
    Mode selection based on query type:
    - Default: "hybrid" (combines graph entity matching + vector similarity)
    - For relational/prerequisite queries: "local" (1-2 hop entity traversal)
    """
    if state.get("error"):
        return {}

    query = state["query"]
    rag = _get_lightrag()

    try:
        # Determine mode from query characteristics (Phase 3 will add proper routing)
        mode = "hybrid"  # Default for Phase 2; Phase 3 adds adaptive routing

        graph_result = asyncio.run(
            rag.aquery(query, param=QueryParam(mode=mode))
        )

        # Wrap as a single "graph_doc" compatible with existing RAGState schema
        graph_docs = [{
            "text": graph_result,
            "metadata": {
                "book_title": "Knowledge Graph",
                "chapter": "Multi-source synthesis",
                "content_type": "graph_context",
                "page_start": 0,
                "page_end": 0,
                "section_path": f"LightRAG/{mode} mode",
            },
            "score": 1.0,  # Graph results are pre-synthesized — no raw score
        }]

        return {"graph_docs": graph_docs}

    except Exception as e:
        logger.error(f"Graph retrieval failed: {e}")
        return {"graph_docs": []}
```

### Pattern 4: Extended RAGState for Phase 2

Add `graph_docs` field to `RAGState` without breaking Phase 1 compatibility:

```python
# src/agents/state.py (addition)
class RAGState(TypedDict):
    """Phase 2 LangGraph state schema.
    Backward-compatible with Phase 1 — all Phase 1 fields preserved.
    """
    query: str
    expanded_query: Optional[str]
    query_embedding: Optional[list[float]]
    retrieved_docs: Optional[list[dict]]        # Qdrant hybrid search results
    graph_docs: Optional[list[dict]]            # NEW: LightRAG graph results
    reranked_docs: Optional[list[dict]]
    response: Optional[str]
    citations: Optional[list[dict]]
    error: Optional[str]
```

### Pattern 5: Post-Extraction Entity Normalization

Run after initial ingestion audit to merge duplicate entities before full corpus ingestion.

```python
# src/knowledge_graph/entity_normalizer.py
from config.glossary import GLOSSARY, GLOSSARY_REVERSE

# Canonical mapping: any variant -> canonical accounting term
ACCOUNTING_CANONICAL = {
    "ABC Costing": "Activity-Based Costing",
    "ABC method": "Activity-Based Costing",
    "ABC system": "Activity-Based Costing",
    "activity based costing": "Activity-Based Costing",
    "Variable Costing": "Variable Costing",
    "Direct Costing": "Variable Costing",  # same concept, different name
    "Marginal Costing": "Variable Costing",
    "Absorption Costing": "Absorption Costing",
    "Full Costing": "Absorption Costing",
    # Add more as discovered in 50-chunk sample audit
}

def normalize_entity_name(raw_name: str) -> str:
    """Map raw LLM-extracted entity name to canonical accounting term."""
    # Check direct mapping first
    canonical = ACCOUNTING_CANONICAL.get(raw_name)
    if canonical:
        return canonical
    # Check case-insensitive
    for variant, canon in ACCOUNTING_CANONICAL.items():
        if raw_name.lower() == variant.lower():
            return canon
    return raw_name  # No normalization needed
```

### Pattern 6: LightRAG Query Modes Routing

Different query types map to different LightRAG modes:

| Query Signal | LightRAG Mode | Rationale |
|-------------|---------------|-----------|
| "apa prerequisite..." / "apa hubungan..." / relational keywords | `local` | Direct entity neighbor traversal (1-2 hops); fast; returns specific relationships |
| "bandingkan..." / "compare..." / comparative keywords | `hybrid` | Combines vector search (finds relevant passages) + graph (finds concept relationships) |
| General accounting questions with known concepts | `hybrid` | Default for Phase 2; balanced depth/speed |
| Direct concept definition | `naive` | Basic vector search within LightRAG's chunk store (may overlap Qdrant; avoid for Phase 2) |
| Multi-textbook synthesis needed | `mix` | Integrates reranking; most comprehensive but 4-5 API calls; reserve for Phase 3 |

For Phase 2, use `"hybrid"` as the default mode and expose `"local"` for clearly relational queries (detected by keyword matching). Full adaptive routing with LLM classification is Phase 3 scope.

### Anti-Patterns to Avoid

- **Do not use `rag.insert()` (sync) in the ingestion pipeline.** LightRAG's internals are async; calling the sync wrapper creates nested event loops that fail on Windows (ProactorEventLoop) and Streamlit. Use `asyncio.run(rag.ainsert(...))` in scripts, and await in async contexts.
- **Do not initialize LightRAG at module import time.** It triggers async storage initialization synchronously, causing slow startup and "Event loop is closed" on Windows. Use lazy singleton pattern.
- **Do not route LightRAG queries through Qdrant.** LightRAG's nano-vectordb is its own vector store for entity embeddings. Mixing the two creates dimension/index conflicts. Qdrant is for chunk retrieval; LightRAG nano-vectordb is for entity matching.
- **Do not embed LightRAG-extracted entities with the instruction prefix.** The prefix `"Instruct: Retrieve English accounting textbook passages..."` is for query-time Qdrant search only. LightRAG embeds entities/relations as "documents" — no prefix.
- **Do not run LightRAG ingestion and SiliconFlow embedding simultaneously.** They compete for the same SiliconFlow RPD pool. Run graph ingestion as a separate offline job, never concurrent with Phase 1 indexing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Knowledge graph entity/relation extraction from text | Custom NLP pipeline with spaCy or regex | LightRAG 1.4.11 `ainsert` | LightRAG's LLM-based extraction with `entity_extract_max_gleaning` handles the multi-pass extraction loop, de-duplicates within a document, stores to nano-vectordb, and builds the GraphML file automatically. Custom NLP misses accounting relationship semantics. |
| Graph traversal for relational queries | Custom NetworkX traversal + LLM synthesis | LightRAG `aquery(mode="local")` | LightRAG's local mode already traverses the entity neighborhood (1-2 hops), formats the graph context, and generates a synthesized answer. Hand-rolling requires reproducing this pipeline. |
| Cross-textbook entity comparison | Multi-query + custom merge | LightRAG `aquery(mode="hybrid")` | Hybrid mode combines entity-level graph context with chunk-level vector similarity in a single call. Custom merge logic would require building the same dual-level context assembly. |
| Async-sync bridge for Streamlit + LightRAG | Custom thread pool executor | `nest_asyncio` | `nest_asyncio.apply()` patches the existing event loop to allow nested `asyncio.run()` calls. Thread pools introduce threading complexity without benefit in Streamlit's single-threaded model. |

**Key insight:** LightRAG is a complete GraphRAG engine, not just a library wrapper. Its value is in the full pipeline: extraction → storage → retrieval → synthesis. Cherry-picking individual pieces defeats the purpose.

---

## Common Pitfalls

### Pitfall 1: Entity Deduplication Failure for Accounting Term Variants

**What goes wrong:** LightRAG creates separate graph nodes for "ABC Costing", "Activity-Based Costing", "ABC method", "ABC system" — four nodes for one concept. After ingesting 5+ textbooks, 30-50% of accounting entities are duplicated. `local` mode traversal for "Activity-Based Costing" returns 0 relationships because the specific variant string used in the query doesn't match the extracted node.

**Why it happens:** LightRAG's extraction prompt does not enforce canonical naming. The LLM normalizes based on context window visibility — entities seen across different pages or books are extracted independently.

**How to avoid:** Run a 50-chunk sample ingestion first. Count entity nodes (`graph_chunk_entity_relation.graphml` can be inspected). If >200 unique nodes appear for 50 chunks (should be ~20-30 accounting concepts), entity normalization is needed. Build `ACCOUNTING_CANONICAL` mapping from the sample before proceeding to full ingestion. Set `ENTITY_TYPES` restriction to the 10 accounting types to reduce noise.

**Warning signs:** `local` mode returns empty or contradictory results for standard accounting concepts. Entity count in `vdb_entities.json` is 3-5× higher than expected core concept count.

### Pitfall 2: Zombie Task Pollution on Failed ainsert

**What goes wrong:** When `ainsert` fails mid-insertion (e.g., SiliconFlow 429), LightRAG persists a partial "document content not found" state in `kv_store_doc_status.json`. On next restart, LightRAG attempts to re-process the zombie tasks alongside new documents, causing cascading failures.

**Why it happens:** LightRAG uses a persistent document status store. Failed tasks are marked as "pending" but their content is no longer in the KV store — classic inconsistency.

**How to avoid:** Never re-raise exceptions from `ainsert` in a loop — catch and log, continue to next chunk. If a restart is needed after failures, delete the `lightrag_storage/` directory and re-ingest from the JSON chunk backup (saved in Phase 1 before embedding). This is why Phase 1 saves chunks to disk before uploading to Qdrant.

**Warning signs:** LightRAG log shows "Document content not found" on startup. Insertion appears to run but no new entities appear in the graph.

### Pitfall 3: Windows Event Loop Conflict in Streamlit

**What goes wrong:** Calling `asyncio.run(rag.aquery(...))` inside a LangGraph node that runs inside Streamlit raises `RuntimeError: This event loop is already running` on Windows (ProactorEventLoop).

**Why it happens:** Streamlit runs its own event loop internally. Calling `asyncio.run()` inside an already-running loop is invalid by default.

**How to avoid:** Call `nest_asyncio.apply()` once at app startup (before any LangGraph calls). This patches the event loop to allow nested `asyncio.run()` calls. Place this in `app/main.py` or `src/agents/nodes.py` module level.

**Warning signs:** Error appears only in Streamlit context, not when running the script directly from CLI. Error message includes "This event loop is already running."

### Pitfall 4: SiliconFlow Rate Limit During Ingestion

**What goes wrong:** LightRAG entity extraction makes approximately 2-4 LLM calls per chunk (extraction + optional gleaning pass). At SiliconFlow's default 50 RPD, this means only 12-25 chunks per day. At 1000 RPD (post-credit purchase), this is 250-500 chunks/day — still ~10-20 days for a 5-textbook corpus (~5000 chunks).

**Why it happens:** LightRAG's `entity_extract_max_gleaning` default is 1 additional pass, doubling the LLM calls. `llm_model_max_async` defaults to high concurrency, hitting rate limits immediately.

**How to avoid:** Set `llm_model_max_async=4` conservatively. Set `entity_extract_max_gleaning=0` for initial sample audit (faster, fewer API calls). Monitor SiliconFlow dashboard for 429 responses. Plan ingestion timeline: at 1000 RPD, 5 textbooks (~5000 chunks × 3 calls = 15,000 calls) takes ~15 days. Consider purchasing additional credits or requesting a temporary rate limit increase from SiliconFlow for the ingestion window.

**Warning signs:** LightRAG logs show HTTP 429 within first 5 minutes of ingestion. `asyncio.TimeoutError` in the LLM function.

### Pitfall 5: EMBEDDING_DIM Mismatch Between Phase 1 and LightRAG

**What goes wrong:** Phase 1 uses Qwen3-Embedding-8B with MRL truncation to 1024 dimensions, stored in Qdrant. LightRAG's `EmbeddingFunc` must use exactly the same model AND dimension setting. If `embedding_dim` is misconfigured in LightRAG's `EmbeddingFunc`, internal vector operations fail with dimension mismatch errors.

**Why it happens:** LightRAG stores entity embeddings in its own `vdb_entities.json` using whatever dimension the `EmbeddingFunc` returns. If the model returns 4096-dim vectors (Qwen3-Embedding-8B native) but `embedding_dim=1024` is set in `EmbeddingFunc`, the truncation must happen inside the embedding function via the `dimensions` parameter in the SiliconFlow API call, not just as a metadata attribute.

**How to avoid:** Always pass `embedding_dim=settings.embedding_dimensions` (1024) to `openai_embed()` inside the LightRAG embedding function. Verify this in the 50-chunk sample audit by checking `vdb_entities.json` — each entity's embedding should have exactly 1024 floats.

**Warning signs:** `ValueError: shapes (N,1024) and (4096,) not aligned` in LightRAG query logs. Entity embeddings in `vdb_entities.json` have length 4096 when they should be 1024.

### Pitfall 6: LightRAG Graph Context Loses Source Attribution

**What goes wrong:** LightRAG's synthesis response from `aquery` returns a free-text answer that references entities and relationships but may not clearly attribute each statement to "Horngren" vs "Garrison" vs "Hansen & Mowen". The GEN-04 requirement demands explicit per-author attribution.

**Why it happens:** LightRAG's generation prompt does not specifically instruct the LLM to attribute each factual claim to its source textbook. The `source_id` is stored in the graph per entity/relation, but may not be surfaced in the final answer without explicit prompting.

**How to avoid:** Prepend source metadata to every chunk at ingestion time (see Pattern 2: `[Source: Horngren, Cost Accounting, Chapter 5, page 168]`). This embeds source information into the entity extraction context, so LightRAG stores it as entity/relation descriptions. Additionally, extend the synthesis prompt in `generate_response()` to explicitly request multi-source attribution when `graph_docs` are present.

**Warning signs:** Graph query returns "According to accounting literature, ABC costing uses cost drivers" with no book attribution. GEN-04 acceptance test fails because no specific author is cited.

---

## Code Examples

### Verify LightRAG Storage Structure After 50-Chunk Sample Audit

```python
# Check entity count and quality after sample ingestion
import json
from pathlib import Path

storage_dir = Path("./lightrag_storage")

# Entity count
entities = json.loads((storage_dir / "vdb_entities.json").read_text())
print(f"Entity count: {len(entities.get('data', []))}")
# Expected for 50 chunks: 20-60 unique accounting concepts
# Red flag: >200 entities (deduplication needed)

# Check embedding dimension
if entities.get("data"):
    sample_emb = entities["data"][0].get("__vector__", [])
    print(f"Embedding dim: {len(sample_emb)}")
    # Must be exactly 1024

# Relationship count
graph_file = storage_dir / "graph_chunk_entity_relation.graphml"
print(f"Graph file size: {graph_file.stat().st_size} bytes")
# Red flag: graph file < 5KB after 50 chunks (extraction failed silently)
```

### Run LightRAG Query in Multiple Modes (for Success Criterion 4)

```python
import asyncio
from lightrag import QueryParam
from src.knowledge_graph.lightrag_client import build_lightrag_instance

async def test_query_modes(query: str) -> dict:
    rag = await build_lightrag_instance()
    results = {}
    for mode in ["local", "hybrid"]:
        results[mode] = await rag.aquery(query, param=QueryParam(mode=mode))
        print(f"\n=== Mode: {mode} ===\n{results[mode][:300]}...")
    await rag.finalize_storages()
    return results

asyncio.run(test_query_modes("apa hubungan variance analysis dengan standard costing?"))
```

### Extended Generator: Multi-Source Attribution

```python
# src/generation/generator.py (addition for Phase 2)
def generate_synthesis_response(
    query: str,
    vector_docs: list[dict],    # From Qdrant (Phase 1)
    graph_context: str,          # From LightRAG (Phase 2)
) -> dict:
    """
    Generate response combining vector docs (specific passages) with
    graph context (relational synthesis). Explicitly prompts for
    per-author attribution to satisfy GEN-04.
    """
    context_block = _build_context_block(vector_docs)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SYNTHESIS},  # New prompt
        {"role": "user", "content": (
            f"Konteks dari knowledge graph:\n{graph_context}\n\n"
            f"Konteks dari textbook passages:\n{context_block}\n\n"
            f"Pertanyaan: {query}\n\n"
            "Instruksi: Sebutkan secara eksplisit sumber textbook (nama pengarang) "
            "untuk setiap klaim yang berbeda antara penulis."
        )},
    ]

    response_text = generate(messages, temperature=0.3)
    citations = build_citations(vector_docs)
    return {"response": response_text, "citations": citations}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Microsoft GraphRAG (requires GPT-4 tier) | LightRAG with open-source LLMs (Qwen3-30B-A3B) | Sep 2025 (LightRAG Sep update) | LightRAG specifically optimized for Qwen3-30B-A3B entity extraction; cost reduced from $100+ to $5-15 per corpus |
| LightRAG sync insert API | LightRAG async ainsert/aquery API | LightRAG 1.0+ | All production use requires async API; sync is a thin wrapper with event loop issues on Windows |
| Single-mode RAG queries | Multi-mode: naive/local/global/hybrid/mix | LightRAG 1.0 (EMNLP2025) | Different modes expose different retrieval depths: local=entity neighborhood, hybrid=graph+vector, mix=with reranking |
| Entity types: organization/person/geo/event (generic) | Domain-specific via `addon_params["entity_types"]` | LightRAG 1.0+ (confirmed via issue #308 COMPLETED Feb 2025) | Custom entity types via `addon_params` at constructor — no source code modification needed |
| LightRAG with external Qdrant vector storage | LightRAG with built-in nano-vectordb | Project decision (pre-Phase 1) | Avoids configuration conflicts; nano-vectordb is file-based JSON, sufficient for 5-30 textbook scale |

**Deprecated/outdated for this project:**
- `rag.insert()` (sync): Use `asyncio.run(rag.ainsert(...))` in scripts; await in async functions
- Direct `PROMPTS` dict modification for entity types: Use `addon_params["entity_types"]` instead
- `rag.query()` (sync): Use `asyncio.run(rag.aquery(...))` pattern

---

## Open Questions

1. **SiliconFlow rate limit for 5-textbook ingestion**
   - What we know: 1000 RPD after credit purchase; ~15,000 LLM calls for 5 books; ~15 days ingestion time
   - What's unclear: Whether SiliconFlow grants temporary higher limits for batch ingestion jobs
   - Recommendation: Contact SiliconFlow support before starting full ingestion. Build the ingestion script with full checkpoint/resume support so it can run incrementally across days.

2. **LightRAG `language` parameter for cross-lingual queries**
   - What we know: `addon_params["language"]` controls entity extraction output language; setting "English" keeps entity names in English for consistent graph traversal
   - What's unclear: Whether setting `language="English"` causes issues when the query is in Indonesian at retrieval time
   - Recommendation: Set `language="English"` for extraction (textbooks are English). At query time, `aquery` handles Indonesian input via the shared embedding space (same Qwen3-Embedding-8B). Test explicitly with 5 Indonesian relational queries before declaring success.

3. **Entity normalization completeness**
   - What we know: Post-extraction normalization is needed; 50-chunk audit will reveal the scale of the problem
   - What's unclear: Whether the existing `config/glossary.py` (~100+ terms) covers enough accounting concept variants to be effective as a normalization source
   - Recommendation: Build the initial `ACCOUNTING_CANONICAL` mapping from the sample audit findings, not from assumptions. Expand `config/glossary.py` simultaneously with accounting term variants discovered during sample audit.

4. **LightRAG `finalize_storages()` in long-running Streamlit app**
   - What we know: `finalize_storages()` must be called for proper resource cleanup
   - What's unclear: How to handle `finalize_storages()` in a Streamlit app that runs indefinitely (no clean shutdown hook)
   - Recommendation: Use the lazy singleton pattern (never call `finalize_storages()` in a Streamlit app). For the offline ingestion script, always call it in a `try/finally` block.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already configured in pyproject.toml dev extras) |
| Config file | `pyproject.toml` (hatchling build) + `tests/conftest.py` |
| Quick run command | `pytest tests/test_knowledge_graph.py -x -q --timeout=30` |
| Full suite command | `pytest tests/ -x -q --timeout=60` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INDEX-04 | LightRAG initialized with accounting entity types | unit | `pytest tests/test_knowledge_graph.py::test_lightrag_entity_types -x` | Wave 0 |
| INDEX-04 | LightRAG ainsert processes a chunk without error | unit (mocked LLM) | `pytest tests/test_knowledge_graph.py::test_lightrag_ainsert_mock -x` | Wave 0 |
| RETR-03 | LightRAG aquery returns non-empty string for local mode | unit (mocked) | `pytest tests/test_knowledge_graph.py::test_graph_query_local -x` | Wave 0 |
| RETR-03 | LightRAG aquery returns non-empty string for hybrid mode | unit (mocked) | `pytest tests/test_knowledge_graph.py::test_graph_query_hybrid -x` | Wave 0 |
| RETR-03 | Two query modes return different context depths | integration (requires live graph) | manual / `pytest tests/test_integration_graph.py -x --live` | Wave 0 |
| GEN-04 | generate_synthesis_response produces multi-source attribution | unit | `pytest tests/test_generation.py::test_synthesis_attribution -x` | Wave 0 |
| GEN-05 | Relational query returns relationship traversal context | unit (mocked) | `pytest tests/test_knowledge_graph.py::test_relational_query -x` | Wave 0 |
| GEN-06 | Comparison query draws from both vector docs and graph context | unit | `pytest tests/test_generation.py::test_comparison_response -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_knowledge_graph.py -x -q --timeout=30`
- **Per wave merge:** `pytest tests/ -x -q --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_knowledge_graph.py` — covers INDEX-04, RETR-03, GEN-05 (unit tests with mocked LightRAG)
- [ ] `tests/test_integration_graph.py` — covers RETR-03 live mode comparison (manual-only flag)
- [ ] `src/knowledge_graph/__init__.py` — module init
- [ ] `src/knowledge_graph/lightrag_client.py` — LightRAG initialization
- [ ] `src/knowledge_graph/entity_normalizer.py` — post-extraction normalization
- [ ] `src/knowledge_graph/graph_ingestion.py` — ingestion pipeline
- [ ] `scripts/ingest_lightrag.py` — CLI ingestion script

---

## Sources

### Primary (HIGH confidence)

- PyPI `lightrag-hku` 1.4.11 — released 2026-03-20 — version and feature set verified
- GitHub HKUDS/LightRAG `lightrag/lightrag.py` — constructor parameters (`working_dir`, `addon_params`, `llm_model_max_async`, `embedding_func_max_async`, `entity_extract_max_gleaning`), `initialize_storages` and `finalize_storages` requirements
- GitHub HKUDS/LightRAG `lightrag/llm/openai.py` — `openai_complete_if_cache` and `openai_embed` function signatures with `base_url`, `api_key`, `embedding_dim` parameters
- GitHub HKUDS/LightRAG `lightrag/utils.py` — `EmbeddingFunc` wrapper with `.embedding_dim` and `.max_token_size` attributes
- Project `.planning/research/PITFALLS.md` — Phase 2 pitfalls (entity deduplication, rate limits) already researched at project start
- Project `.planning/research/STACK.md` — lightrag-hku 1.4.11 confirmed, nano-vectordb decision locked
- Project `config/settings.py` — existing settings (siliconflow_base_url, embedding_model, llm_model, embedding_dimensions=1024)
- Project `src/llm/client.py` — existing retry patterns (_RETRY_CONFIG, _UI_RETRY_CONFIG) to reuse

### Secondary (MEDIUM confidence)

- GitHub HKUDS/LightRAG issue #308 (COMPLETED Feb 2025) — custom entity types via `addon_params["entity_types"]` confirmed working
- GitHub HKUDS/LightRAG issue #1946 — EMBEDDING_DIM configuration must match actual output; Qwen3-Embedding-8B native is 4096; must pass `embedding_dim=1024` inside the embedding function to SiliconFlow API for MRL truncation
- GitHub HKUDS/LightRAG issue #1968 — zombie task pollution on failed ainsert; mitigation: catch and continue, never re-raise in ingestion loop
- GitHub HKUDS/LightRAG issue #2264 — performance tuning: `llm_model_max_async=8`, `embedding_batch_num=64`, `insert_batch_size=100` for speed; conservative settings needed for SiliconFlow rate limits
- GitHub HKUDS/LightRAG issue #209 — Windows event loop closed fix: `nest_asyncio.apply()` at startup
- WebSearch "LightRAG LangGraph async 2025" — `asyncio.run()` wrapper pattern for sync LangGraph nodes calling async LightRAG

### Tertiary (LOW confidence — flag for validation)

- LightRAG `language="English"` behavior with Indonesian queries at retrieval time — researched pattern but not explicitly tested for this combination
- SiliconFlow temporary rate limit increase for batch ingestion — referenced in project research but not independently verified as an option

---

## Metadata

**Confidence breakdown:**
- Standard stack (LightRAG 1.4.11 + nest-asyncio): HIGH — PyPI versions verified, GitHub source read
- Architecture (async patterns, LangGraph integration): HIGH — code patterns verified against LightRAG source
- Pitfalls (entity deduplication, zombie tasks, Windows asyncio): HIGH — verified against GitHub issues
- Entity types customization via addon_params: MEDIUM — issue #308 marked COMPLETED but exact API not shown in source read
- Cross-lingual (Indonesian query + English graph): MEDIUM — Qwen3-Embedding-8B multilingual is confirmed HIGH; LightRAG language parameter interaction at query time is LOW/unverified

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (LightRAG updates frequently; re-verify breaking changes before Phase 3)
