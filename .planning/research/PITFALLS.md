# Pitfalls Research

**Domain:** Adding KPE protocol-based prompting, multi-domain retrieval, and consulting book ingestion to existing RAG accounting assistant (v1.1 milestone)
**Researched:** 2026-03-29
**Confidence:** HIGH — all pitfalls grounded in existing codebase (`src/`, `frontend/`, `config/`)

> This file extends and supersedes the v1.0 PITFALLS.md for the v1.1 milestone scope.
> v1.0 pitfalls (MinerU VRAM, cross-lingual retrieval, LightRAG deduplication, etc.) remain valid and are archived in git history. This document covers only the NEW risks introduced by v1.1 changes.

---

## Critical Pitfalls

### Pitfall 1: System Prompt Token Budget Overflow With KPE Protocol Steps + Few-Shot + Glossary

**What goes wrong:**
The current prompts in `config/prompts.py` are compact: `SYSTEM_PROMPT_GENERATOR` is approximately 350 tokens including the glossary snippet (50 terms × ~5 tokens each). Adding KPE protocol steps (e.g., CVP Analysis: 8 steps × ~30 tokens = 240 tokens) plus a few-shot example (a worked CVP example: ~400 tokens) plus the same glossary snippet pushes the system prompt to ~1,000 tokens. Across 9 protocols, the worst case (a complex protocol like Transfer Pricing with 10 steps plus a multi-party example) reaches ~1,500 tokens of system prompt. Combined with a retrieved context block of 5 reranked documents at ~400 tokens each (2,000 tokens) plus conversation history (10 messages × ~80 tokens = 800 tokens) plus the user query (~100 tokens), the total input is 4,400 tokens for straightforward queries — and up to 6,000+ tokens when context docs are long. Qwen3-30B-A3B supports a 32K context window, so overflow is not the risk. The actual risk is **cost creep**: at $0.10/1M input tokens (SiliconFlow pricing), a 6,000-token input costs $0.0006 per query — 6× the current ~1,000-token baseline. At 500 queries/day, this is $90/month vs. the $8–35 budget target.

**Why it happens:**
Protocol design naturally trends toward completeness. Each framework owner (CVP, ABC, etc.) wants all their steps and a representative example. No one reviews the cumulative token budget across all 9 protocols until the first month's API invoice arrives.

**How to avoid:**
Enforce a token budget at design time, not after:
1. Cap each protocol definition at 300 tokens maximum: steps list (≤8 items × 20 tokens = 160 tokens) + no inline few-shot examples in the system prompt.
2. Move few-shot examples to a separate reference document injected ONLY when the protocol requires calculation demonstration — use `query_type == "Calculation"` to gate this injection.
3. Keep the glossary snippet at its current cap of 50 terms (already implemented in `_build_glossary_snippet(max_terms=50)`). Do not increase this for KPE prompts.
4. Add a `count_prompt_tokens()` test in `tests/test_prompts.py` that asserts every protocol's system prompt + typical context block stays under 5,000 total input tokens.
5. Use tiered protocol verbosity: Simple queries get a 2-sentence protocol summary; Complex queries get the full step list.

**Warning signs:**
- Any single protocol definition exceeds 400 tokens when measured with a tokenizer
- Monthly SiliconFlow cost increases >2× after KPE rollout without a corresponding increase in query volume
- Generation latency increases from the current ~3–5s to >8s (longer prompts = longer time to first token on Qwen3-30B)

**Phase to address:** Protocol registry phase (first KPE phase) — build budget enforcement before writing any protocol content

---

### Pitfall 2: Citation Format Breaking Change Ripples to Frontend

**What goes wrong:**
`build_citations()` in `src/generation/citation_builder.py` currently returns `list[dict]` where each dict has: `formatted`, `book_title`, `chapter`, `page_start`, `page_end`, `section_path`, `author`. The frontend TypeScript type `Citation` in `frontend/src/types/sse.ts` (lines 3–11) mirrors this shape exactly — `formatted: string` is the rendered display string. The v1.1 plan introduces `[Kerangka N]` citations for methodology sources, which requires either: (a) a new `citation_type: "textbook" | "methodology"` field on each citation, or (b) separate citation lists. If `citation_type` is added without updating the TypeScript type, the frontend silently ignores it. If the `formatted` string format changes (e.g., adding "Kerangka: " prefix), `ChatMessage.tsx` renders raw strings so visual output changes but nothing breaks — until the history DB stores the new format and old history items with the old format are loaded alongside new items, creating inconsistent UI display. If a second `citations` array is added to the SSE event (e.g., `framework_citations`), the `SSEEvent` union type in `sse.ts` line 38 needs a new variant or the frontend ignores the new array entirely with no error.

