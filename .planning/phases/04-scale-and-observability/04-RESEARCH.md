# Phase 4: Scale and Observability - Research

**Researched:** 2026-03-22
**Domain:** LLM Observability (Langfuse), Incremental Corpus Ingestion, Late Chunking, RAG Evaluation
**Confidence:** MEDIUM-HIGH (Langfuse HIGH, incremental ingestion HIGH, late chunking MEDIUM)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-06 | Incremental ingestion: add new textbook without re-ingesting existing books | Qdrant upsert is idempotent by book_title; Qdrant delete-by-filter for replacement; LightRAG ainsert() adds to existing graph without rebuild |
| CHUNK-05 | Late chunking enhancement via Qwen3-Embedding-8B API batch processing | Late chunking requires local token-level pooling — SiliconFlow API returns final pooled embeddings only; implementation must use API batch embedding with contextual window approach as pragmatic alternative |
| MON-01 | Langfuse tracing per-query: routing decision, retrieval results, CRAG grade, token usage | Langfuse CallbackHandler v4 + custom spans via `propagate_attributes()`; token usage tracked via `usage_details`; custom model pricing in Langfuse UI |
| MON-02 | Retrieval accuracy >= 85% on 20-query accounting evaluation set (human review) | Evaluation set: 20 curated queries with expected citations; human-scored binary pass/fail on citation relevance |
| MON-03 | Response time <= 10s Simple, <= 20s Complex (measured on Langfuse trace timeline) | Langfuse span duration captured automatically per node; timeline view shows per-node latency breakdown |
| MON-04 | Monthly API cost <= $35/month for 500 queries/day (measurable from Langfuse) | Langfuse custom model pricing + usage_details; SiliconFlow cost ~$0.001-0.003/query estimated |
</phase_requirements>

---

## Summary

Phase 4 has two independent workstreams: (1) Langfuse observability integration across the LangGraph pipeline, and (2) incremental corpus ingestion (Qdrant + LightRAG) that avoids full re-ingestion when a new textbook is added.

The Langfuse integration is straightforward: langfuse v4.0.1 (March 2026) provides `from langfuse.langchain import CallbackHandler` which plugs into LangGraph via `config={"callbacks": [langfuse_handler]}`. This automatically traces all LangGraph nodes. Custom per-node metadata (query_type, crag_grade, routing decision) requires wrapping graph.invoke in a `langfuse.start_as_current_observation()` context. Token usage must be manually passed via `usage_details` since SiliconFlow is not a natively supported provider. Custom model pricing can be registered in the Langfuse UI.

Incremental ingestion for Qdrant is already mostly done: `client.upsert()` is idempotent, the existing pipeline saves per-book chunk JSON backups. The work is: (a) add a `book_title` existence check via `client.scroll()` before ingestion, (b) add `client.delete()` with `FilterSelector` by `book_title` for re-ingestion of updated books, (c) extend `ingest_lightrag.py` to call `rag.ainsert()` on new-book chunks only (LightRAG does not need full rebuild — it merges nodes/edges). Late chunking (CHUNK-05) cannot be implemented via the SiliconFlow API because the API returns final pooled vectors, not token-level representations. The pragmatic implementation is contextual embedding windows: embed each chunk with a ±1 section context window prepended, which captures cross-chunk semantics at the API level.

**Primary recommendation:** Implement Langfuse integration first (MON-01, -03, -04 unblocked after this), then incremental ingestion guard (INGEST-06), then contextual embedding as the CHUNK-05 realization, then build the evaluation set (MON-02).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langfuse | 4.0.1 (March 2026) | LLM observability, tracing, token/cost tracking | Project decision (locked): MIT license, self-hostable, accounting data privacy |
| langfuse[langchain] | 4.0.1 | LangGraph callback handler | Standard integration path for LangGraph |
| qdrant-client | 1.17.1 (already pinned) | Incremental upsert, scroll, delete-by-filter | Already in stack; upsert is idempotent by point ID |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | already pinned | Test infrastructure for evaluation harness | MON-02 evaluation set test runner |
| python-dotenv | already pinned | Langfuse env vars (LANGFUSE_PUBLIC_KEY, etc.) | Required for Langfuse cloud auth |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| langfuse cloud | self-hosted Docker | Cloud is simpler for personal tool; self-hosting adds ops burden. Use cloud free tier (1M spans/month) |
| manual token counting | Langfuse auto-inference | SiliconFlow not natively supported — must pass usage_details manually for accurate cost tracking |
| true late chunking | contextual window embedding | True late chunking needs token-level pooling (not available via API). Contextual window is the API-compatible equivalent |

