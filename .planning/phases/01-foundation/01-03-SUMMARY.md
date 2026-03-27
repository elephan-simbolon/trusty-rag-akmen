---
phase: 01-foundation
plan: 03
subsystem: ingestion
tags: [chunking, rag, page-markers, hierarchy, llama-index, content-classification]

# Dependency graph
requires:
  - phase: 01-02
    provides: Parsed Markdown with <!-- PAGE_START:N --> markers from MinerU/Docling parsers
provides:
  - Page marker injection, extraction, and stripping (page_markers.py)
  - Element content type classification with 5 types (classifier.py)
  - Heading-based structure splitting with breadcrumb metadata (structure_splitter.py)
  - Content-type-specific splitting rules: 512t narrative, atomic/header-repeat tables (content_splitter.py)
  - Parent-child hierarchy builder at 1500-token parent threshold (hierarchy_builder.py)
  - Per-chapter formula index chunk creation (formula_indexer.py)
  - Metadata enricher attaching 6 required fields to every chunk (metadata_enricher.py)
affects: [01-04, 01-05, 01-06, indexing, retrieval, qdrant-ingestion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Content-type-first splitting: classify before splitting, never split tables or formulas mid-element"
    - "Inline page markers: <!-- PAGE_START:N --> injected at parse time, extracted at chunk time, stripped before embedding"
    - "Parent-child hierarchy: accumulate children up to 1500 tokens, then flush to parent — child is the retrieval unit"
    - "Formula index chunk: per-chapter synthetic chunk listing all formulas, high-relevance target for Calculation routing"

key-files:
  created:
    - src/ingestion/chunking/page_markers.py
    - src/ingestion/chunking/classifier.py
    - src/ingestion/chunking/structure_splitter.py
    - src/ingestion/chunking/content_splitter.py
    - src/ingestion/chunking/hierarchy_builder.py
    - src/ingestion/chunking/formula_indexer.py
    - src/ingestion/chunking/metadata_enricher.py
  modified:
    - tests/test_page_markers.py
    - tests/test_element_classifier.py
    - tests/test_chunking.py

key-decisions:
  - "TABLE_SEPARATOR regex includes | in character class to match multi-column separator rows like '| --- | --- | --- |'"
  - "test_hierarchy_builder_parent_child uses 6 chunks (not 5) to guarantee at least 2 parents and verify parent > single-child text length"
  - "Formula index page_start/page_end set to 0 — it is a synthetic chunk not tied to a specific page range"

patterns-established:
  - "Pattern 1: Strip page markers before embedding — keep them only in raw chunk text for metadata extraction"
  - "Pattern 2: All 6 metadata fields required per chunk: book_title, chapter, section_path, content_type, page_start, page_end"
  - "Pattern 3: classify_element priority order: table > formula > example_problem > diagram > narrative_text"

requirements-completed: [CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, CHUNK-06, CHUNK-07, CHUNK-08]

# Metrics
duration: 12min
completed: 2026-03-22
---

# Phase 01 Plan 03: Chunking Pipeline Summary

**Seven-module chunking pipeline with inline page marker extraction, content-type classification (5 types), heading-hierarchy splitting with breadcrumb, 512-token narrative splitting with 75-token overlap, large table splitting with header repetition, parent-child hierarchy at 1500-token threshold, formula index chunks, and metadata enrichment — 14 tests pass**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-22T05:49:45Z
- **Completed:** 2026-03-22T06:01:45Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Complete chunking pipeline with 7 production modules covering every step from raw markdown to enriched, hierarchical chunks
- Content-type-aware splitting: narrative (512t/75t overlap), tables (atomic or split with repeated headers), formulas/diagrams/examples (atomic)
- Full metadata traceability: every chunk carries book_title, chapter, section_path, content_type, page_start, page_end extracted from inline markers

## Task Commits

Each task was committed atomically:

1. **Task 1: Create page markers module and element classifier** - `ab4a5a3` (feat)
2. **Task 2: Create structure splitter, content splitter, and hierarchy builder** - `2a4fc9d` (feat)
3. **Task 3: Create formula indexer and metadata enricher** - `5fdd208` (feat)

## Files Created/Modified

- `src/ingestion/chunking/page_markers.py` - inject_page_markers, extract_page_range, strip_page_markers
- `src/ingestion/chunking/classifier.py` - ContentType enum (5 types) and classify_element with priority rules
- `src/ingestion/chunking/structure_splitter.py` - split_by_headings producing Section objects with breadcrumb
- `src/ingestion/chunking/content_splitter.py` - estimate_tokens, split_narrative, split_large_table, split_content_by_type
- `src/ingestion/chunking/hierarchy_builder.py` - ChunkNode dataclass and build_hierarchy grouping at 1500-token threshold
- `src/ingestion/chunking/formula_indexer.py` - create_formula_index producing per-chapter formula reference chunks
- `src/ingestion/chunking/metadata_enricher.py` - enrich_metadata and validate_metadata with 6-field REQUIRED_METADATA_FIELDS
- `tests/test_page_markers.py` - Activated 3 stubs: inject, extract, strip
- `tests/test_element_classifier.py` - Activated 5 stubs: narrative, table, formula, diagram, example_problem
- `tests/test_chunking.py` - Activated 4 stubs + added test_metadata_enrichment (new test)

## Decisions Made

- TABLE_SEPARATOR regex: Original pattern `r"^\|[\s\-:]+\|$"` failed on multi-column separators like `| --- | --- | --- |` because it doesn't allow `|` between cells. Fixed to `r"^\|[\s\-:|]+\|$"` to include `|` in the character class.
- test_hierarchy_builder_parent_child: Changed from 5 to 6 chunks to guarantee the first parent has at least 2 children (allowing parent text > child text assertion to pass deterministically).
- Formula index synthetic chunk: page_start and page_end set to 0 — this chunk aggregates formulas from across a chapter and is not tied to any specific page.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TABLE_SEPARATOR regex for multi-column separator rows**
- **Found during:** Task 1 (test_classify_table failure)
- **Issue:** `r"^\|[\s\-:]+\|$"` matched only single-cell separator rows; multi-column rows like `| --- | --- | --- |` failed to match because `|` was not in the character class
- **Fix:** Changed to `r"^\|[\s\-:|]+\|$"` adding `|` to allowed characters
- **Files modified:** src/ingestion/chunking/classifier.py
- **Verification:** test_classify_table passes, all other classifier tests still pass
- **Committed in:** ab4a5a3 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed test_hierarchy_builder_parent_child assertion logic**
- **Found during:** Task 2 (test failure: assert 1300 > 1300)
- **Issue:** 5 chunks with ~312 tokens each: first group gets 4 children (total ~1248t under 1500t limit), last group is 1 child — parent text equals single child text, making the assertion non-deterministic
- **Fix:** Changed to 6 chunks so first parent gets 4 children and assertion `len(parent.text) > len(child.text)` holds (parent is 4x child text joined with double newlines)
- **Files modified:** tests/test_chunking.py
- **Verification:** test_hierarchy_builder_parent_child passes with asserted len(first_parent_children) >= 2
- **Committed in:** 2a4fc9d (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes were necessary for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed bugs documented above.

## User Setup Required

None - no external service configuration required. All modules are pure Python, no cloud dependencies.

## Next Phase Readiness

- Chunking pipeline complete: all 7 modules ready for consumption by the indexing pipeline (Plan 01-04)
- Chunk structure follows the contract: every chunk has 'text' and 'metadata' keys with 6 required fields
- Formula index chunks are ready for Plan 03 (Phase 3) Calculation routing — content_type="formula_index" is the filter key
- Concern: page_start=0 warning logs will fire for any chunk lacking page markers — parsers must inject markers consistently

## Self-Check: PASSED

All 7 source files and SUMMARY.md confirmed present on disk. All 3 task commits (ab4a5a3, 2a4fc9d, 5fdd208) confirmed in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-22*
