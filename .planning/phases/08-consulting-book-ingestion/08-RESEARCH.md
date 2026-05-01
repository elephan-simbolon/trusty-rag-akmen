# Phase 08: Consulting Book Ingestion - Research

**Researched:** 2026-03-30
**Domain:** Batch PDF ingestion using existing pipeline with VLM disabled and `author` metadata added
**Confidence:** HIGH

## Summary

Phase 08 ingests 21 consulting/methodology books into the existing Qdrant collection using the pipeline built in Phases 01-07. The infrastructure is complete: `--source-domain consulting` flag exists in `scripts/ingest.py`, `run_ingestion_pipeline()` stamps `source_domain` into every chunk's metadata, `upload_batch` spreads that into the Qdrant point payload, and the `[Kerangka N]` citation label is already live. Phase 08 has exactly three new concerns compared to a normal accounting book ingestion.

**Concern 1 — VLM captioning must be disabled.** The current pipeline unconditionally calls `extract_and_caption_diagrams()` in Step 2. There is no `use_vlm` parameter — the function always runs and finds any images in the parsed output directory. For 21 consulting books this could generate ~210 VLM calls, consuming SiliconFlow rate limit budget budgeted for accounting queries. The pipeline needs a `use_vlm: bool = True` parameter (defaulting True to not break existing accounting ingestion) that gates the Step 2 call. The `--no-vlm` flag in `scripts/ingest.py` passes it through.

**Concern 2 — `author` field is not in the current ingestion pipeline.** The INGEST-02 success criterion explicitly requires `author` in chunk metadata. `citation_builder.build_citation()` already reads `metadata.get("author", "")` and prefixes it to the formatted citation string — but the ingestion pipeline (`enrich_metadata`, `run_ingestion_pipeline`) never sets `author`. The `REQUIRED_METADATA_FIELDS` list in `metadata_enricher.py` does not include `author`. Phase 08 must add an `--author` CLI argument to `ingest.py` and thread it into every chunk's metadata dict, parallel to how `source_domain` was added in Phase 07. The `author` field is optional (defaults to `""`) — existing accounting ingestion callers are unaffected.

**Concern 3 — No consulting PDFs exist yet in `data/pdfs/`.** The directory contains only 9 accounting textbooks. The 21 consulting PDFs must be collected and placed (or symlinked) into `data/pdfs/consulting/` before ingestion can run. There is no book list in the codebase — it must be sourced externally (user-supplied). The dry-run approach (3 books first, validate chunk counts, then full 21) is the safe path given the 2,800-12,600 chunk count variance documented in STATE.md.

