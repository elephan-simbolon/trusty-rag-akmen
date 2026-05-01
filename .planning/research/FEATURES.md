# Feature Research

**Domain:** KPE (Knowledge Protocol Engineering) milestone — adding protocol-driven reasoning, consulting book ingestion, and domain-aware retrieval to existing management accounting RAG assistant
**Researched:** 2026-03-29
**Confidence:** HIGH for architecture decisions; MEDIUM for KPE-paper specifics (paper does not address implementation details directly)

---

## Context

**Milestone goal:** Upgrade Trusty RAG Akmen from a textbook Q&A tool to a consulting-grade assistant that structures answers using domain-specific reasoning frameworks (protocols), backed by both accounting textbooks and consulting methodology books.

**Existing system (already built — do NOT rebuild):**
- Hybrid RAG: dense + sparse BM25, RRF fusion, Qwen3-Embedding-8B
- CRAG quality gate: CORRECT/AMBIGUOUS/INCORRECT grading on rerank_score thresholds
- Adaptive routing: rule-based `is_calculation_query()` → Calculation path; everything else → Simple
- fast-graphrag knowledge graph for relational queries
- LangGraph Phase 3 graph: route → preprocess → retrieve → graph_retrieve → rerank → crag_grade → generate/generate_calc/reformulate
- Three system prompt variants: `SYSTEM_PROMPT_GENERATOR`, `SYSTEM_PROMPT_GENERATOR_CALCULATION`, `SYSTEM_PROMPT_SYNTHESIS`
- React 19 + SSE streaming frontend

**KPE paper (arXiv 2507.02760) core finding:** RAG provides declarative facts ("what"). KPE provides operational procedures ("how"). The paper treats source documents as source code for protocols, not passive retrieval targets. The protocol encodes expert decision trees, heuristics, and step sequences. The paper does NOT specify how many protocols a domain needs, how to do protocol selection, or how to structure few-shot examples — those are implementation decisions not addressed in the paper.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that the user will assume exist once the KPE milestone is announced. Missing these = milestone fails to deliver its promise.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Protocol registry with management accounting frameworks | Core KPE value prop — without registered protocols, there is nothing to select or apply | LOW | 9 protocols hardcoded as Python dataclasses/dicts: CVP, Variance, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General. Steps encoded as ordered lists of strings. Zero LLM calls to select. |
| Enhanced query classifier with protocol selection | The route_node currently only distinguishes Calculation vs Simple. KPE requires mapping query → protocol, not just type. | MEDIUM | Extend `route_node` and `is_calculation_query`. Add protocol keyword matching (rule-based, zero LLM calls) for CVP/Variance/ABC/Budgeting queries. Fall back to General protocol when no specific match. Output: `query_type` + `selected_protocol` in RAGState. |
| Composable prompt builder | Protocol-specific reasoning steps must be injected into system prompts without creating 9×3=27 static prompt files | MEDIUM | Single `build_system_prompt(query_type, protocol, source_types)` function composing base role + protocol steps + citation rules + glossary. Keeps prompts in one place (config/prompts.py) and avoids duplication. |
| Consulting book ingestion into Qdrant (21 books) | Without ingested consulting books, the new citation type `[Kerangka N]` has nothing to cite | HIGH | 21 books tagged `source_domain="consulting"` at ingestion. Skip fast-graphrag (procedural knowledge ≠ entity extraction targets). Reuse existing 9-step ingestion pipeline — only add metadata field. |
| Backfill `source_domain="accounting"` on existing Qdrant points | Without this, domain_filter cannot distinguish accounting vs consulting chunks | MEDIUM | Qdrant `set_payload` on all existing points (batch by scroll). Qdrant supports filter-based payload updates without knowing point IDs. Required before domain_filter can work. |
| Domain-aware retrieval | CVP questions should prefer accounting textbooks; McKinsey methodology questions should prefer consulting books; mixed questions should search both | MEDIUM | Add `domain_filter` parameter to `hybrid_search()`. Pass through Qdrant `Filter(must=[FieldCondition(key="source_domain", ...)])` in Prefetch blocks. `route_node` decides domain scope from protocol. |
| Citation differentiation `[Sumber N]` vs `[Kerangka N]` | User is a consultant — citing "McKinsey framework step 2" must look different from "Horngren p.245" to clients | LOW | Generator layer checks `source_domain` on each doc to assign citation prefix. Extend citation builder in `src/generation/generator.py`. |