**Why it happens:**
Backend citation format is defined in pure Python (no schema enforcement between layers). The frontend consumes it via JSON parsing of SSE events with TypeScript types that are assertions, not runtime validators. Changes to Python output that are structurally additive (new keys) silently pass through. Changes that are structurally different (new arrays) require coordinated frontend updates that are easy to miss.

**How to avoid:**
Treat the citation contract as an API contract:
1. Extend, do not replace: add `citation_type: str = "textbook"` as a new key with a default that preserves existing behavior. Existing frontend continues working — new frontend reads the key.
2. Update `frontend/src/types/sse.ts` `Citation` interface in the same commit that changes `citation_builder.py`.
3. Add `citation_type` rendering to `ChatMessage.tsx` (different icon or label for methodology vs textbook sources).
4. Write a test `tests/test_citation_builder.py` that asserts `build_citations()` output always contains `citation_type` key and that textbook docs produce `"textbook"` and consulting docs produce `"methodology"`.
5. Do not add a second separate array to the SSE event payload. One `citations` list with typed entries is simpler than two parallel lists that must stay synchronized.

**Warning signs:**
- Frontend renders citations with no visual distinction between textbook and consulting sources (even after the backend change)
- History sidebar shows mixed old/new citation formats for items loaded together
- TypeScript type checking passes but browser console shows undefined property warnings at runtime

**Phase to address:** Domain-aware retrieval + citation differentiation phase — address before wiring up multi-domain search

---

### Pitfall 3: Qdrant Payload Index for `source_domain` Missing Before Filtering

**What goes wrong:**
`hybrid_search()` in `src/retrieval/vector_search.py` currently sends unfiltered queries to Qdrant (no `filter` parameter in `client.query_points()`). The v1.1 plan adds a `domain_filter` parameter that translates to a Qdrant `Filter(must=[FieldCondition(key="source_domain", ...)])`. Qdrant evaluates filters by scanning the payload index for the field. If `source_domain` was never added to the payload index, Qdrant falls back to a full payload scan on every query — for a collection with 80,000+ points this is 3–5× slower than an indexed lookup. Worse: on Qdrant Cloud Free Tier (1 GB RAM), the full scan may trigger an OOM-style timeout that presents as a generic connection error, not a "missing index" error. The existing `create_collection()` function already creates payload indices for `book_title`, `chapter`, and `content_type` (lines 73–79 of `qdrant_uploader.py`). But `source_domain` is a new field — it is NOT in the current collection schema. Backfilling the index on an existing collection requires a separate `create_payload_index()` call with `wait=True` — which blocks the Qdrant cluster for the duration of the indexing operation (estimated 10–30 minutes for 80,000 points on the free tier).

**Why it happens:**
New filter fields added during development are tested against a small local collection (100–1,000 points) where full payload scans are fast enough to seem correct. The index gap only manifests at scale in production. There is no Qdrant error for "this field has no index" — it just scans slower.

**How to avoid:**
1. Add `source_domain` to the `create_collection()` payload index creation block (lines 73–79 of `qdrant_uploader.py`) immediately when writing the backfill script — before uploading any consulting book chunks.
2. For the existing production collection, run the backfill as a migration step with explicit index creation first: call `create_payload_index(field_name="source_domain", field_schema=PayloadSchemaType.KEYWORD, wait=True)` before any filtered queries go live.
3. Add a startup health check that verifies `source_domain` index exists: use `client.get_collection(name).payload_schema` and assert `"source_domain"` is in the schema.
4. Test filtered queries on the actual production collection size (not a test collection) before releasing the domain filter feature.

**Warning signs:**
- Filtered queries take >3 seconds whereas unfiltered queries take <500ms (signals full payload scan)
- Qdrant Cloud dashboard shows elevated memory usage during query bursts after domain filter rollout
- Query returns correct results but latency is inconsistent (sometimes fast, sometimes slow) due to caching masking the missing index

**Phase to address:** Multi-domain retrieval phase — index creation must precede backfill, backfill must precede filtered queries

---

