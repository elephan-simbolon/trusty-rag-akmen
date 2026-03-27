# Pitfalls Research

**Domain:** AI-powered domain-specific RAG assistant (accounting textbooks, cross-lingual Indonesian/English)
**Researched:** 2026-03-22
**Confidence:** HIGH (stack-specific findings from official sources and community reports)

---

## Critical Pitfalls

### Pitfall 1: MinerU VRAM Not Released Between Processing Stages

**What goes wrong:**
After MinerU finishes processing a PDF, CUDA memory from its sequential model pipeline (DocLayout-YOLO → YOLOv8-MFD → UniMERNet → paddleocr2torch → RapidTable) is not fully released before the next document starts. Over several documents, the 6 GB VRAM fills with fragmented, unreleased memory, causing `torch.OutOfMemoryError` mid-batch. There is an active GitHub issue (`opendatalab/MinerU#3399`) confirming VRAM is not released after task completion.

**Why it happens:**
PyTorch's memory allocator caches freed memory by default for reuse (to avoid `cudaMalloc` overhead). Fragmentation accumulates when blocks of different sizes are allocated and freed across model stages. On 6 GB devices there is no buffer for this fragmentation.

**How to avoid:**
After every document (not just every stage), call the full cleanup sequence:
```python
del model
import gc; gc.collect()
torch.cuda.empty_cache()
torch.cuda.synchronize()
```
Set `PYTORCH_CUDA_ALLOC_CONF='max_split_size_mb:512,expandable_segments:True'` in the environment before importing torch. Process documents in a subprocess pool (one subprocess per document) so the OS reclaims memory between files. Never run Docling and MinerU in the same Python process without a full process restart.

**Warning signs:**
- VRAM reported as "free" by `nvidia-smi` is lower than expected after processing completes
- OOM errors begin on the 3rd–5th document but not the 1st
- `torch.cuda.memory_reserved()` keeps climbing while `torch.cuda.memory_allocated()` is low (classic fragmentation signal)

**Phase to address:** Phase 1 (PDF parsing pipeline foundation)

---

### Pitfall 2: MinerU VLM Backend Silently Falls Back to CPU

**What goes wrong:**
MinerU has three backends: `pipeline` (GPU, requires ~6 GB), `vlm-transformers` (GPU, requires ~10 GB), and `vlm-sglang-engine` (GPU, requires ~8 GB). On a GTX 1660 Ti with 6 GB VRAM, the `--backend auto` flag may attempt a VLM backend, fail silently, and fall back to CPU-only pipeline mode. Parsing then takes 10–30× longer (hours instead of minutes per textbook) with no explicit error surfaced.

**Why it happens:**
The `auto` backend selection tries to maximize quality by preferring VLM backends. The fallback to `pipeline` does not always emit a prominent warning, so the user continues believing GPU-accelerated parsing is running.

**How to avoid:**
Explicitly set `--backend pipeline` in all MinerU CLI calls. Never use `--backend auto` on the GTX 1660 Ti. Add a startup assertion that verifies the chosen backend:
```python
assert backend == "pipeline", f"Unexpected backend: {backend}. VLM backends require >8 GB VRAM."
```
Monitor `nvidia-smi dmon` during the first page of each document to verify GPU utilization is nonzero.

**Warning signs:**
- First page of MinerU takes >30 seconds on a modern GPU (pipeline should be 1–3 seconds)
- `nvidia-smi` shows near-zero GPU utilization during "GPU parsing"
- Log output mentions "auto-detected device: cpu"

**Phase to address:** Phase 1 (PDF parsing pipeline foundation)

---

### Pitfall 3: Table Splitting Destroys Financial Data Context

**What goes wrong:**
Accounting textbooks contain multi-page variance analysis tables, cost allocation matrices, and standard cost schedules. When a naive 512-token text splitter hits the token limit mid-table, it creates chunks that contain only partial rows with no column headers. At retrieval time, a chunk with `"| 48,500 | 47,200 | 1,300 |"` is uninterpretable without knowing the column names (e.g., "Actual Cost | Standard Cost | Variance"). Recall drops significantly: benchmarks show naive chunking on tables achieves only 30% accuracy vs. 73.8% for structure-aware table chunking.