**Installation:**
```bash
uv add langfuse
```

**Version verification:**
```bash
# langfuse 4.0.1 confirmed via PyPI as of 2026-03-22
# qdrant-client 1.17.1 already in pyproject.toml - no change needed
```

---

## Architecture Patterns

### Recommended Project Structure additions
```
src/
├── monitoring/          # NEW: Langfuse integration
│   ├── __init__.py      # currently empty - needs langfuse_handler factory
│   └── langfuse_client.py  # CallbackHandler factory + custom span helpers
config/
└── settings.py          # add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
scripts/
└── evaluate_retrieval.py  # 20-query evaluation set runner (MON-02)
data/
└── eval/
    └── eval_queries.json   # 20 curated accounting queries + expected citations
```

### Pattern 1: Langfuse LangGraph Integration (MON-01, MON-03, MON-04)

**What:** Pass `CallbackHandler` as a LangGraph callback. Automatically traces all node executions, latencies, and LLM calls. Custom metadata (query_type, crag_grade) added via `propagate_attributes()`.

**When to use:** Every `graph.invoke()` call in Streamlit UI and CLI.

```python
# Source: https://langfuse.com/integrations/frameworks/langchain
# Source: https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4

import os
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Required env vars (add to .env):
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_BASE_URL=https://cloud.langfuse.com

def get_langfuse_handler(session_id: str, user_id: str = "consultant") -> CallbackHandler:
    """Return a configured CallbackHandler for one query session."""
    return CallbackHandler()


# In app/main.py — wrap graph.invoke with Langfuse context:
def run_query_with_tracing(graph, state: dict, thread_id: str) -> dict:
    langfuse = get_client()
    handler = get_langfuse_handler(session_id=thread_id)

    with langfuse.start_as_current_observation(name="rag-query") as span:
        span.update(
            input=state.get("query"),
            metadata={"thread_id": thread_id},
        )
        result = graph.invoke(
            state,
            config={
                "configurable": {"thread_id": thread_id},
                "callbacks": [handler],
            }
        )
        span.update(
            output=result.get("response"),
            metadata={
                "query_type": result.get("query_type"),
                "crag_grade": result.get("crag_grade"),
                "llm_call_count": result.get("llm_call_count"),
            }
        )
    return result
```

### Pattern 2: Token Usage and Cost Tracking (MON-04)

**What:** SiliconFlow is not a natively supported Langfuse model provider. Must manually inject `usage_details` from OpenAI-format responses. Custom model pricing registered once in Langfuse UI.

**When to use:** In `generate_node` and `generate_calc_node` where LLM responses include usage data.

```python
# Source: https://langfuse.com/docs/observability/features/token-and-cost-tracking

# In generate_response() — capture token usage from OpenAI response:
response = client.chat.completions.create(
    model=settings.llm_model,
    messages=messages,
    temperature=temperature,
    max_tokens=2048,
)
usage = response.usage  # input_tokens, output_tokens

# Pass to current Langfuse generation span:
langfuse = get_client()
current_obs = langfuse.get_current_observation()
if current_obs:
    current_obs.update(
        usage_details={
            "input": usage.prompt_tokens,
            "output": usage.completion_tokens,
        }
    )

# Register Qwen3-30B-A3B-Instruct pricing in Langfuse UI (one-time setup):
# Input: $0.29/1M tokens, Output: $1.00/1M tokens (SiliconFlow US pricing 2026)
# Model name pattern: "Qwen/Qwen3-30B-A3B-Instruct-2507"
```

