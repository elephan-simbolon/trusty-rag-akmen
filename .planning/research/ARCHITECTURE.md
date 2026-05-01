# Architecture: KPE Integration with Existing LangGraph Pipeline

**Domain:** Knowledge Protocol Engineering (KPE) integration into Trusty RAG Akmen v1.1
**Researched:** 2026-03-29
**Confidence:** HIGH (integration points sourced directly from production code)

---

## Existing Architecture — Verified State

This document is based on direct code inspection of the v1.0 codebase, not documentation alone. All integration point analysis reflects actual code in the repository.

### Current LangGraph Graph (Phase 3)

```
Entry
  │
  ▼
route_node          ← is_calculation_query() + hardcoded Simple default
  │
  ▼
preprocess_node     ← glossary expansion + embed_query()
  │
  ▼
retrieve_node       ← hybrid_search(query_embedding, query_text, top_k)
  │                    NO domain_filter param currently
  ▼
graph_retrieve_node ← fast-graphrag (accounting textbook KG)
  │
  ▼
rerank_node         ← Qwen3-Reranker-8B
  │
  ▼
crag_grade_node     ← threshold: ≥0.5→CORRECT, ≥0.2→AMBIGUOUS, else INCORRECT
  │
  ▼ [conditional_edges via crag_router()]
  ├── CORRECT + Simple/Medium/Complex → generate_node
  ├── CORRECT + Calculation           → generate_calc_node
  └── AMBIGUOUS/INCORRECT (iter<2)    → reformulate_node ──▶ retrieve_node
```

### Current RAGState (14 fields, TypedDict)

| Field | Type | Phase |
|-------|------|-------|
| `query` | `str` | 1 |
| `expanded_query` | `Optional[str]` | 1 |
| `query_embedding` | `Optional[list[float]]` | 1 |
| `retrieved_docs` | `Optional[list[dict]]` | 1 |
| `reranked_docs` | `Optional[list[dict]]` | 1 |
| `response` | `Optional[str]` | 1 |
| `citations` | `Optional[list[dict]]` | 1 |
| `error` | `Optional[str]` | 1 |
| `graph_docs` | `Optional[list[dict]]` | 2 |
| `query_type` | `Optional[str]` | 3 |
| `crag_grade` | `Optional[str]` | 3 |
| `crag_iterations` | `Optional[int]` | 3 |
| `llm_call_count` | `Optional[int]` | 3 |
| `conversation_history` | `Annotated[list, operator.add]` | 3 |

### Current Prompt Selection Logic (generator.py)

```python
if query_type == "Calculation":
    system_prompt = SYSTEM_PROMPT_GENERATOR_CALCULATION
elif graph_context:
    system_prompt = SYSTEM_PROMPT_SYNTHESIS
else:
    system_prompt = SYSTEM_PROMPT_GENERATOR
```

Three hardcoded branches. No protocol concept. No consulting-domain awareness.

### Current citation_builder.py Return Shape

`build_citations()` returns `list[dict]` where each dict has:
```python
{
    "formatted": str,     # "Author, Title, Chapter, hal. N-M"
    "book_title": str,
    "chapter": str,
    "page_start": int,
    "page_end": int,
    "section_path": str,
    "author": str,
}
```

There is no `label` field, no `source_domain` field. The `"formatted"` field is a string that is used directly by the frontend for citation display.

---

## KPE Integration Map

### Integration Point 1: RAGState — 15th Field

**Change:** Add `selected_protocol: Optional[str]` to `RAGState`.

**File:** `src/agents/state.py`

**Scope:** Additive — new Optional field does not break existing TypedDict consumers. LangGraph passes unknown fields through unchanged. No migration needed.

**Value flows:** `route_node` writes it → `generate_node` and `generate_calc_node` read it → `build_system_prompt()` uses it.

**Decision:** Do NOT add `source_domain` to state. Domain filter is an input parameter to `retrieve_node`, not a persistent state field. `route_node` derives the domain from the query and passes it via state only as `selected_protocol`. The retrieval layer reads this to determine filter behavior — see Integration Point 4.

```python
# state.py addition
selected_protocol: Optional[str]  # e.g., "CVP", "Variance", "ABC", "General"
```

---

### Integration Point 2: route_node — classify_query() Replacement

**Current:** `is_calculation_query()` returns `bool`. Only sets `query_type` to `"Calculation"` or `"Simple"`. Medium/Complex never set.

**Change:** Replace `is_calculation_query()` call with `classify_query()` that returns both `query_type` and `selected_protocol`.

**File:** `src/agents/nodes.py` (route_node function only)