### Pitfall 4: Query Classifier Extension Breaks Existing Calculation Detection

**What goes wrong:**
`is_calculation_query()` in `src/retrieval/query_classifier.py` is a single boolean function called in `route_node()` (nodes.py line 21). The v1.1 plan extends routing to also select a KPE protocol (CVP, Variance, ABC, etc.). The simplest extension is to add protocol selection into the same `route_node()` function. The risk is that the current classifier uses a keyword + number pattern — and protocol detection keywords (e.g., "CVP", "break-even", "variance") overlap with calculation detection keywords (`_CALC_KEYWORDS` already contains "bep", "break-even"). A query like "hitung CVP analysis untuk produk ini dengan fixed cost 500000" must trigger BOTH Calculation routing AND CVP protocol selection. If the protocol classifier runs a separate regex pass that partially matches on "CVP" and returns "CVP" as the protocol without checking for numbers, the integration point where `query_type` and `protocol_id` are set can have conflicting states: `query_type="Calculation"` but `protocol_id=None` (if number check blocked CVP selection), or `query_type="Simple"` but `protocol_id="CVP"` (if protocol selection runs first and shortcuts the calculation check).

**Why it happens:**
The existing classifier was designed as a single-concern function. Adding protocol selection as a second concern to the same routing function creates implicit state dependencies that are not captured in the function signature or tests.

**How to avoid:**
Keep `is_calculation_query()` untouched. Add a new independent function `select_protocol(query: str) -> str | None` that returns a protocol ID or `None`. Call both in `route_node()` and store results in separate state fields: `query_type` (existing) and `protocol_id` (new). Explicitly define the interaction: if `query_type=="Calculation"` and `protocol_id` is set, the prompt builder uses the calculation protocol variant of that protocol. Write tests covering all four cases: (Calculation, protocol), (Calculation, no protocol), (non-Calculation, protocol), (non-Calculation, no protocol).

```python
# In route_node — explicit, not conflated
return {
    "query_type": "Calculation" if is_calculation_query(query) else "Simple",
    "protocol_id": select_protocol(query),  # None if no protocol matched
    "llm_call_count": 0,
    "crag_iterations": 0,
    "crag_grade": None,
}
```

**Warning signs:**
- Test suite for `test_query_routing.py` passes but a new integration test for "hitung CVP dengan data 50000, 200, 150" returns `protocol_id=None` when it should return `"cvp"`
- Queries that previously routed to `generate_calc_node` now route to `generate_node` (missing calculation step format)
- Protocol is selected but the system prompt used is the non-calculation variant (check Langfuse traces)

**Phase to address:** Query classifier extension phase — write all four-case tests before touching `route_node()`

---

### Pitfall 5: 21-Book Ingestion Blows the Qdrant Free Tier Disk Limit

**What goes wrong:**
The Qdrant Cloud Free Tier provides 4 GB disk. The existing collection already contains chunks from v1.0 ingestion. Consulting books are methodology/process books — they tend to be more text-dense than accounting textbooks with fewer tables and formulas, meaning a higher proportion of their content produces narrative_text chunks. Estimated consulting book chunk counts: 21 books × average 300 pages × 1.5 chunks/page × 30% narrative selection rate = ~2,800 chunks minimum. More realistically at full ingestion (all content types): 21 books × 300 pages × 2 chunks/page = ~12,600 new chunks. Each chunk has a 1,024-dim dense vector at INT8 quantization (1 byte/dim = 1 KB) + sparse vector (~200 non-zero entries × 8 bytes = ~1.6 KB) + payload text (~500 bytes) = ~3 KB per point. 12,600 new chunks × 3 KB = ~38 MB of raw data, well within 4 GB. However, existing accounting book chunks may already consume 300–500 MB with indices. The real risk is if consulting books include large diagrams or scanned PDFs that generate substantially more chunks than estimated — a 500-page McKinsey methodology book with diagrams could produce 5,000+ chunks alone.

**Why it happens:**
Disk usage estimates are made for the average case, not the worst case. A single unexpectedly large book (e.g., a consulting methodology with extensive appendices) can double the estimate.

