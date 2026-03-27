# GraphRAG Alternatives Research — Trusty RAG Akmen

**Researched:** 2026-03-23
**Domain:** GraphRAG alternatives, local NER/RE models, SiliconFlow rate limits
**Confidence:** MEDIUM overall (web research; LightRAG call structure HIGH from installed source)

---

## Purpose

This document is contingency research: what to use if the SiliconFlow L2 tier upgrade
(the locked decision in CONTEXT.md) does not deliver the 15-20 min/book target, or for
planning Phase 5+ knowledge graph improvements.

The existing CONTEXT.md locks the decision to **stay with LightRAG and optimize it**.
This document does NOT override that decision. It documents the alternatives landscape
for the planner and for future phases.

---

## LightRAG Baseline (Verified)

**Source: LightRAG v1.4.11 source + arxiv 2410.05779**

| Config | LLM calls/chunk | At 50K TPM (L0) | At ~500K TPM (L2) |
|--------|----------------|-----------------|-------------------|
| gleaning=1 (default) | 2 calls | ~80 min/1000 chunks | ~8 min/1000 chunks |
| gleaning=0 (Phase 4.1 fix) | 1 call | ~40 min/1000 chunks | ~4 min/1000 chunks |

How the 2-call figure is derived: `entity_extract_max_gleaning=1` (default) means one
initial extraction LLM call, then one "gleaning" retry call per chunk. Setting it to 0
eliminates the retry, halving total LLM call volume. This is already planned in CONTEXT.md
as the single highest-leverage change.

---

## Alternative 1: Microsoft GraphRAG

**Version:** v3.0.6 (released 2026-03-06)
**Package:** `graphrag` on PyPI

### Three indexing modes

#### Standard GraphRAG
- **LLM calls per chunk: 4-6**
  - Entity extraction (1 call)
  - Relationship extraction (1 call)
  - Entity summarization (1 call per entity)
  - Relationship summarization (1 call per relation)
  - Optional claim extraction (1 call)
  - Community report generation (1 call per cluster, not per chunk)
- Real-world cost: $10-15 for 800KB text using GPT-4-class models
- "Graph extraction constitutes roughly 75% of indexing cost" (official docs)
- **Verdict: WORSE than LightRAG per-chunk.** 4-6x more API calls. Do not use.

#### FastGraphRAG (no LLM at index time)
- **LLM calls at index time: 0**
- Uses NLTK + spaCy noun phrase extraction for entities
- Relationships = co-occurrence in same 50-100 token chunk (not semantic)
- Still uses LLM at query time for synthesis
- Entity quality: noun phrases — produces "cost", "method", "firm", "period" instead of
  domain-specific accounting entities like "CostAllocationMethod" or "VariableCostBehavior"
- Bilingual support: unknown — NLTK/spaCy noun phrase extraction is primarily English
- **Verdict: Fast indexing, but noun-phrase entities are poor fit for accounting domain.**

#### LazyGraphRAG (no LLM at index time, introduced Nov 2024)
- **LLM calls at index time: 0** — NLP noun phrase + co-occurrence only
- "Indexing cost = 0.1% of full GraphRAG" (Microsoft Research blog)
- Defers ALL LLM work to query time
- Quality claim: "outperforms all competing methods at 4% of query cost of full GraphRAG"
- Same noun-phrase limitation as FastGraphRAG for entity types
- **Verdict: Best indexing speed of any packaged GraphRAG alternative. But noun-phrase
  entities limit domain quality. Promising for Phase 5+ if query quality proves adequate.**

### Custom Endpoint Support
GraphRAG uses LiteLLM as its model backend. SiliconFlow (OpenAI-compatible) should work:
```yaml
# graphrag settings.yml
models:
  default_chat_model:
    model_provider: openai
    model: Qwen/Qwen3-30B-A3B
    api_base: https://api.siliconflow.cn/v1
    api_key: ${SILICONFLOW_API_KEY}
```
**Confidence: MEDIUM** — LiteLLM OpenAI-compatible support is documented. SiliconFlow JSON
schema output for graphrag indexing has not been tested by the community (no evidence found).