### Pattern 3: Incremental Ingestion Guard (INGEST-06)

**What:** Before running the full 9-step ingestion pipeline for a new textbook, check if `book_title` already exists in Qdrant. If it exists and is intentional re-ingestion, delete-by-filter first. This prevents duplicate chunks.

**When to use:** In `run_ingestion_pipeline()` or as a new `check_book_exists()` utility.

```python
# Source: https://python-client.qdrant.tech/ + community discussion on delete-by-filter

from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector

def check_book_exists(client: QdrantClient, book_title: str, collection_name: str) -> bool:
    """Return True if any chunks for this book_title exist in Qdrant."""
    results, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key="book_title", match=MatchValue(value=book_title))]
        ),
        limit=1,
        with_payload=False,
        with_vectors=False,
    )
    return len(results) > 0


def delete_book(client: QdrantClient, book_title: str, collection_name: str) -> None:
    """Delete all Qdrant points for a given book_title (for re-ingestion)."""
    client.delete(
        collection_name=collection_name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="book_title", match=MatchValue(value=book_title))]
            )
        )
    )
```

LightRAG incremental ingestion uses the existing `rag.ainsert()` — LightRAG merges new nodes/edges without rebuilding:

```python
# Source: https://github.com/HKUDS/LightRAG README
# LightRAG ainsert() adds to existing graph — nodes/edges merged, no full rebuild needed.
# Only new-book chunks need to be passed. Existing book chunks are idempotent (same text
# content yields same entity extraction results).

await rag.ainsert(new_book_text_with_context)
```

### Pattern 4: CHUNK-05 Contextual Window Embedding (API-compatible Late Chunking)

**What:** True late chunking (token-level pooling after full-doc transformer pass) requires local model inference. SiliconFlow API returns final pooled embeddings only. The API-compatible approach: embed each child chunk with its parent section text prepended as a context prefix. This captures cross-chunk semantics similar to late chunking.

**When to use:** In `embed_chunks_batch()` when `use_contextual_window=True`.

```python
# Contextual window pattern — API-compatible alternative to true late chunking:
# For each child chunk, prepend the parent section text (truncated to 256 tokens).
# The embedding model sees chunk text IN context of surrounding section content.

def build_contextual_text(chunk: dict, parent_section_text: str, max_context_tokens: int = 256) -> str:
    """Prepend truncated parent-section context to child chunk text."""
    words = parent_section_text.split()
    context = " ".join(words[:max_context_tokens])
    return f"[Context: {context}]\n\n{chunk['text']}"
```

**Note:** This is distinct from true late chunking. True late chunking cannot be implemented via the SiliconFlow API because it requires access to per-token hidden states before pooling. The contextual window approach provides similar retrieval benefit (better cross-reference resolution) at modest additional token cost (~15-25%).

### Anti-Patterns to Avoid

- **Don't add Langfuse at module import time:** Initialize `CallbackHandler()` inside the query function, not at startup — avoids auth errors when env vars absent (test environments).
- **Don't skip `usage_details` on LLM calls:** Without it, Langfuse shows 0 tokens for SiliconFlow-backed calls. Cost tracking fails silently.
- **Don't re-embed all chunks for a new book:** The existing checkpoint resume in `embed_chunks_batch()` handles per-book checkpoints already. Only process the new book's chunk file.
- **Don't call `rag.initialize_storages()` twice for LightRAG incremental add:** The `_get_lightrag()` singleton in `nodes.py` already handles this. Reuse the singleton for LightRAG ingestion scripts.
- **Don't delete Qdrant collection for incremental adds:** Use `client.delete()` with `FilterSelector` per book_title, not `client.delete_collection()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM call tracing | Custom logging decorators | `langfuse.langchain.CallbackHandler` | Handles node-level spans, token counts, latency automatically |
| Cost calculation | Manually multiply tokens × price | Langfuse custom model pricing + `usage_details` | Aggregated dashboard, per-query cost breakdown built-in |
| Span nesting | Custom context managers | `langfuse.start_as_current_observation()` | Context propagation built into SDK |
| Evaluation harness | Custom eval runner | `pytest` + JSON eval set + human review script | Consistent with existing test infrastructure |
| Graph rebuild on new book | Re-index entire Qdrant collection | `check_book_exists()` + `client.delete(FilterSelector)` + `run_ingestion_pipeline()` | Upsert is idempotent; delete-by-filter is targeted |

