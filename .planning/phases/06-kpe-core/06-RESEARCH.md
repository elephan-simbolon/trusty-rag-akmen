# Phase 06: KPE Core - Research

**Researched:** 2026-03-29
**Domain:** Protocol registry design, rule-based query classification, modular prompt composition
**Confidence:** HIGH

## Summary

Phase 06 implements a Knowledge Protocol Engine (KPE) that gives every management accounting query a structured, framework-driven response shape. The core insight is that protocol selection must be zero-LLM (rule-based keyword matching) while prompt composition must be fully modular, replacing the current three-branch if/elif/else static prompt logic.

The existing codebase already has the right pattern to extend: `is_calculation_query()` in `src/retrieval/query_classifier.py` proves that keyword + pattern matching works well for routing with zero LLM calls. The KPE protocol selector follows the same pattern but for 9 named protocols (CVP, Variance Analysis, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General). The `RAGState` TypedDict will need one new field: `protocol_key: Optional[str]`. The `generate_response()` function accepts this key and composes the system prompt from atomic blocks rather than selecting from three hardcoded string constants.

The critical backward compatibility constraint: the existing `Calculation` query type and `generate_calc_node` path must remain fully intact. Protocol selection runs inside `route_node` alongside `is_calculation_query` — if `is_calculation_query` returns True, we keep `query_type="Calculation"` and the protocol_key is either `"cvp"` (if BEP/CVP keywords present) or `"general"`. Protocol-driven formatting applies inside both `generate_node` and `generate_calc_node` since both call `generate_response()`.

