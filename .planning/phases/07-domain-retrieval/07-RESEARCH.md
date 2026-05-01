# Phase 07: Domain Retrieval Infrastructure - Research

**Researched:** 2026-03-30
**Domain:** Qdrant payload filtering, backfill scripting, domain-aware hybrid search, citation label differentiation
**Confidence:** HIGH

## Summary

Phase 07 adds one new payload field (`source_domain`) to every Qdrant point and wires it through all three layers: ingestion, retrieval, and citation rendering. The changes are structurally simple — no new dependencies, no schema migration, no collection recreation — but must be executed in a strict safety order: (1) create the payload index, (2) backfill all existing points, (3) verify 100% coverage, (4) enable the domain filter in search. Enabling the filter before backfill completes is the catastrophic failure mode: it would silently exclude all untagged accounting chunks from domain-filtered queries.

The four touch-points are: `qdrant_uploader.py` (create `source_domain` payload index on collection creation, include `source_domain` in `upload_batch` payload), `vector_search.py` (add `domain_filter` parameter to `hybrid_search`, pass it as a `Filter` on the `Prefetch` objects), `citation_builder.py` (change `build_citation` to read `source_domain` and emit `[Sumber N]` vs `[Kerangka N]` labels), and `scripts/ingest.py` (add `--source-domain` CLI flag with default `"accounting"`).

A standalone backfill script is the safest delivery mechanism for the data migration. It uses `scroll` + `set_payload` in batches of 100 points, is idempotent (skips points that already have `source_domain` set), and emits a progress log and final count verification.

**Primary recommendation:** Three plans — (1) Payload index + upload_batch source_domain field + backfill script, (2) domain-aware hybrid_search + ingest.py flag, (3) citation label differentiation + tests.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RETR-01 | User mendapat retrieval yang memfilter berdasarkan source_domain (accounting/consulting) sesuai konteks query | `Prefetch.filter` accepts a `Filter(must=[FieldCondition(key="source_domain", match=MatchValue(...))])` — confirmed via qdrant-client 1.17.1 model inspection; existing `hybrid_search` signature is extended with `domain_filter: str | None = None` |
| RETR-02 | Semua existing Qdrant points di-backfill dengan source_domain="accounting" dan payload index dibuat sebelum domain filter aktif | `client.set_payload(collection_name, {"source_domain": "accounting"}, points=Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="source_domain"))]))` — confirmed API; `client.count(count_filter=FieldCondition(...))` verifies 100% coverage |
| RETR-03 | User melihat [Sumber N] untuk referensi textbook akuntansi dan [Kerangka N] untuk referensi methodology consulting di setiap respons | `citation_builder.build_citation()` reads `metadata["source_domain"]`; label is `[Sumber]` when `source_domain=="accounting"` or absent, `[Kerangka]` when `source_domain=="consulting"`; `_build_context_block()` in generator.py drives the inline label |
| RETR-04 | Pipeline ingestion menerima --source-domain flag untuk menandai buku consulting vs accounting | `scripts/ingest.py` adds `--source-domain` argparse argument (default `"accounting"`); `run_ingestion_pipeline()` accepts `source_domain: str = "accounting"` and passes it through to `upload_batch` via chunk metadata |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11 (pinned in `.python-version`)
- No new dependencies — all Qdrant payload operations use `qdrant-client==1.17.1` already installed
- `uv run pytest` — 30s timeout per test, pytest-timeout enforced
- Test markers: `integration` (live services), `e2e`, `gpu` — new tests for this phase must be pure unit (no markers needed) or marked `integration` if they require live Qdrant
- Bilingual convention: Indonesian prose + English technical terms in parentheses
- All documentation in Indonesian; English for code identifiers
- Ruff lint: line-length 100, `select = ["E", "F", "I"]`, `ignore = ["E501"]`
- Qdrant dual vectors: collection MUST be created with both dense and sparse vector configs at creation time — this phase does NOT recreate the collection; it only adds a payload index
- `_build_context_block()` in `generator.py` is the single place that controls inline citation labels — this is where `[Sumber N]` vs `[Kerangka N]` must be injected

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `qdrant-client` | 1.17.1 (installed) | `scroll`, `set_payload`, `count`, `create_payload_index`, `Prefetch.filter` | Already in use; all required APIs confirmed present |
| Python `argparse` | stdlib 3.11 | `--source-domain` CLI flag in `scripts/ingest.py` | Already used in `ingest.py` for `--book-title`, `--replace`, `--contextual` |
| Python `logging` | stdlib 3.11 | Backfill progress + verification logging | Consistent with all other scripts in the project |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `qdrant_client.models.IsEmptyCondition` | 1.17.1 | Filter points that lack `source_domain` field | Backfill script: only update points without `source_domain` to make the script idempotent |
| `qdrant_client.models.PayloadField` | 1.17.1 | Required argument for `IsEmptyCondition` | Paired with `IsEmptyCondition` |
| `qdrant_client.models.Filter` + `FieldCondition` + `MatchValue` | 1.17.1 | Domain filter for `Prefetch.filter` in hybrid search | Already used in `qdrant_uploader.py` for `check_book_exists` and `delete_book` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Payload filter on existing collection | Separate collection per domain | Qdrant official recommendation for logical separation is payload filter, not collection sharding; cross-domain query needs single-collection RRF fusion (confirmed in REQUIREMENTS.md Out of Scope rationale) |
| `set_payload` with `IsEmptyCondition` filter | Scroll page-by-page and call `set_payload` per page | Both work; `IsEmptyCondition` filter is cleaner and still idempotent; Qdrant Cloud free tier has no timeout for `set_payload` with filter |
| Backfill via `set_payload` with `FilterSelector` | Re-ingest all books from scratch | Re-ingestion would cost ~$2-8 in embedding API calls and several hours; `set_payload` updates payload only, vectors unchanged |