**How to avoid:**
1. Before ingesting all 21 books, ingest 3–5 representative books and measure actual chunk counts and Qdrant disk usage via the dashboard.
2. Set a pre-ingestion checkpoint: if the test batch produces >200 chunks per book on average, reconsider the chunking strategy for consulting content (larger parent chunks, fewer child chunks).
3. Monitor Qdrant disk usage after each batch of 5 books during the full ingestion run.
4. Consulting books skip fast-graphrag (already decided) — this saves the ~50 MB workdir overhead per book that graphrag would add.
5. Keep the existing `check_book_exists()` guard active to prevent accidental double-ingestion inflating chunk counts.

**Warning signs:**
- Qdrant Cloud dashboard shows disk at >70% after the first 10 consulting books
- Individual consulting books producing >500 chunks during ingestion (check pipeline logs)
- Ingestion script hangs or returns network errors (Qdrant Cloud throttles writes when disk is nearly full)

**Phase to address:** Consulting book ingestion phase — measure disk usage after first 5 books before committing to full 21-book run

---

### Pitfall 6: Domain Filter Breaks Existing Queries by Excluding Accounting Chunks

**What goes wrong:**
The v1.1 plan adds `domain_filter` to `hybrid_search()`. Existing Qdrant points (all 80,000+ accounting chunks) do NOT have a `source_domain` payload field — they were ingested before this field existed. The backfill script must set `source_domain="accounting"` on all existing points. If the backfill runs partially (interrupted mid-way), some accounting chunks have the field and some do not. A filter `must=[FieldCondition(key="source_domain", match=MatchValue(value="accounting"))]` returns only chunks WHERE the field exists AND equals "accounting" — not chunks where the field is absent. Points with no `source_domain` field are excluded from filtered queries entirely. This means: partial backfill silently reduces retrieval scope. A user asking "apa itu ABC costing" after partial backfill might get 3 results instead of 20 — CRAG grades it INCORRECT, reformulates, gets 3 again, returns "not found." No error is raised; the quality degradation is silent.

**Why it happens:**
Qdrant's filter semantics are "field exists AND matches value" not "field matches OR field is absent." Developers accustomed to SQL `WHERE source_domain = 'accounting' OR source_domain IS NULL` expect a fallback for missing fields — Qdrant does not do this by default.

**How to avoid:**
1. Design the backfill as an atomic operation: use Qdrant's `set_payload()` with scroll iteration + explicit progress tracking. Log count of updated points every 1,000 points. Verify final count matches total collection point count before enabling any domain-filtered queries.
2. After backfill, verify with a count query: `client.count(filter=Filter(must=[FieldCondition(key="source_domain", match=MatchValue(value="accounting"))]))` must equal the pre-backfill total collection count.
3. Make domain filtering opt-in via the API, not the default: `hybrid_search()` with no `domain_filter` argument behaves exactly as before (no filter). Domain-filtered queries are only used when the API caller explicitly requests them.
4. Add a migration test `tests/test_qdrant_indexing.py::test_backfill_coverage` that verifies 100% of points have `source_domain` set.

**Warning signs:**
- Post-backfill, a count of `source_domain="accounting"` points is less than total collection points
- Existing test queries that returned 15+ results now return <5 results after domain filter rollout
- CRAG grade distribution shifts toward INCORRECT/AMBIGUOUS after rollout (monitoring via Langfuse)

**Phase to address:** Multi-domain retrieval phase — backfill must complete and be verified before domain filter queries go live

---

### Pitfall 7: Protocol Over-Engineering Adds LLM Calls to What Should Be Zero-LLM Routing

**What goes wrong:**
The v1.1 KPE design specifies "hardcode framework steps in system prompts (zero LLM calls for protocol selection)." The correct implementation: `select_protocol()` is a pure Python regex/keyword function that returns a protocol ID string — no LLM call. The temptation during implementation is to call the LLM to select the "most appropriate" protocol when the keyword match is ambiguous (e.g., a query about "variance analysis for transfer pricing" could match both Variance and Transfer Pricing protocols). An LLM-based fallback adds 1 extra API call per ambiguous query — raising the per-query cost from 2–3 calls (Simple path) to 3–4 calls, and potentially from 4–5 calls (Calculation path) to 5–6 calls. At 200 queries/day with 40% ambiguous, this is 80 extra LLM calls/day × $0.0004/call = $0.032/day = ~$1/month extra. Small, but the principle matters: the "no LLM calls for routing" decision exists because it keeps latency predictable and avoids cascading failures where routing itself fails due to API errors.

**Why it happens:**
Pure keyword matching feels brittle for ambiguous queries. An LLM call "feels safer." The cost and latency implications are not front-of-mind during feature development.