**Primary recommendation:** Use a `@dataclass` for the protocol registry entry, a plain `dict[str, ProtocolConfig]` as the registry, and Python f-string concatenation for modular prompt composition — no new dependencies required.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROT-01 | User mendapat respons terstruktur menggunakan framework analisis yang tepat (CVP, Variance, ABC, Transfer Pricing, Relevant Costing, Product Profitability, Budgeting, Cost Classification, General) berdasarkan topik query | Protocol registry + `select_protocol()` provides framework selection; protocol steps injected into system prompt shape the response |
| PROT-02 | User dapat mengirim query apapun dan sistem memilih protocol yang sesuai tanpa tambahan LLM call (rule-based keyword matching, fallback ke General) | Keyword frozenset pattern from `is_calculation_query` scales to 9 protocols; General is explicit fallback key |
| PROT-03 | User mendapat respons dengan section headers konsisten per protocol (## Jawaban Singkat, ## Analisis, ## Rekomendasi) dan few-shot format | Protocol steps are prompt text that instructs the LLM to emit these headers; few-shot block in each protocol config |
| PROT-04 | User mendapat system prompt yang di-compose secara modular (persona block + rules block + protocol steps + synthesis block + glossary) menggantikan hardcoded prompts | Modular composition replaces `SYSTEM_PROMPT_GENERATOR`, `SYSTEM_PROMPT_GENERATOR_CALCULATION`, `SYSTEM_PROMPT_SYNTHESIS` with a single `compose_system_prompt()` function |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11 (pinned in `.python-version`)
- No new pip dependencies for this phase — stdlib only (`re`, `dataclasses`, `frozenset`)
- Bilingual convention: Indonesian prose + English technical terms in parentheses
- All documentation in Indonesian; English for code identifiers and API references
- `uv run pytest` — 30s timeout per test, `pytest-timeout` enforced
- Test markers: `integration` (live services), `e2e`, `gpu` — new tests for this phase must be pure unit (no markers needed)
- Ruff lint: line-length 100, `select = ["E", "F", "I"]`, `ignore = ["E501"]`

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `dataclasses` | stdlib 3.11 | Protocol registry entry struct | Zero-dep, type-checked, `__repr__` included |
| Python `re` | stdlib 3.11 | Keyword matching (already used in `query_classifier.py`) | Already in use, consistent pattern |
| Python `frozenset` | stdlib 3.11 | Immutable keyword sets per protocol | Hashable, O(1) lookup, same pattern as `_CALC_KEYWORDS` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `typing.Literal` | stdlib 3.11 | Protocol key type alias | Adds IDE completions for `protocol_key` field |
| Pydantic `BaseModel` | already in project (pydantic-settings) | Alternative to dataclass for protocol config | Only if runtime validation of protocol config is needed — overkill here |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@dataclass` for protocol config | `TypedDict` | TypedDict has no defaults; dataclass cleaner |
| `@dataclass` for protocol config | `Enum` | Enum works for protocol name constants but not for bundling name + keywords + steps + few_shot together |
| Plain `dict` registry | Pydantic model registry | Pydantic adds validation; no benefit for static config with no user input |
| f-string composition | `string.Template` | Template requires `$var` syntax, less readable for multi-block prompts |
| f-string composition | Jinja2 templates | Jinja2 is not in project deps; f-strings are sufficient |

**Installation:** No new packages needed. All stdlib.

---

## Architecture Patterns

### Recommended Project Structure

New files:

```
src/
└── retrieval/
    └── query_classifier.py    # EXTEND: add select_protocol()
config/
├── prompts.py                 # REFACTOR: add compose_system_prompt(), keep old constants as deprecated
└── protocols.py               # NEW: ProtocolConfig dataclass + PROTOCOL_REGISTRY dict
src/
└── agents/
    ├── state.py               # EXTEND: add protocol_key field
    └── nodes.py               # EXTEND: route_node writes protocol_key; generate_node passes it
src/
└── generation/
    └── generator.py           # REFACTOR: generate_response() accepts protocol_key param
tests/
└── test_protocol_selection.py # NEW: pure unit tests for select_protocol() accuracy
```

### Pattern 1: ProtocolConfig Dataclass

**What:** A frozen dataclass bundling all protocol metadata in one place.

**When to use:** When the registry entry has multiple heterogeneous fields (name, keywords, steps, few_shot example).

**Example:**

```python
# config/protocols.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ProtocolConfig:
    key: str                        # machine identifier, e.g. "cvp"
    display_name: str               # e.g. "CVP Analysis"
    keywords_id: frozenset[str]     # Indonesian keywords (lowercase)
    keywords_en: frozenset[str]     # English keywords (lowercase)
    steps: str                      # multi-line prompt text injected into system prompt
    few_shot: str                   # one-shot example showing expected section headers
```

### Pattern 2: Protocol Registry as Dict

**What:** A `dict[str, ProtocolConfig]` keyed by `protocol_key` string, loaded at module import (singleton, no I/O).

**When to use:** O(1) lookup by key, easy iteration for tests.

```python
# config/protocols.py (continued)
PROTOCOL_REGISTRY: dict[str, ProtocolConfig] = {
    "cvp": ProtocolConfig(
        key="cvp",
        display_name="CVP Analysis",
        keywords_id=frozenset([
            "cvp", "bep", "break-even", "break even", "titik impas",
            "contribution margin", "margin kontribusi", "operating leverage",
            "leverage operasi", "margin of safety", "margin keamanan",
            "volume laba", "cost-volume-profit",
        ]),
        keywords_en=frozenset([
            "cost volume profit", "breakeven", "break even point",
            "contribution margin ratio", "margin of safety",
        ]),
        steps="""Gunakan framework CVP Analysis:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat.]
## Analisis
[Jelaskan hubungan biaya-volume-laba. Sertakan rumus BEP jika relevan: BEP = Fixed Cost / (Price - Variable Cost per Unit).]
## Rekomendasi
[Implikasi manajerial dari analisis CVP untuk pengambilan keputusan.]""",
        few_shot="""Contoh output yang diharapkan:
## Jawaban Singkat
Break-even point (*titik impas*) adalah volume penjualan di mana total revenue sama dengan total cost [Sumber 1].
## Analisis
BEP (unit) = Fixed Cost / Contribution Margin per Unit = Rp 100.000.000 / Rp 30.000 = 3.333 unit [Sumber 2].
## Rekomendasi
Manajemen sebaiknya memantau margin of safety agar volume penjualan tidak mendekati titik impas.""",
    ),
    # ... other protocols
    "general": ProtocolConfig(
        key="general",
        display_name="General",
        keywords_id=frozenset(),   # empty — fallback
        keywords_en=frozenset(),
        steps="""Jawab pertanyaan akuntansi secara terstruktur:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat.]
## Analisis
[Jelaskan konsep, metode, atau prinsip yang relevan dengan referensi sumber.]
## Rekomendasi
[Implikasi praktis atau langkah selanjutnya jika relevan.]""",
        few_shot="",
    ),
}
```

### Pattern 3: select_protocol() — Rule-Based Keyword Matching

**What:** Function that scans query lowercase against each protocol's keyword sets. Returns `protocol_key` string. Falls back to `"general"` if no match. Zero LLM calls.

**When to use:** Called inside `route_node()` — runs before any retrieval.

```python
# src/retrieval/query_classifier.py (extended)
from config.protocols import PROTOCOL_REGISTRY

# Priority order for protocols (more specific first to avoid CVP shadowing Variance etc.)
_PROTOCOL_PRIORITY = [
    "variance_analysis",
    "abc",
    "transfer_pricing",
    "relevant_costing",
    "product_profitability",
    "budgeting",
    "cost_classification",
    "cvp",
    "general",
]

def select_protocol(query: str) -> str:
    """Return protocol_key for query via rule-based keyword matching.

    Iterates protocols in priority order. Returns 'general' if no match.
    Zero LLM calls (PROT-02).

    Examples:
        "jelaskan break-even point"    → "cvp"
        "hitung varians harga bahan"   → "variance_analysis"
        "apa itu activity-based cost?" → "abc"
        "bandingkan produk A dan B"    → "product_profitability"
        "apa itu biaya?"               → "general"
    """
    q_lower = query.lower()
    for key in _PROTOCOL_PRIORITY:
        if key == "general":
            return "general"
        config = PROTOCOL_REGISTRY[key]
        all_keywords = config.keywords_id | config.keywords_en
        if any(kw in q_lower for kw in all_keywords):
            return key
    return "general"
```

### Pattern 4: Modular Prompt Composition

**What:** `compose_system_prompt()` builds the system prompt from atomic blocks. The old three prompt constants are deprecated (not deleted) for one phase to allow A/B testing.

**When to use:** Called inside `generate_response()` replacing the if/elif/else block.

```python
# config/prompts.py (new addition)
from config.protocols import PROTOCOL_REGISTRY

_PERSONA_BLOCK = """Kamu adalah asisten akuntansi biaya dan manajemen yang menjawab berdasarkan textbook."""

_RULES_BLOCK = """Aturan:
1. Jawab dalam bahasa Indonesia. Gunakan istilah teknis Inggris dalam tanda kurung.
2. Setiap klaim HARUS disertai nomor referensi inline [Sumber N].
3. JANGAN tulis nama pengarang panjang — gunakan HANYA [Sumber N].
4. Jika konteks tidak cukup, katakan dengan jujur bahwa informasi tidak ditemukan.
5. Jangan mengarang informasi yang tidak ada di konteks."""

_SYNTHESIS_BLOCK = """6. Untuk query relasional: gunakan knowledge graph untuk menjelaskan hubungan konseptual.
7. Untuk query perbandingan: sajikan perspektif tiap sumber terpisah, kemudian sintesis."""

_CALCULATION_BLOCK = """Aturan tambahan untuk kalkulasi:
- Tunjukkan langkah perhitungan secara detail: rumus → substitusi → hasil.
- WAJIB sertakan disclaimer: "Verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional."
- Sertakan [Sumber N] untuk setiap rumus yang digunakan."""

def compose_system_prompt(
    protocol_key: str,
    glossary_snippet: str,
    is_calculation: bool = False,
    has_graph_context: bool = False,
) -> str:
    """Compose modular system prompt for a given protocol (PROT-04).

    Block order:
    1. Persona
    2. Rules (+ synthesis extension if graph context present)
    3. Calculation rules (if is_calculation=True)
    4. Protocol steps (from PROTOCOL_REGISTRY)
    5. Few-shot example (if non-empty)
    6. Glossary
    """
    protocol = PROTOCOL_REGISTRY.get(protocol_key, PROTOCOL_REGISTRY["general"])

    blocks = [_PERSONA_BLOCK, ""]
    rules = _RULES_BLOCK
    if has_graph_context:
        rules = rules + "\n" + _SYNTHESIS_BLOCK
    blocks.append(rules)

    if is_calculation:
        blocks.append("")
        blocks.append(_CALCULATION_BLOCK)

    blocks.append("")
    blocks.append(protocol.steps)

    if protocol.few_shot:
        blocks.append("")
        blocks.append(protocol.few_shot)

    blocks.append("")
    blocks.append(f"Glosarium istilah:\n{glossary_snippet}")

    return "\n".join(blocks)
```

### Pattern 5: RAGState Extension

**What:** Add `protocol_key: Optional[str]` as a Phase 6 field. Annotated comment style matches existing Phase 3 additions.

```python
# src/agents/state.py — new field addition
class RAGState(TypedDict):
    # ... existing fields unchanged ...
    # Phase 6 additions
    protocol_key: Optional[str]   # "cvp"|"variance_analysis"|"abc"|...|"general"
```

**Backward compatibility note:** TypedDict optional fields default to `None` when absent from state dict. Existing callers writing partial state dicts (e.g., `{"query_type": "Calculation"}` from `route_node`) do not set `protocol_key`, which is fine — `generate_response()` defaults to `"general"` if `protocol_key` is `None`.

**CRITICAL:** The existing test `test_total_field_count` in `test_query_routing.py` asserts `len(annotations) == 14`. Adding `protocol_key` changes this to 15. That test MUST be updated.

### Pattern 6: route_node Extension

**What:** `route_node` calls both `is_calculation_query` (existing) and `select_protocol` (new). Both run against the same `query` string.

```python
# src/agents/nodes.py — route_node update
def route_node(state: RAGState) -> dict:
    """Classify query type and protocol; reset CRAG state for this turn."""
    query = state["query"]
    protocol_key = select_protocol(query)

    if is_calculation_query(query):
        return {
            "query_type": "Calculation",
            "protocol_key": protocol_key,
            "llm_call_count": 0,
            "crag_iterations": 0,
            "crag_grade": None,
        }

    return {
        "query_type": "Simple",
        "protocol_key": protocol_key,
        "llm_call_count": 0,
        "crag_iterations": 0,
        "crag_grade": None,
    }
```

**Design note:** `protocol_key` is written in `route_node` alongside `query_type`. The Calculation path does NOT suppress protocol — a calculation query about BEP still gets `protocol_key="cvp"`, and `compose_system_prompt()` will receive both `protocol_key="cvp"` and `is_calculation=True`. This is intentional: the CVP steps plus calculation rules both apply.

### Pattern 7: generate_response() Refactor

**What:** Accept `protocol_key: str = "general"` as new parameter. Replace the if/elif/else prompt selection with `compose_system_prompt()`.

```python
# src/generation/generator.py — refactored generate_response()
def generate_response(
    query: str,
    context_docs: list[dict],
    graph_context: str = "",
    query_type: str = "Simple",
    conversation_history: list[dict] | None = None,
    protocol_key: str = "general",   # NEW — Phase 6
) -> dict:
    """
    ...existing docstring...
    Phase 6: protocol_key selects protocol framework for structured response.
    Backward compatible: callers omitting protocol_key get "general" behavior.
    """
    glossary_snippet = _build_glossary_snippet()
    context_block = _build_context_block(context_docs)
    is_calculation = (query_type == "Calculation")
    has_graph = bool(graph_context)

    system_prompt = compose_system_prompt(
        protocol_key=protocol_key,
        glossary_snippet=glossary_snippet,
        is_calculation=is_calculation,
        has_graph_context=has_graph,
    )
    # ... rest of function unchanged (history, messages, generate call) ...
```

### Pattern 8: generate_node / generate_calc_node Update

Both nodes already pass `query_type` to `generate_response()`. They need one additional line to pass `protocol_key`:

```python
result = generate_response(
    query=state["query"],
    context_docs=docs,
    graph_context=graph_context,
    query_type=query_type,
    conversation_history=history,
    protocol_key=state.get("protocol_key", "general"),  # Phase 6 addition
)
```

### Anti-Patterns to Avoid

- **LLM-based protocol selection:** Adding an LLM call to classify the protocol type defeats PROT-02. Rule-based is sufficient at ~88% accuracy for well-defined accounting domains.
- **Enum for protocol keys:** `Enum` complicates dict lookups (need `.value`). Plain string keys like `"cvp"` are cleaner for TypedDict and logging.
- **Deleting old prompt constants immediately:** Keep `SYSTEM_PROMPT_GENERATOR`, `SYSTEM_PROMPT_GENERATOR_CALCULATION`, `SYSTEM_PROMPT_SYNTHESIS` as deprecated aliases pointing to composed output for one phase. This preserves any caller that imported them directly (e.g., future tests or scripts).
- **Registering keywords in both `_CALC_KEYWORDS` and protocol keywords:** BEP/break-even keywords exist in `_CALC_KEYWORDS` (for Calculation detection) AND in `cvp.keywords_id` (for protocol selection). This is correct and intentional — they serve different purposes.
- **Single frozenset combining both languages:** Keep `keywords_id` and `keywords_en` separate in the dataclass for clarity and easier debugging. Merge with `|` at match time.
- **Putting few-shot examples in a separate file:** Keep them in `config/protocols.py` as inline strings for locality. They are short (3-6 lines per protocol).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template engine | Custom `{var}` substitution parser | Python f-strings | f-strings are native, zero overhead, already used everywhere in codebase |
| Priority queue for protocol matching | Custom priority logic | Static `_PROTOCOL_PRIORITY` list iterated in order | Protocols are stable; a list is readable and trivially correct |
| Fuzzy keyword matching | Levenshtein distance, TF-IDF | `str.lower()` + `in` | Accounting terms are canonical; fuzzy matching adds false positives (e.g., "variance" matching "relevance") |

**Key insight:** The keyword set approach works precisely because accounting terminology is highly domain-specific and canonical. "Varians" doesn't appear in CVP contexts; "margin kontribusi" doesn't appear in Variance Analysis contexts. Fuzzy matching would create cross-contamination.

---

## Keyword Mapping Per Protocol

**Confidence:** HIGH (sourced from existing `config/glossary.py` + CLAUDE.md domain knowledge)

### CVP Analysis
```
Indonesian: cvp, bep, break-even, break even, titik impas, margin kontribusi,
            leverage operasi, margin keamanan, volume laba, cost-volume-profit,
            biaya-volume-laba, contribution margin, titik pulang pokok
English:    cost volume profit, breakeven, break even point, contribution margin ratio,
            margin of safety, operating leverage, cvp analysis
```

### Variance Analysis
```
Indonesian: varians, analisis varians, varians harga, varians kuantitas,
            varians efisiensi, varians volume, varians anggaran, varians overhead,
            selisih, menguntungkan, tidak menguntungkan, favorable, unfavorable
English:    variance, variance analysis, material price variance, material quantity variance,
            labor rate variance, labor efficiency variance, overhead variance,
            spending variance, volume variance, price variance, quantity variance
```

### ABC (Activity-Based Costing)
```
Indonesian: abc, activity-based costing, kalkulasi biaya berdasarkan aktivitas,
            pemicu biaya, cost driver, aktivitas, cost pool, kumpulan biaya,
            resource driver, pemicu aktivitas, activity driver, alokasi berbasis aktivitas
English:    activity based costing, activity-based costing, abc costing, cost driver,
            cost pool, activity cost pool, resource driver, activity driver
```

### Transfer Pricing
```
Indonesian: harga transfer, transfer pricing, transfer price, desentralisasi,
            pusat laba, pusat investasi, harga antar divisi, laba divisi,
            penetapan harga transfer, market price, biaya penuh
English:    transfer pricing, transfer price, decentralization, profit center,
            investment center, divisional pricing, negotiated price, cost-based transfer
```

### Relevant Costing
```
Indonesian: biaya relevan, relevant cost, biaya diferensial, differential cost,
            keputusan make or buy, make or buy, keputusan khusus, special order,
            pesanan khusus, avoidable cost, biaya terhindarkan, sunk cost,
            biaya tertanam, incremental, inkremental, tambahan, eliminasi produk
English:    relevant cost, differential cost, make or buy, special order, avoidable cost,
            sunk cost, incremental cost, product elimination, dropping a segment
```

### Product Profitability
```
Indonesian: profitabilitas produk, laba produk, margin per produk, bauran produk,
            product mix, product line, segmen, pelaporan segmen, lini produk,
            kontribusi per produk, pendapatan per produk, analisis produk
English:    product profitability, product mix, product line analysis, segment reporting,
            segment margin, contribution by product, product performance
```

### Budgeting
```
Indonesian: anggaran, budgeting, budget, master budget, anggaran induk,
            anggaran fleksibel, flexible budget, anggaran statis, static budget,
            anggaran penjualan, anggaran produksi, anggaran bahan baku,
            anggaran kas, cash budget, penganggaran, anggaran operasional,
            variance anggaran, budget variance
English:    budget, budgeting, master budget, flexible budget, static budget,
            sales budget, production budget, cash budget, capital budget,
            operating budget, budgetary control
```

### Cost Classification
```
Indonesian: klasifikasi biaya, jenis biaya, biaya tetap, biaya variabel,
            biaya semi-variabel, mixed cost, biaya campuran, biaya langsung,
            biaya tidak langsung, biaya produk, biaya periode, product cost,
            period cost, biaya overhead pabrik, manufacturing overhead,
            perilaku biaya, cost behavior, step cost, biaya bertahap,
            prime cost, conversion cost, biaya utama, biaya konversi
English:    cost classification, cost behavior, fixed cost, variable cost,
            mixed cost, step cost, product cost, period cost, direct cost,
            indirect cost, manufacturing overhead, prime cost, conversion cost
```

### General (fallback)
```
Keywords: empty frozenset — always matches as last resort
```

**Priority order (most-specific first to prevent shadowing):**

1. `variance_analysis` — "varians" is unambiguous
2. `abc` — "activity-based" is unambiguous
3. `transfer_pricing` — "harga transfer" is unambiguous
4. `relevant_costing` — "biaya relevan", "make or buy" are unambiguous
5. `product_profitability` — "profitabilitas produk" is unambiguous
6. `budgeting` — "anggaran" could appear in other contexts but budget queries are distinctive
7. `cost_classification` — "biaya tetap"/"biaya variabel" broad terms, check AFTER more specific ones
8. `cvp` — "bep", "titik impas" appear in general questions but CVP is specific enough
9. `general` — fallback

**Rationale for cost_classification vs cvp ordering:** "biaya variabel" and "biaya tetap" appear in CVP analysis discussions too, but when a user asks "apa itu biaya variabel?" they want classification, not CVP analysis. Placing cost_classification before cvp means classification queries are caught first. CVP-specific terms like "break-even" and "titik impas" are distinct enough not to trigger cost_classification.

---

## Common Pitfalls

### Pitfall 1: Keyword Overlap Between CVP and Cost Classification
**What goes wrong:** "biaya tetap" and "biaya variabel" exist in both CVP and Cost Classification keyword sets. If both protocols match, the first in priority order wins — which may not be correct.
**Why it happens:** CVP analysis inherently discusses fixed and variable costs.
**How to avoid:** Remove generic cost terms ("biaya tetap", "biaya variabel") from the CVP keyword set entirely. CVP should only match on CVP-specific terms: "bep", "titik impas", "margin kontribusi", "break-even". Generic cost type questions should fall to cost_classification.
**Warning signs:** Test case "jelaskan biaya tetap" returning "cvp" instead of "cost_classification".

### Pitfall 2: Calculation Query Suppressing Protocol Steps
**What goes wrong:** `is_calculation=True` is passed to `compose_system_prompt()` but the calculation rules block overwrites the protocol steps block in the composer, causing CVP protocol steps to be absent.
**Why it happens:** If the composer concatenates blocks naively and calculation block appears after protocol steps, but the steps are still included — this is NOT a problem. The pitfall is if someone conditionally skips protocol steps when `is_calculation=True`.
**How to avoid:** Always include protocol steps regardless of `is_calculation`. The calculation rules block is ADDITIVE, not a replacement.
**Warning signs:** Calculation queries about BEP not generating "## Jawaban Singkat" sections.

### Pitfall 3: Breaking the Calculation Node Test (test_total_field_count)
**What goes wrong:** `tests/test_query_routing.py::TestRAGStateFields::test_total_field_count` asserts `len(annotations) == 14`. Adding `protocol_key` to RAGState changes this to 15.
**Why it happens:** The test was written to catch accidental field additions.
**How to avoid:** Update the assertion to 15 AND add a comment explaining the increment is intentional for Phase 6. Update `PHASE_3_FIELDS` or add a `PHASE_6_FIELDS` set.
**Warning signs:** Test failure immediately after RAGState edit.

### Pitfall 4: Old Prompt Constants Imported by External Callers
**What goes wrong:** `config/prompts.py` exports `SYSTEM_PROMPT_GENERATOR` etc. If these are deleted and any script/test directly imports them, an `ImportError` occurs at runtime.
**Why it happens:** `scripts/test_query.py` or other scripts may do `from config.prompts import SYSTEM_PROMPT_GENERATOR`.
**How to avoid:** Keep the constants as module-level strings (deprecated aliases) for at least this phase. Add a `# DEPRECATED: use compose_system_prompt()` comment. Do not delete until Phase 07.
**Warning signs:** `ImportError: cannot import name 'SYSTEM_PROMPT_GENERATOR'`.

### Pitfall 5: Protocol Registry Import Cycle
**What goes wrong:** If `config/protocols.py` imports from `config/glossary.py` and `config/glossary.py` also imports from `config/protocols.py`, circular import at module load.
**Why it happens:** Glossary injection could be tempted to live in `protocols.py`.
**How to avoid:** `config/protocols.py` MUST NOT import `config/glossary.py`. Glossary snippet is injected at call time in `compose_system_prompt()`, not baked into protocol config.
**Warning signs:** `ImportError: cannot import name 'GLOSSARY' (circular import)` at startup.

### Pitfall 6: Fuzzy Keyword Matching False Positives
**What goes wrong:** Using `keyword in query` where keyword is too short (e.g., "abc") will match "tidak" (no), "applicable" (unrelated).
**Why it happens:** Short abbreviations can be substrings of longer unrelated words.
**How to avoid:** For short abbreviations like "abc", use word-boundary matching: `re.search(r'\babc\b', q_lower)` or check with spaces: `" abc " in f" {q_lower} "`. Alternatively, use full phrases: "activity-based costing" instead of just "abc".
**Warning signs:** Test case "kontrak ABC dengan vendor" being classified as ABC costing protocol.

---

## Code Examples

### Full compose_system_prompt() Pattern

```python
# config/prompts.py
# Source: verified against existing prompt structure in this file

def compose_system_prompt(
    protocol_key: str,
    glossary_snippet: str,
    is_calculation: bool = False,
    has_graph_context: bool = False,
) -> str:
    """Compose modular system prompt (PROT-04).

    Block order: persona → rules [+synthesis] → [calculation] → protocol_steps → [few_shot] → glossary
    """
    from config.protocols import PROTOCOL_REGISTRY
    protocol = PROTOCOL_REGISTRY.get(protocol_key, PROTOCOL_REGISTRY["general"])

    parts: list[str] = []

    # Block 1: Persona
    parts.append(_PERSONA_BLOCK)

    # Block 2: Core rules (+ synthesis extension if graph context)
    if has_graph_context:
        parts.append(_RULES_BLOCK + "\n" + _SYNTHESIS_BLOCK)
    else:
        parts.append(_RULES_BLOCK)

    # Block 3: Calculation addendum (additive, does NOT replace protocol steps)
    if is_calculation:
        parts.append(_CALCULATION_BLOCK)

    # Block 4: Protocol-specific steps (always included)
    parts.append(protocol.steps)

    # Block 5: Few-shot example (optional per protocol)
    if protocol.few_shot:
        parts.append(protocol.few_shot)

    # Block 6: Glossary
    parts.append(f"Glosarium istilah:\n{glossary_snippet}")

    return "\n\n".join(parts)
```

### select_protocol() with Word-Boundary Guard for Short Abbreviations

```python
# src/retrieval/query_classifier.py
import re

def select_protocol(query: str) -> str:
    """Return protocol_key via rule-based matching. Zero LLM calls (PROT-02)."""
    q_lower = query.lower()
    # Guard: pad with spaces for word-boundary matching on short terms
    q_padded = f" {q_lower} "

    for key in _PROTOCOL_PRIORITY:
        if key == "general":
            return "general"
        config = PROTOCOL_REGISTRY[key]
        all_keywords = config.keywords_id | config.keywords_en
        for kw in all_keywords:
            # Short keywords (≤4 chars): require word boundary
            if len(kw) <= 4:
                if f" {kw} " in q_padded or q_padded.startswith(f"{kw} ") or q_padded.endswith(f" {kw}"):
                    return key
            else:
                if kw in q_lower:
                    return key
    return "general"
```

### Test Pattern for Protocol Selection (Pure Unit)

```python
# tests/test_protocol_selection.py
# No mocks, no live services — pure function tests

import pytest
from src.retrieval.query_classifier import select_protocol

class TestSelectProtocol:
    """PROT-02: Zero-LLM protocol selection via keyword matching."""

    @pytest.mark.parametrize("query,expected", [
        # CVP
        ("jelaskan break-even point", "cvp"),
        ("apa itu titik impas?", "cvp"),
        ("hitung margin kontribusi", "cvp"),
        # Variance Analysis
        ("jelaskan varians harga bahan baku", "variance_analysis"),
        ("analisis varians efisiensi tenaga kerja", "variance_analysis"),
        ("apa itu favorable variance?", "variance_analysis"),
        # ABC
        ("jelaskan activity-based costing", "abc"),
        ("apa itu cost driver dalam abc?", "abc"),
        # Transfer Pricing
        ("bagaimana harga transfer ditetapkan?", "transfer_pricing"),
        ("metode transfer pricing antar divisi", "transfer_pricing"),
        # Relevant Costing
        ("biaya relevan dalam keputusan make or buy", "relevant_costing"),
        ("apa yang dimaksud biaya diferensial?", "relevant_costing"),
        # Budgeting
        ("bagaimana membuat master budget?", "budgeting"),
        ("jelaskan flexible budget vs static budget", "budgeting"),
        # Cost Classification
        ("apa perbedaan biaya tetap dan biaya variabel?", "cost_classification"),
        ("jelaskan jenis-jenis biaya produksi", "cost_classification"),
        # General fallback
        ("apa itu akuntansi manajemen?", "general"),
        ("jelaskan konsep dasar akuntansi biaya", "general"),
        ("", "general"),
    ])
    def test_protocol_selection(self, query, expected):
        assert select_protocol(query) == expected

    def test_no_false_positive_abc_in_kontrak_abc(self):
        """'kontrak ABC dengan vendor' should NOT match ABC costing protocol."""
        result = select_protocol("kontrak ABC dengan vendor lainnya")
        assert result != "abc"

    def test_calculation_query_still_gets_protocol(self):
        """Calculation queries also receive a protocol_key (CVP for BEP calculations)."""
        # is_calculation_query and select_protocol are independent
        from src.retrieval.query_classifier import is_calculation_query
        query = "hitung BEP dengan fixed cost 100000"
        assert is_calculation_query(query) is True
        assert select_protocol(query) == "cvp"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 3 static prompt constants (if/elif/else selection) | Modular composition via `compose_system_prompt()` | Phase 6 | Protocol steps injectable without code changes; adding a new protocol = add one dict entry |
| Single query classifier (`is_calculation_query`) | Dual classifiers: `is_calculation_query` + `select_protocol` | Phase 6 | Protocol selection for all 9 frameworks, zero LLM calls |
| `RAGState` has 14 fields | 15 fields (+ `protocol_key`) | Phase 6 | Routes protocol information from `route_node` to `generate_*_node` via state |

**Deprecated/outdated after Phase 6:**
- `SYSTEM_PROMPT_GENERATOR`: Replaced by `compose_system_prompt(protocol_key="general")`. Keep as deprecated alias.
- `SYSTEM_PROMPT_GENERATOR_CALCULATION`: Replaced by `compose_system_prompt(protocol_key=<any>, is_calculation=True)`. Keep as deprecated alias.
- `SYSTEM_PROMPT_SYNTHESIS`: Replaced by `compose_system_prompt(protocol_key=<any>, has_graph_context=True)`. Keep as deprecated alias.

---

## Open Questions

1. **Product Profitability vs General overlap**
   - What we know: "analisis produk" and "lini produk" keywords are in product_profitability
   - What's unclear: A query like "bandingkan biaya produk A dan B" might be Relevant Costing (decision) or Product Profitability (performance)
   - Recommendation: Add "perbandingan produk" to relevant_costing keywords (make-or-buy framing) and "profitabilitas" to product_profitability. Test with real queries from Phase 06 QA.

2. **Few-shot example length vs context window budget**
   - What we know: Few-shot examples add ~100-200 tokens per protocol to the system prompt
   - What's unclear: Current system prompt with glossary is ~800 tokens. Adding 8 protocol few-shot blocks would add ~1400 tokens if all were included — but only ONE protocol's few-shot is included per query
   - Recommendation: One few-shot per query (the matched protocol). Total system prompt budget increase: ~200 tokens. Acceptable.

3. **Budgeting keyword "anggaran" — too broad?**
   - What we know: "anggaran" appears in variance analysis context ("varians anggaran"), cost classification context, and pure budgeting context
   - What's unclear: Will "varians anggaran" be classified as budgeting instead of variance_analysis?
   - Recommendation: Since variance_analysis is higher priority in `_PROTOCOL_PRIORITY` than budgeting, "varians anggaran" will match variance_analysis first (via "varians" keyword). No conflict. Verify with test case.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` — none set, defaults apply) |