### Differentiators (Competitive Advantage)

Features that elevate the tool above generic RAG and validate the KPE investment.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Structured protocol steps in generated responses | Consultant answers with a framework look more professional and defensible to clients vs. free-form prose | MEDIUM | Protocol steps injected into system prompt as numbered procedure. LLM is instructed to follow steps, not invent its own structure. Output becomes auditable: "Step 1: Classify costs as fixed/variable..." |
| Protocol-specific few-shot examples (1-2 per protocol) | Anchors the LLM to the expected output format for each protocol — critical for consistency across 9 protocol variants | MEDIUM | Best practice: 1-2 examples per protocol max (research confirms 1-3 examples hit sweet spot; 5+ add cost without proportional gain). Place in system prompt, not user turn. Each example: ~150-250 tokens. Total budget per protocol prompt: keep under 600 tokens pre-context. |
| General fallback protocol | When no specific protocol matches, General protocol triggers broad synthesis without framework overhead | LOW | Avoids forcing wrong frameworks on edge queries. Maps to existing `SYSTEM_PROMPT_SYNTHESIS` behavior with added bilingual glossary. |
| Consulting book retrieval as second-domain augmentation | "How do big consulting firms approach transfer pricing decisions?" now has dedicated retrieval from McKinsey, BCG, Deloitte methodology books | HIGH | Consulting books provide procedural heuristics (how to structure a client recommendation) that textbooks don't contain. The combination — textbook accuracy + consulting methodology — is the unique value proposition. |
| Protocol-aware CRAG grading | INCORRECT grade on a CVP query should trigger reformulation that stays within CVP domain, not generic reformulation | LOW | Small enhancement to `reformulate_node`: include selected_protocol in reformulation prompt so the rewrite stays domain-specific. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| LLM-based protocol selection (LLM call to pick which framework to apply) | "LLM knows the domain better than keywords" — seems smarter | (1) Adds 1 LLM call to every query = +$0.001-0.003/query, blowing the $8-35/month budget at 100+ queries/day. (2) Latency: adds 1-2s per query. (3) Accuracy gain over keyword-based routing for well-defined accounting frameworks is marginal — CVP queries reliably contain "break-even", "margin of safety", "contribution ratio"; Variance queries contain "favorable/unfavorable", "material variance", "labor variance". (4) arXiv 2505.23052 (RAGRouter) shows rule-based complexity classifiers achieve 85-92% accuracy at <1ms. Use LLM fallback only for ambiguous cases (AMBIGUOUS CRAG grade + no keyword match). | Rule-based protocol selection (keyword matching on Indonesian+English terms) with General fallback. Reserve LLM protocol selection as a future Phase 2 enhancement if keyword accuracy proves insufficient. |
| 20+ protocols | "More specific protocols = better answers" | (1) Protocol explosion: 20 protocols × 2 few-shot examples × ~200 tokens = 8,000 tokens of overhead before any context is injected. (2) Hard to maintain — every protocol needs curated examples. (3) Marginal benefit past 9-12 well-defined frameworks; management accounting decision trees cluster into fewer than 15 meaningful categories. | 9 protocols covering the core decision space: CVP, Variance, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General. Add protocols only when user demonstrates a real query pattern that General protocol handles poorly. |
| Separate vector collection per domain | "Cleaner architecture if accounting and consulting are separate collections" | (1) Two collections = two sets of Prefetch blocks, two embedding calls, two BM25 indexes. (2) Cross-domain queries (which are common: "what does ABC methodology say vs what do textbooks say?") require manual merging. (3) Qdrant payload filter is the right primitive — single collection, filter by `source_domain`. (4) Qdrant documentation explicitly recommends payload filtering over collection sharding for logical domain separation. | Single collection `trusty_rag` with `source_domain` payload field. Domain-aware retrieval via Filter in query. |
| fast-graphrag ingestion for consulting books | "Entity extraction makes everything better" | (1) fast-graphrag is tuned to accounting entity types: CostType, CostingMethod, Formula, AccountingStandard. (2) Consulting methodology books have different entity patterns: Framework, Engagement, Deliverable, Stakeholder — these will not map to accounting entity types and will degrade graph quality. (3) Explicit decision in PROJECT.md: skip fast-graphrag for consulting books. | Qdrant-only ingestion for consulting books. The value of consulting books is procedural text retrieval, not graph relationships. |
| Dynamic protocol updating via UI | "Let the consultant add new protocols without code changes" | (1) UI complexity high. (2) Protocol quality depends on careful curation of steps and few-shot examples — free-form user input will create inconsistent protocols. (3) Not needed for personal tool. | Protocols as Python dataclasses in `config/protocols.py`. Add new protocols by editing code — low friction for a developer-owned personal tool. |
| Streaming protocol steps (show framework selection in UI before answer) | "Show user which framework is being applied" | (1) Requires new SSE event type `protocol_selected` in backend. (2) Adds frontend UI complexity. (3) Nice-to-have, not blocking core KPE value. | Include selected protocol name at top of generated response as a brief header line. Simple to implement, zero SSE changes. |