**Key insight:** The Langfuse SDK handles all the complexity of distributed tracing, span nesting, and aggregation. The integration cost is ~50 lines of code. Building equivalent logging/cost tracking manually would require hundreds of lines and miss dashboard/alerting features.

---

## Common Pitfalls

### Pitfall 1: Langfuse v4 Breaking Change — update_trace Parameter Removed
**What goes wrong:** Code written for Langfuse v2/v3 using `CallbackHandler(update_trace=True)` raises `TypeError` in v4.
**Why it happens:** v4 migrated to an observation-centric model; trace attributes propagate via `propagate_attributes()`, not via handler params.
**How to avoid:** Use `CallbackHandler()` with no arguments. Set trace-level attributes via `langfuse.start_as_current_observation()` context manager.
**Warning signs:** `TypeError: CallbackHandler.__init__() got an unexpected keyword argument 'update_trace'`

### Pitfall 2: Langfuse Shows Zero Tokens for SiliconFlow Calls
**What goes wrong:** Langfuse dashboard shows 0 input/output tokens and $0.00 cost for all SiliconFlow API calls.
**Why it happens:** Langfuse auto-infers token counts only for natively supported providers (OpenAI, Anthropic). SiliconFlow model names (e.g., `Qwen/Qwen3-30B-A3B-Instruct-2507`) are not in Langfuse's default registry.
**How to avoid:** (1) Manually pass `usage_details={"input": n, "output": n}` from the OpenAI response object. (2) Register Qwen model pricing in Langfuse UI under Settings > Models.
**Warning signs:** All generation spans show 0 tokens; cost stays $0 even after many queries.

### Pitfall 3: Duplicate Chunks from Repeated Ingestion
**What goes wrong:** Running `ingest.py` twice on the same book doubles the chunk count in Qdrant. Retrieval returns near-duplicate passages.
**Why it happens:** Qdrant `client.upsert()` is idempotent by **point ID** (UUID). Each ingestion run generates fresh UUIDs via `uuid.uuid4()` in `qdrant_uploader.py`, so the same chunk gets two different UUIDs.
**How to avoid:** Add `check_book_exists()` before ingestion. Use `client.delete(FilterSelector)` to remove old chunks before re-running for the same book. Or generate deterministic UUIDs from `(book_title, section_path, chunk_index)`.
**Warning signs:** `client.get_collection()` shows `points_count` doubling after second ingestion run.

### Pitfall 4: LightRAG Incremental Add Triggering Full Entity Extraction
**What goes wrong:** Adding one new book re-processes all existing graph data, taking hours.
**Why it happens:** Calling `rag.ainsert()` with existing book's text re-extracts entities (idempotent graph merge, but still calls the LLM). This is expensive for large existing corpora.
**How to avoid:** Track which books have already been ingested into LightRAG (write a JSON manifest: `lightrag_storage/ingested_books.json`). Only call `rag.ainsert()` for genuinely new books.
**Warning signs:** `ingest_lightrag.py` takes hours on a 5-book corpus when only 1 new book was added.

### Pitfall 5: Langfuse Cloud Free Tier Retention Limit
**What goes wrong:** Evaluation trace data older than 14 days disappears from Langfuse Cloud free tier.
**Why it happens:** Langfuse Cloud free tier: 1M spans/month, 14-day data retention.
**How to avoid:** Export evaluation set traces via Langfuse SDK (`langfuse.fetch_traces()`) to local JSON before the 14-day window. Or upgrade to Pro ($249/month) for 1-month retention.
**Warning signs:** MON-02 evaluation traces disappear before post-analysis is complete.