**How to avoid:**
For ambiguous protocol matches, fall back to the "General" protocol (already in the 9-protocol registry) rather than calling an LLM. The General protocol is designed for exactly this case. Document this fallback explicitly in the protocol registry code so future developers do not add an LLM call to "fix" ambiguous routing.

```python
def select_protocol(query: str) -> str:
    """Pure keyword matching — zero LLM calls. Returns protocol_id or 'general'."""
    # ... keyword matching logic ...
    if len(matches) > 1:
        return "general"  # fallback, not LLM resolution
    return matches[0] if matches else "general"
```

**Warning signs:**
- Langfuse traces show 4+ LLM calls for Simple queries (expected: 2 calls)
- Average query latency increases from ~5s to ~8s after KPE rollout
- A code review shows `llm_generate()` called inside `select_protocol()` or `route_node()`

**Phase to address:** Protocol registry + query classifier phase — define the zero-LLM constraint as a test assertion

---

### Pitfall 8: 21-Book Ingestion Time and API Cost Underestimation at SiliconFlow Rate Limits

**What goes wrong:**
At SiliconFlow's standard tier (1,000 RPD for embedding model), embedding 21 consulting books proceeds as follows: 21 books × 300 pages average × 2 chunks/page = 12,600 chunks. The current embedder in `src/ingestion/indexing/embedder.py` processes in batches with rate limiting. At 1,000 RPD, and assuming batch size of 32 chunks per embedding call = ~394 embedding API calls total. That is well within daily limits for a single day. However, the parsing stage (MinerU/Docling) runs on the GTX 1660 Ti at ~3–8 minutes per book for complex PDFs. 21 books × 5 min average = ~105 minutes of parsing. The actual risk is **sequential parsing blocking embedded-then-upload**: if parsing and embedding run as a linear pipeline per book (current `run_ingestion_pipeline()` design), total wall time is 105 min (parsing) + ~30 min (embedding 12,600 chunks) = ~135 minutes minimum. This is manageable but a single failed PDF (MinerU crash on a corrupt PDF) in the middle of the batch halts the entire run unless the `check_book_exists()` guard allows partial restart. The bigger risk is VLM captioning: 21 books × average 10 diagrams/book × 1 VLM call/diagram = 210 VLM API calls to `Qwen2.5-VL-72B` — at 50 RPD default this is 4+ days. At 1,000 RPD it is still 210 calls which hits if other calls are also running simultaneously.

**Why it happens:**
VLM calls are easy to forget when estimating ingestion cost/time because diagrams are sparse per book. But 21 books with variable diagram density can accumulate to a rate-limit-significant number.

**How to avoid:**
1. For consulting/methodology books, disable VLM diagram captioning (`use_vlm=False`) — these books have process diagrams and org charts that do not contribute meaningfully to accounting text retrieval. Save VLM budget for the remaining accounting textbooks.
2. Run a dry-run estimate before full ingestion: parse 3 books, count chunks + diagram calls, extrapolate to 21 books.
3. Use the existing checkpoint resume (`data/checkpoints/`) — verify it is enabled in the batch ingestion script.
4. Process books in batches of 5, verify Qdrant disk usage and API call counts between batches.
5. Estimated cost for 21 books (no VLM): 12,600 chunks × ~300 tokens/chunk × $0.04/1M tokens = ~$0.15 total embedding cost. This is negligible.

**Warning signs:**
- SiliconFlow dashboard shows VLM model approaching daily limit after the first 10 books
- Pipeline log shows `vlm_captioner.py` being called for books identified as "consulting" type
- Individual book ingestion taking >15 minutes (signals VLM calls or MinerU falling back to CPU)

**Phase to address:** Consulting book ingestion phase — add `skip_vlm` flag to pipeline before starting batch run

---

### Pitfall 9: Test Suite Contamination From New State Fields in RAGState

**What goes wrong:**
`RAGState` in `src/agents/state.py` is the shared data contract for all LangGraph nodes. Adding `protocol_id: str | None` as a new field to `RAGState` is a non-breaking Python change — existing code that does not set `protocol_id` still works because LangGraph state updates are dict merges. However, existing tests that construct `RAGState` dicts directly (e.g., `{"query": "...", "query_type": "Simple", ...}`) do NOT include `protocol_id`. If any new node reads `state.get("protocol_id")` and the test does not set it, the test passes vacuously (returns `None` as fallback). This creates a hidden test gap: protocol selection is never exercised in the existing test suite. The more dangerous case is if a node is added that fails on `None` protocol (e.g., a prompt builder that does `PROTOCOL_REGISTRY[state["protocol_id"]]` with `None` as key) — existing tests pass but production fails on the first real query.