### Implementation Cost to Replace LightRAG
- New package: `graphrag` (~50MB, heavy dependency including Neo4j drivers optional)
- Rewrite `graph_ingestion.py` and `lightrag_client.py` entirely
- Rewrite `graph_retrieve` node in LangGraph to use graphrag query API
- Estimated effort: 1-2 weeks engineering

---

## Alternative 2: nano-graphrag

**Package:** `nano-graphrag` on PyPI, ~3.7K GitHub stars
**Status:** Actively maintained as of 2025

- Same LLM call architecture as LightRAG (entity extraction + summarization)
- **Does not reduce API call count** — same 1-2 calls per chunk as LightRAG
- Uses dual-model design (powerful model for extraction, cheap model for summarization)
  — the cheap model reduces some summarization cost but doesn't help the extraction bottleneck
- Simpler codebase (~1100 lines) — "easy to hack"
- Less production-ready than LightRAG (no `apipeline_enqueue_documents` resume mechanism)
- LightRAG was originally based on nano-graphrag and surpasses it in features
- **Verdict: Not a meaningful throughput improvement. Not recommended as replacement.**

---

## Alternative 3: GLiNER (Local NER, Zero API Calls)

**Package:** `gliner` on PyPI, NAACL 2024
**Models:** `urchade/gliner_large-v2` (English), `urchade/gliner_multi-v2.1` (multilingual)

### Capabilities
| Property | Value | Source |
|----------|-------|--------|
| Model size (large-v2) | 459M params, ~1.8GB RAM | HuggingFace model card |
| GPU requirement | None — CPU-optimized | Official docs |
| Indonesian support | Likely (gliner_multi-v2.1, multilingual DeBERTa backbone) | NAACL paper |
| Entity type specification | Any labels at inference time | Official docs |
| Zero-shot quality | Competitive with ChatGPT on standard NER benchmarks | NAACL 2024 paper |

### Speed Reality Check (CRITICAL)
- **CPU inference: ~4 chunks/minute** (community-reported; 25 chunks = 6.5 minutes on CPU)
- This is 300x slower than spaCy rule-based NER
- 1000 chunks at 4 chunks/min = **~250 minutes on CPU** — worse than LightRAG at L0
- GTX 1660 Ti 6GB is reserved for MinerU PDF parsing (VRAM isolation design, per CLAUDE.md)
- Cannot run GLiNER on GPU simultaneously with MinerU pipeline
- ONNX optimization exists but does not produce dramatic speedups for CPU (reported ~50% slower
  in some cases due to overhead)

### GLiNER-Relex (Combined NER + Relation Extraction)
**Model:** `knowledgator/gliner-relex-large-v1.0`
- NER + relation extraction in single forward pass (shared encoder weights)
- Schema-driven: specify entity types AND relation types at inference time
- More efficient than separate NER + RE models
- Still CPU-bound at similar speed to base GLiNER
- Outputs: `(subject_entity, relation_type, object_entity)` triples — directly usable for graph

### What You'd Need to Build (Not Included in GLiNER)
GLiNER extracts entities and relations. It does NOT provide:
1. Graph storage layer (NetworkX or otherwise)
2. Graph query modes (hybrid, local, global)
3. Text synthesis from subgraph context
4. Incremental update / resume capability

To fully replace LightRAG with GLiNER-Relex:
| Component | Effort |
|-----------|--------|
| GLiNER-Relex entity+relation extraction script | 2-3 days |
| NetworkX graph storage + serialization | 1-2 days |
| Graph query engine (1-2 hop subgraph + PPR) | 1-2 weeks |
| `graph_retrieve` node rewrite in LangGraph | 2-3 days |
| Testing + tuning entity types | 1-2 weeks |
| **Total** | **~4-5 weeks** |

**Verdict for Phase 4.1: Not feasible.** CPU speed alone is too slow (250 min vs 15-20 min target).
VRAM conflict with MinerU prevents GPU acceleration.
**Verdict for Phase 5+: Promising zero-API-cost path if GPU access is available.**

---

## Alternative 4: REBEL (Babelscape Relation Extraction)

