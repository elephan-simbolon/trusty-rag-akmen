---
phase: 01-foundation
plan: "04"
subsystem: ingestion
tags: [qdrant, embedding, qwen3, sparse-vector, bm25, python, batch-processing]

requires:
  - phase: 01-01
    provides: embed_batch, embed_query, embed_document functions in src/llm/client.py
  - phase: 01-02
    provides: route_and_parse, extract_and_caption_diagrams from parsing layer
  - phase: 01-03
    provides: chunking pipeline (structure_splitter, content_splitter, hierarchy_builder, formula_indexer, metadata_enricher)
provides:
  - Batch embedder with checkpoint resume (src/ingestion/indexing/embedder.py)
  - Qdrant collection initializer with dense+sparse vectors (src/ingestion/indexing/qdrant_uploader.py)
  - Chunk uploader with metadata payloads and BM25 sparse vectors
  - End-to-end ingestion pipeline orchestrator (src/ingestion/pipeline.py)
  - CLI ingest script accepting PDF paths (scripts/ingest.py)
affects: [02-graphrag, 03-agentic, retrieval, search, citation-generation]

tech-stack:
  added: [qdrant-client==1.17.1]
  patterns:
    - Batch embedding with checkpoint resume to survive SiliconFlow rate limit interruptions
    - Dense+sparse Qdrant collection configured at creation time (cannot add sparse later)
    - INT8 scalar quantization always_ram=True for Qdrant free tier memory efficiency
    - ScalarQuantization(scalar=ScalarQuantizationConfig(...)) wrapper required by qdrant-client v1.17.1
    - Hash-based word indices for BM25 sparse vectors (stable across runs)
    - Chunk backup to JSON before embedding (re-embed without re-parsing)

key-files:
  created:
    - src/ingestion/indexing/embedder.py
    - src/ingestion/indexing/qdrant_uploader.py
    - src/ingestion/pipeline.py
    - scripts/ingest.py
  modified:
    - tests/test_embedding.py
    - tests/test_qdrant_indexing.py

key-decisions:
  - "ScalarQuantization(scalar=ScalarQuantizationConfig(...)) is correct qdrant-client v1.17.1 API — QuantizationConfig is a Union type alias, not instantiable directly"
  - "BM25 sparse vectors use abs(hash(word)) % 2^31 for stable word-to-index mapping without a vocabulary file"
  - "Chunk backup to JSON saved before embedding (step 7) — allows re-embedding without re-parsing if SiliconFlow interrupts"
  - "Pipeline uses child nodes only for Qdrant indexing — parent nodes provide retrieval context window in Phase 3"

patterns-established:
  - "Pattern: Checkpoint resume — save last_completed_idx after each batch to survive rate limit interruptions"
  - "Pattern: Health check before upload — fail fast with descriptive error if Qdrant unreachable"
  - "Pattern: create_collection is idempotent — checks collection_exists before creating"

requirements-completed: [INDEX-01, INDEX-02, INDEX-03, INDEX-05]

duration: 4min
completed: "2026-03-22"
---

# Phase 01 Plan 04: Indexing Layer Summary

**Batch embedder with checkpoint resume, Qdrant collection with dense(1024,cosine,INT8)+sparse(BM25,IDF), and 9-step pipeline wiring PDF to indexed Qdrant collection**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-22T05:56:59Z
- **Completed:** 2026-03-22T06:00:42Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Batch embedder processes chunks with is_query=False (no prefix) and checkpoint resume for SiliconFlow rate limit recovery
- Qdrant collection initialized with dense (1024-dim, cosine, INT8 scalar quantization in RAM) and sparse (BM25, IDF modifier) at creation — cannot be added later
- Every chunk uploaded with all 6 metadata fields (book_title, chapter, section_path, content_type, page_start, page_end) for downstream citation generation
- BM25 sparse vectors computed from word frequencies with hash-based word indices for cross-lingual exact terminology matching
- End-to-end pipeline wires all 9 steps with chunk JSON backup before embedding
- CLI script accepts PDF paths/directories with argparse for batch ingestion

## Task Commits

Each task was committed atomically:

1. **Task 1: Create batch embedder, Qdrant uploader, and activate indexing tests** - `9aad150` (feat)
2. **Task 2: Create end-to-end ingestion pipeline and CLI ingest script** - `e244c5d` (feat)