**Why it happens:**
LangChain's `RecursiveCharacterTextSplitter` treats Markdown table rows as plain text lines. It splits at token boundaries without awareness that table rows are semantically bound to their headers. With accounting tables frequently exceeding 20–30 rows, this is nearly unavoidable without explicit table detection.

**How to avoid:**
After MinerU/Docling parsing, run an element classifier that detects Markdown tables before any text splitting. Apply the rule: tables ≤20 rows are kept as single atomic chunks (up to 1,024 tokens). Tables >20 rows are split into logical groups (e.g., by cost category) with column headers **repeated** at the start of every child chunk:
```
[Section: Chapter 8 > Standard Costing] Table: Material Variance Analysis
| Item | Std Qty | Act Qty | Price Var | Usage Var |
| Direct Material A | 500 | 520 | $240 | $440 |
```
Store `column_names`, `row_range`, `table_title` as chunk metadata for citation reconstruction.

**Warning signs:**
- Test queries on table content return chunks starting with `|` delimiters but no recognizable headers
- CRAG grades these as AMBIGUOUS or INCORRECT more than 40% of the time
- Manual inspection of indexed chunks shows orphaned rows without column context

**Phase to address:** Phase 1 (hybrid chunking pipeline)

---

### Pitfall 4: LightRAG Entity Deduplication Fails for Accounting Terminology Variants

**What goes wrong:**
LightRAG's LLM-based extraction creates separate graph nodes for semantically identical entities that appear in different surface forms across 20–30 textbooks. For example: `"ABC Costing"`, `"Activity-Based Costing"`, `"Activity Based Costing"`, `"ABC method"`, and `"ABC system"` become five disconnected nodes instead of one. In a graph with 10,000+ nodes across 30 textbooks, 30–50% of accounting entities may be duplicated. This fragments the relationship graph, degrading `local` and `hybrid` query modes that depend on traversing connected nodes.

**Why it happens:**
LightRAG's default extraction prompt does not enforce canonical entity naming. The LLM normalizes based on context window visibility — entities seen pages apart in different books are extracted independently. Research confirms LLM-based KG construction produces "noisy and redundant" graphs with no built-in deduplication (LightRAG GitHub, Neo4j analysis, 2025 arxiv studies).

**How to avoid:**
Build a domain-specific entity normalization layer that runs post-extraction:
1. Define a canonical accounting glossary (~200–500 terms) in `config/glossary.py` mapping variants to canonical forms: `{"ABC Costing": "Activity-Based Costing", "ABC method": "Activity-Based Costing"}`
2. After LightRAG extraction, run a graph post-processing pass that merges nodes with >0.92 embedding similarity
3. Use the `ENTITY_TYPES` restriction in LightRAG's extraction prompt to limit entity types to the 10 defined accounting types (`CostType`, `CostingMethod`, `Formula`, etc.), reducing noise
4. Evaluate entity quality on a 50-chunk sample before full ingestion

**Warning signs:**
- Graph has >2× as many entity nodes as expected accounting concepts (~200 core concepts × 30 books should yield ~300–400 unique nodes, not 2,000+)
- `graph_query` mode returns disconnected, contradictory answers for standard concepts
- Traversal for "Activity-Based Costing" returns 0 relationships despite it being in multiple chapters

**Phase to address:** Phase 2 (LightRAG/GraphRAG integration)

---

### Pitfall 5: Cross-Lingual Retrieval Degrades Without Instruction Prefix

**What goes wrong:**
Qwen3-Embedding-8B is the #1 multilingual embedding model (MTEB Multilingual, score 70.58) but its cross-lingual performance degrades by 1–5% without a task-specific instruction prefix on queries. For domain-specific Indonesian accounting queries against English textbooks, this gap can compound: a query like `"apa itu contribution margin"` without the instruction prefix retrieves semantically adjacent but less relevant chunks than the same query prefixed with `Instruct: Retrieve English accounting textbook passages relevant to the Indonesian accounting query\nQuery:`.