**Can route_node change without breaking CRAG?** YES. The CRAG flow depends on `query_type` values (`"Calculation"`, `"Simple"`, `"Medium"`, `"Complex"`) and `crag_router()` checks `query_type == "Calculation"`. The new classifier must preserve this exact value for Calculation queries. All other `query_type` values map to the `"generate"` branch, so `"Medium"` and `"Complex"` are safe additions — `crag_router()` already handles them via the `else` branch.

**New module:** `src/retrieval/query_classifier.py` — add `classify_query(query: str) -> dict` function alongside the existing `is_calculation_query()`. Do not delete `is_calculation_query()` — it is tested independently. `classify_query()` calls `is_calculation_query()` internally for the Calculation branch.

```python
# nodes.py route_node — new implementation
from src.retrieval.query_classifier import classify_query

def route_node(state: RAGState) -> dict:
    result = classify_query(state["query"])
    return {
        "query_type": result["query_type"],          # unchanged field
        "selected_protocol": result["protocol"],      # new field
        "llm_call_count": 0,
        "crag_iterations": 0,
        "crag_grade": None,
    }
```

**classify_query() contract:**
```python
def classify_query(query: str) -> dict:
    """Returns {"query_type": str, "protocol": str}
    query_type: "Simple"|"Medium"|"Complex"|"Calculation"
    protocol: "CVP"|"Variance"|"ABC"|"TransferPricing"|"RelevantCosting"
              |"ProductProfitability"|"Budgeting"|"CostClassification"|"General"
    """
```

**Implementation approach for classify_query():**
- Calculation detection: delegate to existing `is_calculation_query()` (zero LLM calls)
- Protocol selection: keyword matching against protocol registry (zero LLM calls)
- Complexity: rule-based heuristics on query length/structure (zero LLM calls)
- No LLM call in route_node — this preserves the "Simple=2 LLM calls" budget constraint

---

### Integration Point 3: generate_node — build_system_prompt() Replacement

**Current:** Three-branch `if/elif/else` in `generator.py:generate_response()`.

**Change:** Replace the three branches with `build_system_prompt(query_type, protocol, has_graph_context)`.

**File:** `src/generation/generator.py` (generate_response function)

**New module:** `src/generation/prompt_builder.py` with `build_system_prompt()` and the KPE protocol registry.

**Backward compatibility:** `generate_response()` receives `selected_protocol` as a new optional parameter. Callers that don't pass it get `protocol=None` → falls back to `"General"` protocol → produces prompt identical to current `SYSTEM_PROMPT_GENERATOR`. This is fully backward compatible.

```python
# generator.py signature change
def generate_response(
    query: str,
    context_docs: list[dict],
    graph_context: str = "",
    query_type: str = "Simple",
    conversation_history: list[dict] | None = None,
    selected_protocol: str | None = None,     # NEW — optional, defaults to "General"
) -> dict:
```

The `generate_node` reads `state.get("selected_protocol")` and passes it through:

```python
# nodes.py generate_node addition
result = generate_response(
    query=state["query"],
    context_docs=docs,
    graph_context=graph_context,
    query_type=query_type,
    conversation_history=history,
    selected_protocol=state.get("selected_protocol"),   # new
)
```

Same change applies to `generate_calc_node`.

**Protocol registry** lives in `src/generation/prompt_builder.py`. Each protocol defines:
- `steps`: list of framework steps (hardcoded strings, zero LLM calls)
- `few_shot`: optional example (kept short for token budget)
- `consulting_lens`: one-sentence framing for the system prompt

The 9 protocols: CVP, Variance, ABC, TransferPricing, RelevantCosting, ProductProfitability, Budgeting, CostClassification, General.

---

### Integration Point 4: hybrid_search() — domain_filter Parameter

**Current:** `hybrid_search()` signature:
```python
def hybrid_search(
    query_embedding, query_text, top_k=20,
    collection_name=None, book_filter=None
) -> list[dict]:
```

**Change:** Add `domain_filter: str | None = None` parameter. When set, adds a Qdrant `Filter` condition on the `source_domain` payload field.

**File:** `src/retrieval/vector_search.py`

**Does domain_filter need a Qdrant payload index?** YES. Qdrant requires a payload index for filter fields to avoid full-scan on every query. The `source_domain` field must be indexed as KEYWORD type. Two paths:

1. **New collections:** `create_collection()` in `qdrant_uploader.py` adds `source_domain` to the `create_payload_index()` loop (already contains `["book_title", "chapter", "content_type"]`).
2. **Existing collection:** One-time migration call to `client.create_payload_index(field_name="source_domain", field_schema=KEYWORD)` for the existing collection. This is safe on a live collection.