**Why it happens:**
LangGraph's dict-merge state semantics mean tests can omit new fields without syntax errors. The gap is not visible until a production query triggers a code path that requires the new field.

**How to avoid:**
1. Add `protocol_id: str | None = None` to `RAGState` with an explicit default.
2. Update `conftest.py` sample state fixtures to include `protocol_id: None` so all existing tests remain valid without change.
3. Add dedicated tests for the new protocol selection path: one test with `protocol_id="cvp"` confirming the CVP prompt is used, one test with `protocol_id=None` confirming the General prompt is used.
4. Add a `test_protocol_none_safety.py` test that calls each new node with `protocol_id=None` and asserts it does not raise a `KeyError` or `TypeError`.

**Warning signs:**
- A `KeyError: None` appears in production logs for a query that should use the General protocol
- Existing test suite passes at 100% after RAGState extension (expected: correct) but no new tests were added for `protocol_id` (suspicious)
- Langfuse shows `protocol_id` as null for all production queries, including ones where CVP/Variance protocol should have been selected

**Phase to address:** Protocol registry + RAGState extension phase — update fixtures in the same PR as state schema changes

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding protocol steps as multi-line strings in `config/prompts.py` | Fastest to implement; single file | Adding a 10th protocol requires editing a 600-line file; protocol variations (standard vs. calculation) double the line count | MVP only — move to structured registry before beta |
| Skipping the `source_domain` backfill test assertion | Saves 1 day of test writing | Partial backfill silently degrades retrieval quality; only caught when a user reports "not found" on a known topic | Never acceptable — backfill correctness is directly observable |
| Running domain-filtered queries without a verified payload index | Correct results from full payload scan | 5–10× query latency; Qdrant Cloud free tier OOM under load | Never in production |
| Adding `protocol_id` selection logic inside `generate_node()` instead of `route_node()` | Avoids changing route_node | Protocol selection runs after retrieval — retrieval could have used protocol context to filter better | Never — routing decisions must precede retrieval |
| Using the same `build_citations()` function for both textbook and consulting sources with no `citation_type` | Zero frontend changes | All citations look identical; consultant cannot tell client which source is a methodology framework vs. a textbook | Never — citation differentiation is a stated v1.1 requirement |
| Ingesting all 21 consulting books in one `for book in books: ingest()` loop with no batch size control | Single script, clean code | One OOM or API error at book 18 loses no data (checkpoint resume helps) but may leave partial state in Qdrant if uploader partially succeeded | Acceptable only if `check_book_exists()` guard is verified to handle partial uploads |

---

## Integration Gotchas