| Quick run command | `uv run pytest tests/test_protocol_selection.py tests/test_query_routing.py -q` |
| Full suite command | `uv run pytest -m "not integration and not gpu" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROT-01 | Protocol matched to query and response uses correct steps | unit | `uv run pytest tests/test_protocol_selection.py -k "test_protocol_selection" -x` | Wave 0 |
| PROT-02 | select_protocol() makes no LLM calls; returns string key | unit | `uv run pytest tests/test_protocol_selection.py -x` | Wave 0 |
| PROT-03 | LLM output contains section headers from protocol steps | unit (mock LLM) | `uv run pytest tests/test_protocol_prompts.py -x` | Wave 0 |
| PROT-04 | compose_system_prompt() output contains all 4+ blocks | unit | `uv run pytest tests/test_protocol_prompts.py -k "test_compose" -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_protocol_selection.py tests/test_query_routing.py tests/test_generation.py -q`
- **Per wave merge:** `uv run pytest -m "not integration and not gpu" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_protocol_selection.py` — covers PROT-01, PROT-02 (select_protocol accuracy)
- [ ] `tests/test_protocol_prompts.py` — covers PROT-03, PROT-04 (compose_system_prompt blocks, few-shot format)
- [ ] Update `tests/test_query_routing.py::TestRAGStateFields::test_total_field_count` — change `== 14` to `== 15`; add `protocol_key` to PHASE_6_FIELDS set

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — all changes are pure Python code/config, no new CLI tools, databases, or services required).

---

## Sources

### Primary (HIGH confidence)

- Direct code reading of `config/prompts.py` — 3-branch prompt structure documented
- Direct code reading of `src/retrieval/query_classifier.py` — `is_calculation_query` pattern for extension
- Direct code reading of `src/agents/state.py` — RAGState TypedDict structure
- Direct code reading of `src/agents/nodes.py` — `route_node` and `generate_*_node` logic
- Direct code reading of `src/generation/generator.py` — `generate_response()` signature and if/elif/else
- Direct code reading of `config/glossary.py` — 130+ bilingual terms (keyword source)
- Direct code reading of `tests/test_query_routing.py` — existing test patterns to extend

### Secondary (MEDIUM confidence)

- Python stdlib `dataclasses` documentation — `@dataclass(frozen=True)` for immutable config
- Python stdlib `frozenset` — O(1) keyword membership testing

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all stdlib, no new dependencies, pattern directly extends existing `query_classifier.py`
- Architecture: HIGH — direct code analysis of all 5 key files; patterns are proven in existing codebase
- Pitfalls: HIGH — pitfalls derived from direct code reading (field count test, import cycles, keyword overlap)
- Keyword mapping: MEDIUM — keywords sourced from `config/glossary.py` (authoritative for this project) + accounting domain knowledge; full accuracy requires QA testing in Phase 07

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable domain — no external library changes affect this phase)