**Primary recommendation:** Two plans — (1) Pipeline extension: add `use_vlm` parameter + `--no-vlm` flag + `author` parameter + `--author` flag to ingest.py and pipeline.py. (2) Operational ingestion: dry-run 3 books, verify metadata and retrieval, then full 21-book batch with monitoring.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | 21 buku consulting/methodology di-ingest ke Qdrant dengan source_domain="consulting" melalui existing PDF parsing pipeline (Docling primary) | `--source-domain consulting` flag already exists in `scripts/ingest.py` (Phase 07 RETR-04); `run_ingestion_pipeline` accepts `source_domain` parameter; only gap is `use_vlm` disable and PDF file availability |
| INGEST-02 | Setiap chunk consulting memiliki metadata lengkap (book_title, chapter, page_start, page_end, author, source_domain) konsisten dengan format accounting chunks | `author` field NOT currently set by ingestion pipeline — `enrich_metadata()` has no author param, `run_ingestion_pipeline` has no author param, `scripts/ingest.py` has no `--author` flag. `citation_builder.build_citation()` already reads `metadata.get("author", "")` gracefully. Gap: add `--author` flag to ingest.py + `author` param to pipeline |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11 (pinned in `.python-version`)
- No new dependencies — all required libraries already installed
- `uv run pytest` — 30s timeout per test, pytest-timeout enforced; `uv run pytest -m "not integration and not gpu"` for full unit suite
- Test markers: `integration` (live services), `e2e`, `gpu` — Phase 08 unit tests must be pure unit (no live Qdrant, no live SiliconFlow)
- Bilingual convention: Indonesian prose + English technical terms in parentheses
- All documentation in Indonesian; English for code identifiers
- Ruff lint: line-length 100, `select = ["E", "F", "I"]`, `ignore = ["E501"]`
- Consulting books → Qdrant only, skip fast-graphrag (locked decision from STATE.md)
- VLM captioning disabled for consulting books (`use_vlm=False`) — locked decision from STATE.md
- Single Qdrant collection with payload filter — no separate collection for consulting domain (locked, REQUIREMENTS.md Out of Scope)
- RETR-02 backfill is confirmed complete: 9845/9845 Qdrant points carry `source_domain="accounting"` — domain filter is safe to activate in Phase 08

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `src/ingestion/pipeline.py` | existing | End-to-end PDF→Qdrant orchestration | Already handles parsing, chunking, embedding, upload |
| `scripts/ingest.py` | existing | CLI entry point | Already has `--source-domain`, `--replace`, `--contextual` flags |
| `qdrant-client` | 1.17.1 (installed) | Upload, verify, scroll | All required APIs confirmed present |
| `docling` | installed | PDF parsing (Docling primary, MinerU fallback) | Confirmed available: `import docling` succeeds |
| Python `argparse` | stdlib 3.11 | `--author`, `--no-vlm` CLI flags | Consistent with existing `ingest.py` pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `src/ingestion/parsing/vlm_captioner.py` | existing | `extract_and_caption_diagrams()` — disabled via `use_vlm=False` | Still runs for accounting ingestion; gated by new parameter |
| `src/ingestion/chunking/metadata_enricher.py` | existing | `enrich_metadata()` — add `author` param | Called per chunk in pipeline Step 4 |
| `data/checkpoints/` | existing | Checkpoint resume on embedding rate limit | Automatically used; no changes needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `--no-vlm` flag (boolean) | `--vlm / --no-vlm` flag pair | `--no-vlm` is cleaner for consulting use case; boolean store_false pattern matches `--replace` flag pattern in ingest.py |
| `--author` CLI flag per book | CSV manifest with book metadata | CLI flag is consistent with existing `--book-title` pattern; manifest adds complexity and a new file format. For 21 books the CLI flag approach is sufficient |
| `data/pdfs/consulting/` subdirectory | flat `data/pdfs/` with all books | Subdirectory keeps consulting PDFs separate from accounting; prevents accidental re-ingestion of accounting books with wrong `--source-domain` |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
scripts/
└── ingest.py                          # EXTEND: add --author + --no-vlm flags

src/
└── ingestion/
    ├── pipeline.py                    # EXTEND: add use_vlm + author params
    └── chunking/
        └── metadata_enricher.py       # EXTEND: add author param to enrich_metadata()

data/
└── pdfs/
    └── consulting/                    # NEW: place 21 consulting PDFs here
        ├── McKinsey_Way.pdf
        ├── ...
        └── [20 more PDFs]

tests/
└── test_consulting_ingestion.py       # NEW: unit tests for INGEST-01, INGEST-02
```

No new source modules needed. All changes are additive extensions to existing files.

### Pattern 1: Disabling VLM Captioning

**What:** Add `use_vlm: bool = True` parameter to `run_ingestion_pipeline()`. When `False`, replace Step 2's `extract_and_caption_diagrams()` call with `diagram_captions = []` and log a skip message.

**When to use:** `--no-vlm` flag in `scripts/ingest.py` passes `use_vlm=False` for consulting ingestion. Default `True` preserves existing accounting behavior.

```python
# In scripts/ingest.py — new flag
parser.add_argument(
    "--no-vlm",
    action="store_true",
    default=False,
    help="Disable VLM diagram captioning (default: enabled). Use for consulting books to conserve API rate limit.",
)

# Passed to pipeline:
result = run_ingestion_pipeline(
    ...
    use_vlm=not args.no_vlm,
)

# In src/ingestion/pipeline.py — gated Step 2
def run_ingestion_pipeline(
    ...,
    use_vlm: bool = True,
) -> dict:
    ...
    # Step 2: Diagram captioning
    if use_vlm:
        logger.info("[2/9] Extracting and captioning diagrams...")
        diagram_captions = extract_and_caption_diagrams(output_dir)
        logger.info(f"Captioned {len(diagram_captions)} diagrams")
    else:
        diagram_captions = []
        logger.info("[2/9] VLM captioning SKIPPED (use_vlm=False)")