**Backfill existing points:** All existing Qdrant points need `source_domain="accounting"` in their payload. Use Qdrant's `set_payload` with a scroll-and-update loop. This is a one-time offline migration, not a collection recreation.

**retrieve_node change:** Pass domain filter to hybrid_search based on selected_protocol. Two modes:
- No protocol or `"General"`: no domain filter — retrieves from all domains (broad search)
- Any specific protocol: retrieve from both domains (accounting + consulting) with equal weight

**Decision on filtering strategy:** Do NOT apply domain_filter exclusively for specific protocols. The consulting books provide methodology; the textbooks provide the accounting grounding. For most queries, you want both. The `domain_filter` parameter is for cases where you explicitly want only one domain — e.g., a future "cite only textbooks" mode. For v1.1, the retrieve_node passes `domain_filter=None` (no filter) and relies on reranking to surface the best mix.

The correct use of `source_domain` is in citation differentiation (Integration Point 5), not retrieval filtering.

---

### Integration Point 5: citation_builder — Adding label Field

**Is string→dict a breaking change?** CLARIFICATION: `build_citations()` already returns `list[dict]`. It is NOT a string. The concern is adding a `label` field to the existing dict structure.

**Current shape:** each citation dict has `{"formatted", "book_title", "chapter", "page_start", "page_end", "section_path", "author"}`.

**Change:** Add `label` field derived from `source_domain` in metadata:
```python
{
    "formatted": str,     # unchanged
    "label": str,         # NEW: "Sumber" or "Kerangka"
    "book_title": str,
    "chapter": str,
    "page_start": int,
    "page_end": int,
    "section_path": str,
    "author": str,
    "source_domain": str, # NEW: "accounting" or "consulting"
}
```

**Is this a breaking change?** For the backend, NO — adding fields to a dict is backward compatible. For the frontend, it must handle the case where `label` is absent (older history entries). The frontend citation renderer should default to `"Sumber"` when `label` is absent.

**Implementation:** `build_citation()` receives `metadata` which already contains all payload fields. When `metadata.get("source_domain") == "consulting"`, use label `"Kerangka"` instead of `"Sumber"`. The `formatted` string becomes `"[Kerangka N]: Author, Title, Chapter"` for consulting sources.

**Context block in generator.py:** `_build_context_block()` currently builds `[Sumber N: ...]`. With KPE, blocks from consulting sources should be labeled `[Kerangka N: ...]`. This requires `_build_context_block()` to read `source_domain` from metadata. Add it as a secondary concern after citation_builder is updated.

---

### Integration Point 6: Consulting Book Ingestion

**Where does it fit in the existing pipeline?** The existing `run_ingestion_pipeline()` in `src/ingestion/pipeline.py` is the correct entry point. It already supports per-book metadata enrichment via `enrich_metadata()`. The required change is minimal:

1. Add `source_domain` parameter to `run_ingestion_pipeline()` (default: `"accounting"`)
2. Pass it through to `enrich_metadata()` so every chunk carries `source_domain` in its metadata
3. `upload_batch()` already writes all metadata as Qdrant payload — `source_domain` will be included automatically

**GraphRAG skip:** Consulting books skip fast-graphrag entirely. This is already the design decision in PROJECT.md. No change to `ingest_graphrag.py` needed.

**Content type considerations for consulting books:** Consulting books contain mostly narrative text and procedural frameworks. The existing `classify_element()` content classifier will map most content to `narrative_text` — which is correctly handled by the 512-token recursive splitter. Tables in consulting books (comparison matrices, decision frameworks) may be smaller and less dense than accounting textbooks, so the existing table handling is sufficient.

**Ingestion script:** Create `scripts/ingest_consulting.py` (or reuse `scripts/ingest.py` with a `--source-domain consulting` flag). The script passes `source_domain="consulting"` to `run_ingestion_pipeline()`. This is a thin wrapper — no new pipeline logic.

---

## Component Boundaries After KPE