**Model:** `Babelscape/rebel-large` on HuggingFace
**Architecture:** BART-based seq2seq, trained on Wikipedia/Wikidata, 200+ relation types

### Why It Doesn't Fit
- Trained on general-domain Wikipedia relation types: "born in", "part of", "instance of",
  "employer", "member of" — none of these are accounting relations
- No entity extraction capability — only relation extraction (needs separate NER)
- No Indonesian language support (Wikipedia-based training data, primarily English)
- Domain mismatch is fundamental — fine-tuning would require annotated accounting corpus

**Verdict: Eliminate from consideration.** Domain mismatch is not fixable without significant
fine-tuning effort on annotated accounting data.

---

## Alternative 5: spaCy + NetworkX (Rule-Based)

**Indonesian spaCy model:** `id_core_news_sm` (community model, HuggingFace)
- NER F1 ~0.69 for standard entities (PER, ORG, LOC, GPE) — news domain
- No accounting domain entities in standard model
- Would require custom `EntityRuler` using the 130+ term accounting glossary in `config/glossary.py`

### Speed
Sub-second for 1000 chunks with rule-based `EntityRuler` matching.
spaCy's statistical NER (en_core_web_md): also very fast — 300x faster than GLiNER on CPU.

### Quality Gap
Standard spaCy NER identifies persons, organizations, locations — useless for accounting.
EntityRuler with glossary would only match exact-string accounting terms, missing:
- Indonesian paraphrases and synonyms
- Context-dependent entity classification
- Relations between entities

### Same Build-From-Scratch Problem
Same missing components as GLiNER: graph storage, query modes, text synthesis.
Rule-based entity matching produces worse entity quality than GLiNER for novel phrasings.

**Verdict: Fast extraction, poor quality for accounting domain. Not recommended.**

---

## Alternative 6: SPRIG (Academic, No Package)

**Paper:** arxiv 2602.23372 "Democratizing GraphRAG: Linear, CPU-Only Graph Retrieval"

### Architecture
- Zero LLM calls at index time: spaCy NER or regex for entity mentions
- Entity-document bipartite graph with TF-IDF edge weights
- Personalized PageRank (PPR) for multi-hop query retrieval
- No LLM at query time (PPR scores rank documents, LLM only for final generation)

### Performance
- Recall@10: 0.844 on HotpotQA, 0.747 on 2WikiMultiHopQA
- Total query latency: 582s for 7,405 queries (~78ms/query)
- Memory: runs within 4GB RAM

### Status
February 2026 academic paper. No PyPI package. No Python library available.
Would require implementing from scratch based on the paper.

**Verdict: Architecturally interesting. Not actionable until packaged.**

---

## SiliconFlow Model Options

**Source: siliconflow.com pricing pages (MEDIUM confidence — site renders as CSS-only,
actual numbers from galaxy.ai comparison page)**

### Pricing Comparison (USD per million tokens)

| Model | Input | Output | Architecture | Notes |
|-------|-------|--------|-------------|-------|
| Qwen3-30B-A3B (current) | $0.08 | $0.28 | MoE (3.3B active) | Current extraction model |
| Qwen3-14B | $0.06 | $0.24 | Dense (14.8B) | ~20% cheaper output |
| Qwen3-8B | Not confirmed | Not confirmed | Dense (8B) | May have higher rate limits |

### Rate Limit Tier Structure

**Source: docs.siliconflow.cn (MEDIUM confidence — exact per-model limits not published)**

- Tiers L0-L5 based on monthly consumption in RMB
- Free models: FIXED rate limits — do NOT scale with tier upgrade
- Paid models (Pro/ prefix): rate limits scale with tier
- General range for chat models: RPM 1,000-10,000 / TPM 50,000-5,000,000
- L0 (current): TPM ~50,000 for paid models
- L2 (target): TPM estimate ~500,000 (midpoint of documented range; not confirmed per-model)
- Per-model limits: smaller models likely have higher TPM caps at same tier (unconfirmed)

### Qwen3-14B as Qwen3-30B-A3B Substitute

Both models share:
- Structured output / JSON schema support (confirmed)
- Function calling capability
- Non-thinking mode (required for LightRAG extraction — thinking mode wastes tokens)
- Same tokenizer family

