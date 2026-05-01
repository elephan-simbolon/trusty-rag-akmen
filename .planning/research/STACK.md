# Technology Stack

**Project:** Trusty RAG Akmen — v1.1 Knowledge Protocol Engineering
**Researched:** 2026-03-29
**Milestone:** v1.1 KPE + Consulting Book Ingestion (subsequent milestone)

---

## Scope of This Document

This file covers **only the stack additions and changes** needed for v1.1. All v1.0 validated decisions (LangGraph, LangChain, Qdrant, SiliconFlow, MinerU, Docling, fast-graphrag) are carried forward unchanged unless explicitly noted here.

For the full original stack, see the v1.0 research above the separator line — this section extends it.

---

## v1.1 Stack Additions

### No New Python Packages Required

The KPE layer and consulting book ingestion require **zero new package additions**. All required capabilities are already present in the installed stack. The work is entirely in new Python modules using existing primitives.

| Capability Needed | Existing Package | Why Sufficient |
|-------------------|-----------------|----------------|
| Protocol dataclass registry | Python stdlib `dataclasses` (3.11 built-in) | `@dataclass` is the right tool for immutable protocol definitions — no runtime validation needed on internal data that is hardcoded, not user-input |
| Consulting PDF ingestion | `mineru==2.7.6` + `docling==2.81.0` | Same parsing pipeline as accounting textbooks — consulting books (McKinsey Way, Pyramid Principle, etc.) are commercial non-fiction PDFs, primarily text-native, well within Docling's strengths |
| Domain-aware Qdrant filtering | `qdrant-client==1.17.1` | `query_points()` Prefetch objects accept `filter` parameter natively; `create_payload_index()` with `PayloadSchemaType.KEYWORD` already used for `book_title`/`chapter` — same API for `source_domain` |
| Source domain backfill on existing points | `qdrant-client==1.17.1` | `set_payload()` with scroll-based iterator updates existing points without re-embedding or collection recreation |
| Composable prompt builder | Python stdlib string formatting (`str.format()`) | KPE prompts are string templates assembled at runtime — no templating library needed |
| Extended query classifier | Python stdlib `re` + `frozenset` | Current `query_classifier.py` is rule-based; protocol selection extends the same pattern with a keyword-to-protocol dict |
| Citation label differentiation | Python stdlib string formatting | `[Sumber N]` vs `[Kerangka N]` is a rendering concern in `generator.py` — no new library |

---

## Qdrant: source_domain Payload Index

**Question answered:** Does Qdrant require explicit payload index creation for `source_domain` filtering to work?

**Answer:** Filtering works without a payload index (Qdrant performs a full scan), but a payload index is required for correct HNSW performance with filtered vector search. Without the index, Qdrant loads the entire payload from disk for each candidate to check the filter condition, which defeats the purpose of the HNSW graph for this collection size.

**Verdict: Yes, create the payload index. It is the same one-liner already used for `book_title`.**

From official Qdrant docs (verified 2026-03-29):
> "If you're performing a search with a filter but you don't have a payload index, Qdrant will have to load whole payload data from disk to check the filtering condition."
> "It's highly recommended to create all payload indices immediately after collection creation."

**Required change in `qdrant_uploader.py`:**

```python
# In create_collection(), add source_domain to the index creation loop:
for field in ["book_title", "chapter", "content_type", "source_domain"]:
    client.create_payload_index(
        collection_name=name,
        field_name=field,
        field_schema=PayloadSchemaType.KEYWORD,
    )
```

**Required backfill for existing accounting points:**

Existing Qdrant points from v1.0 do not have a `source_domain` field. They must be backfilled with `source_domain="accounting"` using scroll + set_payload. The Qdrant API supports this without re-embedding:

```python
# Pattern for backfill script (no new libraries needed):
offset = None
while True:
    points, next_offset = client.scroll(
        collection_name=name,
        limit=500,
        offset=offset,
        with_payload=["book_title"],   # only need to confirm these are accounting chunks
        with_vectors=False,
    )
    if not points:
        break
    ids = [p.id for p in points]
    client.set_payload(
        collection_name=name,
        payload={"source_domain": "accounting"},
        points=ids,
    )
    offset = next_offset
    if offset is None:
        break
```

**Integration point for new ingestion:** `metadata_enricher.py` adds `source_domain` as a required field. Consulting book ingestion passes `source_domain="consulting"`. Accounting book ingestion passes `source_domain="accounting"`. Uploader stores it in the Qdrant payload alongside `book_title`, `chapter`, etc.