```
src/
├── agents/
│   ├── state.py          MODIFIED — add selected_protocol field
│   ├── nodes.py          MODIFIED — route_node, generate_node, generate_calc_node
│   └── graph.py          UNCHANGED — graph topology unchanged
├── retrieval/
│   ├── query_classifier.py  MODIFIED — add classify_query() alongside is_calculation_query()
│   ├── vector_search.py     MODIFIED — add domain_filter parameter
│   ├── preprocessor.py      UNCHANGED
│   └── reranker.py          UNCHANGED
├── generation/
│   ├── generator.py         MODIFIED — accept selected_protocol, delegate to build_system_prompt()
│   ├── prompt_builder.py    NEW — KPE protocol registry + build_system_prompt()
│   └── citation_builder.py  MODIFIED — add label + source_domain fields
├── ingestion/
│   ├── pipeline.py          MODIFIED — add source_domain parameter (default "accounting")
│   ├── indexing/
│   │   └── qdrant_uploader.py  MODIFIED — add source_domain to create_payload_index() loop
│   └── chunking/
│       └── metadata_enricher.py  MODIFIED — accept + store source_domain
config/
└── prompts.py               POTENTIALLY MODIFIED — KPE protocols may live here or in prompt_builder.py
                             Recommendation: keep in prompt_builder.py for cohesion
```

**What does NOT change:**
- `graph.py` — graph topology, edges, conditional routing all unchanged
- `preprocessor.py` — glossary expansion and embedding unchanged
- `reranker.py` — reranking unchanged
- `backend/main.py` — API unchanged; citations SSE event already sends `list[dict]`, frontend reads dict fields
- `history_db.py` — stores citations as JSON blob, schema-agnostic
- FastAPI lifespan (graphrag init) — unchanged

---

## Data Flow with KPE

```
User query (Indonesian)
        │
        ▼
route_node
  classify_query(query)
  → query_type: "CVP" scenario → "Calculation"
  → selected_protocol: "CVP"
  Writes: {query_type, selected_protocol, crag_iterations=0, crag_grade=None}
        │
        ▼
preprocess_node (unchanged)
  glossary expansion + embed_query()
        │
        ▼
retrieve_node (updated)
  hybrid_search(
      query_embedding,
      expanded_query,
      top_k=20,
      domain_filter=None     ← no filtering; reranker handles domain mix
  )
  Returns chunks from BOTH accounting + consulting domains
        │
        ▼
graph_retrieve_node (unchanged)
  fast-graphrag on accounting KG
        │
        ▼
rerank_node (unchanged)
  Qwen3-Reranker-8B scores all chunks regardless of source_domain
        │
        ▼
crag_grade_node (unchanged)
  threshold scoring
        │
        ▼ [crag_router — unchanged]
generate_node (updated)
  generate_response(
      ...,
      selected_protocol=state.get("selected_protocol")  ← NEW
  )
  → build_system_prompt("CVP") → consultant-style prompt with CVP steps
  → _build_context_block() labels consulting chunks as [Kerangka N]
  → build_citations() adds label="Kerangka" for source_domain="consulting"
        │
        ▼
Response with mixed citations:
  [Sumber 1]: Horngren, Cost Accounting, Ch.3, hal. 89
  [Kerangka 1]: McKinsey, The McKinsey Way, Ch.5
```

---

## Build Order

The build order is driven by three dependency rules:
1. State schema must be updated before any node uses the new field.
2. The generation layer (prompt builder) is independent of retrieval — build it first to get value immediately with zero retrieval changes.
3. Ingestion (consulting books + backfill) must happen before domain-aware citation display has any consulting content to show.

### Phase A — Generation Layer (no retrieval changes needed)

Order within Phase A:

**A1: Protocol Registry + prompt_builder.py (NEW)**
- Create `src/generation/prompt_builder.py` with 9 protocols
- Implement `build_system_prompt(query_type, protocol, has_graph_context) -> str`
- Write tests: each protocol produces a non-empty, different prompt
- Zero dependencies on other changes

**A2: RAGState + route_node (MODIFIED)**
- Add `selected_protocol` to `state.py`
- Add `classify_query()` to `query_classifier.py` (does NOT delete `is_calculation_query()`)
- Update `route_node` to call `classify_query()`
- Update `generate_node` and `generate_calc_node` to pass `selected_protocol` to `generate_response()`
- Update `generate_response()` signature to accept `selected_protocol`
- Write tests: route_node produces correct protocol for sample queries

**A3: Citation label field (MODIFIED)**
- Add `label` and `source_domain` to `build_citations()` output
- Update `_build_context_block()` to label consulting chunks as `[Kerangka N]`
- Update frontend citation renderer to display label (graceful fallback when absent)
- This is a non-breaking addition

At end of Phase A: the system works end-to-end with KPE prompting for all existing accounting textbook content. No consulting books yet. Verifiable in dev with existing corpus.

### Phase B — Retrieval + Ingestion Layer

Order within Phase B:

**B1: source_domain in ingestion pipeline (MODIFIED)**
- Add `source_domain` param to `metadata_enricher.py` and `pipeline.py`
- Add `source_domain` to `qdrant_uploader.py` payload index list
- Write migration script to backfill `source_domain="accounting"` on existing Qdrant points
- Run migration on existing collection

**B2: domain_filter in hybrid_search() (MODIFIED)**
- Add `domain_filter: str | None = None` to `hybrid_search()`
- Add Qdrant `Filter` when domain_filter is set
- No change to `retrieve_node` — passes `domain_filter=None` for now (future use)

**B3: Consulting book ingestion**
- Add `--source-domain` flag to `scripts/ingest.py` (or create thin `scripts/ingest_consulting.py`)
- Ingest 21 consulting books with `source_domain="consulting"`, skip graphrag
- Verify citation labels appear correctly in dev environment

At end of Phase B: full KPE milestone is complete. System retrieves from both domains, labels citations correctly, uses protocol-aware prompts.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Merging classify_query() into route_node inline

Inline keyword matching directly in `route_node` makes testing hard and the function too long. The existing pattern (separate `is_calculation_query()` module) is correct. Follow it: `classify_query()` is a pure function in `query_classifier.py` that route_node calls. Test it in isolation.

### Anti-Pattern 2: LLM call in route_node for protocol selection

Adding an LLM call to classify protocol type would cost 1 extra LLM call per query. For Simple queries (the majority), this increases cost by 50% (2→3 calls). Keyword matching covers the 9 protocols well for accounting domain queries. Reserve LLM classification for if keyword matching proves insufficient after evaluation.

### Anti-Pattern 3: Filtering by source_domain in retrieve_node

Applying `domain_filter="accounting"` in retrieve_node for non-consulting queries would silently exclude consulting book chunks. The user wants the best answer — reranking will naturally surface the most relevant content from either domain. Domain filtering is a future explicit-mode feature, not a default behavior.

### Anti-Pattern 4: Storing consulting books in a separate Qdrant collection

A second collection doubles infrastructure complexity, requires parallel query execution in retrieve_node, and means the existing RRF fusion cannot blend results. Single collection with `source_domain` payload field + index is the correct approach.

### Anti-Pattern 5: Modifying graph.py for KPE

The graph topology does not need to change. All KPE integration happens inside existing node functions (route_node, generate_node) and via the new state field. Adding a new node would require recompiling the graph and risking regression in the CRAG loop.

---

## Decision Log

| Question | Decision | Rationale |
|----------|----------|-----------|
| Can route_node change without breaking CRAG? | YES | CRAG depends on `query_type` values, which are preserved. `selected_protocol` is a new independent field. `crag_router()` is unchanged. |
| Is citation_builder string→dict breaking? | NOT A STRING. Already `list[dict]`. Adding `label` field is additive, non-breaking. Frontend needs null-safe access. | Direct code inspection of `citation_builder.py` |
| Does domain_filter need Qdrant payload index? | YES | Required for non-full-scan filtering. Add to `create_payload_index()` loop + one-time migration for existing collection. |
| Build order: Phase A (generation) before Phase B (retrieval)? | CORRECT | Generation layer (prompt_builder, classify_query, citation label) has zero dependencies on ingestion. Delivers immediate value on existing corpus. Phase B adds consulting content. |
| Where do protocol definitions live? | `src/generation/prompt_builder.py` | Co-located with their primary consumer. Not in `config/prompts.py` (that file holds operational system prompts, not framework registry). |
| KPE protocol selection: LLM or rule-based? | Rule-based keyword matching | Zero extra LLM calls, preserves 2-call budget for Simple queries, accounting domain is finite/predictable. |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Integration points 1-3 (state, route, generation) | HIGH | Direct code inspection. No inference required. |
| Integration point 4 (domain_filter) | HIGH | Qdrant filter API is well-documented; payload index requirement verified against existing `create_payload_index()` usage in codebase. |
| Integration point 5 (citation label) | HIGH | `build_citations()` already returns `list[dict]`; adding fields is straightforward. |
| Integration point 6 (consulting ingestion) | HIGH | Existing pipeline supports `source_domain` via metadata enricher pattern. No novel engineering. |
| Build order recommendation | HIGH | Dependency analysis is mechanical. Phase A has zero external dependencies on Phase B. |

---

*Architecture analysis completed: 2026-03-29*
*Based on direct inspection of: state.py, nodes.py, graph.py, vector_search.py, generator.py, citation_builder.py, query_classifier.py, pipeline.py, qdrant_uploader.py, preprocessor.py, prompts.py*