Difference:
- 30B-A3B: MoE with 3.3B active params — fast inference despite large param count
- 14B: Dense model — slightly different latency profile
- Quality for accounting entity extraction: unverified; 30B-A3B may extract more complete
  JSON for complex multi-entity chunks

**Recommendation: Test Qwen3-14B with 50-chunk audit before committing to it as the
extraction model.** If quality is adequate, 20% output token savings at scale
(9 books × 4,600 avg narrative chunks × ~2K tokens/call output) is meaningful.

### Free Model Strategy

SiliconFlow offers free variants (e.g., `Qwen/Qwen2.5-7B-Instruct` without `Pro/` prefix).
Free model rate limits are FIXED and do not scale with tier upgrades.
These models are likely inadequate for LightRAG extraction:
- LightRAG's entity extraction prompt requires complex JSON output with 10 entity types
- Qwen2.5-7B (free) performance on structured extraction: unknown but risky
- **Not recommended as primary extraction model.**

---

## Hybrid Approaches (2024-2025 Trend)

The research literature trend is: extract entities offline cheaply (NLP), use LLM only at query time.

### Practical Hybrid Design for Phase 5+

```
INDEX TIME (zero API calls):
  GLiNER-Relex (knowledgator/gliner-relex-large-v1.0)
    → (entity_text, entity_type, relation_type, entity_text) triples per chunk
  NetworkX graph
    → nodes: entity_text (normalized), type annotations
    → edges: relation_type, source_chunk_id
  Serialized as JSONL: lightrag_storage/graph.jsonl

QUERY TIME:
  Query preprocessing (existing)
    → extract query entities via GLiNER or glossary lookup
  Subgraph retrieval
    → 1-2 hop BFS from query entities
    → return entity descriptions + source chunks
  Synthesis (existing graph_retrieve node rewrite)
    → LLM synthesizes from subgraph context + Qdrant vector results
```

**Why this isn't Phase 4.1:**
- GLiNER-Relex CPU speed (~4 chunks/min) = 250 min for 1000 chunks, still slower than L2 LightRAG
- Full stack implementation = 4-5 weeks engineering
- LightRAG already provides this with better entity quality

**Why this is Phase 5+ material:**
- Zero ongoing API costs for ingestion (only pay for query-time synthesis)
- At 9 books × 4,600 avg chunks = 41,400 chunks total → ~170 hours of CPU ingestion
  OR ~6-8 hours if GPU is available
- For 100+ textbooks (Phase 4 scale goal), zero extraction cost is significant

---

## Decision Matrix

| Scenario | Path | 15-20 min target met? | Implementation risk |
|----------|------|-----------------------|---------------------|
| L2 tier upgrade works | LightRAG optimized (current plan) | Yes (~4-8 min) | LOW |
| L2 available, want cost saving | Qwen3-14B + L2 (test first) | Yes | LOW |
| Cannot upgrade tier | Nightly batch on L0 (40 min × 9 books = 6h overnight) | No, but workable | LOW |
| Phase 5+: zero extraction cost | GLiNER-Relex + NetworkX + custom query | With GPU: maybe | VERY HIGH |
| Phase 5+: packaged option | LazyGraphRAG (graphrag v3.0.6) | Yes (index only) | MEDIUM |
| REBEL | Eliminate | No — domain mismatch | N/A |
| spaCy + NetworkX | Eliminate | N/A | HIGH, poor quality |
| nano-graphrag | Eliminate | Same as LightRAG | Not meaningful |

---

## Key Conclusions

### No Drop-In Replacement Exists

No alternative meets all three requirements simultaneously:
1. 15-20 minute ingestion for 1000 chunks
2. Domain-specific accounting entity types
3. Bilingual Indonesian/English support

Without the tier upgrade, the best achievable is 40 min/1000 chunks on L0 (gleaning=0).
With tier upgrade: ~4-8 min/1000 chunks on L2.

### Phase 5+ Best Options

**Option A — GLiNER-Relex + NetworkX (zero API cost):**
- Requires dedicated GPU access for 1660 Ti or dedicated ingestion window
- Full stack engineering: 4-5 weeks
- Result: zero ongoing API cost for any future books