### Pitfall 6: Late Chunking via SiliconFlow API Is Not Possible
**What goes wrong:** Attempting to implement true late chunking (CHUNK-05) by calling SiliconFlow `/embeddings` endpoint and expecting token-level hidden states.
**Why it happens:** Embedding APIs return final pooled embeddings (single vector per input). Token-level states are not exposed via any cloud embedding API.
**How to avoid:** Implement contextual window embedding (prepend parent section text). This is the correct interpretation of CHUNK-05 for this deployment architecture.
**Warning signs:** Searching for a `return_hidden_states=True` parameter in the SiliconFlow API — it does not exist.

### Pitfall 7: CallbackHandler Initialized Outside Request Scope
**What goes wrong:** A single `CallbackHandler` instance is shared across multiple Streamlit queries. Traces from concurrent queries bleed into the same trace.
**Why it happens:** Streamlit reruns each user interaction, so a module-level handler captures the same trace ID across reruns.
**How to avoid:** Create a new `CallbackHandler()` instance per `graph.invoke()` call, inside the request handler function.
**Warning signs:** Langfuse dashboard shows traces with unexpectedly long durations spanning multiple queries.

---

## Code Examples

### Complete Langfuse Setup for settings.py

```python
# Source: https://langfuse.com/integrations/frameworks/langchain
# Add to config/settings.py:

class Settings(BaseSettings):
    # ... existing fields ...
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True  # Set False to disable in testing
```

```bash
# Add to .env:
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

### Langfuse CallbackHandler in Streamlit UI

```python
# Source: https://langfuse.com/guides/cookbook/integration_langgraph
# In app/main.py — replace direct graph.invoke() calls:

from langfuse.langchain import CallbackHandler

def process_query(graph, query: str, thread_id: str) -> dict:
    """Run one query through the Phase 3 graph with Langfuse tracing."""
    if settings.langfuse_enabled:
        handler = CallbackHandler()
        callbacks = [handler]
    else:
        callbacks = []

    return graph.invoke(
        {"query": query, "conversation_history": []},
        config={
            "configurable": {"thread_id": thread_id},
            "callbacks": callbacks,
        },
    )
```

### Evaluation Set Structure (MON-02)

```json
// data/eval/eval_queries.json — 20 curated queries
[
  {
    "id": "EVAL-01",
    "query": "Apa itu break-even point dan bagaimana cara menghitungnya?",
    "expected_books": ["Cost Accounting"],
    "expected_chapters": ["Chapter 3", "Chapter 5"],
    "difficulty": "Simple"
  },
  {
    "id": "EVAL-02",
    "query": "Jelaskan perbedaan variable costing dan absorption costing",
    "expected_books": ["Cost Accounting", "Managerial Accounting"],
    "expected_chapters": ["Chapter 9"],
    "difficulty": "Medium"
  }
  // ... 18 more queries ...
]
```

Human review protocol: for each of the 20 queries, run the system and score each citation as PASS (cited book + chapter matches expected) or FAIL. Accuracy = PASS count / 20. Target: >= 17/20 (85%).

### LightRAG Incremental Ingestion Manifest

```python
# Source: https://github.com/HKUDS/LightRAG
# In scripts/ingest_lightrag.py — add book tracking:

import json
from pathlib import Path

MANIFEST_PATH = Path(settings.lightrag_working_dir) / "ingested_books.json"

def get_ingested_books() -> set:
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text()))
    return set()

def mark_book_ingested(book_title: str) -> None:
    books = get_ingested_books()
    books.add(book_title)
    MANIFEST_PATH.write_text(json.dumps(sorted(books), ensure_ascii=False))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangSmith (LangChain default) | Langfuse (MIT, self-hostable) | Project decision pre-Phase 1 | Privacy-safe for accounting data; no vendor lock-in |
