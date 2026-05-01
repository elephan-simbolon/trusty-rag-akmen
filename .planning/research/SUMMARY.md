# Project Research Summary

**Project:** Trusty RAG Akmen — v1.1 Knowledge Protocol Engineering (KPE) + Consulting Book Ingestion
**Domain:** Protocol-driven RAG for management accounting consulting (bilingual Indonesian/English)
**Researched:** 2026-03-29
**Confidence:** HIGH

## Executive Summary

The v1.1 milestone upgrades an existing, fully working Phase 3 RAG system from a textbook Q&A tool into a consulting-grade assistant. The core technique is Knowledge Protocol Engineering (KPE): encoding domain-specific reasoning frameworks (CVP, Variance Analysis, ABC, etc.) as hardcoded Python dataclasses that are injected into system prompts at query time, guiding the LLM to produce structured, auditable, consultant-style answers. Research confirms this requires zero new Python packages — the entire feature set is buildable on the existing stack. The build is purely additive: new modules, new state fields, new metadata fields. The LangGraph graph topology, CRAG loop, reranker, and FastAPI SSE interface all remain unchanged.

The recommended approach is a two-phase build: Phase A (generation layer first — protocol registry, prompt builder, query classifier extension, citation label field) delivers immediate KPE value on the existing corpus before any ingestion work. Phase B (retrieval and ingestion — source_domain backfill, domain-aware hybrid_search, 21-book consulting ingestion) adds the multi-domain corpus. This ordering is critical because Phase A has zero dependencies on Phase B and can be tested end-to-end against existing accounting chunks. Consulting book ingestion without an indexed payload field and completed backfill would silently break all existing queries by excluding untagged accounting chunks from filtered searches.

The top risks are: (1) system prompt token budget creep from protocol steps plus few-shot examples blowing the $8-35/month cost target, (2) partial Qdrant backfill silently degrading retrieval quality before domain filter goes live, and (3) the query classifier extension conflating protocol selection with calculation detection. All three risks have defined prevention strategies grounded in the existing codebase's established patterns.

---

## Key Findings

### Recommended Stack

No new Python packages are required for v1.1. All capabilities are present in the installed stack (qdrant-client 1.17.1, Python 3.11 stdlib dataclasses, existing LangGraph + LangChain + SiliconFlow clients). The KPE concept (arXiv 2507.02760, July 2025) has no production Python library implementation as of March 2026 — hand-rolling is the only option and is appropriate, since the protocol registry is approximately 50 lines using stdlib `@dataclass(frozen=True)`.

**Core technologies (v1.1 additions/changes):**
- `Python stdlib dataclasses` — KPE protocol registry — frozen dataclasses are 3x faster to instantiate than Pydantic BaseModel; internal constants do not need runtime validation
- `qdrant-client 1.17.1` — source_domain payload index + domain-aware Prefetch filtering — single collection with payload filter is the Qdrant-recommended approach for logical domain separation
- `Python stdlib str.format()` — composable prompt builder — 3-4 string concatenations do not warrant a templating engine
- `Docling` (existing) — consulting book ingestion — consulting books are text-native, matching Docling's design target; MinerU's scanned-PDF OCR is not needed for this content type

**What NOT to add:** Pydantic for protocol registry, Jinja2 for prompts, LlamaIndex for consulting PDFs, separate Qdrant collection for consulting, any KPE library.

### Expected Features