```

### Pattern 2: Adding `author` to Chunk Metadata

**What:** Add `author: str = ""` to `run_ingestion_pipeline()` signature and `scripts/ingest.py` argparse. Thread it into `enrich_metadata()` and explicitly stamp it on every chunk in the `all_chunks` assembly loop, parallel to how `source_domain` is stamped.

**Why stamp separately instead of adding to `enrich_metadata()`:** `enrich_metadata()` extracts page markers and classifies content — it does not know book-level metadata like author. The stamping pattern is already established for `source_domain` in pipeline.py line 115. Repeat the pattern for `author`.

```python
# In scripts/ingest.py — new flag
parser.add_argument(
    "--author",
    default="",
    help="Book author(s) for metadata (default: empty). Example: 'Ethan Rasiel'",
)

# Passed to pipeline:
result = run_ingestion_pipeline(
    ...
    author=args.author,
)

# In src/ingestion/pipeline.py — stamp in Step 4 loop alongside source_domain
for sub in sub_chunks:
    enriched = enrich_metadata(
        chunk_text=sub,
        book_title=book_title,
        chapter=chapter,
        section_path=section_path,
        content_type=content_type.value,
    )
    enriched["metadata"]["source_domain"] = source_domain  # existing (Phase 07)
    enriched["metadata"]["author"] = author                 # NEW (Phase 08)
    all_chunks.append(enriched)

# Also stamp diagram chunks if VLM is enabled:
for dc in diagram_captions:
    if not dc["caption"].startswith("[Captioning failed"):
        all_chunks.append(
            {
                "text": dc["caption"],
                "metadata": {
                    "book_title": book_title,
                    "chapter": "Diagrams",
                    "section_path": f"{book_title} > Diagrams",
                    "content_type": "diagram",
                    "page_start": 0,
                    "page_end": 0,
                    "source_domain": source_domain,
                    "author": author,              # NEW (Phase 08)
                },
            }
        )
```

### Pattern 3: Dry-Run Before Full Ingestion

**What:** Ingest 3 representative consulting books first, verify chunk counts and metadata completeness, then proceed with the remaining 18. This is the operational safety pattern documented in STATE.md.

**Dry-run command:**
```bash
# 3-book dry run
uv run python scripts/ingest.py \
    "data/pdfs/consulting/Book1.pdf" \
    "data/pdfs/consulting/Book2.pdf" \
    "data/pdfs/consulting/Book3.pdf" \
    --source-domain consulting \
    --author "Author Name" \
    --no-vlm

# Verify chunks in Qdrant
uv run python -c "
from qdrant_client import QdrantClient
from config.settings import settings
from qdrant_client.models import FieldCondition, Filter, MatchValue
api_key = settings.qdrant_api_key
if hasattr(api_key, 'get_secret_value'):
    api_key = api_key.get_secret_value()
client = QdrantClient(url=settings.qdrant_url, api_key=api_key)
count = client.count(
    collection_name=settings.qdrant_collection_name,
    count_filter=Filter(must=[FieldCondition(key='source_domain', match=MatchValue(value='consulting'))]),
    exact=True
).count
print(f'Consulting chunks: {count}')
"
```

**Full batch command (after dry-run validated):**
```bash
# All 21 books (if all PDFs are in a directory)
uv run python scripts/ingest.py data/pdfs/consulting/ \
    --source-domain consulting \
    --no-vlm
    # Note: --author must be set per book when authors differ
    # For batch with mixed authors, run books individually or add a manifest