**Why it happens:**
Qwen3-Embedding-8B is instruction-tuned to use the prefix for task disambiguation. The model was trained with task instructions to route query vectors into the correct region of the 4,096-dimensional embedding space. Without the prefix, it defaults to a generic retrieval mode rather than cross-lingual accounting retrieval.

**How to avoid:**
Always wrap query embeddings (not document embeddings) with the instruction prefix. Document chunks are embedded without a prefix:
```python
# Documents at ingestion time — no prefix
doc_embedding = embed(chunk_text)

# Queries at retrieval time — always with prefix
query_embedding = embed(
    f"Instruct: Retrieve English accounting textbook passages "
    f"relevant to the Indonesian accounting query\nQuery: {user_query}"
)
```
The instruction string should be written in English per Qwen3 recommendations, even though the query is in Indonesian. Add this as a constant in `config/settings.py` — never hardcode inline.

**Warning signs:**
- Retrieval recall drops 3–8% compared to expected benchmarks when tested without the instruction prefix
- Same Indonesian query returns correct results sometimes and fails other times (session-dependent)
- The semantic similarity score for correct chunks hovers near threshold rather than clearly above it

**Phase to address:** Phase 1 (embedding/retrieval foundation)

---

### Pitfall 6: CRAG Reformulation Creates Infinite Loop on Out-of-Scope Queries

**What goes wrong:**
When a user asks a question genuinely outside the indexed textbooks (e.g., about Indonesian tax regulations or IFRS 2025 amendments not in the corpus), CRAG grades every retrieval as INCORRECT or AMBIGUOUS. It then reformulates the query and re-retrieves. The second retrieval also fails. Without an explicit loop limit and out-of-scope detection, the system can cycle through 3–10 reformulations before exhausting API budget on a single unanswerable query. At SiliconFlow pricing, a 10-reformulation loop costs ~$0.01–0.03 per failed query — trivial individually but catastrophic if a user discovers the loop trigger.

**Why it happens:**
The CRAG paper's original design assumes fallback to web search as a relief valve for INCORRECT grades. Without web search (which is out of scope for this project), every failed retrieval cycles back into reformulation with no exit condition other than an iteration counter.

**How to avoid:**
Implement a strict iteration cap of 2 reformulations maximum. After 2 failed reformulations, return a structured "not in corpus" response: `"Topik ini tidak ditemukan dalam textbook yang diindeks. Untuk informasi terkini tentang peraturan pajak Indonesia, konsultasikan langsung ke sumber resmi."` Add a confidence score threshold — if the best retrieved chunk scores below 0.55 cosine similarity after reformulation, skip generation and return the out-of-scope response. Log all out-of-scope queries to identify corpus gaps.

**Warning signs:**
- LangSmith/Langfuse traces show the same query appearing 3+ times in a single session with slight variations
- API cost for a single query exceeds $0.05 (expected cost is $0.001–0.005)
- CRAG grader consistently returns AMBIGUOUS for an entire topic category

**Phase to address:** Phase 3 (agentic orchestration + CRAG)

---

### Pitfall 7: SiliconFlow 50 RPD Default Limit Blocks Ingestion Pipeline

**What goes wrong:**
SiliconFlow defaults new accounts to 50 RPD (requests per day) for each model. The LightRAG entity extraction pipeline makes one LLM call per chunk (~120,000 chunks for 30 textbooks). At 50 RPD, completing entity extraction would take 2,400 days. Even after purchasing credits (which raises the limit to 1,000 RPD), a full ingestion with 1,000 RPD takes 120 days at the single-model level — clearly unworkable.

**Why it happens:**
The architectural spec correctly identifies the rate limit issue, but the implication for ingestion sequencing is not fully internalized: LightRAG entity extraction, embedding, and generation all share the same account-level rate limits. If all three run simultaneously during ingestion, they compete for the same RPD pool.