**Must have (table stakes — milestone fails without these):**
- Protocol registry — 9 hardcoded management accounting frameworks (CVP, Variance, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General) as Python dataclasses in `src/generation/prompt_builder.py`
- RAGState extension — add `selected_protocol: Optional[str]` field (14 → 15 fields)
- Enhanced query classifier — keyword-based `select_protocol()` function alongside existing `is_calculation_query()`; zero LLM calls; fall back to General on ambiguous match
- Composable prompt builder — `build_system_prompt(query_type, protocol, has_graph_context)` replacing the current three-branch if/elif/else in `generator.py`
- source_domain metadata field — add to `metadata_enricher.py` and pipeline; pass `"accounting"` or `"consulting"` at ingest time
- Consulting book ingestion (21 books) — reuse existing 9-step pipeline; skip fast-graphrag; tag `source_domain="consulting"`
- Backfill script — one-time `set_payload(source_domain="accounting")` on all existing Qdrant points via scroll iteration
- Domain-aware hybrid_search — `domain_filter: str | None = None` parameter using Qdrant Prefetch filter; default `None` (no filter — reranker handles domain mix naturally)
- Citation differentiation — `[Kerangka N]` for consulting sources vs `[Sumber N]` for accounting; add `label` and `source_domain` fields to `build_citations()` output

**Should have (adds reliability and polish, implement after P1 is validated):**
- Payload index on source_domain — KEYWORD index in `create_payload_index()` loop; one-time migration for existing collection
- Protocol-aware CRAG reformulation — pass `selected_protocol` into `reformulate_node` prompt to keep rewrites domain-scoped
- Per-protocol few-shot examples — 1-2 examples at 150-250 tokens each; gated to `query_type == "Calculation"` to manage token budget
- Protocol name header in response — prepend human-readable framework label at top of response; zero SSE changes needed

**Defer to v2+:**
- LLM-based protocol selection fallback — add only if keyword accuracy falls below 85% on real query logs
- Expanding to 12+ protocols — add only when observed query gaps demonstrate need
- Protocol library UI — allow consultant to view/edit protocols via frontend
- Cross-protocol synthesis — detect queries spanning multiple frameworks

### Architecture Approach

All KPE integration happens inside existing node functions and via new state fields. The LangGraph graph topology (`graph.py`) does not change. The CRAG loop, conditional routing, and all existing node function signatures are preserved. Integration is surgical: 8 existing files are modified, 2 new files are created (`src/generation/prompt_builder.py`, `scripts/backfill_source_domain.py`). Build order is: Phase A (generation layer, zero external dependencies) then Phase B (retrieval/ingestion layer, depends on Phase A state fields).

**Major components and their changes:**

1. `src/generation/prompt_builder.py` (NEW) — KPE protocol registry (9 protocols as frozen dataclasses) + `build_system_prompt()` function; primary consumer of protocol definitions; co-located for cohesion
2. `src/retrieval/query_classifier.py` (MODIFIED) — add `select_protocol(query: str) -> str` alongside existing `is_calculation_query()`; do NOT delete existing function; it is tested independently and called internally by the new classifier
3. `src/agents/state.py` + `src/agents/nodes.py` (MODIFIED) — add `selected_protocol` to RAGState; update `route_node` to call both classifiers; update `generate_node` and `generate_calc_node` to pass `selected_protocol` to generator
4. `src/generation/generator.py` + `src/generation/citation_builder.py` (MODIFIED) — accept `selected_protocol`; delegate to `build_system_prompt()`; add `label` and `source_domain` fields to citation dict output
5. `src/retrieval/vector_search.py` (MODIFIED) — add `domain_filter: str | None = None` parameter; default behavior unchanged; Qdrant Filter applied only when explicitly set
6. `src/ingestion/` chain (MODIFIED) — `metadata_enricher.py` + `pipeline.py` + `qdrant_uploader.py` — add `source_domain` as metadata field and payload index

### Critical Pitfalls

1. **System prompt token budget overflow** — KPE protocol steps plus few-shot examples plus glossary can push system prompt to 1,500 tokens, raising per-query cost 6x at 500 queries/day. Prevention: cap each protocol at 300 tokens; move few-shot examples behind a `query_type == "Calculation"` gate; add a `count_prompt_tokens()` test asserting all protocols stay under 5,000 total input tokens.

2. **Partial Qdrant backfill silently excludes accounting chunks** — Qdrant filter semantics are "field exists AND matches" not "matches OR absent." Partial backfill causes CRAG to grade queries INCORRECT with no error raised. Prevention: atomic backfill with progress logging; verify `client.count(filter=source_domain="accounting")` equals total collection count before enabling domain filter.