```

**Note on per-book author flag:** Since `--author` is a single value per CLI invocation and consulting books have different authors, the full batch with a directory argument sets one author for all books in that call. For books with distinct authors, run individually or in author-grouped batches. This is not a code problem — it is an operational workflow decision.

### Pattern 4: Domain Filter Activation

**What:** Once consulting books are indexed, `retrieve_node` in `nodes.py` can be updated to pass `domain_filter` based on the routed query type. Consulting-specific queries (MECE, issue tree, structured problem solving) get `domain_filter="consulting"`; accounting queries get `domain_filter="accounting"`; general queries pass `domain_filter=None`.

**When:** This is post-ingestion wiring. The infrastructure is ready (Phase 07). The actual `domain_filter` activation logic in `nodes.py` is optional for Phase 08 — Phase 08's success criterion only requires that consulting chunks are retrievable, not that domain filtering is mandatory. However, if the planner wants to make consulting retrieval automatic, this is the correct hook.

```python
# In src/agents/nodes.py — retrieve_node (optional Phase 08 extension)
def retrieve_node(state: RAGState) -> RAGState:
    query_type = state.get("query_type", "General")
    # Domain filter: consulting queries prefer consulting corpus
    domain_filter = None
    if "consulting" in state.get("protocol_key", ""):
        domain_filter = "consulting"
    results = hybrid_search(
        query_embedding=state["query_embedding"],
        query_text=state["processed_query"],
        domain_filter=domain_filter,
    )
    ...