Common mistakes when connecting the new features to existing services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Qdrant `set_payload()` for backfill | Using `overwrite=True` on a per-point upsert loop instead of `set_payload` with a scroll filter — O(n) individual calls instead of batched | Use `client.set_payload(collection_name, payload={"source_domain": "accounting"}, points_selector=FilterSelector(filter=Filter(must_not=[FieldCondition(key="source_domain", ...)])))` to update all untagged points in one call |
| `hybrid_search()` domain filter | Passing `domain_filter="accounting"` but the Qdrant Filter being constructed inside uses `must` instead of `should` — with `must`, a query that matches on dense vectors but the `source_domain` field is null (pre-backfill point) is excluded | Verify backfill is complete before enabling filter; or use `should` semantics until backfill is verified |
| `generate_response()` in `generator.py` | Adding `protocol_id` as a new parameter that defaults to `None` but forgetting to update `generate_calc_node()` in `nodes.py` (line 287) which calls `generate_response()` without the new param | Update both call sites: `generate_node()` line 179 and `generate_calc_node()` line 287 in `nodes.py` |
| FastAPI SSE `/api/query` endpoint | Adding `protocol_id` to the SSE event stream (`query_type` event) but not updating the `SSEEvent` TypeScript union type — frontend silently ignores the new field | Coordinate `backend/main.py` SSE event changes with `frontend/src/types/sse.ts` type updates in same commit |
| `history_db.py` `save_history()` | Current signature: `save_history(question, response, citations, query_type, crag_grade)`. Adding `protocol_id` requires updating this call in `main.py` line 133 AND the SQLite schema | Run a schema migration (ALTER TABLE or recreate); test against existing history DB to verify old rows load correctly |
| SiliconFlow embedding during bulk ingestion | Batch embedding 12,600 chunks without per-batch delay allows hitting rate limit on the 1001st call — the existing `_RETRY_CONFIG` (60s initial wait) will pause the job for 60s but resume correctly | Verify checkpoint resume works: kill the ingestion mid-batch, verify the restart skips already-embedded chunks |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Building protocol prompt inline for every query (string concatenation in hot path) | Unnoticeable with 9 protocols | At 500 queries/day, string building adds ~1ms overhead per query (negligible) | Never a real problem — pre-building prompt templates is good practice but not urgent |
| Loading all 9 protocol definitions into RAM at import time | Fast import, no issue | If protocol definitions grow to include large few-shot datasets, startup memory increases | When each protocol definition exceeds 50 KB (unlikely in v1.1 scope) |
| Domain-filtered queries always scanning both accounting and consulting domains separately and merging | Correct results, cleaner code | Double the vector search calls per domain-split query | When domain routing is implemented as two separate `hybrid_search()` calls instead of one filtered call |
| Storing `protocol_id` in conversation history (LangGraph MemorySaver) for all turns | Simple to persist | Protocol selection for turn 1 may bleed into turn 5 of the same session, forcing wrong protocol on follow-up questions | Any multi-turn session where user changes topic within one session |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing the protocol name ("CVP Analysis Protocol") as a badge without explaining what it means | User sees an opaque label they did not request and does not understand | Either omit the protocol badge entirely (it is an internal implementation detail) or show a human-readable label like "Analisis biaya-volume-laba" |
| Differentiating [Sumber N] vs [Kerangka N] only in the response body text but not in the citations panel | User sees "Sumber 1" and "Kerangka 2" in the text but the citations panel shows a flat undifferentiated list | The citations panel in `ChatMessage.tsx` must visually distinguish methodology sources (e.g., different color or icon) |
| Returning a consulting methodology citation when the user asked a conceptual textbook question | User is confused: "why is McKinsey cited for a question about standard costing?" | Domain filter must be applied correctly: conceptual accounting queries search only `source_domain="accounting"` by default; consulting sources are added only when the query explicitly requests methodology/framework guidance |
| Failing to indicate that consulting book content is "methodology" not "authoritative accounting standard" | User presents methodology citation to client as if it were a textbook fact | Add a soft disclaimer on consulting-source citations: "(sumber metodologi — bukan standar akuntansi)" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Backfill script:** Runs without errors on 100 test points — verify it actually runs on the full production collection and the final count matches total collection size. Check `client.count()` before and after.
- [ ] **Payload index creation:** `create_collection()` updated to include `source_domain` index — verify by calling `client.get_collection(name).payload_schema` and asserting `"source_domain"` appears. Do not assume the migration ran.
- [ ] **Protocol selection:** `select_protocol("hitung CVP dengan fixed cost 500000")` returns `"cvp"` (not `None`) — write this as a named test, not an ad-hoc sanity check.
- [ ] **Citation type differentiation:** The frontend renders a visual distinction between textbook and methodology citations — verify in the browser, not just by reading the TypeScript type definition.
- [ ] **Token budget:** All 9 protocol system prompts measured with a tokenizer — assert the maximum is under 500 tokens. A "looks complete" protocol spec may have crept to 800 tokens.
- [ ] **Calculation + protocol combined routing:** A query with a number AND a protocol keyword routes to both `generate_calc_node` AND uses the correct protocol prompt — this requires a specific test, not derivable from passing the individual unit tests.
- [ ] **21-book ingestion checkpoint resume:** Kill the batch script mid-ingestion at book 12, restart, verify books 1–12 are skipped via `check_book_exists()` and books 13–21 are ingested correctly.
- [ ] **Multi-domain retrieval returns both domains:** A query about "methodology for implementing ABC costing" should return chunks from BOTH accounting textbooks AND consulting books — verify the top-k results include both `source_domain` values.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| System prompt token budget exceeded (discovery post-launch) | LOW | Truncate protocol steps to ≤5 items; remove few-shot examples from system prompt; redeploy in <1 hour |
| Citation format break — frontend shows raw dict strings | LOW | Revert `citation_builder.py` change; fix TypeScript type; redeploy; no data loss |
| Qdrant payload index missing — slow queries | MEDIUM | Call `create_payload_index("source_domain", wait=True)`; blocks cluster 10–30 min; all existing queries continue to work (just slowly) during index build |
| Partial backfill — some accounting chunks missing `source_domain` | LOW | Re-run backfill script; it sets payload on all points matching filter; idempotent if backfill uses `set_payload` (not upsert) |
| Consulting book double-ingested (duplicate chunks) | LOW | Call `delete_book(client, book_title)` for the duplicate; re-ingest once; no embedding cost if chunks backup exists |
| Protocol routing stuck on "General" for all queries | LOW | Protocol keyword list needs expansion; zero downtime fix — update `select_protocol()` keyword set and redeploy |
| `source_domain` filter accidentally excludes all results | LOW | Revert domain filter to optional; default to no filter; query behavior reverts to v1.0 behavior immediately |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| System prompt token budget overflow | Protocol registry phase (first KPE phase) | Token count test asserts all 9 protocols < 500 tokens system prompt |
| Citation format breaking change | Domain-aware retrieval + citation differentiation phase | TypeScript `Citation` interface updated in same commit; visual test in browser |
| Qdrant `source_domain` payload index missing | Multi-domain retrieval phase (before backfill) | `client.get_collection().payload_schema` includes `source_domain` before any filtered query |
| Query classifier extension breaks Calculation detection | Query classifier extension phase | Four-case test matrix: (Calculation+protocol), (Calculation, no protocol), (non-Calc+protocol), (non-Calc, no protocol) |
| 21-book ingestion exceeds disk limit | Consulting book ingestion phase | Measure disk usage after first 5 books; verify headroom before committing to full 21-book run |
| Domain filter excludes un-backfilled accounting chunks | Multi-domain retrieval phase | `client.count(source_domain="accounting")` == total pre-consulting collection count |
| LLM call added to protocol selection | Protocol registry + classifier phase | Assert `select_protocol()` contains zero calls to `llm_generate()` via code review + test |
| VLM calls during consulting book ingestion | Consulting book ingestion phase | Pipeline log shows `use_vlm=False` for all consulting books; VLM API call count = 0 post-ingestion |
| Test suite contamination from new RAGState fields | RAGState extension phase | All new state fields have explicit `None` safety tests; `conftest.py` fixtures updated |
| Partial backfill causes silent retrieval degradation | Multi-domain retrieval phase | Backfill completion test: count of `source_domain="accounting"` == original collection count |