| Langfuse v2/v3 | Langfuse v4 (March 2026) | March 2026 | `update_trace` param removed; `propagate_attributes()` is new pattern |
| Full collection re-creation for schema change | `FilterSelector` delete + upsert | Qdrant v1.9+ | Targeted book replacement without downtime |
| True late chunking (local model) | Contextual window embedding (API) | Always has been — API constraint | 15-25% more tokens per embedding call; similar retrieval benefit |
| Manual token logging | Langfuse `usage_details` + custom model pricing | Langfuse v3+ | Automated cost dashboard, no manual calculation |

**Deprecated/outdated:**
- `CallbackHandler(update_trace=True)`: Removed in Langfuse v4. Use `start_as_current_observation()` instead.
- `langfuse.langchain.CallbackHandler` from v2 with positional args: Now keyword-only in v4.

---

## Open Questions

1. **Should CHUNK-05 use contextual window or be deprioritized?**
   - What we know: True late chunking is impossible via SiliconFlow API. Contextual window embedding adds ~15-25% token cost per chunk re-embedding. Current corpus is ~5 books; re-embedding 5 books is feasible.
   - What's unclear: Whether the retrieval improvement justifies the re-embedding cost given the corpus is already small and cross-lingual retrieval is already strong.
   - Recommendation: Implement contextual window as optional enhancement (flag in `embed_chunks_batch`). Run retrieval evaluation (MON-02) first with and without to measure actual improvement.

2. **Langfuse cloud vs self-hosted?**
   - What we know: Cloud free tier = 1M spans/month, 14-day retention. For 500 queries/day × 8 spans/query = 4M spans/month. Free tier may be insufficient.
   - What's unclear: Actual span count per query with LangGraph node tracing.
   - Recommendation: Start with cloud free tier and monitor span count. If > 1M/month, consider Hobby tier ($59/month) or self-hosted Docker Compose on local machine.

3. **Deterministic vs random UUIDs for Qdrant point IDs?**
   - What we know: Current code uses `uuid.uuid4()` (random) — causes duplicate chunks on repeated ingestion.
   - What's unclear: Whether switching to deterministic UUIDs (based on book_title + chunk_index) could break any existing data.
   - Recommendation: Implement `check_book_exists()` + `delete(FilterSelector)` guard as the safe path. Avoid UUID changes that would invalidate existing points.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured in pytest.ini) |