---

## Feature Dependencies

```
[Protocol Registry (config/protocols.py)]
    └──required_by──> [Composable Prompt Builder]
    └──required_by──> [Enhanced Query Classifier]
    └──required_by──> [Protocol-specific Few-shot Examples]

[Enhanced Query Classifier (route_node extension)]
    └──requires──> [Protocol Registry]
    └──enables──> [Domain-aware Retrieval] (classifier decides domain scope)
    └──enables──> [Composable Prompt Builder] (classifier outputs selected_protocol)
    └──requires──> [RAGState extension] (add selected_protocol field)

[RAGState extension (add selected_protocol)]
    └──required_by──> [Enhanced Query Classifier]
    └──required_by──> [Composable Prompt Builder]
    └──required_by──> [Protocol-aware CRAG reformulation]

[Composable Prompt Builder (config/prompts.py extension)]
    └──requires──> [Protocol Registry]
    └──requires──> [RAGState.selected_protocol]
    └──replaces──> [Static SYSTEM_PROMPT_GENERATOR / SYSTEM_PROMPT_SYNTHESIS]
    └──enables──> [Structured protocol steps in responses]
    └──enables──> [Protocol-specific few-shot examples]

[Consulting Book Ingestion (21 books → Qdrant)]
    └──requires──> [source_domain metadata field in ingestion pipeline]
    └──requires──> [Existing 9-step ingestion pipeline] (reuse, add metadata only)
    └──enables──> [Domain-aware Retrieval]
    └──enables──> [Citation differentiation [Kerangka N]]
    └──independent_of──> [fast-graphrag] (explicitly skipped)

[Backfill existing Qdrant points (source_domain="accounting")]
    └──requires──> [Consulting Book Ingestion] (must exist before domain_filter makes sense)
    └──enables──> [Domain-aware Retrieval]
    └──implementation──> [Qdrant set_payload via scroll+filter, no IDs needed]

[Domain-aware Retrieval (hybrid_search + domain_filter)]
    └──requires──> [Backfill] (accounting points tagged)
    └──requires──> [Consulting Book Ingestion] (consulting points tagged)
    └──requires──> [Enhanced Query Classifier] (decides domain scope)
    └──requires──> [Qdrant payload index on source_domain]
    └──extends──> [hybrid_search() in src/retrieval/vector_search.py]

[Citation Differentiation [Sumber N] vs [Kerangka N]]
    └──requires──> [source_domain in retrieved doc metadata]
    └──requires──> [Domain-aware Retrieval]
    └──extends──> [citation builder in src/generation/generator.py]

[Protocol-aware CRAG Reformulation]
    └──requires──> [RAGState.selected_protocol]
    └──extends──> [reformulate_node in src/agents/nodes.py]
    └──enhances──> [CRAG quality gate] (reformulation stays protocol-scoped)
```