**How to avoid:**
Before starting any ingestion:
1. Purchase credits ($10+ triggers tier upgrade) to reach 1,000 RPD
2. Contact SiliconFlow support for further tier increase for the ingestion window
3. Implement exponential backoff with jitter for all SiliconFlow API calls (catch HTTP 429, retry after 60s with 2× delay each retry, max 5 retries)
4. Run LightRAG entity extraction as a **separate job** from embedding — never overlap them
5. Process LightRAG in batches of 50–100 chunks with explicit rate limit tracking
6. Store intermediate results after every successful API call so a rate limit interruption does not restart from zero

**Warning signs:**
- SiliconFlow API returns HTTP 429 within the first 10 minutes of ingestion
- LightRAG ingestion log shows long gaps (>60s) between entity extraction calls
- Entity extraction completes for some chapters but not others after a restart

**Phase to address:** Phase 1 (ingestion pipeline) — must resolve before large-scale ingestion begins

---

### Pitfall 8: Citation Page Numbers Are Lost During Chunk Splitting

**What goes wrong:**
After parsing with MinerU/Docling, PDF page numbers are embedded in the structured Markdown output as metadata or comments. When LangChain's text splitter creates child chunks from a parent section, the page number metadata from the parent is not automatically propagated to every child. A child chunk ending at the page boundary may contain text from page 245 but carry the metadata `page: 243` (the page where the parent chunk started). Since the project's core value proposition is "exact book + chapter + page citation," incorrect page numbers directly undermine user trust with clients.

**Why it happens:**
LangChain's `RecursiveCharacterTextSplitter` and LlamaIndex's `HierarchicalNodeParser` propagate parent metadata to children by copying the parent's metadata dict. This copies the *starting* page number, not the actual page of each character position. Multi-page sections always produce children with incorrect page numbers after the first page.

**How to avoid:**
During PDF parsing, inject page boundary markers into the Markdown text itself (not just metadata):
```markdown
<!-- PAGE_START:245 -->
The material variance is calculated as follows...
<!-- PAGE_START:246 -->
Table 8-3: Standard Cost Variance Summary
```
After chunking, parse page markers within each chunk's text to determine the *actual* page range (`page_start`, `page_end`) and store both in metadata. When a chunk spans multiple pages, cite as "p. 245–246" rather than a single page. Remove the marker comments from the text before embedding (they corrupt semantic vectors).

**Warning signs:**
- Manual check of 10 random chunks shows page numbers off by 2–5 pages for sections that span multiple PDF pages
- User reports: "You cited page 112 but the formula is on page 115"
- All chunks from the same chapter share identical page numbers despite spanning 20+ pages