| Config file | `pytest.ini` — `addopts = --timeout=30 -q` |
| Quick run command | `uv run pytest tests/test_langfuse_integration.py tests/test_incremental_ingestion.py -x` |
| Full suite command | `uv run pytest -m "not integration and not gpu"` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-06 | `check_book_exists()` returns False for unknown book | unit | `uv run pytest tests/test_incremental_ingestion.py::test_check_book_not_exists -x` | Wave 0 |
| INGEST-06 | `check_book_exists()` returns True for ingested book | unit | `uv run pytest tests/test_incremental_ingestion.py::test_check_book_exists -x` | Wave 0 |
| INGEST-06 | `delete_book()` removes chunks by book_title filter | unit (mock) | `uv run pytest tests/test_incremental_ingestion.py::test_delete_book_by_filter -x` | Wave 0 |
| INGEST-06 | Full pipeline skips re-embedding when book already indexed | integration | `uv run pytest tests/test_incremental_ingestion.py -m integration` | Wave 0 |
| CHUNK-05 | `build_contextual_text()` prepends truncated parent context | unit | `uv run pytest tests/test_contextual_embedding.py::test_contextual_text_prepend -x` | Wave 0 |
| CHUNK-05 | Contextual text does not exceed embedding model token limit | unit | `uv run pytest tests/test_contextual_embedding.py::test_contextual_text_length -x` | Wave 0 |
| MON-01 | `get_langfuse_handler()` returns CallbackHandler when env vars set | unit | `uv run pytest tests/test_langfuse_integration.py::test_handler_created -x` | Wave 0 |
| MON-01 | `graph.invoke()` with handler does not raise without live Langfuse | unit (mock) | `uv run pytest tests/test_langfuse_integration.py::test_handler_graceful_when_disabled -x` | Wave 0 |
| MON-02 | Evaluation runner loads 20-query JSON, executes queries, outputs scores | integration | `uv run pytest tests/test_evaluation_set.py -m integration` | Wave 0 |
| MON-03 | Span latency assertions — integration test only (live graph + clock) | integration | `uv run pytest tests/test_evaluation_set.py::test_simple_query_latency -m integration` | Wave 0 |
| MON-04 | `usage_details` dict contains `input` and `output` keys | unit | `uv run pytest tests/test_langfuse_integration.py::test_usage_details_keys -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_langfuse_integration.py tests/test_incremental_ingestion.py tests/test_contextual_embedding.py -x`
- **Per wave merge:** `uv run pytest -m "not integration and not gpu"`
- **Phase gate:** Full suite green (including integration where live services available) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_langfuse_integration.py` — covers MON-01, MON-04
- [ ] `tests/test_incremental_ingestion.py` — covers INGEST-06
- [ ] `tests/test_contextual_embedding.py` — covers CHUNK-05
- [ ] `tests/test_evaluation_set.py` — covers MON-02, MON-03 (integration marker)
- [ ] `data/eval/eval_queries.json` — 20-query evaluation set (created in Wave 0 or Plan 1)

---

## Sources

### Primary (HIGH confidence)
- `https://langfuse.com/integrations/frameworks/langchain` — LangGraph CallbackHandler integration pattern
- `https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4` — v4 breaking changes, `update_trace` removal
- `https://langfuse.com/docs/observability/features/token-and-cost-tracking` — `usage_details` API, custom model pricing
- `https://langfuse.com/guides/cookbook/integration_langgraph` — Complete LangGraph integration cookbook
- `https://pypi.org/project/langfuse/` — Version 4.0.1 confirmed, March 19 2026
- `https://python-client.qdrant.tech/qdrant_client.qdrant_client` — `scroll()`, `delete()` with FilterSelector API
- `https://github.com/HKUDS/LightRAG` — `ainsert()` incremental add, node/edge merge behavior

### Secondary (MEDIUM confidence)
- `https://jina.ai/news/late-chunking-in-long-context-embedding-models/` — Late chunking technique; confirmed API-only limitation (Jina-specific, extended to SiliconFlow by architecture reasoning)
- `https://www.siliconflow.com/models/qwen-qwen3-30b-a3b` — Qwen3-30B-A3B pricing ~$0.29/1M input, $1.00/1M output (scraped data, Framer-rendered page partially inaccessible)
- `https://github.com/langfuse/langfuse/issues/7323` — Breaking change: CallbackHandler import path for v3+

### Tertiary (LOW confidence)
- SiliconFlow pricing for Qwen3-Embedding-8B and Qwen3-Reranker-8B — exact figures not confirmed (Framer-rendered pages not parseable). Reranker-8B ~$0.04/1M tokens from search snippet.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Langfuse 4.0.1 version confirmed via PyPI; qdrant-client already pinned at 1.17.1 with known-good API
- Architecture (Langfuse integration): HIGH — Official docs verified, v4 breaking changes confirmed
- Architecture (incremental ingestion): HIGH — Qdrant scroll/delete-by-filter API is stable; LightRAG ainsert() incremental behavior documented in official README
- Architecture (CHUNK-05 late chunking): MEDIUM — SiliconFlow API limitation is architectural reasoning, not official documentation; contextual window pattern is pragmatic interpretation
- Pitfalls: HIGH for Langfuse v4 pitfalls (confirmed from migration guide); MEDIUM for LightRAG ingestion manifest pattern (inferred from architecture)

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (90 days — Langfuse is actively developed but v4 API is stable; Qdrant client is pinned)