**Installation:** No new packages. Existing `qdrant-client==1.17.1` covers all required APIs.

---

## Architecture Patterns

### Recommended Project Structure

No new files except the backfill script:

```
scripts/
└── backfill_source_domain.py   # NEW: one-time migration script

src/
├── ingestion/
│   └── indexing/
│       └── qdrant_uploader.py  # EXTEND: add source_domain to upload_batch payload + create_payload_index
├── retrieval/
│   └── vector_search.py        # EXTEND: add domain_filter param to hybrid_search
└── generation/
    └── citation_builder.py     # EXTEND: [Sumber N] vs [Kerangka N] label based on source_domain

scripts/
└── ingest.py                   # EXTEND: add --source-domain flag
```

The `run_ingestion_pipeline()` function in `src/ingestion/pipeline.py` receives `source_domain` and passes it down through `upload_batch`. The pipeline itself does not need to know what the domain value means — it just threads the parameter.

### Pattern 1: Payload Index Creation

**What:** Add `source_domain` KEYWORD payload index to `create_collection()` alongside existing `book_title`, `chapter`, `content_type` indices.
**When to use:** Collection creation — index enables fast filtering without full scan on Qdrant Cloud.
**Example:**
```python
# In qdrant_uploader.create_collection(), alongside existing index creation loop
client.create_payload_index(
    collection_name=name,
    field_name="source_domain",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

**Important:** For the existing collection that already exists in Qdrant Cloud, `create_collection()` is skipped (early return because `client.collection_exists(name)` is True). The payload index on `source_domain` must be created separately in the backfill script for the live collection.

### Pattern 2: Domain Filter in hybrid_search

**What:** Pass an optional `domain_filter` string to `hybrid_search`; when provided, inject a `Filter(must=[FieldCondition(key="source_domain", match=MatchValue(value=domain_filter))])` into both `Prefetch` objects.
**When to use:** When query context indicates domain-specific retrieval (Phase 08 will drive this from protocol selection; for Phase 07, the parameter exists and is tested, but default `None` preserves existing behavior).

```python
# Source: qdrant-client 1.17.1 — Prefetch.model_fields confirms 'filter' key
from qdrant_client.models import FieldCondition, Filter, MatchValue