### Dependency Notes

- **Protocol Registry must exist before everything else:** All KPE features depend on a defined registry. This is a zero-dependency module (pure Python dataclasses). Build first.
- **RAGState extension is a central coordination point:** Adding `selected_protocol` to `RAGState` requires touching state.py, route_node, and generate_node. Do this in one commit to avoid partial state schema inconsistencies.
- **Backfill must run before domain_filter is activated:** Enabling domain_filter on a collection where accounting points have no `source_domain` tag would silently exclude all existing textbook results. Backfill is a one-time migration script, not a feature — treat it as infrastructure.
- **Composable Prompt Builder replaces static prompts:** The three existing `SYSTEM_PROMPT_*` constants in `config/prompts.py` should be refactored into components used by the prompt builder, not deleted. Backward compatibility matters for tests.
- **Citation differentiation is a generator-layer concern:** `hybrid_search()` already returns `metadata` dict per result. Adding `source_domain` to that dict is the only retrieval-side change needed. The generator then decides prefix.

---

## Downstream Answers to Specific Questions

### (1) Is 9 protocols enough for management accounting?

**Yes — 9 is the right number for v1.1.** Research confirms management accounting's decision tree clusters into approximately 9-12 meaningful categories. The 9 proposed protocols (CVP, Variance Analysis, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General) map precisely to the domains the ICAG Management Accounting syllabus and standard consulting engagements cover. The General protocol provides a safe fallback for edge cases. Adding more protocols without demonstrated query patterns that General handles poorly would increase maintenance cost without improving answer quality. Expand to 12 protocols only after observing real query logs showing specific gaps.

### (2) Rule-based vs LLM-based protocol selection

**Use rule-based keyword matching for v1.1.** Evidence:
- arXiv 2505.23052 shows rule-based complexity classifiers achieve 85-92% accuracy at <1ms
- The existing `is_calculation_query()` already demonstrates this pattern works reliably for one protocol type
- Indonesian accounting queries are terminologically predictable: "break-even" / "BEP" / "margin of safety" → CVP; "selisih" / "variance" / "favorable" / "unfavorable" → Variance; "berbasis aktivitas" / "ABC" / "cost driver" → ABC; "harga transfer" / "transfer pricing" → Transfer Pricing
- LLM classification adds 1 call = $0.001-0.003/query = $10-30/month at 100 queries/day, exceeding the $8-35/month budget for intelligence overhead
- Reserve LLM-based protocol selection as a Phase 2 upgrade if keyword accuracy falls below 85% on real query logs

### (3) Few-shot examples in system prompts — best practices

**Use 1-2 examples per protocol, ~150-250 tokens each, placed in system prompt (not user turn).** Evidence:
- Research consensus: 1-3 examples hit the quality sweet spot; 5+ add cost without proportional gain
- Practical budget rule: keep total system prompt (role + protocol steps + 1-2 examples + citation rules + glossary snippet) under 600 tokens to preserve context window budget for retrieved documents
- Example quality > example quantity: a single well-crafted example showing the expected bilingual format (Indonesian prose + English terms + [Sumber N] citation) anchors output format more reliably than 3 mediocre examples
- Place in system prompt for stable, session-wide patterns; reserve user-turn examples for one-off task-specific formats
- For calculation protocols: show one complete worked example (rumus → substitusi → hasil + disclaimer) — do not show abstract structure, show actual numbers