3. **Missing Qdrant payload index for source_domain** — Without the index, Qdrant does a full payload scan; on 80,000+ points this is 3-5x slower and may cause free-tier OOM. No error is raised — only silent latency degradation. Prevention: add `source_domain` to `create_payload_index()` loop immediately when writing the backfill script; run `create_payload_index(..., wait=True)` on the existing collection before any filtered queries go live.

4. **Query classifier extension breaks existing calculation detection** — Protocol keywords overlap with calculation keywords ("break-even" appears in both). A combined classifier can produce inconsistent `query_type`/`protocol_id` states. Prevention: keep `is_calculation_query()` untouched; add `select_protocol()` as a separate independent function; call both in `route_node()` and store in separate state fields; test all four combinations (Calculation+protocol, Calculation+no-protocol, non-Calculation+protocol, non-Calculation+no-protocol).

5. **Protocol over-engineering adds LLM calls to zero-LLM routing** — Ambiguous protocol matches tempt developers to add an LLM fallback call, adding $10-30/month and 1-2s latency per ambiguous query. Prevention: use General protocol as the fallback for ambiguous matches; document the zero-LLM constraint as an explicit test assertion (`assert llm_call_count == 0` in route_node tests).

6. **21-book consulting ingestion VLM rate limit underestimation** — 21 books × 10 diagrams/book = 210 VLM API calls to Qwen2.5-VL-72B; at 50 RPD this is 4+ days. Prevention: disable VLM captioning for consulting books (`use_vlm=False`); ingest in batches of 5; verify checkpoint resume works before starting full run.

7. **Citation format breaking change ripples to frontend** — Adding `label` and `source_domain` to citation dict is additive for Python but TypeScript types are assertions, not runtime validators — the frontend silently ignores new keys if `SSEEvent` union is not updated simultaneously. Prevention: update `frontend/src/types/sse.ts` `Citation` interface in the same commit as `citation_builder.py`; add a test asserting both keys are always present in `build_citations()` output.

---

## Implications for Roadmap

The dependency graph dictates a 2-phase build with 6 sequential tasks. The generation layer has zero dependencies on ingestion and must be built first.

### Phase A: Generation Layer (KPE Core)

**Rationale:** Protocol registry, composable prompt builder, query classifier extension, and citation label field are fully independent of ingestion. They can be built, tested, and validated against the existing accounting textbook corpus before a single consulting book is ingested. Delivering Phase A first de-risks the KPE concept before investing in the 21-book ingestion effort.

**Delivers:** Protocol-driven prompting for all existing queries; structured CVP/Variance/ABC/etc. answers on accounting corpus; citation label infrastructure ready for consulting content.

**Task A1 — Protocol Registry + Prompt Builder (NEW file)**
- Create `src/generation/prompt_builder.py`
- 9 protocols as `@dataclass(frozen=True)` with steps list, consulting_lens, few_shot (optional)
- `build_system_prompt(query_type, protocol, has_graph_context) -> str`
- Tests: each of 9 protocols produces a distinct, non-empty prompt; all protocols under 300-token cap

**Task A2 — RAGState + Route Node + Generator (MODIFIED)**
- Add `selected_protocol: Optional[str]` to `state.py`
- Add `select_protocol(query: str) -> str` to `query_classifier.py` (do NOT modify `is_calculation_query()`)
- Update `route_node` to call both classifiers; store both results in state
- Update `generate_node` and `generate_calc_node` to pass `selected_protocol`
- Update `generate_response()` signature; delegate to `build_system_prompt()`
- Tests: all four combinations of (calculation, protocol) routing; `llm_call_count == 0` in route_node