def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    top_k: int = 20,
    collection_name: str | None = None,
    book_filter: str | None = None,
    domain_filter: str | None = None,   # NEW
) -> list[dict]:
    payload_filter = None
    if domain_filter:
        payload_filter = Filter(
            must=[FieldCondition(key="source_domain", match=MatchValue(value=domain_filter))]
        )

    results = client.query_points(
        collection_name=name,
        prefetch=[
            Prefetch(
                query=NearestQuery(nearest=query_embedding),
                using="dense",
                limit=top_k,
                filter=payload_filter,   # None when no filter
            ),
            Prefetch(
                query=NearestQuery(
                    nearest=SparseVector(indices=sparse_vec.indices, values=sparse_vec.values)
                ),
                using="sparse",
                limit=top_k,
                filter=payload_filter,   # None when no filter
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
    )
```

The `filter=None` in `Prefetch` is a no-op — confirmed by qdrant-client model definition. Existing callers with no `domain_filter` argument get identical behavior to today.

### Pattern 3: Backfill Script (Idempotent)

**What:** Scroll through all Qdrant points, update those missing `source_domain` with `"accounting"`. Safe to re-run.
**Key insight:** `IsEmptyCondition` finds points where the field does not exist or is `null`. Calling `set_payload` with this filter as `points=` argument updates only matching points in one API call — no scrolling required if the collection is small enough.

```python
# Source: qdrant-client 1.17.1 — set_payload + IsEmptyCondition verified
from qdrant_client.models import Filter, IsEmptyCondition, PayloadField

# Step 1: Create payload index on the live collection (idempotent — Qdrant ignores duplicate)
client.create_payload_index(
    collection_name=name,
    field_name="source_domain",
    field_schema=PayloadSchemaType.KEYWORD,
)

# Step 2: Backfill all points missing source_domain
filter_no_domain = Filter(
    must=[IsEmptyCondition(is_empty=PayloadField(key="source_domain"))]
)
client.set_payload(
    collection_name=name,
    payload={"source_domain": "accounting"},
    points=filter_no_domain,
    wait=True,
)

# Step 3: Verify — count with filter must equal total count
total = client.count(collection_name=name, exact=True).count
tagged = client.count(
    collection_name=name,
    count_filter=Filter(must=[FieldCondition(key="source_domain", match=MatchValue(value="accounting"))]),
    exact=True,
).count
assert total == tagged, f"Backfill incomplete: {tagged}/{total} points tagged"
```

### Pattern 4: Citation Label Differentiation

**What:** `_build_context_block()` in `generator.py` currently hardcodes `[Sumber {i}:]`. Change it to read `source_domain` from metadata and emit `[Sumber N]` vs `[Kerangka N]`.
**Where:** `src/generation/citation_builder.py` (for the structured citation list) AND `src/generation/generator.py` (for the inline LLM context block prefix). Both must be consistent.

```python
# In generator._build_context_block()
def _build_context_block(docs: list[dict]) -> str:
    blocks = []
    for i, doc in enumerate(docs, 1):
        meta = doc.get("metadata", {})
        domain = meta.get("source_domain", "accounting")
        label = "Kerangka" if domain == "consulting" else "Sumber"
        source = f"{meta.get('book_title', 'Unknown')}, {meta.get('chapter', '')}, hal. {meta.get('page_start', '?')}"
        blocks.append(f"[{label} {i}: {source}]\n{doc['text']}")
    return "\n\n---\n\n".join(blocks)
```

`citation_builder.build_citations()` must also include `source_domain` in its output dict so the frontend can distinguish labels. Add `"source_domain": metadata.get("source_domain", "accounting")` to the citation dict returned.

### Pattern 5: source_domain Through the Ingestion Chain

**What:** Thread `source_domain` from CLI flag → `run_ingestion_pipeline()` → `upload_batch()` chunk metadata.
**Key insight:** `upload_batch` already does `payload={**chunk.get("metadata", {})}`. Adding `source_domain` to the chunk metadata dict is sufficient — no changes to `upload_batch` signature needed. The metadata is set in `pipeline.py` when building `all_chunks`.

```python
# In scripts/ingest.py argparse block
parser.add_argument(
    "--source-domain",
    default="accounting",
    choices=["accounting", "consulting"],
    help="Source domain tag for Qdrant payload (default: accounting)",
)

# In pipeline.run_ingestion_pipeline() — add to function signature
def run_ingestion_pipeline(..., source_domain: str = "accounting") -> dict:
    ...
    # When building enriched chunks (Step 4), add source_domain to each chunk's metadata
    enriched["metadata"]["source_domain"] = source_domain
```

### Anti-Patterns to Avoid

- **Enable domain filter before backfill completes:** If `domain_filter="accounting"` is passed while backfill is incomplete, any untagged point is invisible. Always verify `total == tagged` before enabling domain filtering in production calls.
- **Add `source_domain` index after collection recreation:** The collection already exists — `create_collection()` skips if collection exists. The backfill script must call `create_payload_index` directly against the live collection.
- **Call `set_payload` per point in a loop:** Qdrant `set_payload` accepts a `Filter` as the `points` argument — it updates all matching points server-side in one call. Per-point loop is unnecessary and slow.
- **Filter both prefetch AND the top-level query_points call:** For hybrid search with RRF fusion, the filter belongs on each `Prefetch`, not on the outer `query_points` call. The outer call's `filter` would filter the fused results, which is correct if you want global domain isolation, but applying it at the `Prefetch` level means each vector type is independently filtered before fusion — the semantically correct approach for domain safety.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Find all points without source_domain | Scroll all pages manually + filter in Python | `IsEmptyCondition` filter in `set_payload` | Single server-side operation; no client-side pagination needed |
| Count points matching a filter | Scroll and count in Python | `client.count(count_filter=...)` | Native Qdrant operation, `exact=True` guarantees precision |
| Keyword payload index | Custom Python hash-based lookup | `create_payload_index(field_schema=PayloadSchemaType.KEYWORD)` | Qdrant indexed keyword filter is O(log n) vs O(n) unindexed scan |
| Batch payload update | `scroll` → loop → `set_payload` per point | `set_payload(points=Filter(...))` | Single API call updates all matching points atomically |

**Key insight:** The entire backfill — index creation, bulk update, verification — requires 3 Qdrant API calls total. This is not a complex migration.

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | All existing Qdrant points in `trusty_rag_akmen` collection lack `source_domain` field | Data migration: `set_payload({"source_domain": "accounting"}, points=IsEmptyCondition filter)` |
| Live service config | Qdrant Cloud free tier: `trusty_rag_akmen` collection exists; no `source_domain` payload index yet | API call: `create_payload_index("source_domain", PayloadSchemaType.KEYWORD)` — must run against live collection, not just in `create_collection()` code path |
| OS-registered state | None — no Task Scheduler, pm2, or systemd entries for this project | None |
| Secrets/env vars | No new keys needed — existing `QDRANT_URL` + `QDRANT_API_KEY` used by backfill script | None |
| Build artifacts | `data/chunks_backup.json` — the existing chunk backup does NOT include `source_domain` in metadata | On re-ingestion from backup, add `source_domain="accounting"` to each chunk. The backfill script handles the live Qdrant collection independently |

**Critical ordering constraint from PROJECT.md v1.1 roadmap:** "This strict ordering prevents the most dangerous failure mode: a partial Qdrant backfill silently excluding all accounting chunks from domain-filtered queries." The backfill must be 100% complete and verified before any query code passes a non-None `domain_filter`.

---

## Common Pitfalls

### Pitfall 1: Filter Active Before Backfill Complete
**What goes wrong:** `hybrid_search` is called with `domain_filter="accounting"` while only 70% of points have been tagged. The 30% untagged points are invisible — silently degraded retrieval with no error.
**Why it happens:** Code deploy happens before the migration script runs, or the migration script crashes partway through.
**How to avoid:** Keep `domain_filter` parameter as optional with default `None`. The nodes.py `retrieve_node` does NOT pass `domain_filter` in Phase 07 — it stays None. Domain filtering is an opt-in feature that Phase 08 or a future change enables after confirming RETR-02 success criterion (total == tagged count).
**Warning signs:** Retrieval returns fewer results than expected; `client.count(count_filter=...)` < `client.count()`.

### Pitfall 2: create_payload_index on Already-Existing Collection
**What goes wrong:** `create_collection()` has an early return when the collection already exists. Adding `create_payload_index` calls inside `create_collection()` is sufficient for new collections (Phase 08 fresh data) but does NOT index the live existing collection.
**Why it happens:** Developer adds the index to `create_collection()` code path only, forgetting the live collection bypasses that code.
**How to avoid:** Backfill script calls `create_payload_index` directly against the live collection as its first step. `create_payload_index` is idempotent in Qdrant — calling it again on a field that already has an index is a no-op.
**Warning signs:** Keyword filter queries against `source_domain` are slow (O(n) scan) — visible in Qdrant Cloud dashboard as high CPU on filter queries.

### Pitfall 3: Citation Label Inconsistency Between Context Block and Frontend
**What goes wrong:** `_build_context_block()` emits `[Kerangka N]` in the LLM prompt but `build_citations()` returns `[Sumber N]` in the citations list sent to the frontend. The LLM response references `[Kerangka 2]` but the UI shows it as `[Sumber 2]`.
**Why it happens:** Two places generate citation labels: the LLM prompt context block (in `generator.py`) and the structured citations list (in `citation_builder.py`). Both must be kept in sync.
**How to avoid:** `_build_context_block()` and `build_citations()` both read `metadata["source_domain"]` with the same fallback logic (`"accounting"` if absent). The label mapping (`"consulting"` → `"Kerangka"`, else → `"Sumber"`) is defined once in a shared helper or duplicated carefully with a test that checks both paths.
**Warning signs:** LLM response body references a different label than the citation list below it.

### Pitfall 4: source_domain Missing from metadata dict in search results
**What goes wrong:** `hybrid_search` returns results with a `metadata` dict that doesn't include `source_domain`. `citation_builder.build_citation()` falls back to `"accounting"` label silently — consulting chunks get labeled `[Sumber N]`.
**Why it happens:** `hybrid_search` currently builds the `metadata` dict with an explicit list of fields. `source_domain` must be added to that list.
**How to avoid:** In `vector_search.py`, the `metadata` dict construction reads `payload.get("source_domain", "accounting")` and includes it in the returned metadata. Add a test that verifies `source_domain` is present in returned results.
**Warning signs:** All citations show `[Sumber N]` even for consulting books.

### Pitfall 5: --source-domain flag breaks existing ingest.py callers
**What goes wrong:** Adding a required `--source-domain` argument breaks scripts or CI pipelines that call `scripts/ingest.py` without the flag.
**Why it happens:** argparse required argument vs optional with default.
**How to avoid:** Use `default="accounting"` — no flag means accounting. Existing callers are unaffected. The flag is only needed for Phase 08 consulting ingestion.
**Warning signs:** `error: the following arguments are required: --source-domain` in CI logs.

---

## Code Examples

### Verified: scroll signature (qdrant-client 1.17.1)
```python
# Source: live introspection of qdrant_client.QdrantClient installed in project
records, next_offset = client.scroll(
    collection_name=name,
    scroll_filter=Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="source_domain"))]),
    limit=100,
    with_payload=False,  # don't need payload content, just IDs
    with_vectors=False,
    offset=None,        # start from beginning; pass next_offset to paginate
)
```

### Verified: set_payload with filter (qdrant-client 1.17.1)
```python
# Source: live introspection — set_payload accepts Filter as 'points' argument
result = client.set_payload(
    collection_name=name,
    payload={"source_domain": "accounting"},
    points=Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="source_domain"))]),
    wait=True,
)
```

### Verified: count with filter (qdrant-client 1.17.1)
```python
# Source: live introspection — count accepts count_filter argument
total = client.count(collection_name=name, exact=True).count
tagged = client.count(
    collection_name=name,
    count_filter=Filter(
        must=[FieldCondition(key="source_domain", match=MatchValue(value="accounting"))]
    ),
    exact=True,
).count
```

### Verified: Prefetch.filter field (qdrant-client 1.17.1)
```python
# Source: Prefetch.model_fields.keys() == dict_keys(['prefetch','query','using','filter',...])
Prefetch(
    query=NearestQuery(nearest=query_embedding),
    using="dense",
    limit=top_k,
    filter=Filter(must=[FieldCondition(key="source_domain", match=MatchValue(value="accounting"))]),
)
```

### Verified: IsEmptyCondition + PayloadField construction
```python
# Source: live construction — Filter(must=[IsEmptyCondition(is_empty=PayloadField(key='source_domain'))]) confirmed valid
from qdrant_client.models import Filter, IsEmptyCondition, PayloadField
f = Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="source_domain"))])
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini: testpaths=tests, addopts=--timeout=30 -q) |
| Config file | `pytest.ini` in project root |
| Quick run command | `uv run pytest tests/test_domain_retrieval.py tests/test_domain_citation.py -x` |
| Full suite command | `uv run pytest -m "not integration and not gpu"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETR-01 | `hybrid_search(domain_filter="accounting")` passes Filter to both Prefetch objects; `domain_filter=None` passes no filter | unit | `uv run pytest tests/test_domain_retrieval.py::test_domain_filter_passed_to_prefetch -x` | Wave 0 |
| RETR-01 | `hybrid_search(domain_filter="consulting")` returns only consulting-tagged results (mock) | unit | `uv run pytest tests/test_domain_retrieval.py::test_domain_filter_consulting -x` | Wave 0 |
| RETR-01 | `hybrid_search()` with no domain_filter returns results from both domains (mock) | unit | `uv run pytest tests/test_domain_retrieval.py::test_no_domain_filter_returns_all -x` | Wave 0 |
| RETR-02 | `upload_batch` includes `source_domain` in Qdrant point payload | unit | `uv run pytest tests/test_domain_retrieval.py::test_upload_batch_includes_source_domain -x` | Wave 0 |
| RETR-02 | Backfill script: `set_payload` called with `IsEmptyCondition` filter and `{"source_domain": "accounting"}` | unit | `uv run pytest tests/test_domain_retrieval.py::test_backfill_calls_set_payload -x` | Wave 0 |
| RETR-02 | Backfill script: verification step asserts total == tagged count | unit | `uv run pytest tests/test_domain_retrieval.py::test_backfill_verification -x` | Wave 0 |
| RETR-03 | `_build_context_block` emits `[Sumber N]` for `source_domain="accounting"` chunks | unit | `uv run pytest tests/test_domain_citation.py::test_accounting_citation_label -x` | Wave 0 |
| RETR-03 | `_build_context_block` emits `[Kerangka N]` for `source_domain="consulting"` chunks | unit | `uv run pytest tests/test_domain_citation.py::test_consulting_citation_label -x` | Wave 0 |
| RETR-03 | `build_citations` includes `source_domain` field in returned citation dicts | unit | `uv run pytest tests/test_domain_citation.py::test_citations_include_source_domain -x` | Wave 0 |
| RETR-03 | `hybrid_search` returns metadata with `source_domain` field | unit | `uv run pytest tests/test_domain_retrieval.py::test_search_results_include_source_domain -x` | Wave 0 |
| RETR-04 | `scripts/ingest.py` argparse: `--source-domain consulting` sets source_domain in pipeline call | unit | `uv run pytest tests/test_domain_retrieval.py::test_ingest_source_domain_flag -x` | Wave 0 |
| RETR-04 | `run_ingestion_pipeline` threads `source_domain` into chunk metadata | unit | `uv run pytest tests/test_domain_retrieval.py::test_pipeline_threads_source_domain -x` | Wave 0 |
| RETR-04 | No `--source-domain` flag defaults to `"accounting"` — existing ingest callers unaffected | unit | `uv run pytest tests/test_domain_retrieval.py::test_ingest_default_source_domain -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_domain_retrieval.py tests/test_domain_citation.py -x`
- **Per wave merge:** `uv run pytest -m "not integration and not gpu"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_domain_retrieval.py` — covers RETR-01, RETR-02, RETR-04 (hybrid_search filter, upload_batch payload, backfill, ingest flag)
- [ ] `tests/test_domain_citation.py` — covers RETR-03 (citation label differentiation)

*(Existing `tests/test_retrieval.py` covers the no-filter hybrid_search path — extend it or keep new tests separate. Separate files are cleaner for this phase's scope.)*

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `qdrant-client` | RETR-01, RETR-02, RETR-04 | Yes | 1.17.1 | — |
| Qdrant Cloud (live) | RETR-02 backfill script execution | Assumed yes (pre-existing collection) | Cloud Free Tier | — |
| Python 3.11 | All | Yes | pinned in `.python-version` | — |
| `uv` | Test runner, pipeline | Yes | present | — |

**Missing dependencies with no fallback:** None.

**Note for backfill script execution:** The script requires a live Qdrant connection (`QDRANT_URL` + `QDRANT_API_KEY` in `.env`). It is not a test — it is a one-time operational script run manually before Phase 08 begins. It is safe to run in production because `set_payload` with `IsEmptyCondition` is idempotent and does not touch vectors.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qdrant filter via `scroll_filter` (legacy) | `Prefetch.filter` for per-vector-type filtering in hybrid search | qdrant-client ≥1.7 (query API) | Filters apply pre-fusion — semantically correct for domain isolation |
| `set_payload` per-point loop | `set_payload(points=Filter(...))` bulk update | qdrant-client ≥1.0 | Single API call; no pagination needed for payload-only updates |

---

## Open Questions

1. **How many existing points need backfill?**
   - What we know: The collection `trusty_rag_akmen` holds all ingested accounting textbook chunks; the CLAUDE.md notes 20-30 textbooks for v1. A typical book produces 2,000-8,000 child chunks.
   - What's unclear: Exact point count without a live Qdrant query.
   - Recommendation: The backfill script should log the count before and after. The operation is O(1) API calls regardless of point count (server-side filter) — point count does not affect the script design.

2. **Should retrieve_node pass domain_filter in Phase 07?**
   - What we know: RETR-01 says the retrieval pipeline *can* filter by domain, not that it *must*. Phase 07 success criterion 1 uses "a retrieval call with domain_filter" — implying explicit test, not always-on in production.
   - What's unclear: Whether `retrieve_node` in `nodes.py` should pass `domain_filter` during Phase 07 or wait for Phase 08.
   - Recommendation: Phase 07 builds the infrastructure (parameter exists, tested, works). `retrieve_node` stays with `domain_filter=None` in Phase 07 production code. Phase 08 or a dedicated routing decision in `route_node` activates it when consulting books are actually indexed. This prevents RETR-02's catastrophic failure mode during Phase 07 itself.

---

## Sources

### Primary (HIGH confidence)
- Live `qdrant-client==1.17.1` introspection in project venv — `set_payload`, `scroll`, `count`, `create_payload_index` signatures, `Prefetch.model_fields`, `IsEmptyCondition`, `PayloadField` construction all verified via `uv run python -c` calls
- Project source files: `src/retrieval/vector_search.py`, `src/generation/generator.py`, `src/generation/citation_builder.py`, `src/ingestion/indexing/qdrant_uploader.py`, `src/ingestion/pipeline.py`, `scripts/ingest.py` — all read in full

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` v1.1 — RETR-01 through RETR-04 requirement text (verbatim)
- `.planning/milestones/v1.1-ROADMAP.md` — Phase 07 success criteria (verbatim), ordering rationale
- `.planning/PROJECT.md` — v1.1 Key Decisions section (out-of-scope rationale for separate collections)

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — qdrant-client 1.17.1 installed; all APIs introspected live
- Architecture: HIGH — all touch-points identified from full source read; no guessing
- Pitfalls: HIGH — backfill ordering pitfall is documented in roadmap; others derived from code inspection
- Runtime state: HIGH — one live migration item (Qdrant points); no other runtime state affected

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (qdrant-client is stable; Qdrant Cloud API has been stable for 18+ months)