### (4) Multi-domain citation patterns in RAG

**Use inline citation with distinct prefixes, differentiated at the generator layer by source_domain metadata.** Evidence:
- Current system already uses `[Sumber N]` inline citations successfully
- Extending to `[Kerangka N]` for consulting sources is a minimal diff: same citation builder logic, different prefix based on `source_domain` field in doc metadata
- Research (RankStudio citation frameworks survey) confirms inline citations with numeric references are the most readable format for consulting deliverables
- Do NOT use footnote-style or end-of-response source lists as the primary citation — users read Indonesian prose inline and the `[Sumber N]` convention is already established and working
- Mixed queries (CVP textbook + consulting methodology) should interleave both citation types in the same response: "ABC mengalokasikan biaya berdasarkan aktivitas [Sumber 2] dan pendekatan ini umum digunakan konsultan dalam analisis profitabilitas produk [Kerangka 1]."

---

## MVP Definition (for this milestone)

### Launch With (v1.1 — KPE Milestone)

Minimum viable KPE — validates that protocol-driven prompting improves response structure without breaking existing features.

- [ ] Protocol registry — 9 protocols as Python dataclasses in `config/protocols.py` with steps list and protocol_name
- [ ] RAGState extension — add `selected_protocol: Optional[str]` field
- [ ] Enhanced route_node — keyword-based protocol selection, outputs `selected_protocol` alongside `query_type`
- [ ] Composable prompt builder — `build_system_prompt()` function composing role + protocol steps + 1 few-shot example + citation rules + glossary snippet
- [ ] source_domain field in ingestion pipeline — add to chunk metadata at ingest time
- [ ] Consulting book ingestion (21 books) — run ingestion pipeline with `source_domain="consulting"`, skip fast-graphrag
- [ ] Backfill script — one-time Qdrant `set_payload(source_domain="accounting")` on all existing points
- [ ] Domain-aware hybrid_search — add `domain_filter` parameter using Qdrant payload filter
- [ ] Citation differentiation — `[Kerangka N]` prefix for consulting docs in generator

### Add After Validation (v1.1.x)

- [ ] Payload index on `source_domain` — create Qdrant index for efficient filtering (add after backfill confirms data shape)
- [ ] Protocol-aware CRAG reformulation — pass selected_protocol into reformulate_node prompt
- [ ] Few-shot examples per protocol — add 1-2 examples after observing which protocols produce inconsistent output
- [ ] Protocol name header in response — prepend "**Framework: CVP Analysis**" to response for user transparency

### Future Consideration (v2+)

- [ ] LLM-based protocol selection — upgrade rule-based classifier if keyword accuracy falls below 85%
- [ ] Expanding to 12 protocols — add only when real query logs show specific gaps that General protocol handles poorly
- [ ] Protocol library UI — allow consultant to view, edit, and add protocols via frontend
- [ ] Cross-protocol synthesis — detect queries that span multiple frameworks and activate two protocols simultaneously

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Protocol registry (9 protocols) | HIGH | LOW | P1 |
| RAGState extension (selected_protocol) | HIGH | LOW | P1 |
| Enhanced query classifier (keyword protocol selection) | HIGH | LOW | P1 |
| Composable prompt builder | HIGH | MEDIUM | P1 |
| source_domain metadata in ingestion | HIGH | LOW | P1 |
| Consulting book ingestion (21 books) | HIGH | HIGH | P1 |
| Backfill script (existing points → accounting) | HIGH | MEDIUM | P1 |
| Domain-aware hybrid_search (domain_filter) | HIGH | LOW | P1 |
| Citation differentiation [Sumber N] vs [Kerangka N] | MEDIUM | LOW | P1 |
| Payload index on source_domain | MEDIUM | LOW | P2 |
| Protocol-aware CRAG reformulation | LOW | LOW | P2 |
| Few-shot examples per protocol | MEDIUM | MEDIUM | P2 |
| Protocol name header in response | LOW | LOW | P2 |
| LLM-based protocol selection fallback | LOW | MEDIUM | P3 |
| Protocol library UI | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have — milestone is incomplete without these
- P2: Should have — adds reliability and polish, add after P1 is validated
- P3: Nice to have — future enhancement, defer unless explicitly requested

