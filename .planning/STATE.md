---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
stopped_at: Completed 08-consulting-book-ingestion 08-02-PLAN.md
last_updated: "2026-03-30T02:57:58.556Z"
last_activity: 2026-03-30
progress:
  total_phases: 11
  completed_phases: 11
  total_plans: 35
  completed_plans: 35
  percent: 11
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-29)

**Core value:** Mempercepat pencarian referensi akuntansi dari 45-60 menit menjadi 5-10 menit, dengan source citation (buku, chapter, halaman) yang bisa dipertanggungjawabkan ke klien
**Current focus:** Phase 08 — consulting-book-ingestion

## Current Position

Phase: 08
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-03-30

Progress: [█░░░░░░░░░] 11% (v1.1) — 1/9 plans complete

## Performance Metrics

**Velocity (v1.0 reference):**

- Total plans completed: 27
- Average duration: ~6 min/plan
- Total execution time: ~2.7 hours across 8 phases

**By Phase (v1.0):**

| Phase | Plans | Status |
|-------|-------|--------|
| 01-foundation | 8/8 | Complete |
| 02-knowledge-graph | 3/3 | Complete |
| 03-agentic-orchestration | 4/4 | Complete |
| 04-scale-and-observability | 4/4 | Complete |
| 04.1-ingestion-polish | 2/2 | Complete |
| 05-polish | 2/2 | Complete |
| 05.1-cleanup-and-hardening | 2/2 | Complete |
| 05.2-session-and-observability-fixes | 2/2 | Complete |

**v1.1 Trend:** Not started

*Updated after each plan completion*
| Phase 06-kpe-core P02 | 6 | 2 tasks | 6 files |
| Phase 06-kpe-core P03 | 9m | 3 tasks | 5 files |
| Phase 07-domain-retrieval P03 | 5 | 2 tasks | 4 files |
| Phase 07-domain-retrieval P02 | 15 | 2 tasks | 4 files |
| Phase 07-domain-retrieval P01 | 3 | 2 tasks | 2 files |
| Phase 08-consulting-book-ingestion P01 | 13 | 2 tasks | 3 files |
| Phase 08-consulting-book-ingestion P02 | 8 | 3 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting v1.1 work:

- [v1.1 design]: Protocol registry uses stdlib @dataclass(frozen=True), NOT Pydantic — 3x faster instantiation; internal constants need no runtime validation
- [v1.1 design]: KPE protocol selection is rule-based keyword matching (zero LLM calls) — budget constraint $8-35/month; 85-92% accuracy confirmed sufficient
- [v1.1 design]: Consulting books ingest to Qdrant only, skip fast-graphrag — accounting entity types (CostType, CostDriver, Formula) not suitable for procedural consulting knowledge
- [v1.1 design]: Single Qdrant collection with payload filter for domain separation — Qdrant official recommendation over collection sharding; enables cross-domain RRF fusion
- [v1.1 design]: Phase 06 (generation layer) before Phase 07 (retrieval) — generation layer has zero dependencies on ingestion; de-risks KPE concept before 21-book effort
- [v1.1 design]: Backfill must be 100% verified complete before domain_filter goes live — Qdrant filter semantics: "field exists AND matches", not "matches OR absent"
- [v1.1 design]: VLM captioning disabled for consulting books (use_vlm=False) — 21 books x 10 diagrams = 210 VLM calls; saves rate limit budget for accounting queries

- [06-01]: ProtocolConfig frozen=True — immutable registry prevents mutation bugs in downstream prompt composition
- [06-01]: Word-boundary guard for keywords ≤4 chars — prevents "kontrak ABC" false-positive matching abc protocol
- [06-01]: _PROTOCOL_PRIORITY order: variance_analysis before budgeting, cost_classification before cvp — specificity-first prevents keyword shadowing
- [Phase 06-kpe-core]: Local import of PROTOCOL_REGISTRY inside compose_system_prompt() avoids circular import at module load time
- [Phase 06-kpe-core]: _CALCULATION_BLOCK is additive — protocol steps always included even for calculation queries
- [Phase 06-kpe-core]: compose_system_prompt() falls back to 'general' protocol on unknown key — no KeyError at runtime
- [Phase 06-kpe-core]: BEP calculation test query uses 'titik impas' to avoid shadowing by cost_classification protocol
- [Phase 06-kpe-core]: collect_ignore_glob in conftest.py prevents fast_graphrag ImportError from aborting test collection
- [Phase 07-domain-retrieval]: source_domain absent defaults to 'accounting' — backward compatible with all pre-Phase-07 Qdrant points
- [Phase 07-domain-retrieval]: build_citation() formatted string unchanged — source_domain only in build_citations() dict, preserving GEN-01 locked citation format
- [Phase 07-domain-retrieval]: Sync comment above build_citation() in citation_builder.py documents label parity requirement between _build_context_block and build_citations
- [Phase 07-domain-retrieval]: domain_filter=None default in hybrid_search — opt-in infrastructure, not activated until RETR-02 backfill verified complete (Phase 08)
- [Phase 07-domain-retrieval]: Filter placed on each Prefetch pre-fusion (not outer query_points) — correct qdrant-client 1.17.1 pattern for domain filtering
- [Phase 07-domain-retrieval]: source_domain fallback 'accounting' in hybrid_search metadata — covers transition period before RETR-02 backfill
- [Phase 07-domain-retrieval]: get_qdrant_client imported at module level in backfill script for test patchability (patch target: scripts.backfill_source_domain.get_qdrant_client)
- [Phase 08-consulting-book-ingestion]: use_vlm defaults True + author defaults '' — existing accounting callers unchanged; consulting callers opt-in with use_vlm=False, author='Name'
- [Phase 08-consulting-book-ingestion]: create_parser() extracted from main() in ingest.py — enables patch('scripts.ingest.run_ingestion_pipeline') in tests; lazy import inside main() creates local binding unreachable by patch
- [Phase 08-consulting-book-ingestion]: git add -f for .gitkeep inside gitignored data/ — force-add is correct pattern; no new .gitignore entry needed
- [Phase 08-consulting-book-ingestion]: UAT mixed-domain result correct — consulting query returns [Kerangka N]; ABC costing query returns [Sumber N] only (no consulting match expected)
- [Phase 08-consulting-book-ingestion]: 10,134 consulting chunks ingested across 21 books; total Qdrant: 19,979 (accounting 9,845 + consulting 10,134)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 07]: Qdrant backfill must be atomic — verify client.count(filter=source_domain="accounting") equals total point count before activating domain_filter in any query path
- [Phase 08]: Consulting book chunk count estimate is wide (2,800–12,600 range) — run 3-book dry run before committing to full 21-book ingestion to validate disk usage

## Session Continuity

Last session: 2026-03-30T02:50:43.870Z
Stopped at: Completed 08-consulting-book-ingestion 08-02-PLAN.md
Resume file: None