---

## Qdrant: Domain-Aware Filtering in hybrid_search()

**Current signature:**
```python
def hybrid_search(query_embedding, query_text, top_k=20,
                  collection_name=None, book_filter=None) -> list[dict]
```

**Required change:** Add `domain_filter: str | None = None` parameter. When provided, pass as a filter on the `source_domain` payload field to both `Prefetch` objects.

```python
# Within hybrid_search(), build optional filter:
from qdrant_client.models import Filter, FieldCondition, MatchValue

payload_filter = None
if domain_filter:
    payload_filter = Filter(
        must=[FieldCondition(
            key="source_domain",
            match=MatchValue(value=domain_filter),
        )]
    )

results = client.query_points(
    collection_name=name,
    prefetch=[
        Prefetch(query=NearestQuery(nearest=query_embedding),
                 using="dense", limit=top_k,
                 filter=payload_filter),         # <-- added
        Prefetch(query=NearestQuery(nearest=SparseVector(...)),
                 using="sparse", limit=top_k,
                 filter=payload_filter),         # <-- added
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=top_k,
)
```

The `Prefetch` object in qdrant-client 1.17.1 supports a `filter` parameter — confirmed from the Qdrant API reference.

---

## KPE Protocol Registry: Python dataclasses (stdlib)

**Question answered:** Python dataclass vs Pydantic BaseModel for protocol definitions?

**Verdict: Use `@dataclass` from Python stdlib.**