---

## Sources

- `src/generation/citation_builder.py` — current citation contract; lines 6–63 define the dict shape consumed by frontend
- `frontend/src/types/sse.ts` — `Citation` TypeScript interface at lines 3–11; `SSEEvent` union at lines 34–41
- `src/retrieval/vector_search.py` — `hybrid_search()` signature; currently no `filter` parameter
- `src/ingestion/indexing/qdrant_uploader.py` — `create_collection()` lines 33–79; existing payload index fields
- `src/retrieval/query_classifier.py` — `_CALC_KEYWORDS` and `is_calculation_query()` — overlapping keywords with protocol names
- `src/agents/nodes.py` — `route_node()` lines 17–34; both `generate_node()` and `generate_calc_node()` call `generate_response()`
- `config/prompts.py` — current prompt token baseline (~350 tokens per prompt variant)
- `config/settings.py` — Qdrant collection name, SiliconFlow model IDs
- `.planning/PROJECT.md` — v1.1 milestone scope, constraints (SiliconFlow 50–1,000 RPD, GTX 1660 Ti, Qdrant Free Tier)
- [Qdrant payload filtering semantics — official docs](https://qdrant.tech/documentation/concepts/filtering/) — filter excludes points where field is absent
- [Qdrant set_payload API](https://qdrant.tech/documentation/concepts/payload/#set-payload) — batch payload update without re-embedding
- [SiliconFlow rate limit tiers](https://docs.siliconflow.cn/en/userguide/rate-limits/rate-limit-and-upgradation) — 50 RPD default, 1,000 RPD after credit purchase

---
*Pitfalls research for: v1.1 KPE + multi-domain retrieval + consulting book ingestion*
*Researched: 2026-03-29*