**Plan metadata:** (docs commit, this summary)

## Files Created/Modified

- `src/ingestion/indexing/embedder.py` - Batch embedding with checkpoint resume, is_query=False for documents
- `src/ingestion/indexing/qdrant_uploader.py` - Collection init (dense+sparse), chunk upload with metadata payloads, BM25 sparse vectors, health check
- `src/ingestion/pipeline.py` - 9-step orchestrator: parse -> diagram caption -> heading split -> classify+split -> hierarchy -> formula index -> save JSON -> embed -> upload
- `scripts/ingest.py` - CLI entry point with argparse, supports PDF files or directory
- `tests/test_embedding.py` - Activated: query prefix assertion, document no-prefix assertion
- `tests/test_qdrant_indexing.py` - Activated: dense+sparse schema, payload metadata, INT8 quantization

## Decisions Made

- Used `ScalarQuantization(scalar=ScalarQuantizationConfig(...))` wrapper — qdrant-client v1.17.1 uses `QuantizationConfig` as a Union type alias (not instantiable); the concrete wrapper class is `ScalarQuantization`
- BM25 sparse vectors use `abs(hash(word)) % 2^31` for stable word-to-index mapping without maintaining a vocabulary file
- Chunk JSON backup written before embedding (step 7) so re-embedding is possible without re-parsing if SiliconFlow rate limits interrupt at step 8
- Pipeline uses child nodes only for Qdrant indexing; parent nodes (1000-1500 tokens) are retained for Phase 3 retrieval context window expansion

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed QuantizationConfig instantiation error with ScalarQuantization wrapper**
- **Found during:** Task 1 (qdrant_uploader.py creation)
- **Issue:** Plan template used `QuantizationConfig(scalar=ScalarQuantizationConfig(...))` but qdrant-client v1.17.1 defines `QuantizationConfig` as `Union[ScalarQuantization, ProductQuantization, BinaryQuantization]` — a type alias, not a class. Calling it raises `TypeError: Cannot instantiate typing.Union`.
- **Fix:** Replaced `QuantizationConfig(scalar=...)` with `ScalarQuantization(scalar=ScalarQuantizationConfig(...))`. Also updated test import to use `ScalarQuantization` and `isinstance(quant, ScalarQuantization)` assertion.
- **Files modified:** `src/ingestion/indexing/qdrant_uploader.py`, `tests/test_qdrant_indexing.py`
- **Verification:** All 5 tests pass; `python -c "from src.ingestion.indexing.qdrant_uploader import create_collection; print('OK')"` succeeds
- **Committed in:** `9aad150` (Task 1 commit)

**2. [Rule 3 - Blocking] Installed missing qdrant-client dependency**
- **Found during:** Task 1 (test collection phase)
- **Issue:** `qdrant_client` module not installed in environment
- **Fix:** `pip install qdrant-client`
- **Verification:** All 5 tests pass after installation
- **Committed in:** n/a (pip install, no source change)

---

**Total deviations:** 2 auto-fixed (1 bug — wrong API class, 1 blocking — missing pip package)
**Impact on plan:** Both auto-fixes required for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None — no new external service configuration required. Qdrant credentials already captured in `config/settings.py` (Plan 01-01).

## Next Phase Readiness

- Qdrant collection schema is correct (dense+sparse cannot be modified after creation) — ready for retrieval queries in Phase 3
- Ingestion pipeline ready for first end-to-end test with a real PDF textbook
- CLI `python scripts/ingest.py path/to/book.pdf` is the entry point for Phase 4 bulk ingestion (100 textbooks)
- SiliconFlow rate limit concern documented: checkpoint resume in embedder.py handles interruptions; Phase 4 SiliconFlow tier upgrade still required before large-scale ingestion

## Self-Check: PASSED

- FOUND: src/ingestion/indexing/embedder.py
- FOUND: src/ingestion/indexing/qdrant_uploader.py
- FOUND: src/ingestion/pipeline.py
- FOUND: scripts/ingest.py
- FOUND: .planning/phases/01-foundation/01-04-SUMMARY.md
- FOUND: commit 9aad150 (Task 1)
- FOUND: commit e244c5d (Task 2)

---
*Phase: 01-foundation*
*Completed: 2026-03-22*