Rationale:
- Protocol objects are **internal, hardcoded constants** — they are never deserialized from JSON, never received from an API, never user-input. Runtime validation (Pydantic's primary value) adds zero benefit for constant definitions.
- `@dataclass` in Python 3.11 is 3x faster to instantiate than Pydantic BaseModel (benchmark: Python 3.13 further improved this gap). For protocol objects used in a hot path (every query), dataclasses are the correct choice.
- The existing `RAGState` (a `TypedDict`) and configuration (`pydantic-settings BaseSettings`) pattern in this codebase already follows "Pydantic at the edge, stdlib in the core" — consistent with ecosystem best practice.
- `@dataclass(frozen=True)` provides immutability for protocol definitions, which is semantically correct (protocols don't mutate at runtime).

```python
# config/protocols.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AccountingProtocol:
    name: str                         # e.g. "CVP"
    display_name: str                 # e.g. "Cost-Volume-Profit Analysis"
    trigger_keywords: frozenset[str]  # keywords that activate this protocol
    system_prompt_steps: str          # protocol-specific reasoning steps for prompt
    few_shot_example: str             # one worked example in Indonesian
    citation_label: str               # "[Sumber N]" or "[Kerangka N]"

PROTOCOL_REGISTRY: dict[str, AccountingProtocol] = {
    "CVP": AccountingProtocol(...),
    "VARIANCE": AccountingProtocol(...),
    # ... 9 protocols total
}
```

No alternative library (attrs, msgspec, Pydantic dataclasses) is needed. Stdlib `@dataclass` is sufficient and keeps the dependency count flat.

---

## KPE Prompt Builder: stdlib str.format()

**Question answered:** Are there KPE/protocol-based prompting libraries worth using?

**Answer:** No. KPE is a concept described in a July 2025 position paper (arxiv 2507.02760). There are no production Python libraries implementing a "KPE framework" as of March 2026. The concept is hand-rolled everywhere it appears in practice.

**Verdict: Hand-roll a composable prompt builder using stdlib string formatting. One file, ~50 lines.**

The existing `config/prompts.py` already uses Python string `.format()` for `{glossary_snippet}` injection. The KPE prompt builder is a natural extension of this pattern:

```python
# config/prompt_builder.py
def build_system_prompt(
    base_prompt: str,
    protocol: AccountingProtocol | None,
    glossary_snippet: str,
    has_consulting_context: bool = False,
) -> str:
    """Compose final system prompt from base + protocol steps + glossary."""
    parts = [base_prompt]
    if protocol:
        parts.append(f"\n\nFramework yang digunakan: {protocol.display_name}\n{protocol.system_prompt_steps}")
        if protocol.few_shot_example:
            parts.append(f"\n\nContoh:\n{protocol.few_shot_example}")
    if has_consulting_context:
        parts.append("\n\nGunakan [Kerangka N] untuk referensi dari buku metodologi/consulting.")
    parts.append(f"\n\nGlosarium:\n{glossary_snippet}")
    return "\n".join(parts)
```

No templating library (Jinja2, Mako, Mustache) is warranted. The prompts are short, structured, and don't require loops, conditionals, or inheritance that would justify a templating engine.

---

## Query Classifier Extension: Rule-Based Protocol Selection

**Current state:** `query_classifier.py` uses keyword + number pattern for `is_calculation_query()` — zero LLM calls.

**v1.1 extension:** Add `classify_protocol(query: str) -> str | None` that returns a protocol key or None, using the same rule-based keyword matching pattern. No new library needed.

```python
# Extend src/retrieval/query_classifier.py
_PROTOCOL_KEYWORDS: dict[str, frozenset[str]] = {
    "CVP": frozenset(["cvp", "cost-volume-profit", "break-even", "bep", "contribution margin"]),
    "VARIANCE": frozenset(["variance", "selisih", "price variance", "quantity variance"]),
    "ABC": frozenset(["abc", "activity-based", "activity based"]),
    # ... etc
}

def classify_protocol(query: str) -> str | None:
    """Return protocol key if query matches a known framework, else None."""
    q_lower = query.lower()
    for protocol_key, keywords in _PROTOCOL_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            return protocol_key
    return None
```

The existing `route_node` in `nodes.py` calls this and stores the result in a new `active_protocol: str | None` field on `RAGState`.

---

## RAGState Extension

**Required addition to `src/agents/state.py`:**

```python
# v1.1 additions:
active_protocol: Optional[str]      # Protocol key from classify_protocol(), e.g. "CVP"
source_domain_filter: Optional[str] # "accounting" | "consulting" | None (search all)
```

No new packages. TypedDict extension is backward-compatible — existing nodes that don't read these fields are unaffected.

---

## Consulting Book Ingestion: PDF Characteristics

**Consulting book PDFs (McKinsey Way, Pyramid Principle, Issue Trees, etc.) differ from accounting textbooks in these ways:**

| Characteristic | Accounting Textbooks | Consulting Books |
|----------------|---------------------|------------------|
| PDF format | Mixed (text + scanned) | Predominantly text-native |
| Tables | Heavy (cost sheets, ledgers, variance tables) | Light (2x2 matrices, priority grids) |
| Formulas | LaTeX-rendered math | None or minimal |
| Diagrams | Many (flowcharts, graphs) | Some (pyramid diagrams, issue trees) |
| Chapter structure | Dense, numbered headings | Lighter structure, prose-heavy |
| Language | English | English |
| Page count | 600-900 pages per book | 150-350 pages per book |

**Ingestion decision:** Use **Docling as primary** for consulting books (not MinerU). Consulting books are text-native with simple layouts — Docling's 97.9% table accuracy and faster batch processing are better suited. MinerU's scanned-PDF OCR capability is not needed.

**fast-graphrag decision:** Skip for consulting books (as per PROJECT.md). The accounting entity schema (CVP, variance, overhead) used for fast-graphrag entity extraction would produce low-quality entities from procedural consulting content ("Issue Trees," "MECE," "Hypothesis-Driven"). Qdrant-only ingestion is correct.

**Metadata schema:** Consulting chunks get `source_domain="consulting"` plus the standard fields. The `book_title` field carries the consulting book title (e.g., "The McKinsey Way"), which becomes the `[Kerangka N]` citation.

---

## Citation Differentiation: [Sumber N] vs [Kerangka N]

**Implementation location:** `src/generation/generator.py` and `config/prompts.py`

**No new library.** The citation builder already constructs a numbered list. The change is:
1. Annotate each retrieved chunk with its `source_domain` in the context passed to the LLM
2. Update `SYSTEM_PROMPT_GENERATOR` to instruct: "Gunakan [Sumber N] untuk buku akuntansi, [Kerangka N] untuk buku konsulting/metodologi"
3. The citation list in the response renders both prefixes with the same formatting logic

---

## What NOT to Add for v1.1

| Do Not Add | Why |
|-----------|-----|
| Pydantic BaseModel for protocol dataclass | Runtime validation is unnecessary for hardcoded constant objects. Adds import overhead per query. Dataclass is correct. |
| Jinja2 or any templating library | Prompt composition is 3-4 string concatenations. A templating engine would add 100KB of dependency for zero benefit. |
| LlamaIndex for consulting book chunking | Already replaced by custom chunking pipeline in v1.0. Adding LlamaIndex for consulting books creates two parallel chunking paths. |
| A new Qdrant collection for consulting books | Single collection with `source_domain` payload filter is simpler, maintains unified hybrid search, and avoids Qdrant free tier collection limits. |
| Langchain document loaders for consulting PDFs | The existing `route_and_parse()` → Docling path handles this. Adding LangChain document loaders creates a third parsing path. |
| Any KPE library (no production ones exist as of 2026-03) | KPE is a concept (arxiv 2507.02760, July 2025). No Python library has stabilized around it. Hand-rolling is the only viable approach. |
| msgspec or attrs as dataclass alternative | msgspec is excellent for high-volume serialization; irrelevant for 9 protocol objects defined at module import. attrs is heavier than dataclass for this use case. |

---

## Integration Map: Where Code Changes Live

| Change | File | Type |
|--------|------|------|
| Add `source_domain` to metadata schema | `src/ingestion/chunking/metadata_enricher.py` | Extend `REQUIRED_METADATA_FIELDS` list, add parameter |
| Add `source_domain` to Qdrant index | `src/ingestion/indexing/qdrant_uploader.py` | Add `"source_domain"` to index creation loop |
| Add `domain_filter` param to hybrid_search | `src/retrieval/vector_search.py` | Extend function signature + Prefetch filter |
| Add `classify_protocol()` | `src/retrieval/query_classifier.py` | New function, same file |
| Add `active_protocol` + `source_domain_filter` to state | `src/agents/state.py` | Extend `RAGState` TypedDict |
| KPE protocol registry | `config/protocols.py` | New file, stdlib dataclasses |
| KPE prompt builder | `config/prompt_builder.py` | New file, stdlib str methods |
| Update `SYSTEM_PROMPT_GENERATOR` for dual citation | `config/prompts.py` | Edit existing string |
| Update `route_node` to call `classify_protocol` | `src/agents/nodes.py` | Edit route_node |
| Update `retrieve_node` to pass `domain_filter` | `src/agents/nodes.py` | Edit retrieve_node |
| Source domain backfill script | `scripts/backfill_source_domain.py` | New script |
| Consulting book ingestion script | `scripts/ingest.py` | Add `--source-domain consulting` CLI flag |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Qdrant payload index requirement | HIGH | Official Qdrant docs (2026-03-29), consistent across multiple sources |
| Qdrant Prefetch filter support | HIGH | API reference schema + qdrant-client 1.17.1 `query_points` signature |
| set_payload backfill pattern | HIGH | Official Qdrant API reference, multiple code examples verified |
| dataclass over Pydantic for protocol registry | HIGH | Benchmark data + official Pydantic docs on when to use each |
| No KPE Python libraries exist | HIGH | No library found after WebSearch; KPE arxiv paper is July 2025, too recent for library ecosystem |
| Docling as primary for consulting books | HIGH | Consulting book characteristics (text-native) match Docling's design target |
| No new packages needed | HIGH | Verified against all 4 feature areas — all capabilities present in installed stack |

---

## Sources

- [Qdrant Indexing Documentation](https://qdrant.tech/documentation/manage-data/indexing/) — payload index creation, performance implications, KEYWORD type, timing recommendation — HIGH confidence
- [Qdrant API Reference: query_points](https://api.qdrant.tech/api-reference/search/query-points) — Prefetch.filter parameter existence — HIGH confidence
- [Qdrant Python Client Docs](https://python-client.qdrant.tech/qdrant_client.qdrant_client) — create_payload_index, set_payload signatures — HIGH confidence
- [KPE arxiv paper 2507.02760](https://arxiv.org/abs/2507.02760) — confirmed KPE is a concept paper, no library — HIGH confidence
- [KPE Medium article by Robert Encarnacao](https://medium.com/@delimiterbob/knowledge-protocol-engineering-teaching-ai-the-how-not-just-the-what-7b2d931bb4c4) — hand-rolled implementations are the norm — MEDIUM confidence
- [Pydantic dataclasses docs](https://docs.pydantic.dev/latest/concepts/dataclasses/) — when to use stdlib vs Pydantic dataclass — HIGH confidence
- WebSearch "python dataclass vs pydantic basemodel performance 2025" — benchmark data for instantiation speed — MEDIUM confidence
- qdrant-client 1.17.1 installed in project (verified via pyproject.toml) — version confirmation — HIGH confidence

---

*Stack research for: v1.1 KPE + Consulting Book Ingestion milestone*
*Researched: 2026-03-29*
*Scope: Additions and changes only — does not replace v1.0 stack decisions*