**Task A3 — Citation Label Field (MODIFIED)**
- Add `label: str` and `source_domain: str` to `build_citations()` output dict
- Update `_build_context_block()` to label consulting chunks as `[Kerangka N]`
- Update `frontend/src/types/sse.ts` `Citation` interface in same commit
- Update `ChatMessage.tsx` citation renderer for visual distinction (different icon or color)
- Tests: `build_citations()` always returns `label` and `source_domain` keys; textbook produces `"Sumber"`, consulting produces `"Kerangka"`

**Avoids:** Token budget overflow (enforce 300-token cap in A1 tests); citation breaking change (coordinate frontend update in A3); protocol over-engineering (document zero-LLM constraint as test in A2).

**Research flag:** Standard patterns — no additional research needed. All integration points verified against production code.

---

### Phase B: Retrieval and Ingestion Layer

**Rationale:** Phase B builds on the state fields established in Phase A. Must be executed in B1 then B2 then B3 order because domain-filtered queries (B2) are unsafe until backfill (B1) is verified complete, and citation differentiation only surfaces consulting sources once books are ingested (B3).

**Delivers:** Multi-domain corpus (accounting + consulting); domain-aware citation display; full KPE milestone completion.

**Task B1 — source_domain in Ingestion Pipeline + Backfill (MODIFIED + NEW script)**
- Add `source_domain` param to `metadata_enricher.py` and `pipeline.py` (default `"accounting"`)
- Add `"source_domain"` to `create_payload_index()` loop in `qdrant_uploader.py`
- Run `create_payload_index(field_name="source_domain", ..., wait=True)` on existing production collection
- Write `scripts/backfill_source_domain.py`: scroll all points, `set_payload(source_domain="accounting")` in batches of 500
- Verify: `client.count(filter=source_domain="accounting")` equals total collection count before proceeding
- Tests: `test_backfill_coverage` asserts 100% of points have `source_domain` after migration

**Task B2 — Domain-Aware hybrid_search (MODIFIED)**
- Add `domain_filter: str | None = None` to `hybrid_search()` in `vector_search.py`
- Build Qdrant `Filter(must=[FieldCondition(key="source_domain", ...)])` only when `domain_filter` is set
- Pass `domain_filter=None` in `retrieve_node` (no filtering by default; reranker handles domain mix)
- Tests: filtered query returns only matching-domain chunks; unfiltered query returns both domains

**Task B3 — Consulting Book Ingestion (21 books)**
- Add `--source-domain consulting` flag to `scripts/ingest.py`
- Set `use_vlm=False` for consulting books (saves VLM rate limit budget)
- Skip fast-graphrag for consulting books (explicit design decision in PROJECT.md)
- Ingest in batches of 5 books; monitor Qdrant disk usage after each batch
- Verify checkpoint resume by killing and restarting mid-batch before full run
- Verify final queries return chunks from both `source_domain` values

**Avoids:** Partial backfill silent exclusion (B1 verification gate before B2 activation); missing payload index (B1 creates index before backfill); Qdrant disk overflow (batched ingestion with monitoring in B3); VLM rate limit (disable VLM in B3).

**Research flag:** B3 benefits from a dry-run on 3 representative consulting books to validate chunk count estimate (2,800-12,600 range) before committing to full 21-book run.

---

### Phase Ordering Rationale

- Phase A before Phase B: Generation layer has zero dependencies on ingestion. Delivers immediate KPE value on existing corpus. De-risks the KPE concept before expensive ingestion work.
- B1 before B2: Payload index and backfill must be complete and verified before any domain-filtered query goes live. Qdrant filter on an un-backfilled collection silently excludes all pre-existing accounting chunks.
- B2 before B3: domain_filter infrastructure must exist in code before consulting books are ingested, to ensure new chunks receive correct `source_domain` from day one.
- B3 last: Consulting book ingestion is the highest-effort, highest-risk task (disk usage, VLM rate limits, 21 books × parse time). Do it last when all infrastructure is verified working.

### Research Flags

Phases needing deeper research during planning:
- **None identified** — all integration points were verified against the production codebase directly. Architecture research is based on code inspection, not documentation alone.