**Option B — LazyGraphRAG (packaged, fast):**
- Uses `graphrag` v3.0.6 with LazyGraphRAG indexing mode
- Zero index-time API calls (NLP only)
- Deferred LLM calls to query time only
- Risk: noun-phrase entities for accounting domain
- Effort: 1-2 weeks to integrate and test

### Immediate Action (Non-Tier-Upgrade Path)

If tier upgrade is blocked for any reason, the optimized LightRAG on L0 can ingest 9 books
in ~6 hours overnight:
- 9 books × 4,600 avg narrative chunks × 1 LLM call × ~2K tokens/call = ~82M tokens
- At 50K TPM: ~27.5 hours total (with rate limiting 100% efficient)
- Realistic with retries and overhead: 2-3 nights
- Not "15-20 minutes" but gets the knowledge graph built once for the initial corpus

---

## Open Questions

1. **Qwen3-14B extraction quality on LightRAG prompts**
   - Unverified: does 14B produce complete, valid JSON for all 10 entity types?
   - Test: 50-chunk audit run with Qwen3-14B, compare entity count vs 30B-A3B
   - If quality is equal: switch to 14B for 20% savings

2. **SiliconFlow per-model rate limits by tier**
   - Docs say "varies by model size and tier" but don't publish exact numbers
   - Qwen3-8B may have higher TPM cap than Qwen3-30B-A3B at same tier
   - Test: Check SiliconFlow console after L2 upgrade for per-model rate limit display

3. **GLiNER-Relex bilingual performance on Indonesian text**
   - Unverified: `gliner_multi-v2.1` trained on 11 languages; Indonesian not explicitly listed
   - Test: 10-chunk sample with Indonesian accounting text, inspect entity extraction results
   - Alternative: Use English chunk text for extraction (chunks are bilingual; English terms present)

4. **LazyGraphRAG query quality on accounting domain**
   - Unverified: noun-phrase entity graph quality for multi-hop accounting queries
   - Test: Prototype with 200 chunks from one chapter, evaluate 10 accounting queries

---

## Sources

### HIGH Confidence (primary sources verified)
- LightRAG v1.4.11 installed source (`lightrag.py`) — gleaning call structure
- arxiv 2410.05779v1 (LightRAG paper) — gleaning=1 fixed, extraction call structure
- arxiv 2602.23372 (SPRIG paper) — CPU-only GraphRAG approach, Recall@10 benchmarks
- microsoft.github.io/graphrag/index/methods/ — FastGraphRAG/LazyGraphRAG indexing modes
- microsoft.github.io/graphrag/config/models/ — LiteLLM custom endpoint config
- Microsoft Research blog: LazyGraphRAG (Nov 2024) — 0.1% indexing cost claim
- github.com/urchade/GLiNER (NAACL 2024) — model capabilities, multilingual support
- huggingface.co/urchade/gliner_large-v2 — model size, architecture details

### MEDIUM Confidence (web search, verified with secondary sources)
- github.com/theirstory/gliner-spacy discussion #28 — GLiNER CPU speed ~4 chunks/min
- blog.galaxy.ai Qwen3 comparison — pricing $0.08/$0.28 vs $0.06/$0.24
- docs.siliconflow.cn/en/userguide/rate-limits/ — tier structure L0-L5, TPM range 50K-5M
- knowledgator/gliner-relex-large-v1.0 HuggingFace — GLiNER-Relex combined NER+RE
- github.com/Babelscape/rebel — REBEL domain scope (Wikipedia/Wikidata only)
- spacy.io/models — Indonesian id_core_news_sm NER F1 ~0.69

### LOW Confidence (not directly verifiable)
- L2 TPM estimate of ~500K — inferred from doc range 50K-5M; actual value requires checking
  SiliconFlow console after upgrade
- Qwen3-8B pricing on SiliconFlow — not confirmed from accessible sources
- Indonesian language inclusion in GLiNER-multi — inferred from "11+ languages" claim, not confirmed

---

**Research date:** 2026-03-23
**Valid until:** 2026-06-23 (stable domain — alternatives landscape unlikely to change dramatically)