```

### Anti-Patterns to Avoid

- **Run VLM captioning on 21 consulting books without `--no-vlm`:** 21 books × ~10 images = ~210 VLM calls at SiliconFlow. This consumes rate limit budget allocated for query-time operations and costs real money per the $8-35/month budget constraint.
- **Ingest all 21 books without dry-run first:** The chunk count estimate is 2,800-12,600 (STATE.md). A poorly structured consulting PDF (e.g., heavy tables, scanned pages) can produce 0 useful chunks. Validate 3 books first.
- **Omit `--author` flag:** The INGEST-02 requirement explicitly requires `author` in chunk metadata for consulting books. Without it, `citation_builder.build_citation()` formats citations as "McKinsey Way, Chapter 1, hal. 22" instead of "Ethan Rasiel, McKinsey Way, Chapter 1, hal. 22" — degrading citation quality for client-facing use.
- **Ingest consulting books without `--source-domain consulting`:** They will be tagged `source_domain="accounting"` (the default) and intermixed with accounting chunks. The domain filter built in Phase 07 will not separate them correctly.
- **Use `--replace` for existing books without verifying intent:** `--replace` deletes all Qdrant points for the book_title before re-indexing. For consulting books being ingested fresh (first time), `--replace` is not needed and risks accidental deletion if a book_title collision exists.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF parsing for consulting books | Custom parser | `route_and_parse()` in `src/ingestion/parsing/router.py` | Already handles Docling (text PDFs) / MinerU (scanned) routing; 9 books already ingested successfully |
| Chunking consulting content | Type-specific splitter | `classify_element()` + `split_content_by_type()` | Content types (narrative_text, table, formula, example) apply to consulting books as well; formula type will rarely trigger but does no harm |
| Embedding consulting chunks | Separate embedding logic | `embed_chunks_batch()` with checkpoint resume | Same Qwen3-Embedding-8B via SiliconFlow; same asymmetric embedding pattern; checkpointing handles rate limit interruptions |
| Verifying post-ingestion metadata | Manual Qdrant scroll | `client.count(count_filter=Filter(FieldCondition("source_domain","consulting")))` | Native Qdrant aggregation; one call verifies all chunks tagged correctly |
| Batch ingestion of 21 books | Custom orchestration loop | `scripts/ingest.py data/pdfs/consulting/` | ingest.py already iterates `path.glob("*.pdf")` when given a directory argument |

**Key insight:** Phase 08 is primarily an operational phase — the code changes (VLM gate + author field) are small (< 30 lines across 3 files). The bulk of work is PDF collection, per-book author metadata, and batch execution with monitoring.

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Qdrant `trusty_rag_akmen`: 9845 points, all `source_domain="accounting"`, 0 consulting points | Ingest 21 consulting books → consulting points added (no migration of existing points needed) |
| Live service config | Qdrant Cloud free tier — single collection, `source_domain` payload index already exists (Phase 07) | None — index created in Phase 07; new consulting chunks pick up the index automatically |
| OS-registered state | None — no Task Scheduler, pm2, or systemd entries | None |
| Secrets/env vars | `SILICONFLOW_API_KEY` — used for embedding; `QDRANT_URL` + `QDRANT_API_KEY` — used for upload. No new keys needed | None |
| Build artifacts | `data/chunks/` — 9 accounting `*_chunks.json` files. Consulting books will add 21 new `*_chunks.json` files here as the JSON backup step in pipeline | After ingestion, `data/pdfs/consulting/` and `data/chunks/*consulting*` will be the new artifacts |
| PDF source files | `data/pdfs/consulting/` does NOT exist — 21 consulting PDFs are not present | User must supply 21 PDF files and place them in `data/pdfs/consulting/` before ingestion can run |

---

## Common Pitfalls

### Pitfall 1: VLM Step Runs on Consulting Books
**What goes wrong:** `extract_and_caption_diagrams()` scans `output_dir` for any `.png/.jpg/.jpeg/.gif/.webp` files Docling extracted. Consulting books like McKinsey Way contain frameworks/charts. Each image gets a VLM API call. 21 books × ~10 images = ~210 calls at ~$0.002-0.005/call = $0.42-1.05 unbudgeted cost + SiliconFlow rate limit consumption.
**Why it happens:** No `use_vlm` parameter exists — the function is unconditionally called in Step 2.
**How to avoid:** Add `use_vlm: bool = True` parameter to `run_ingestion_pipeline()`. Gate Step 2 with `if use_vlm:`. Add `--no-vlm` flag to `ingest.py`.
**Warning signs:** SiliconFlow dashboard shows unexpected `/chat/completions` calls with `Qwen2.5-VL-72B` model during ingestion.

### Pitfall 2: `author` Field Missing from Consulting Chunks
**What goes wrong:** INGEST-02 requires `author` in every consulting chunk's metadata. Without the `--author` flag and pipeline support, `citation_builder.build_citation()` emits "McKinsey Way, Problem Structuring, hal. 22" instead of "Ethan Rasiel, McKinsey Way, Problem Structuring, hal. 22". The citation quality degrades for client-facing use.
**Why it happens:** `enrich_metadata()` signature has no `author` parameter. `REQUIRED_METADATA_FIELDS` does not list `author`. The pipeline never sets it.
**How to avoid:** Add `author: str = ""` to `run_ingestion_pipeline()` and `scripts/ingest.py --author`. Stamp `enriched["metadata"]["author"] = author` in Step 4 (same pattern as `source_domain`). Validate with: `uv run pytest tests/test_consulting_ingestion.py::test_pipeline_stamps_author -x`.
**Warning signs:** `build_citations()` returns dicts where `"author": ""` for all consulting chunks.

### Pitfall 3: Accounting Chunks Accidentally Tagged as Consulting
**What goes wrong:** Running `scripts/ingest.py data/pdfs/ --source-domain consulting` on the accounting PDF directory tags all accounting books as consulting, corrupting the corpus.
**Why it happens:** `data/pdfs/` contains all books (accounting + consulting). The `--source-domain` flag applies to all PDFs in one CLI invocation.
**How to avoid:** Place consulting PDFs in `data/pdfs/consulting/` subdirectory. Ingest with `scripts/ingest.py data/pdfs/consulting/ --source-domain consulting`. Never run with `--source-domain consulting` against the parent `data/pdfs/` directory.
**Warning signs:** After ingestion, `client.count(filter=source_domain="accounting")` < 9845.

### Pitfall 4: Chunk Count Explosion on Dense Consulting PDFs
**What goes wrong:** Some consulting books (dense narrative, small font, 300+ pages) produce 3,000+ child chunks. After 21 books this could approach the Qdrant Cloud free tier point limit.
**Why it happens:** Consulting methodology books have long continuous narrative sections that recursive splitting creates many child chunks from.
**How to avoid:** Dry-run with 3 representative books first. Check the chunks JSON file size: `ls -lh data/chunks/*_chunks.json`. If a single book produces > 1,500 chunks, consider increasing the parent-child split threshold or filtering to `narrative_text` + `example_problem` types only (as done in graphrag ingestion — see CLAUDE.md).
**Warning signs:** `data/chunks/BookName_chunks.json` > 2MB; pipeline logs `Child chunks for indexing: > 1500`.

### Pitfall 5: Docling Fails on Scanned Consulting PDFs
**What goes wrong:** Some consulting books are scanned PDFs (no text layer). Docling produces empty or near-empty markdown. The pipeline produces 0 useful chunks. MinerU subprocess fallback requires a working GPU.
**Why it happens:** `route_and_parse()` in `src/ingestion/parsing/router.py` detects text vs scanned PDFs via PyMuPDF. Scanned PDFs trigger MinerU which requires the GTX 1660 Ti (6GB) and the `--vram 6 --backend pipeline` config.
**How to avoid:** In the dry-run, inspect the first 200 chars of each book's parsed markdown: `uv run python scripts/test_query.py "issue tree" -v`. If a consulting book produces 0 relevant chunks in retrieval, check `data/parsed/` for the book's markdown file to verify parsing quality.
**Warning signs:** Pipeline logs `Parsed with MinerU` (indicates scanned PDF) or `Found 0 sections` after heading split.

---

## Code Examples

### Adding `use_vlm` parameter to pipeline

```python
# Source: src/ingestion/pipeline.py — lines 30-38 (current signature)
def run_ingestion_pipeline(
    pdf_path: str,
    output_dir: str = "data/parsed",
    chunks_dir: str = "data/chunks",
    book_title: str = "",
    checkpoint_dir: str = "data/checkpoints",
    replace_existing: bool = False,
    use_contextual: bool = False,
    source_domain: str = "accounting",
    use_vlm: bool = True,          # NEW: gate VLM captioning in Step 2
    author: str = "",              # NEW: book-level author for chunk metadata
) -> dict:
```

### Gated Step 2 in pipeline

```python
# Source: src/ingestion/pipeline.py — Step 2 block (lines 89-92 currently)
if use_vlm:
    logger.info("[2/9] Extracting and captioning diagrams...")
    diagram_captions = extract_and_caption_diagrams(output_dir)
    logger.info(f"Captioned {len(diagram_captions)} diagrams")
else:
    diagram_captions = []
    logger.info("[2/9] VLM captioning SKIPPED (use_vlm=False) — consulting book mode")
```

### Stamping `author` in Step 4 alongside `source_domain`

```python
# Source: src/ingestion/pipeline.py — Step 4 loop (line 115 currently adds source_domain)
enriched["metadata"]["source_domain"] = source_domain  # existing
enriched["metadata"]["author"] = author                 # NEW
```

### Verifying consulting ingestion from Python

```python
# Post-ingestion verification (operational, not a test)
from qdrant_client import QdrantClient
from config.settings import settings
from qdrant_client.models import FieldCondition, Filter, MatchValue

api_key = settings.qdrant_api_key
if hasattr(api_key, 'get_secret_value'):
    api_key = api_key.get_secret_value()
client = QdrantClient(url=settings.qdrant_url, api_key=api_key)

consulting_count = client.count(
    collection_name=settings.qdrant_collection_name,
    count_filter=Filter(
        must=[FieldCondition(key="source_domain", match=MatchValue(value="consulting"))]
    ),
    exact=True,
).count
print(f"Consulting chunks in Qdrant: {consulting_count}")

# Sample a consulting point to verify metadata completeness
results, _ = client.scroll(
    collection_name=settings.qdrant_collection_name,
    scroll_filter=Filter(
        must=[FieldCondition(key="source_domain", match=MatchValue(value="consulting"))]
    ),
    limit=3,
    with_payload=True,
    with_vectors=False,
)
for r in results:
    print(r.payload)
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini: testpaths=tests, addopts=--timeout=30 -q) |
| Config file | `pytest.ini` in project root |
| Quick run command | `uv run pytest tests/test_consulting_ingestion.py -x` |
| Full suite command | `uv run pytest -m "not integration and not gpu"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | `run_ingestion_pipeline` called with `use_vlm=False` does NOT call `extract_and_caption_diagrams` | unit | `uv run pytest tests/test_consulting_ingestion.py::test_no_vlm_skips_captioning -x` | Wave 0 |
| INGEST-01 | `run_ingestion_pipeline` with `use_vlm=True` (default) still calls `extract_and_caption_diagrams` | unit | `uv run pytest tests/test_consulting_ingestion.py::test_vlm_enabled_by_default -x` | Wave 0 |
| INGEST-01 | `scripts/ingest.py --no-vlm` passes `use_vlm=False` to `run_ingestion_pipeline` | unit | `uv run pytest tests/test_consulting_ingestion.py::test_no_vlm_flag_exists -x` | Wave 0 |
| INGEST-01 | `scripts/ingest.py` without `--no-vlm` defaults to `use_vlm=True` | unit | `uv run pytest tests/test_consulting_ingestion.py::test_vlm_default_true -x` | Wave 0 |
| INGEST-02 | `run_ingestion_pipeline` stamps `author` from parameter into every chunk's metadata dict | unit | `uv run pytest tests/test_consulting_ingestion.py::test_pipeline_stamps_author -x` | Wave 0 |
| INGEST-02 | `run_ingestion_pipeline` with empty `author=""` stamps empty string (not None) — graceful fallback | unit | `uv run pytest tests/test_consulting_ingestion.py::test_pipeline_stamps_empty_author -x` | Wave 0 |
| INGEST-02 | `scripts/ingest.py --author "Ethan Rasiel"` passes `author="Ethan Rasiel"` to `run_ingestion_pipeline` | unit | `uv run pytest tests/test_consulting_ingestion.py::test_author_flag_forwarded -x` | Wave 0 |
| INGEST-02 | `scripts/ingest.py` without `--author` defaults to `author=""` — existing callers unaffected | unit | `uv run pytest tests/test_consulting_ingestion.py::test_author_default_empty -x` | Wave 0 |
| INGEST-02 | `run_ingestion_pipeline` with `source_domain="consulting"` and `author="Test Author"` stamps both fields into chunks | unit | `uv run pytest tests/test_consulting_ingestion.py::test_consulting_chunk_has_author_and_domain -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_consulting_ingestion.py -x`
- **Per wave merge:** `uv run pytest -m "not integration and not gpu"`
- **Phase gate:** Full unit suite green + human UAT (test_query.py with consulting framework query returns `[Kerangka N]` citations)

### Wave 0 Gaps

- [ ] `tests/test_consulting_ingestion.py` — covers INGEST-01 (VLM gate: 4 tests) and INGEST-02 (author field: 5 tests). Does NOT exist yet.

*(Existing `tests/test_incremental_ingestion.py` covers the `replace_existing` and `check_book_exists` path — reuse its `_make_pipeline_mocks()` helper pattern for the new test file.)*

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `docling` | INGEST-01 PDF parsing | Yes | installed (import succeeds) | MinerU (GPU required) |
| `uv` | Test runner, pipeline | Yes | 0.10.12 | — |
| Python 3.11 | All | Yes (via uv venv) | pinned `.python-version` | — |
| `qdrant-client` | Upload, verify | Yes | 1.17.1 | — |
| Qdrant Cloud (live) | Ingestion upload, post-ingestion verification | Yes | Free tier, 9845 points currently | — |
| `SILICONFLOW_API_KEY` | Embedding (Step 8-9) | Assumed yes (.env present) | — | — |
| 21 consulting PDFs | INGEST-01 core requirement | NOT PRESENT | — | User must supply |
| GTX 1660 Ti GPU | MinerU fallback for scanned PDFs | Yes (local) | 6GB VRAM | Skip scanned books if GPU unavailable |

**Missing dependencies with no fallback:**
- 21 consulting PDF files — must be supplied by user before ingestion can execute. This is the single blocking dependency for the operational phase.

**Missing dependencies with fallback:**
- GPU (for scanned PDFs) — if consulting PDFs are all text-based (Docling path), GPU not needed. If any are scanned, MinerU requires the GTX 1660 Ti.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| VLM always runs | `use_vlm=False` gates captioning | Phase 08 (this phase) | Saves ~210 API calls for 21 consulting books |
| No `author` field in ingestion pipeline | `author` param threads into chunk metadata | Phase 08 (this phase) | `build_citation()` now formats consulting citations with author prefix |
| Domain filter inactive (no consulting data) | `domain_filter="consulting"` safe to use after Phase 08 | Phase 08 (activation point) | Enables per-domain retrieval tuning in `retrieve_node` |

**Note on current accounting chunks:** Existing 9845 accounting points in Qdrant have `author=""` (or absent — `citation_builder.build_citation()` uses `.get("author", "")` with graceful fallback). This is acceptable — the `author` field was never populated for accounting books in v1.0 and is not required retroactively.

---

## Open Questions

1. **What are the 21 consulting books?**
   - What we know: STATE.md and REQUIREMENTS.md reference "21 consulting/methodology books" but no book list exists in the codebase. No consulting PDFs exist in `data/pdfs/`.
   - What's unclear: The specific titles, authors, and whether they are text-based or scanned PDFs.
   - Recommendation: The planner should include a Wave 0 task asking the user to place PDFs in `data/pdfs/consulting/`. The ingestion plan should not hard-code book names. The dry-run pattern handles unknown book quality.

2. **Should `domain_filter` activation in `retrieve_node` be part of Phase 08?**
   - What we know: Phase 08 success criterion #2 requires "a query about a consulting framework returns chunks from the consulting corpus with `[Kerangka N]` citation labels." This can be satisfied by testing with `hybrid_search(domain_filter=None)` (no filter) — consulting chunks will still appear in mixed results if relevant.
   - What's unclear: Whether the planner wants automatic domain routing in `nodes.py` as part of Phase 08 or in a future phase.
   - Recommendation: Keep Phase 08 focused on ingestion. The success criterion says "returns chunks from the consulting corpus" — this will work with `domain_filter=None` if consulting content is sufficiently relevant. Domain routing in `nodes.py` is a Phase 09+ concern. This keeps Phase 08 scope tight: pipeline extension + operational ingestion.

3. **Per-book author handling for batch directory ingestion:**
   - What we know: `scripts/ingest.py` accepts a directory and iterates all PDFs with one `--author` value. 21 books have different authors.
   - What's unclear: Whether the user wants to run 21 individual commands or needs a manifest/CSV approach.
   - Recommendation: For Phase 08, document that each book should be ingested individually with its specific `--author`. The batch directory approach works only when all books in the directory share the same author (e.g., a multi-volume series). A manifest-based approach is deferred complexity.

---

## Sources

### Primary (HIGH confidence)

- `src/ingestion/pipeline.py` — full read; `use_vlm` gap confirmed (no parameter exists); `source_domain` stamping pattern confirmed at lines 115, 130
- `src/ingestion/chunking/metadata_enricher.py` — full read; `author` not in `REQUIRED_METADATA_FIELDS`; `enrich_metadata()` has no `author` param
- `scripts/ingest.py` — full read; `--source-domain` flag confirmed present; `--author` and `--no-vlm` flags confirmed absent
- `src/ingestion/parsing/vlm_captioner.py` — full read; `extract_and_caption_diagrams()` has no disable flag
- `src/ingestion/indexing/qdrant_uploader.py` — full read; `upload_batch` spreads `chunk["metadata"]` into payload — `author` will flow through automatically once added to metadata
- `src/generation/citation_builder.py` — full read; `build_citation()` reads `metadata.get("author", "")` — already handles `author` gracefully
- Live Qdrant query: 9845 total points, 9845 accounting, 0 consulting — backfill confirmed complete, Phase 08 safe to activate
- `tests/test_domain_retrieval.py` + `tests/test_domain_citation.py` — 13 tests all passing (2.43s) — Phase 07 infrastructure confirmed intact
- `tests/test_incremental_ingestion.py` — `_make_pipeline_mocks()` helper pattern confirmed reusable for Phase 08 tests

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` — locked decisions: VLM disabled for consulting, Qdrant only (no graphrag), dry-run 3 books first
- `.planning/milestones/v1.1-ROADMAP.md` — Phase 08 success criteria verbatim
- `.planning/REQUIREMENTS.md` — INGEST-01, INGEST-02 requirements verbatim; Out of Scope rationale for graphrag skip

### Tertiary (LOW confidence)

- Chunk count estimate range 2,800-12,600 (STATE.md) — based on accounting book pattern extrapolation; consulting books may differ significantly. Validate with dry-run.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing pipeline modules read in full; gaps confirmed by source inspection
- Architecture: HIGH — two gaps identified (`use_vlm`, `author`) with precise file/line context; pattern already established in Phase 07 for analogous changes
- Pitfalls: HIGH — derived directly from source code inspection and locked decisions; VLM cost and author field gap are verified against actual code
- Runtime state: HIGH — live Qdrant confirmed 9845/9845 accounting points; consulting directory absence confirmed

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (pipeline is stable; qdrant-client 1.17.1 API will not change)