Phases with standard patterns (skip research-phase):
- **Phase A (all tasks):** Integration points fully specified with file paths, function signatures, and test assertions. No novel engineering.
- **Phase B1-B2:** Qdrant scroll + set_payload + create_payload_index patterns verified against the existing `qdrant_uploader.py` codebase patterns.
- **Phase B3:** Reuses the existing 9-step ingestion pipeline. Additions are one CLI flag and a `use_vlm=False` parameter.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new packages; all capabilities verified in installed versions; Qdrant API confirmed against official docs |
| Features | HIGH | 9 protocol count validated against ICAG Management Accounting syllabus; rule-based routing backed by arXiv 2505.23052 (85-92% accuracy at <1ms) |
| Architecture | HIGH | All integration points based on direct code inspection of production files (state.py, nodes.py, vector_search.py, generator.py, citation_builder.py, query_classifier.py, pipeline.py, qdrant_uploader.py) |
| Pitfalls | HIGH | All 9 pitfalls grounded in existing codebase with specific file and line number references; recovery strategies defined |

**Overall confidence:** HIGH

### Gaps to Address

- **Consulting book chunk count estimate (2,800-12,600 range):** Wide range due to unknown diagram density across 21 books. Resolve by running a 3-book dry-run before committing to full ingestion. Operational validation, not a design gap.
- **Token budget per protocol:** Protocol step content is not yet written. Enforce the 300-token cap as a test assertion in Phase A1 before writing any protocol content — prevents token creep from accumulating silently.
- **Few-shot example content:** Research specifies format (1-2 examples at 150-250 tokens each) but content is not yet drafted. Defer drafting to post-A2 validation: observe which protocols produce inconsistent output first, then write targeted examples only for those protocols.
- **Frontend citation visual design:** `ChatMessage.tsx` update is specified (different icon/color for `[Kerangka N]`) but exact visual design is not defined. Low risk — UI-only decision with no backend dependencies.

---

## Sources

### Primary (HIGH confidence)
- Qdrant Indexing Documentation (qdrant.tech/documentation/manage-data/indexing/) — payload index creation, KEYWORD type, timing recommendation, filter semantics
- Qdrant API Reference: query_points (api.qdrant.tech) — Prefetch.filter parameter existence
- Qdrant Python Client Docs (python-client.qdrant.tech) — create_payload_index, set_payload, scroll signatures
- Direct code inspection of production files (2026-03-29): `src/agents/state.py`, `src/agents/nodes.py`, `src/agents/graph.py`, `src/retrieval/vector_search.py`, `src/generation/generator.py`, `src/generation/citation_builder.py`, `src/retrieval/query_classifier.py`, `src/ingestion/pipeline.py`, `src/ingestion/indexing/qdrant_uploader.py`, `config/prompts.py`
- arXiv 2505.23052 (RAGRouter) — rule-based complexity classifiers achieve 85-92% accuracy at <1ms
- Pydantic dataclasses docs — when to use stdlib vs Pydantic dataclass; instantiation speed comparison

### Secondary (MEDIUM confidence)
- arXiv 2507.02760 (KPE paper, July 2025) — confirms KPE is a concept paper; no production library exists; hand-rolling is the norm
- KPE Medium article (Robert Encarnacao) — hand-rolled implementations confirmed as standard practice
- Few-Shot Prompting Best Practices (DigitalOcean) — 1-3 examples hit quality sweet spot; system prompt placement best practice
- ICAG Management Accounting Syllabus 2025 — validates 9 protocol coverage of core management accounting decision space

### Tertiary (LOW confidence)
- WebSearch "python dataclass vs pydantic basemodel performance 2025" — instantiation speed benchmark data supporting dataclass choice; not from authoritative benchmark source
- Consulting book chunk count estimates (2,800-12,600) — based on accounting textbook per-page chunk rates extrapolated to consulting books; needs validation via 3-book dry run

---

*Research completed: 2026-03-29*
*Ready for roadmap: yes*