**Phase to address:** Phase 1 (parsing + chunking pipeline)

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using `RecursiveCharacterTextSplitter` for all content types | Simple, 10 lines of code | Tables and formulas split mid-structure; retrieval quality degrades for ~30% of queries (financial content) | Never for this project — use element classifier first |
| Skipping LightRAG entity normalization (accept raw extraction) | Saves 2–3 days of development | Graph becomes unusable after ingesting 5+ textbooks due to entity proliferation | MVP only if testing on ≤2 books; never for production corpus |
| Hardcoding the embedding instruction prefix inline across the codebase | Fast to implement | Any instruction change requires grep-and-replace across 10+ files; easy to miss | Never — always a single constant in `config/settings.py` |
| Single CRAG grader call with no retry limit | Simplest LangGraph loop | Infinite loop on out-of-scope queries; API cost explosion | Never in production |
| Processing all 30 textbooks with MinerU in a single long-running process | One command to kick off | OOM on book 8 with no resume capability; 40+ hours of work lost | Never — always batch per book with checkpointing |
| Using LightRAG built-in `nano-vectordb` for both graph AND dense search | Avoids Qdrant integration complexity | nano-vectordb has no persistence durability guarantees; loses all vectors on restart | Acceptable for prototype Phase 1 if Qdrant integration is Phase 2 |
| Setting `max_length=8192` for all embeddings regardless of chunk size | Uniform API calls | Wastes token budget — a 200-token chunk does not need 8,192-token context | Acceptable; cost impact is minimal |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| SiliconFlow API | Using `model="Qwen3-30B"` (short name) instead of `"Qwen/Qwen3-30B-A3B-Instruct-2507"` (full model ID) — causes 404 errors that look like auth failures | Use full model IDs exactly as listed in SiliconFlow docs; store in `config/settings.py` as constants |
| SiliconFlow rate limits | No retry logic — a single HTTP 429 crashes the ingestion job | Wrap all API calls with `tenacity` retry: exponential backoff, 60s initial wait, 5 max attempts, jitter |
| Qdrant Cloud Free Tier | Cluster auto-suspends after 1 week of inactivity — first query after suspension fails with connection error | Implement a health-check ping in the startup sequence; handle reconnection gracefully; document the free tier's suspension behavior |
| Qdrant hybrid search | Configuring only dense vectors in the collection, then trying to add sparse vectors later — requires collection recreation | Create the collection with both dense (`size=1024`) and sparse (`modifier="idf"`) vector configs from the start |
| LightRAG + SiliconFlow | Passing `model_name` instead of `model` parameter in the LLM config — silently falls back to default model (not Qwen3) | Use the `lightrag_siliconcloud_demo.py` reference config exactly; verify active model in LightRAG logs on first run |
| LangGraph + LangChain | Creating LangGraph nodes that import LangChain chains at module load time — causes slow startup and memory pre-allocation | Import LangChain components lazily inside node functions; keep the graph definition lightweight |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Embedding all chunks with a single synchronous loop | Works on 100 chunks in 30s | Use batch embedding (SiliconFlow supports 2,048 tokens/request batch) — reduces API calls by 8–16× | At 10,000+ chunks, single-loop takes 3+ hours with rate limit interruptions |
| Loading all chunk metadata into RAM at startup | Fast first query | Memory grows linearly with corpus size; Docker container OOM on cloud hosting | At ~100,000 chunks with metadata, RAM usage hits 2–4 GB — exceeds free tier hosting |
| Fetching parent chunks at query time by re-querying Qdrant | Correct semantically | 2× Qdrant round trips per query; latency spikes to 3–5 seconds | Acceptable at low QPS; breaks above 10 concurrent requests |
| Using LightRAG `mix` mode for all queries regardless of complexity | Most comprehensive answers | 4–5 API calls per query regardless of complexity; monthly cost 3× target ($30 vs $10) | First month of production use |
| Not quantizing Qdrant collection with scalar quantization | Full-precision vectors, higher recall | Exceeds Qdrant free tier 4 GB disk limit at ~70,000 chunks (1,024 dim × 4 bytes × 70,000 ≈ 286 MB per collection, but with index overhead reaches limit around 100,000 chunks) | At >80,000 chunks without quantization |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing SiliconFlow API key in `.env` and accidentally committing it | Full API access to account; potential large unexpected charges | Add `.env` to `.gitignore` before first commit; use `python-dotenv` with `find_dotenv()` — never hardcode keys |
| Exposing Qdrant Cloud API key in frontend/browser code | Anyone can read or corrupt the entire vector corpus | Qdrant API key stays server-side only; Streamlit/Chainlit frontend never touches Qdrant directly |
| Using `eval()` in the calculator tool without sandboxing | A user submitting `eval("__import__('os').system('rm -rf /')")` as a "formula" | Use `asteval` (safe expression evaluator) instead of Python `eval()`; or use `sympy` for symbolic math; explicitly whitelist allowed operations |
| Logging full query text to LangSmith without data governance | User accounting queries may contain confidential client financial data | Use LangSmith/Langfuse with PII scrubbing before logging; or use local Langfuse instance; document data retention policy |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing "Tidak ditemukan" (not found) without explanation | User does not know if the query was too vague, the topic is not in the corpus, or the system failed | Return a structured response: which concept was searched, which books were checked, and a suggestion to rephrase |
| Displaying raw citation metadata (`chunk_id: abc123, score: 0.87`) | Confusing and unprofessional for a consultant presenting to clients | Format citations as: "Horngren et al. (2021), *Cost Accounting*, Chapter 8, hal. 312–315" |
| Showing calculation results without the working steps | Client cannot verify; consultant cannot explain | Always show full step-by-step: `BEP (units) = FC / (P - VC) = Rp500.000 / (Rp25.000 - Rp15.000) = 50 units` |
| Omitting the disclaimer on calculation responses | Consultant liable if client makes a financial decision based on an incorrect computation | Append to every calculation response: "Verifikasi hasil dengan data aktual dan sumber resmi sebelum digunakan dalam pengambilan keputusan bisnis." |
| Streaming partial responses that show intermediate retrieval states | Confusing to see raw retrieved chunks flash on screen before the final answer | Stream only the final generation response; show a simple loading indicator during retrieval |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **PDF parsing pipeline:** Appears complete after parsing 2–3 test books — verify with a 300-page scanned textbook with merged-cell tables. Run `nvidia-smi` to confirm GPU is actually used (not CPU fallback).
- [ ] **Hybrid chunking:** Element classifier may report 100% coverage but silently classify multi-column layouts as `narrative_text`. Verify by spot-checking 20 chunks from a page with side-by-side examples (common in Garrison/Noreen textbooks).
- [ ] **Cross-lingual retrieval:** Works for common terms like "biaya tetap" → "fixed cost" but may fail for compound terms like "analisis varians bahan langsung" → "direct material variance analysis." Test at least 30 domain-specific queries before Phase 1 sign-off.
- [ ] **LightRAG graph:** Running `rag.insert()` on 100 chunks and seeing no errors does not mean the graph is usable. Count entity nodes, check for obvious duplicates, verify at least 3 key relationships exist (e.g., `ABC_Costing --USES→ Cost_Drivers`).
- [ ] **CRAG grader:** A CRAG grader that always returns CORRECT (to avoid reformulation overhead) defeats the purpose. Test with 5 deliberately irrelevant chunk-query pairs and verify it returns INCORRECT/AMBIGUOUS.
- [ ] **Citation accuracy:** Citations "look correct" in demo but page numbers may be off by 2–5 for multi-page sections. Manually verify 10 page citations against the actual PDF before declaring the pipeline complete.
- [ ] **Rate limit handling:** The ingestion pipeline runs fine on 10 books but hits HTTP 429 silently swallowed by a bare `except Exception` clause on book 15. Test retry logic explicitly by mocking 429 responses.
- [ ] **Calculator tool:** Returns correct BEP for a simple example but may fail on edge cases like zero contribution margin or negative fixed costs. Test all 6 calculation types with edge-case inputs.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| VRAM OOM during MinerU batch (books already parsed are safe) | LOW | Kill process, call `torch.cuda.empty_cache()`, restart from last checkpointed book; use subprocess isolation going forward |
| LightRAG graph has severe entity duplication (post-ingestion discovery) | HIGH | Export graph to JSON, run offline deduplication script against canonical glossary, re-import merged graph; entity extraction API cost is already spent but graph rebuild is free |
| SiliconFlow rate limit hit mid-ingestion | LOW | Ingestion halts; wait for daily reset (or upgrade tier); resume from last saved checkpoint — requires checkpointing to be built in from the start |
| Qdrant free tier cluster deleted after inactivity (4-week rule) | MEDIUM | All vectors lost; re-embed all chunks (cost: ~$4–8); restore from backup if chunk texts were saved locally; always save chunks to local SQLite before uploading to Qdrant |
| Citation page numbers systematically wrong | MEDIUM | Re-run parsing pipeline with page marker injection; re-chunk affected books; re-embed changed chunks only (use Qdrant's upsert to update, not recreate collection) |
| Cross-lingual retrieval fails for a category of terms | LOW | Add failed terms to bilingual glossary; re-embed queries during retrieval (no re-ingestion needed); BM25 fallback catches exact English term matches |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| MinerU VRAM not released | Phase 1: PDF parsing pipeline | Run 5 consecutive textbooks; `nvidia-smi` shows stable VRAM usage throughout |
| MinerU VLM backend silent fallback | Phase 1: PDF parsing pipeline | Assert GPU utilization >50% during first page of each document |
| Table splitting destroys context | Phase 1: Hybrid chunking pipeline | Query 10 table-dependent questions; check all retrieved chunks contain column headers |
| LightRAG entity deduplication failure | Phase 2: GraphRAG integration | Count entity nodes; verify <500 unique nodes for 5 textbooks on ~200 core concepts |
| Cross-lingual retrieval without instruction prefix | Phase 1: Embedding/retrieval foundation | A/B test 20 queries with and without instruction prefix; prefixed version must win by ≥3% recall |
| CRAG infinite loop | Phase 3: Agentic orchestration | Test with 5 out-of-scope queries; verify all return "not in corpus" response in ≤3 retrieval attempts |
| SiliconFlow 50 RPD default limit | Phase 1: Before ingestion starts | Purchase credits; verify tier in SiliconFlow dashboard; test rate limit with 60 rapid-fire calls |
| Citation page number loss | Phase 1: Parsing + chunking pipeline | Manually verify 20 citations across 3 textbooks; zero tolerance for >2-page offset |

---

## Sources

- [MinerU CUDA out of memory issue #1388](https://github.com/opendatalab/MinerU/issues/1388) — confirmed GPU memory issue in production MinerU
- [MinerU VRAM not released issue #3399](https://github.com/opendatalab/MinerU/issues/3399) — confirmed VRAM retention bug (August 2025)
- [SiliconFlow Rate Limits documentation](https://docs.siliconflow.cn/en/userguide/rate-limits/rate-limit-and-upgradation) — authoritative source for tier limits
- [Qwen3 Embedding official blog — instruction format best practices](https://qwenlm.github.io/blog/qwen3-embedding/) — 1–5% recall degradation without instruction prefix
- [Benchmarking RAG on tables — LangChain blog](https://blog.langchain.com/benchmarking-rag-on-tables/) — 30% vs 73.8% accuracy on table-heavy content
- [Building a Financial RAG System — chunking to reach 90% recall (Medium, 2026)](https://medium.com/@steveinatorx_49018/building-a-financial-rag-system-pt-5-how-i-fixed-chunking-to-reach-90-recall-7f1158e934a9) — structure-aware table chunking improvement data
- [LightRAG GitHub — EMNLP2025](https://github.com/HKUDS/LightRAG) — model size recommendation (≥32B for quality extraction)
- [Less is More: Denoising Knowledge Graphs For RAG (arxiv 2025)](https://arxiv.org/html/2510.14271v1) — noisy/redundant graph problem in LLM-based KG construction
- [CORE-KG: 33% node duplication reduction for domain-specific KG](https://arxiv.org/pdf/2506.21607) — domain-specific entity normalization strategies
- [Citation Accuracy Challenges in RAG — Stanford/JELS 2025](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf) — RAG hallucination rates 17–33% even with retrieval
- [XRAG: Cross-Lingual RAG pitfalls (arxiv 2025)](https://arxiv.org/html/2505.10089v1) — cross-lingual reasoning challenges
- [Qdrant Free Tier limitations and suspension policy](https://qdrant.tech/pricing/) — 1-week suspension, 4-week deletion policy
- [PyTorch VRAM fragmentation guide 2026](https://blog.path-finder.jp/troubleshooting/pytorch-gpu-memory-guide-2026/) — expandable_segments and max_split_size_mb settings

---
*Pitfalls research for: AI-powered RAG accounting assistant (Trusty RAG Akmen)*
*Researched: 2026-03-22*