---

## Competitor Feature Analysis

No direct competitor builds KPE-style protocol-driven RAG for management accounting consulting. The comparison is against general approaches.

| Feature | Generic ChatGPT | Generic RAG | Our KPE Approach |
|---------|-----------------|-------------|------------------|
| Structured framework steps in answer | Sometimes (depends on prompt) | No | Always — protocol encodes steps, LLM instructed to follow them |
| Source citation with page numbers | No | Yes (basic) | Yes — [Sumber N] textbook + [Kerangka N] consulting |
| Protocol selection (which framework to apply) | Manual (user must specify) | No | Automatic — keyword routing → protocol selection |
| Consulting methodology retrieval | Web scraped | No | Dedicated 21-book corpus with domain-aware retrieval |
| Accounting textbook retrieval | No | Yes | Yes — 20+ textbooks, unchanged from v1.0 |
| Cross-domain synthesis (textbook + consulting) | Partial | No | Yes — mixed [Sumber N] + [Kerangka N] in same response |
| Quality gate (CRAG) | No | Rare | Yes — unchanged from v1.0 |
| Indonesian bilingual output | Yes | Depends | Yes — unchanged from v1.0 |

---

## Sources

- [arXiv 2507.02760 — Knowledge Protocol Engineering: A New Paradigm for AI in Domain-Specific Knowledge Work](https://arxiv.org/abs/2507.02760)
- [KPE Medium article: Teaching AI the How, Not Just the What](https://medium.com/@delimiterbob/knowledge-protocol-engineering-teaching-ai-the-how-not-just-the-what-7b2d931bb4c4)
- [arXiv 2505.23052 — RAGRouter: Learning to Route Queries to Multiple RAG Pipelines](https://arxiv.org/html/2505.23052v1)
- [Query-Adaptive RAG Routing Cuts Latency 35% While Improving Accuracy](https://ascii.co.uk/news/article/news-20260122-9ccbfc03/query-adaptive-rag-routing-cuts-latency-35-while-improving-a)
- [Qdrant — A Complete Guide to Filtering in Vector Search](https://qdrant.tech/articles/vector-search-filtering/)
- [Few-Shot Prompting Best Practices — DigitalOcean](https://www.digitalocean.com/community/tutorials/_few-shot-prompting-techniques-examples-best-practices)
- [LLM Token Optimization — Redis 2026](https://redis.io/blog/llm-token-optimization-speed-up-apps/)
- [Prompt Engineering Patterns for Successful RAG Implementations](https://machinelearningmastery.com/prompt-engineering-patterns-successful-rag-implementations/)
- [Metadata Filtering: Refine RAG Search](https://app.ailog.fr/en/blog/guides/metadata-filtering-rag)
- [RankStudio — LLM Citations Explained: RAG & Source Attribution Methods](https://rankstudio.net/articles/en/ai-citation-frameworks)
- [ICAG Management Accounting Syllabus 2025](https://patstune.org/2026/03/03/icag-management-accounting-past-questions-2025/)
- [Decision-Making Techniques in Management Accounting](https://accountinginsights.org/decision-making-techniques-in-management-accounting/)
- `.planning/PROJECT.md` — validated requirements and KPE milestone scope
- `config/prompts.py` — existing prompt architecture (3 static variants)
- `src/agents/nodes.py` — existing route_node and classifier logic
- `src/retrieval/vector_search.py` — existing hybrid_search signature
- `src/retrieval/query_classifier.py` — existing rule-based is_calculation_query pattern

---

*Feature research for: KPE milestone — Knowledge Protocol Engineering for Trusty RAG Akmen v1.1*
*Researched: 2026-03-29*
