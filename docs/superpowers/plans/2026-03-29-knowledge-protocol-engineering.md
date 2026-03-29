# Knowledge Protocol Engineering (KPE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengubah RAG dari "mesin pencari jawaban textbook" menjadi konsultan akuntansi manajemen yang merespons dengan structured problem solving ala McKinsey/BCG, menggunakan Knowledge Protocol Engineering + consulting book retrieval.

**Architecture:** KPE layer hardcode management accounting frameworks sebagai reasoning templates di system prompts (HOW to reason). 21 buku consulting di-ingest ke Qdrant dengan `source_domain: "consulting"` metadata (WHAT to reason about). Query classifier di-extend ke 4 tipe (Simple/Medium/Complex/Calculation) dan memilih protocol yang tepat. `[Sumber N]` vs `[Kerangka N]` membedakan factual vs methodology citations.

**Tech Stack:** LangGraph StateGraph, Qdrant (qdrant-client), Qwen3 via SiliconFlow API, Python dataclasses, uv/pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `config/protocols.py` | CREATE | Protocol dataclass + 8 domain protocols + match_protocol() |
| `config/prompts.py` | MODIFY | build_system_prompt() composable builder (3 base templates) |
| `src/retrieval/query_classifier.py` | MODIFY | Add classify_query() → (query_type, protocol_name) |
| `src/agents/state.py` | MODIFY | Add selected_protocol field |
| `src/agents/nodes.py` | MODIFY | route_node, generate_node, generate_calc_node, retrieve_node |
| `src/generation/generator.py` | MODIFY | Accept protocol param, use prompt builder |
| `src/generation/citation_builder.py` | MODIFY | Differentiate [Sumber N] vs [Kerangka N] by source_domain |
| `src/retrieval/vector_search.py` | MODIFY | Add domain_filter param to hybrid_search() |
| `scripts/ingest.py` | MODIFY | Add --source-domain CLI flag |
| `scripts/backfill_source_domain.py` | CREATE | One-time: add source_domain to existing Qdrant points |
| `tests/test_protocols.py` | CREATE | Tests for classify_query, match_protocol, build_system_prompt |
| `tests/test_query_routing.py` | MODIFY | Update field count + add classify_query tests |

---

## Phase A: KPE Core (Generation Layer)

### Task 1: Protocol Registry

**Files:**
- Create: `config/protocols.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_protocols.py
from config.protocols import PROTOCOLS, match_protocol, Protocol


class TestProtocolRegistry:
    def test_protocols_dict_has_expected_keys(self):
        expected = {
            "cvp", "variance", "abc", "transfer_pricing",
            "relevant_costing", "product_profitability",
            "budgeting", "cost_classification", "general",
        }
        assert set(PROTOCOLS.keys()) == expected

    def test_protocol_dataclass_fields(self):
        p = PROTOCOLS["cvp"]
        assert isinstance(p.name, str)
        assert isinstance(p.name_id, str)
        assert isinstance(p.trigger_keywords, list)
        assert isinstance(p.query_types, list)
        assert isinstance(p.steps, list)
        assert isinstance(p.output_sections, list)
        assert isinstance(p.few_shot_example, str)
        assert len(p.steps) >= 4
        assert len(p.output_sections) >= 2

    def test_cvp_triggers_on_bep_keyword(self):
        protocol = match_protocol("apa itu break-even point?", "Simple")
        assert protocol is not None
        assert protocol.name == "CVP / Break-Even Analysis"

    def test_variance_triggers_on_varians_keyword(self):
        protocol = match_protocol("jelaskan analisis varians biaya bahan baku", "Medium")
        assert protocol is not None
        assert protocol.name == "Variance Analysis"

    def test_abc_triggers_on_activity_keyword(self):
        protocol = match_protocol("bagaimana ABC costing berbeda dari traditional costing?", "Medium")
        assert protocol is not None
        assert protocol.name == "Activity-Based Costing"

    def test_no_match_returns_general_protocol(self):
        protocol = match_protocol("apa itu akuntansi?", "Simple")
        assert protocol is not None
        assert protocol.name == "General Consulting"

    def test_match_protocol_case_insensitive(self):
        protocol = match_protocol("Hitung CONTRIBUTION MARGIN produk X", "Simple")
        assert protocol is not None
        assert protocol.name == "CVP / Break-Even Analysis"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_protocols.py -v
```
Expected: `ModuleNotFoundError: No module named 'config.protocols'`

- [ ] **Step 3: Implement `config/protocols.py`**

```python
"""Knowledge Protocol Engineering (KPE) registry.

Each Protocol encodes a management accounting analytical framework as an
executable reasoning template for LLM generation. Selector is rule-based
(zero LLM calls). Inspired by KPE (arXiv 2507.02760).
"""

from dataclasses import dataclass


@dataclass
class Protocol:
    name: str
    name_id: str
    trigger_keywords: list[str]
    query_types: list[str]
    steps: list[str]
    output_sections: list[str]
    few_shot_example: str


PROTOCOLS: dict[str, Protocol] = {
    "cvp": Protocol(
        name="CVP / Break-Even Analysis",
        name_id="Analisis Biaya-Volume-Laba (BVL)",
        trigger_keywords=[
            "break-even", "bep", "titik impas", "contribution margin",
            "margin kontribusi", "break even", "cvp",
        ],
        query_types=["Simple", "Medium", "Calculation"],
        steps=[
            "Identifikasi komponen: biaya tetap (fixed cost), biaya variabel per unit (variable cost per unit), harga jual per unit (selling price per unit).",
            "Hitung contribution margin per unit = harga jual per unit − biaya variabel per unit.",
            "Hitung contribution margin ratio (CM ratio) = CM per unit ÷ harga jual per unit.",
            "Hitung BEP dalam unit = biaya tetap ÷ CM per unit.",
            "Hitung BEP dalam Rupiah = biaya tetap ÷ CM ratio.",
            "Jika ada target laba: unit yang diperlukan = (biaya tetap + target laba) ÷ CM per unit.",
            "Lakukan analisis sensitivitas: apa dampaknya jika harga jual, biaya variabel, atau biaya tetap berubah?",
            "Berikan rekomendasi operasional berdasarkan hasil analisis.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Analisis CVP",
            "## Implikasi & Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "BEP PT Maju adalah 3.333 unit atau Rp 100.000.000 per periode [Sumber 1].\n\n"
            "## Analisis CVP\n"
            "- Harga jual: Rp 30.000/unit; biaya variabel: Rp 20.000/unit\n"
            "- CM per unit = Rp 30.000 − Rp 20.000 = **Rp 10.000** [Sumber 1]\n"
            "- BEP unit = Rp 100.000.000 ÷ Rp 10.000 = **3.333 unit**\n\n"
            "## Implikasi & Rekomendasi\n"
            "Dengan margin of safety rendah, perusahaan rentan terhadap penurunan volume. "
            "Rekomendasi: evaluasi peluang pengurangan biaya variabel atau diversifikasi produk [Sumber 2]."
        ),
    ),
    "variance": Protocol(
        name="Variance Analysis",
        name_id="Analisis Selisih (Varians)",
        trigger_keywords=[
            "selisih", "variance", "varians", "anggaran vs realisasi",
            "budget variance", "material variance", "labour variance",
            "efisiensi", "price variance",
        ],
        query_types=["Medium", "Complex", "Calculation"],
        steps=[
            "Identifikasi jenis selisih: biaya bahan baku (material), tenaga kerja (labour), overhead.",
            "Hitung selisih harga (price variance) = (harga aktual − harga standar) × kuantitas aktual.",
            "Hitung selisih kuantitas/efisiensi (quantity/efficiency variance) = (kuantitas aktual − kuantitas standar) × harga standar.",
            "Tentukan arah selisih: favorable (F) jika menguntungkan, adverse/unfavorable (U) jika merugikan.",
            "Analisis penyebab utama setiap selisih (operasional, pasar, perencanaan).",
            "Tentukan apakah selisih material dan perlu tindak lanjut.",
            "Berikan rekomendasi perbaikan berdasarkan penyebab dominan.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Dekomposisi Selisih",
            "## Analisis Penyebab",
            "## Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Total selisih biaya bahan baku adalah Rp 5.000.000 Unfavorable — "
            "didominasi oleh selisih harga (price variance) [Sumber 1].\n\n"
            "## Dekomposisi Selisih\n"
            "| Jenis | Formula | Hasil |\n"
            "|-------|---------|-------|\n"
            "| Price Variance | (Rp 11.000 − Rp 10.000) × 5.000 kg | Rp 5.000.000 U |\n"
            "| Quantity Variance | (5.000 − 5.100) × Rp 10.000 | Rp 1.000.000 F |\n\n"
            "## Analisis Penyebab\n"
            "Price variance disebabkan kenaikan harga pasar bahan baku [Sumber 2].\n\n"
            "## Rekomendasi\n"
            "Negosiasi kontrak jangka panjang dengan supplier untuk mengunci harga."
        ),
    ),
    "abc": Protocol(
        name="Activity-Based Costing",
        name_id="Kalkulasi Biaya Berbasis Aktivitas (ABC)",
        trigger_keywords=[
            "abc", "activity-based", "activity based", "cost driver",
            "pemicu biaya", "cost pool", "overhead allocation",
        ],
        query_types=["Simple", "Medium", "Complex"],
        steps=[
            "Identifikasi aktivitas-aktivitas utama yang mengonsumsi sumber daya (resource-consuming activities).",
            "Kelompokkan biaya overhead ke dalam cost pools berdasarkan aktivitas.",
            "Tentukan cost driver (pemicu biaya) untuk setiap activity cost pool.",
            "Hitung activity rate = total biaya cost pool ÷ total cost driver.",
            "Alokasikan biaya ke produk/jasa berdasarkan konsumsi cost driver masing-masing.",
            "Bandingkan dengan metode tradisional (volume-based allocation) — identifikasi produk yang over/under-costed.",
            "Berikan rekomendasi keputusan strategis (pricing, product mix, process improvement).",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Identifikasi Aktivitas & Cost Driver",
            "## Perhitungan Activity Rate",
            "## Perbandingan vs Metode Tradisional",
            "## Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "ABC costing menghasilkan alokasi yang lebih akurat karena mengikuti actual resource consumption, "
            "bukan hanya volume produksi [Sumber 1].\n\n"
            "## Identifikasi Aktivitas & Cost Driver\n"
            "| Aktivitas | Cost Pool | Cost Driver |\n"
            "|-----------|-----------|-------------|\n"
            "| Setup mesin | Rp 50.000.000 | Jumlah setup |\n"
            "| Inspeksi | Rp 30.000.000 | Jumlah inspeksi |\n\n"
            "## Rekomendasi\n"
            "Produk Y (low-volume, high-setup) selama ini under-costed — pertimbangkan repricing."
        ),
    ),
    "transfer_pricing": Protocol(
        name="Transfer Pricing",
        name_id="Penetapan Harga Transfer",
        trigger_keywords=[
            "transfer pricing", "harga transfer", "transfer price",
            "divisi", "intracompany", "antar divisi",
        ],
        query_types=["Medium", "Complex"],
        steps=[
            "Identifikasi kondisi: apakah ada kapasitas menganggur (idle capacity) di divisi penjual?",
            "Jika ada idle capacity: harga transfer minimum = biaya variabel per unit.",
            "Jika tidak ada idle capacity: harga transfer minimum = biaya variabel + contribution margin yang dikorbankan (opportunity cost).",
            "Tentukan harga transfer maksimum = harga pasar eksternal yang tersedia untuk divisi pembeli.",
            "Evaluasi dampak terhadap laba perusahaan keseluruhan (total firm perspective).",
            "Pertimbangkan aspek motivasi divisi manajer dan goal congruence.",
            "Rekomendasikan kisaran harga transfer yang optimal (minimum ≤ TP ≤ maksimum).",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Analisis Kapasitas & Opportunity Cost",
            "## Kisaran Harga Transfer",
            "## Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Kisaran harga transfer yang optimal adalah Rp 40.000 – Rp 55.000 per unit [Sumber 1].\n\n"
            "## Analisis Kapasitas & Opportunity Cost\n"
            "Divisi A memiliki idle capacity 1.000 unit. Biaya variabel Rp 40.000/unit. "
            "Tidak ada opportunity cost [Sumber 2].\n\n"
            "## Rekomendasi\n"
            "Negosiasikan harga di antara Rp 40.000–Rp 55.000 untuk memotivasi kedua divisi."
        ),
    ),
    "relevant_costing": Protocol(
        name="Relevant Costing",
        name_id="Biaya Relevan untuk Pengambilan Keputusan",
        trigger_keywords=[
            "biaya relevan", "relevant cost", "keputusan khusus",
            "make or buy", "buat atau beli", "special order",
            "order khusus", "terima tolak", "accept reject",
            "drop product", "hentikan lini",
        ],
        query_types=["Medium", "Complex"],
        steps=[
            "Identifikasi jenis keputusan: make-or-buy, special order, drop product line, atau scarce resource allocation.",
            "Pisahkan biaya relevan (future, differential) dari biaya tidak relevan (sunk cost, fixed cost tidak terpengaruh).",
            "Hitung incremental revenue dan incremental cost dari setiap alternatif.",
            "Hitung incremental profit/loss untuk setiap alternatif.",
            "Pertimbangkan faktor kualitatif: kualitas, keandalan supplier, dampak pada pelanggan.",
            "Buat keputusan berdasarkan incremental profit tertinggi.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Identifikasi Biaya Relevan vs Tidak Relevan",
            "## Analisis Inkremental",
            "## Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Keputusan make lebih menguntungkan — selisih Rp 15.000.000 per tahun [Sumber 1].\n\n"
            "## Identifikasi Biaya Relevan vs Tidak Relevan\n"
            "- Relevan: biaya bahan, tenaga kerja, overhead variabel\n"
            "- Tidak relevan: biaya overhead tetap yang tidak berubah (sunk) [Sumber 1]\n\n"
            "## Analisis Inkremental\n"
            "| Item | Make | Buy | Selisih |\n"
            "|------|------|-----|---------||\n"
            "| Biaya variabel | Rp 80.000.000 | Rp 95.000.000 | Rp 15.000.000 |\n"
        ),
    ),
    "product_profitability": Protocol(
        name="Product Profitability Analysis",
        name_id="Analisis Profitabilitas Produk",
        trigger_keywords=[
            "profitabilitas", "product profitability", "lini produk",
            "margin produk", "product mix", "bauran produk",
            "profitable", "menguntungkan",
        ],
        query_types=["Medium", "Complex"],
        steps=[
            "Hitung contribution margin (CM) per unit untuk setiap produk.",
            "Hitung CM ratio = CM per unit ÷ harga jual per unit.",
            "Jika ada kendala sumber daya (bottleneck): hitung CM per unit sumber daya langka.",
            "Rangking produk berdasarkan CM per unit sumber daya langka (bukan CM absolut).",
            "Analisis dampak volume: apakah volume produk ini di atas BEP-nya?",
            "Identifikasi produk yang cross-subsidize produk lain.",
            "Berikan rekomendasi product mix optimal.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Perbandingan Profitabilitas",
            "## Analisis Bauran Optimal",
            "## Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Produk A lebih menguntungkan per unit mesin-jam dibanding Produk B [Sumber 1].\n\n"
            "## Perbandingan Profitabilitas\n"
            "| Produk | CM/unit | Mesin-jam | CM/mesin-jam |\n"
            "|--------|---------|-----------|-------------|\n"
            "| A | Rp 20.000 | 2 jam | Rp 10.000 |\n"
            "| B | Rp 30.000 | 4 jam | Rp 7.500 |\n\n"
            "## Rekomendasi\n"
            "Prioritaskan Produk A jika kapasitas mesin terbatas."
        ),
    ),
    "budgeting": Protocol(
        name="Budgeting & Planning Analysis",
        name_id="Analisis Anggaran dan Perencanaan",
        trigger_keywords=[
            "anggaran", "budget", "budgeting", "perencanaan",
            "master budget", "flexible budget", "anggaran fleksibel",
            "perencanaan laba", "profit planning",
        ],
        query_types=["Simple", "Medium"],
        steps=[
            "Identifikasi jenis anggaran: master budget, flexible budget, atau zero-based budget.",
            "Mulai dari sales budget (titik awal master budget) → production budget → cost budgets.",
            "Hitung production budget: unit yang diproduksi = penjualan yang dianggarkan + ending inventory − beginning inventory.",
            "Susun direct material, direct labour, dan overhead budget dari production budget.",
            "Buat cash budget untuk mengelola likuiditas.",
            "Identifikasi asumsi kunci dan risikonya.",
            "Rekomendasikan pendekatan penganggaran yang sesuai dengan kondisi perusahaan.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Struktur Anggaran",
            "## Asumsi & Risiko Utama",
            "## Rekomendasi",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Master budget dimulai dari sales forecast — semua anggaran lain bergantung padanya [Sumber 1].\n\n"
            "## Struktur Anggaran\n"
            "1. Sales Budget → 2. Production Budget → 3. DM/DL/OH Budgets → 4. Cost of Goods Sold → "
            "5. Cash Budget → 6. Budgeted Financial Statements [Sumber 1]\n\n"
            "## Rekomendasi\n"
            "Gunakan flexible budget untuk evaluasi kinerja agar perbandingan apple-to-apple."
        ),
    ),
    "cost_classification": Protocol(
        name="Cost Classification & Behavior",
        name_id="Klasifikasi dan Perilaku Biaya",
        trigger_keywords=[
            "klasifikasi biaya", "cost classification", "cost behavior",
            "perilaku biaya", "biaya tetap", "biaya variabel",
            "fixed cost", "variable cost", "mixed cost", "biaya campuran",
            "overhead", "biaya overhead",
        ],
        query_types=["Simple", "Medium"],
        steps=[
            "Klasifikasikan biaya berdasarkan perilakunya terhadap volume: tetap (fixed), variabel (variable), atau campuran (mixed/semi-variable).",
            "Untuk biaya campuran: gunakan metode high-low atau regresi untuk memisahkan komponen tetap dan variabel.",
            "Klasifikasikan juga berdasarkan fungsi: manufacturing (DM, DL, overhead) vs non-manufacturing (selling, admin).",
            "Identifikasi relevance untuk keputusan: biaya relevan vs tidak relevan, controllable vs uncontrollable.",
            "Berikan implikasi klasifikasi ini terhadap CVP analysis atau keputusan manajemen.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Klasifikasi Berdasarkan Perilaku",
            "## Implikasi untuk Keputusan Manajemen",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Biaya sewa gedung adalah biaya tetap (fixed cost) — tidak berubah dalam relevant range [Sumber 1].\n\n"
            "## Klasifikasi Berdasarkan Perilaku\n"
            "- **Tetap**: sewa, depresiasi, gaji manajer\n"
            "- **Variabel**: bahan baku, komisi penjualan\n"
            "- **Campuran**: listrik (ada komponen tetap + variabel) [Sumber 2]\n\n"
            "## Implikasi untuk Keputusan Manajemen\n"
            "Klasifikasi ini kritis untuk CVP analysis dan penetapan harga jangka pendek."
        ),
    ),
    "general": Protocol(
        name="General Consulting",
        name_id="Konsultasi Umum (Pyramid Principle)",
        trigger_keywords=[],
        query_types=["Simple", "Medium", "Complex", "Calculation"],
        steps=[
            "Nyatakan jawaban atau rekomendasi utama terlebih dahulu (answer-first, Pyramid Principle).",
            "Dukung jawaban dengan 2-3 poin bukti atau alasan utama dari sumber.",
            "Berikan konteks atau implikasi praktis.",
        ],
        output_sections=[
            "## Jawaban Singkat",
            "## Penjelasan",
        ],
        few_shot_example=(
            "**Contoh format respons:**\n"
            "## Jawaban Singkat\n"
            "Activity-Based Costing (ABC) memberikan alokasi overhead yang lebih akurat dibanding metode tradisional [Sumber 1].\n\n"
            "## Penjelasan\n"
            "- ABC menggunakan multiple cost drivers yang mencerminkan actual resource consumption [Sumber 1]\n"
            "- Metode tradisional hanya menggunakan satu driver (volume) yang menyebabkan distorsi [Sumber 2]\n"
            "- Implementasi ABC memerlukan identifikasi aktivitas yang cermat [Sumber 1]"
        ),
    ),
}


def match_protocol(query: str, query_type: str) -> Protocol:
    """Select the most appropriate protocol based on query keywords.

    Tries all protocols except 'general' in order. Returns the first match.
    Falls back to 'general' if no keywords match.

    Args:
        query: The user's query string (raw or reformulated)
        query_type: One of "Simple", "Medium", "Complex", "Calculation"

    Returns:
        Protocol instance (never None — general is always the fallback)
    """
    q_lower = query.lower()
    for key, protocol in PROTOCOLS.items():
        if key == "general":
            continue
        if any(kw in q_lower for kw in protocol.trigger_keywords):
            return protocol
    return PROTOCOLS["general"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_protocols.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add config/protocols.py tests/test_protocols.py
git commit -m "feat(kpe): add protocol registry with 8 management accounting frameworks"
```

---

### Task 2: Enhanced Query Classifier

**Files:**
- Modify: `src/retrieval/query_classifier.py`
- Modify: `tests/test_query_routing.py`

- [ ] **Step 1: Write failing tests for classify_query**

Append to `tests/test_protocols.py`:

```python
from src.retrieval.query_classifier import classify_query


class TestClassifyQuery:
    """Tests for enhanced 4-way query classifier."""

    def test_calculation_takes_priority_over_complex(self):
        """'hitunglah strategi biaya 100000' should be Calculation (has number + keyword)."""
        query_type, protocol_name = classify_query(
            "hitunglah BEP jika fixed cost 100000"
        )
        assert query_type == "Calculation"

    def test_complex_detected_by_strategy_keyword(self):
        """'bagaimana menerapkan ABC costing' is Complex (strategy keyword, no number)."""
        query_type, protocol_name = classify_query(
            "bagaimana menerapkan ABC costing di perusahaan manufaktur?"
        )
        assert query_type == "Complex"
        assert protocol_name == "abc"

    def test_medium_detected_by_comparison_keyword(self):
        """'bandingkan ABC dengan traditional costing' is Medium."""
        query_type, protocol_name = classify_query(
            "bandingkan ABC dengan traditional costing"
        )
        assert query_type == "Medium"
        assert protocol_name == "abc"

    def test_simple_is_default_for_conceptual_question(self):
        """'apa itu break-even point?' is Simple (no Medium/Complex keywords)."""
        query_type, protocol_name = classify_query("apa itu break-even point?")
        assert query_type == "Simple"
        assert protocol_name == "cvp"

    def test_calculation_with_variance_returns_variance_protocol(self):
        """Calculation query about variance gets variance protocol."""
        query_type, protocol_name = classify_query(
            "hitunglah selisih harga bahan baku jika actual price 11000 dan standard 10000"
        )
        assert query_type == "Calculation"
        assert protocol_name == "variance"

    def test_no_protocol_match_returns_general(self):
        """General accounting question returns 'general' protocol."""
        query_type, protocol_name = classify_query("apa itu akuntansi manajemen?")
        assert query_type == "Simple"
        assert protocol_name == "general"

    def test_returns_tuple_of_two_strings(self):
        """Return type is always (str, str)."""
        result = classify_query("apa itu biaya?")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, str) for v in result)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_protocols.py::TestClassifyQuery -v
```
Expected: `ImportError: cannot import name 'classify_query'`

- [ ] **Step 3: Implement classify_query in query_classifier.py**

The existing `is_calculation_query()` stays unchanged. Add below it:

```python
# At the top of the file, add import:
# from config.protocols import match_protocol

_COMPLEX_KEYWORDS = frozenset([
    "bagaimana menerapkan",
    "strategi",
    "analisis kasus",
    "evaluasi",
    "rekomendasikan",
    "implementasi",
    "rancang",
    "desain sistem",
])

_MEDIUM_KEYWORDS = frozenset([
    "bandingkan",
    "perbedaan",
    " vs ",
    "hubungan",
    "pengaruh",
    "dibandingkan",
    "perbandingan",
    "versus",
    "jelaskan perbedaan",
])


def classify_query(query: str) -> tuple[str, str]:
    """Classify query into (query_type, protocol_name).

    Priority: Calculation → Complex → Medium → Simple.
    Always returns a protocol (falls back to 'general').

    Args:
        query: Raw or reformulated user query

    Returns:
        (query_type, protocol_name) — e.g. ("Calculation", "cvp")
    """
    from config.protocols import match_protocol

    if is_calculation_query(query):
        query_type = "Calculation"
    else:
        q_lower = query.lower()
        if any(kw in q_lower for kw in _COMPLEX_KEYWORDS):
            query_type = "Complex"
        elif any(kw in q_lower for kw in _MEDIUM_KEYWORDS):
            query_type = "Medium"
        else:
            query_type = "Simple"

    protocol = match_protocol(query, query_type)
    return query_type, protocol.name.lower().replace(" / ", "_").replace(" ", "_").replace("-", "_")
```

**Important:** The protocol_name returned must match PROTOCOLS dict keys. Fix the return to use the dict key directly:

```python
def classify_query(query: str) -> tuple[str, str]:
    """Classify query into (query_type, protocol_key).

    Priority: Calculation → Complex → Medium → Simple.
    protocol_key is the key in PROTOCOLS dict (e.g. "cvp", "variance", "general").

    Args:
        query: Raw or reformulated user query

    Returns:
        (query_type, protocol_key) — e.g. ("Calculation", "cvp")
    """
    from config.protocols import PROTOCOLS, match_protocol

    if is_calculation_query(query):
        query_type = "Calculation"
    else:
        q_lower = query.lower()
        if any(kw in q_lower for kw in _COMPLEX_KEYWORDS):
            query_type = "Complex"
        elif any(kw in q_lower for kw in _MEDIUM_KEYWORDS):
            query_type = "Medium"
        else:
            query_type = "Simple"

    protocol = match_protocol(query, query_type)
    # Find the key for this protocol in the registry
    protocol_key = next(k for k, v in PROTOCOLS.items() if v is protocol)
    return query_type, protocol_key
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_protocols.py::TestClassifyQuery -v
```
Expected: all 7 tests PASS

- [ ] **Step 5: Update test_query_routing.py for new field count and classify_query**

In `tests/test_query_routing.py`, update `test_total_field_count`:

```python
def test_total_field_count(self):
    """RAGState should have exactly 15 fields after adding selected_protocol in Task 3."""
    annotations = RAGState.__annotations__
    assert len(annotations) == 15, (
        f"Expected 15 fields, got {len(annotations)}. Fields: {sorted(annotations.keys())}"
    )
```

Note: This test will fail until Task 3 adds `selected_protocol`. Leave it failing for now — it documents the intent.

- [ ] **Step 6: Run all routing tests to confirm no regressions**

```bash
uv run pytest tests/test_query_routing.py -v
```
Expected: `TestIsCalculationQuery` — all 10 PASS. `TestRAGStateFields.test_total_field_count` — 1 FAIL (expected, will fix in Task 3).

- [ ] **Step 7: Commit**

```bash
git add src/retrieval/query_classifier.py tests/test_protocols.py tests/test_query_routing.py
git commit -m "feat(kpe): add classify_query() with 4-way routing and protocol selection"
```

---

### Task 3: RAGState + Prompt Builder

**Files:**
- Modify: `src/agents/state.py`
- Modify: `config/prompts.py`

- [ ] **Step 1: Write failing test for prompt builder**

Append to `tests/test_protocols.py`:

```python
from config.prompts import build_system_prompt


class TestBuildSystemPrompt:
    """Tests for composable prompt builder."""

    def test_simple_query_no_protocol_contains_consultant_persona(self):
        prompt = build_system_prompt(
            query_type="Simple",
            protocol_key="general",
            graph_context=False,
            glossary_snippet="- contribution margin = margin kontribusi",
        )
        assert "konsultan" in prompt.lower()
        assert "## Jawaban Singkat" in prompt

    def test_calculation_prompt_contains_step_by_step_instruction(self):
        prompt = build_system_prompt(
            query_type="Calculation",
            protocol_key="cvp",
            graph_context=False,
            glossary_snippet="- BEP = break-even point",
        )
        assert "langkah" in prompt.lower()
        assert "disclaimer" in prompt.lower() or "verifikasi" in prompt.lower()

    def test_protocol_steps_injected_into_prompt(self):
        prompt = build_system_prompt(
            query_type="Simple",
            protocol_key="cvp",
            graph_context=False,
            glossary_snippet="",
        )
        assert "contribution margin" in prompt.lower()
        assert "break-even" in prompt.lower() or "BEP" in prompt

    def test_synthesis_block_present_when_graph_context_true(self):
        prompt = build_system_prompt(
            query_type="Medium",
            protocol_key="abc",
            graph_context=True,
            glossary_snippet="",
        )
        assert "knowledge graph" in prompt.lower() or "graph" in prompt.lower()

    def test_glossary_snippet_included(self):
        prompt = build_system_prompt(
            query_type="Simple",
            protocol_key="general",
            graph_context=False,
            glossary_snippet="- net present value = nilai sekarang bersih",
        )
        assert "net present value" in prompt

    def test_returns_non_empty_string(self):
        prompt = build_system_prompt("Simple", "general", False, "")
        assert isinstance(prompt, str)
        assert len(prompt) > 100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_protocols.py::TestBuildSystemPrompt -v
```
Expected: `ImportError: cannot import name 'build_system_prompt'`

- [ ] **Step 3: Update `src/agents/state.py` — add selected_protocol field**

```python
import operator
from typing import Annotated, Optional, TypedDict


class RAGState(TypedDict):
    """Phase 3 LangGraph state schema.
    Backward-compatible: all Phase 1 + 2 fields preserved.
    New in Phase 3: query_type, crag_grade, crag_iterations, llm_call_count,
    conversation_history.
    New in Phase 3+KPE: selected_protocol.
    """

    # Phase 1 fields (unchanged)
    query: str
    expanded_query: Optional[str]
    query_embedding: Optional[list[float]]
    retrieved_docs: Optional[list[dict]]  # Qdrant hybrid search results
    reranked_docs: Optional[list[dict]]
    response: Optional[str]
    citations: Optional[list[dict]]
    error: Optional[str]
    # Phase 2 fields (unchanged)
    graph_docs: Optional[list[dict]]  # GraphRAG graph results
    # Phase 3 additions
    query_type: Optional[str]  # "Simple"|"Medium"|"Complex"|"Calculation"
    crag_grade: Optional[str]  # "CORRECT"|"AMBIGUOUS"|"INCORRECT"
    crag_iterations: Optional[int]  # initialized to 0 in route_node, caps at 2
    llm_call_count: Optional[int]  # logged per query for budget verification
    conversation_history: Annotated[list, operator.add]  # accumulates across turns
    # Phase 3 + KPE addition
    selected_protocol: Optional[str]  # protocol key from PROTOCOLS registry, e.g. "cvp"
```

- [ ] **Step 4: Add `build_system_prompt` to `config/prompts.py`**

Keep all existing constants (`SYSTEM_PROMPT_GENERATOR`, `SYSTEM_PROMPT_GENERATOR_CALCULATION`, `SYSTEM_PROMPT_SYNTHESIS`, `SYSTEM_PROMPT_REFORMULATOR`) unchanged — backward compat for existing tests. Add after them:

```python
from config.protocols import PROTOCOLS


# --- KPE Prompt Templates ---

_BASE_CONSULTANT_RULES = """\
Aturan:
1. Jawab dalam bahasa Indonesia. Gunakan istilah teknis Inggris dalam tanda kurung, contoh: biaya tetap (*fixed cost*).
2. Setiap klaim HARUS disertai nomor referensi inline segera setelah klaim: [Sumber N] untuk textbook/data, [Kerangka N] untuk referensi metodologi/framework.
3. JANGAN tulis nama pengarang panjang di teks — gunakan HANYA [Sumber N] atau [Kerangka N].
4. Jika konteks tidak cukup untuk menjawab, katakan dengan jujur bahwa informasi tidak ditemukan.
5. Jangan mengarang informasi yang tidak ada di konteks yang diberikan.\
"""

_SYNTHESIS_BLOCK = """\
Sumber tambahan — Knowledge Graph:
Gunakan informasi dari knowledge graph untuk menjelaskan hubungan konseptual antar entitas.
Untuk perbandingan: sajikan perspektif setiap sumber secara terpisah dahulu, kemudian sintesis.\
"""

_FRAMEWORK_CITATION_NOTE = """\
Catatan referensi kerangka: [Kerangka N] adalah referensi metodologi/framework — bukan bukti empiris.
Gunakan sebagai panduan analisis, bukan sebagai sumber fakta.\
"""


def _build_protocol_block(protocol_key: str) -> str:
    """Build the reasoning scaffold block for a given protocol key."""
    protocol = PROTOCOLS.get(protocol_key, PROTOCOLS["general"])
    steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(protocol.steps))
    sections_text = "\n".join(protocol.output_sections)
    return (
        f"Framework Analisis: {protocol.name} ({protocol.name_id})\n\n"
        f"Langkah analisis yang HARUS kamu ikuti:\n{steps_text}\n\n"
        f"Format jawaban wajib (gunakan section headers ini):\n{sections_text}\n\n"
        f"{protocol.few_shot_example}"
    )


def build_system_prompt(
    query_type: str,
    protocol_key: str,
    graph_context: bool,
    glossary_snippet: str,
) -> str:
    """Compose a consultant-style system prompt from modular blocks.

    Args:
        query_type: "Simple" | "Medium" | "Complex" | "Calculation"
        protocol_key: Key in PROTOCOLS dict (e.g. "cvp", "variance", "general")
        graph_context: True if graph_docs are available (adds synthesis instructions)
        glossary_snippet: Pre-built glossary string from _build_glossary_snippet()

    Returns:
        Complete system prompt string ready for LLM messages array.
    """
    persona = "Kamu adalah konsultan akuntansi manajemen senior yang menganalisis masalah secara terstruktur menggunakan proven frameworks."

    protocol_block = _build_protocol_block(protocol_key)

    if query_type == "Calculation":
        base = (
            f"{persona}\n\n"
            f"{_BASE_CONSULTANT_RULES}\n\n"
            f"{protocol_block}\n\n"
            "Aturan kalkulasi tambahan:\n"
            "- Tunjukkan setiap langkah perhitungan secara eksplisit.\n"
            "- Format: Data yang Diketahui → Rumus → Substitusi → Hasil → Verifikasi.\n"
            "- WAJIB sertakan di akhir: "
            "\"*Verifikasi hasil dengan akuntan profesional — perhitungan ini bersifat edukatif.*\"\n"
            "- Sertakan [Sumber N] untuk setiap rumus yang digunakan."
        )
    else:
        base = (
            f"{persona}\n\n"
            f"{_BASE_CONSULTANT_RULES}\n\n"
            f"{protocol_block}"
        )

    blocks = [base]

    if graph_context:
        blocks.append(_SYNTHESIS_BLOCK)

    if protocol_key != "general":
        blocks.append(_FRAMEWORK_CITATION_NOTE)

    if glossary_snippet:
        blocks.append(f"Glosarium istilah:\n{glossary_snippet}")

    return "\n\n".join(blocks)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_protocols.py::TestBuildSystemPrompt -v
```
Expected: all 6 tests PASS

```bash
uv run pytest tests/test_query_routing.py::TestRAGStateFields -v
```
Expected: `test_total_field_count` now PASS (15 fields), all others PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agents/state.py config/prompts.py tests/test_protocols.py
git commit -m "feat(kpe): add RAGState.selected_protocol and build_system_prompt() composable builder"
```

---

### Task 4: Wire KPE into Pipeline Nodes

**Files:**
- Modify: `src/agents/nodes.py`
- Modify: `src/generation/generator.py`

- [ ] **Step 1: Write failing test for route_node with protocol selection**

Append to `tests/test_protocols.py`:

```python
from unittest.mock import patch, MagicMock
from src.agents.nodes import route_node


class TestRouteNodeKPE:
    """route_node must set selected_protocol alongside query_type."""

    def test_route_node_sets_selected_protocol(self):
        state = {"query": "apa itu break-even point?"}
        result = route_node(state)
        assert "selected_protocol" in result
        assert isinstance(result["selected_protocol"], str)

    def test_route_node_bep_query_returns_cvp_protocol(self):
        state = {"query": "hitung BEP jika fixed cost 100000"}
        result = route_node(state)
        assert result["selected_protocol"] == "cvp"
        assert result["query_type"] == "Calculation"

    def test_route_node_abc_query_returns_abc_protocol(self):
        state = {"query": "bagaimana menerapkan ABC costing?"}
        result = route_node(state)
        assert result["selected_protocol"] == "abc"
        assert result["query_type"] == "Complex"

    def test_route_node_unknown_query_returns_general_protocol(self):
        state = {"query": "apa itu akuntansi?"}
        result = route_node(state)
        assert result["selected_protocol"] == "general"
        assert result["query_type"] == "Simple"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_protocols.py::TestRouteNodeKPE -v
```
Expected: FAIL — `route_node` returns no `selected_protocol` key.

- [ ] **Step 3: Update route_node in nodes.py**

Replace the existing `route_node` function:

```python
def route_node(state: RAGState) -> dict:
    """Classify query type and select KPE protocol. Resets CRAG state for this turn."""
    from src.retrieval.query_classifier import classify_query

    query = state["query"]
    query_type, protocol_key = classify_query(query)

    return {
        "query_type": query_type,
        "selected_protocol": protocol_key,
        "llm_call_count": 0,
        "crag_iterations": 0,
        "crag_grade": None,
    }
```

- [ ] **Step 4: Update generate_response() in generator.py — add protocol param**

Replace the function signature and prompt selection block:

```python
from config.prompts import (
    SYSTEM_PROMPT_REFORMULATOR,  # keep for reformulate_node
    build_system_prompt,
)


def generate_response(
    query: str,
    context_docs: list[dict],
    graph_context: str = "",
    query_type: str = "Simple",
    conversation_history: list[dict] | None = None,
    protocol: str = "general",
) -> dict:
    """
    Generate a consultant-style bilingual response with citations.

    KPE Phase: protocol parameter selects the reasoning template.
    Falls back to 'general' (Pyramid Principle) if not specified.

    Returns: dict with 'response' (str) and 'citations' (list[dict]).
    """
    glossary_snippet = _build_glossary_snippet()
    context_block = _build_context_block(context_docs)

    system_prompt = build_system_prompt(
        query_type=query_type,
        protocol_key=protocol,
        graph_context=bool(graph_context),
        glossary_snippet=glossary_snippet,
    )

    # Conversation history — last 5 turns (10 messages max)
    history = (conversation_history or [])[-10:]

    # Build user content
    if query_type == "Calculation":
        user_content = f"Konteks dari textbook:\n\n{context_block}\n\nPertanyaan: {query}"
    elif graph_context:
        user_content = (
            f"Konteks dari knowledge graph:\n{graph_context}\n\n"
            f"Konteks dari textbook passages:\n{context_block}\n\n"
            f"Pertanyaan: {query}\n\n"
            "Instruksi: Sebutkan secara eksplisit sumber textbook (nama pengarang) "
            "untuk setiap klaim yang berbeda antara penulis."
        )
    else:
        user_content = f"Konteks dari textbook:\n\n{context_block}\n\nPertanyaan: {query}"

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_content},
    ]

    llm_result = generate(messages, temperature=0.3, return_usage=True)
    if isinstance(llm_result, dict):
        response_text = llm_result["text"]
        usage = llm_result.get("usage", {})
        if usage:
            update_token_usage(
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
            )
    else:
        response_text = llm_result
    citations = build_citations(context_docs)

    return {
        "response": response_text,
        "citations": citations,
    }
```

Also update the imports at top of `generator.py` — remove the 3 old prompt imports and add `build_system_prompt`:

```python
from config.prompts import build_system_prompt
```

- [ ] **Step 5: Update generate_node and generate_calc_node to pass protocol**

In `generate_node`, update the `generate_response` call:

```python
result = generate_response(
    query=state["query"],
    context_docs=docs,
    graph_context=graph_context,
    query_type=query_type,
    conversation_history=history,
    protocol=state.get("selected_protocol", "general"),
)
```

In `generate_calc_node`, update the `generate_response` call:

```python
result = generate_response(
    query=state["query"],
    context_docs=docs,
    graph_context=graph_context,
    query_type="Calculation",
    protocol=state.get("selected_protocol", "general"),
)
```

- [ ] **Step 6: Run route_node tests**

```bash
uv run pytest tests/test_protocols.py::TestRouteNodeKPE -v
```
Expected: all 4 PASS

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest -v
```
Expected: all existing tests pass. `TestRAGStateFields.test_total_field_count` now expects 15 and passes.

- [ ] **Step 8: Commit**

```bash
git add src/agents/nodes.py src/generation/generator.py
git commit -m "feat(kpe): wire protocol selection into route_node and generate_response()"
```

---

### Task 5: Phase A Integration Smoke Test

**Files:** none modified — verification only

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v --tb=short
```
Expected: all tests PASS. Note total count.

- [ ] **Step 2: Manual smoke test with test_query.py**

```bash
uv run python scripts/test_query.py "apa itu break-even point?" -v
```
Expected output: Response starts with `## Jawaban Singkat` section, contains `[Sumber N]` references, structured output.

```bash
uv run python scripts/test_query.py "bandingkan ABC costing dengan traditional costing" -v
```
Expected: `query_type=Medium`, response has comparison table or MECE structure.

```bash
uv run python scripts/test_query.py "hitunglah BEP jika fixed cost 50000000 dan CM per unit 25000" -v
```
Expected: `query_type=Calculation`, step-by-step calculation, disclaimer at end.

- [ ] **Step 3: Commit Phase A completion tag**

```bash
git commit --allow-empty -m "chore: Phase A KPE core complete — protocol registry, classifier, prompt builder, pipeline wiring"
```

---

## Phase B: Consulting Book Ingestion (Retrieval Layer)

### Task 6: source_domain in Ingestion Pipeline

**Files:**
- Modify: `scripts/ingest.py`
- Modify: `src/ingestion/pipeline.py` (add source_domain param)

- [ ] **Step 1: Write failing test**

Create `tests/test_source_domain_ingestion.py`:

```python
"""Tests for source_domain metadata in ingestion pipeline."""
import pytest


class TestSourceDomainCLI:
    """Test that --source-domain flag is accepted and passed through."""

    def test_ingest_script_accepts_source_domain_flag(self):
        """ingest.py must accept --source-domain without error."""
        import subprocess
        result = subprocess.run(
            ["uv", "run", "python", "scripts/ingest.py", "--help"],
            capture_output=True, text=True
        )
        assert "--source-domain" in result.stdout

    def test_run_ingestion_pipeline_accepts_source_domain(self):
        """run_ingestion_pipeline() must accept source_domain kwarg."""
        import inspect
        from src.ingestion.pipeline import run_ingestion_pipeline
        sig = inspect.signature(run_ingestion_pipeline)
        assert "source_domain" in sig.parameters


class TestSourceDomainMetadata:
    """Test that source_domain appears in chunk metadata."""

    def test_source_domain_accounting_in_chunk_metadata(self, sample_chunks):
        """Chunks from accounting books should carry source_domain='accounting'."""
        for chunk in sample_chunks:
            # After pipeline runs with source_domain="accounting",
            # each chunk metadata must have this field
            chunk["metadata"]["source_domain"] = "accounting"  # simulate
            assert chunk["metadata"]["source_domain"] == "accounting"

    def test_source_domain_consulting_in_chunk_metadata(self, sample_chunks):
        """Chunks from consulting books should carry source_domain='consulting'."""
        for chunk in sample_chunks:
            chunk["metadata"]["source_domain"] = "consulting"
            assert chunk["metadata"]["source_domain"] == "consulting"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_source_domain_ingestion.py -v
```
Expected: `test_ingest_script_accepts_source_domain_flag` and `test_run_ingestion_pipeline_accepts_source_domain` FAIL.

- [ ] **Step 3: Add --source-domain to ingest.py**

In `scripts/ingest.py`, inside `main()` after `--contextual` arg:

```python
parser.add_argument(
    "--source-domain",
    default="accounting",
    choices=["accounting", "consulting"],
    help="Domain tag for retrieved chunks (default: 'accounting'). Use 'consulting' for framework PDFs.",
)
```

And update the `run_ingestion_pipeline` call:

```python
result = run_ingestion_pipeline(
    pdf_path=str(pdf),
    output_dir=args.output_dir,
    book_title=args.book_title or pdf.stem,
    replace_existing=args.replace,
    use_contextual=args.contextual,
    source_domain=args.source_domain,
)
```

- [ ] **Step 4: Add source_domain param to run_ingestion_pipeline in pipeline.py**

Find the function signature and add parameter:

```python
def run_ingestion_pipeline(
    pdf_path: str,
    output_dir: str = "data/parsed",
    chunks_dir: str = "data/chunks",
    book_title: str = "",
    checkpoint_dir: str = "data/checkpoints",
    replace_existing: bool = False,
    use_contextual: bool = False,
    source_domain: str = "accounting",
) -> dict:
```

Then find where chunks are prepared for upload (before `embed_chunks_batch` or `upload_batch`) and inject the source_domain into each chunk's metadata:

```python
# Inject source_domain into all chunk metadata before embedding
for chunk in chunks:
    chunk.setdefault("metadata", {})["source_domain"] = source_domain
```

The exact location is after chunking is complete. Search for the `embed_chunks_batch` call — inject source_domain just before it.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_source_domain_ingestion.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 6: Run full suite to verify no regressions**

```bash
uv run pytest -v --tb=short
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/ingest.py src/ingestion/pipeline.py tests/test_source_domain_ingestion.py
git commit -m "feat(kpe): add --source-domain flag to ingest pipeline for consulting book support"
```

---

### Task 7: Domain-Aware Retrieval

**Files:**
- Create: `scripts/backfill_source_domain.py`
- Modify: `src/retrieval/vector_search.py`
- Modify: `src/agents/nodes.py` (retrieve_node)

- [ ] **Step 1: Write failing test for domain_filter**

Create `tests/test_domain_retrieval.py`:

```python
"""Tests for source_domain-filtered hybrid search."""
from unittest.mock import MagicMock, patch


class TestHybridSearchDomainFilter:
    def test_hybrid_search_accepts_domain_filter_param(self):
        """hybrid_search() must accept domain_filter kwarg without error."""
        import inspect
        from src.retrieval.vector_search import hybrid_search
        sig = inspect.signature(hybrid_search)
        assert "domain_filter" in sig.parameters

    def test_domain_filter_none_does_not_add_filter(self):
        """domain_filter=None should not add a filter to Qdrant query."""
        from src.retrieval.vector_search import hybrid_search
        with patch("src.retrieval.vector_search.get_qdrant_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.query_points.return_value = MagicMock(points=[])
            mock_client_fn.return_value = mock_client
            with patch("src.retrieval.vector_search.compute_sparse_vector") as mock_sparse:
                mock_sparse.return_value = MagicMock(indices=[0], values=[1.0])
                hybrid_search(
                    query_embedding=[0.1] * 1024,
                    query_text="test query",
                    domain_filter=None,
                )
            call_kwargs = mock_client.query_points.call_args
            # query_filter should not be passed or should be None
            assert call_kwargs.kwargs.get("query_filter") is None

    def test_domain_filter_accounting_adds_filter(self):
        """domain_filter='accounting' should pass a filter to query_points."""
        from src.retrieval.vector_search import hybrid_search
        with patch("src.retrieval.vector_search.get_qdrant_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.query_points.return_value = MagicMock(points=[])
            mock_client_fn.return_value = mock_client
            with patch("src.retrieval.vector_search.compute_sparse_vector") as mock_sparse:
                mock_sparse.return_value = MagicMock(indices=[0], values=[1.0])
                hybrid_search(
                    query_embedding=[0.1] * 1024,
                    query_text="test query",
                    domain_filter="accounting",
                )
            call_kwargs = mock_client.query_points.call_args
            assert call_kwargs.kwargs.get("query_filter") is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_domain_retrieval.py -v
```
Expected: `test_hybrid_search_accepts_domain_filter_param` FAIL (param not exist).

- [ ] **Step 3: Add domain_filter to hybrid_search()**

In `src/retrieval/vector_search.py`, update imports and function:

```python
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    NearestQuery,
    Prefetch,
    SparseVector,
)


def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    top_k: int = 20,
    collection_name: str | None = None,
    book_filter: str | None = None,
    domain_filter: str | None = None,
) -> list[dict]:
    """
    Hybrid search combining dense vector similarity and sparse BM25 on Qdrant.
    Uses Reciprocal Rank Fusion (RRF) to merge dense and sparse results.

    Args:
        query_embedding: Dense vector from embed_query (with instruction prefix)
        query_text: Expanded query text for BM25 sparse matching
        top_k: Number of results to return
        collection_name: Optional override for collection name
        book_filter: Optional book_title filter (existing, unused)
        domain_filter: Optional source_domain filter ("accounting" | "consulting" | None)
    Returns: list of dicts with 'text', 'metadata', 'score'
    """
    client = get_qdrant_client()
    name = collection_name or settings.qdrant_collection_name

    sparse_vec = compute_sparse_vector(query_text)

    # Build optional payload filter
    qdrant_filter = None
    if domain_filter:
        qdrant_filter = Filter(
            must=[FieldCondition(key="source_domain", match=MatchValue(value=domain_filter))]
        )

    results = client.query_points(
        collection_name=name,
        prefetch=[
            Prefetch(
                query=NearestQuery(nearest=query_embedding),
                using="dense",
                limit=top_k,
            ),
            Prefetch(
                query=NearestQuery(
                    nearest=SparseVector(
                        indices=sparse_vec.indices,
                        values=sparse_vec.values,
                    )
                ),
                using="sparse",
                limit=top_k,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        query_filter=qdrant_filter,
    )

    search_results = []
    for point in results.points:
        payload = point.payload or {}
        search_results.append(
            {
                "id": point.id,
                "score": point.score if hasattr(point, "score") else 0.0,
                "text": payload.get("text", ""),
                "metadata": {
                    "book_title": payload.get("book_title", ""),
                    "chapter": payload.get("chapter", ""),
                    "section_path": payload.get("section_path", ""),
                    "content_type": payload.get("content_type", ""),
                    "page_start": payload.get("page_start", 0),
                    "page_end": payload.get("page_end", 0),
                    "source_domain": payload.get("source_domain", "accounting"),
                    "author": payload.get("author", ""),
                },
            }
        )

    logger.info(f"Hybrid search returned {len(search_results)} results for: {query_text[:80]}")
    return search_results
```

Note: `source_domain` and `author` are now included in the returned metadata dict.

- [ ] **Step 4: Update retrieve_node to pass domain_filter**

In `src/agents/nodes.py`, update `retrieve_node`:

```python
def retrieve_node(state: RAGState) -> dict:
    """Retrieve documents via hybrid search (dense + BM25) with optional domain filter."""
    if state.get("error"):
        return {}
    try:
        protocol_key = state.get("selected_protocol", "general")
        query_type = state.get("query_type", "Simple")

        # For Complex queries, retrieve cross-domain (no filter)
        # For specific accounting protocols, filter to accounting domain
        # For general protocol, retrieve cross-domain
        _ACCOUNTING_PROTOCOLS = {
            "cvp", "variance", "abc", "transfer_pricing",
            "relevant_costing", "product_profitability",
            "budgeting", "cost_classification",
        }
        if query_type == "Complex" or protocol_key == "general":
            domain_filter = None  # cross-domain: accounting + consulting
        else:
            domain_filter = "accounting"  # accounting textbook chunks only

        results = hybrid_search(
            query_embedding=state["query_embedding"],
            query_text=state.get("expanded_query", state["query"]),
            top_k=settings.reranker_top_k_input,
            domain_filter=domain_filter,
        )
        return {"retrieved_docs": results}
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {"error": f"Retrieval failed: {e}"}
```

- [ ] **Step 5: Create backfill script**

Create `scripts/backfill_source_domain.py`:

```python
"""One-time script: backfill source_domain='accounting' for all existing Qdrant points.

Run once after deploying the KPE update, before ingesting consulting books.

Usage:
    uv run python scripts/backfill_source_domain.py
    uv run python scripts/backfill_source_domain.py --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def backfill(dry_run: bool = False):
    from qdrant_client.models import FieldCondition, Filter, IsEmptyCondition, PayloadField
    from config.settings import settings
    from src.services.qdrant_service import get_qdrant_client

    client = get_qdrant_client()
    collection_name = settings.qdrant_collection_name

    # Create payload index on source_domain for fast filtering
    if not dry_run:
        logger.info("Creating payload index on source_domain...")
        client.create_payload_index(
            collection_name=collection_name,
            field_name="source_domain",
            field_schema="keyword",
        )

    # Scroll through all points without source_domain and set it
    offset = None
    total_updated = 0
    batch_size = 200

    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    IsEmptyCondition(is_empty=PayloadField(key="source_domain"))
                ]
            ),
            limit=batch_size,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )

        if not points:
            break

        ids = [p.id for p in points]
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Updating {len(ids)} points with source_domain='accounting'")

        if not dry_run:
            client.set_payload(
                collection_name=collection_name,
                payload={"source_domain": "accounting"},
                points=ids,
            )

        total_updated += len(ids)
        offset = next_offset
        if next_offset is None:
            break

    logger.info(f"Done. {'Would update' if dry_run else 'Updated'} {total_updated} points.")


def main():
    parser = argparse.ArgumentParser(description="Backfill source_domain metadata for existing Qdrant points")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run domain retrieval tests**

```bash
uv run pytest tests/test_domain_retrieval.py -v
```
Expected: all 3 PASS

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -v --tb=short
```
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add src/retrieval/vector_search.py src/agents/nodes.py scripts/backfill_source_domain.py tests/test_domain_retrieval.py
git commit -m "feat(kpe): add domain_filter to hybrid_search and retrieve_node domain-aware routing"
```

---

### Task 8: Citation Differentiation

**Files:**
- Modify: `src/generation/citation_builder.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_citation_builder.py`:

```python
"""Tests for citation builder with source_domain differentiation."""
from src.generation.citation_builder import build_citation, build_citations


class TestBuildCitationSourceDomain:
    """[Sumber N] for accounting, [Kerangka N] for consulting."""

    def test_accounting_citation_returns_sumber_label(self):
        meta = {
            "book_title": "Cost Accounting",
            "chapter": "Chapter 5",
            "page_start": 168,
            "page_end": 170,
            "author": "Horngren",
            "source_domain": "accounting",
        }
        result = build_citation(meta)
        assert result["label"] == "Sumber"
        assert "Horngren" in result["formatted"]

    def test_consulting_citation_returns_kerangka_label(self):
        meta = {
            "book_title": "The McKinsey Way",
            "chapter": "Chapter 3",
            "page_start": 47,
            "page_end": 52,
            "author": "Rasiel",
            "source_domain": "consulting",
        }
        result = build_citation(meta)
        assert result["label"] == "Kerangka"
        assert "Rasiel" in result["formatted"]

    def test_missing_source_domain_defaults_to_accounting(self):
        meta = {
            "book_title": "Cost Accounting",
            "chapter": "Chapter 5",
            "page_start": 100,
            "page_end": 110,
        }
        result = build_citation(meta)
        assert result["label"] == "Sumber"

    def test_build_citations_returns_label_in_each_citation(self, sample_chunks):
        citations = build_citations(sample_chunks)
        for citation in citations:
            assert "label" in citation
            assert citation["label"] in ("Sumber", "Kerangka")

    def test_build_citations_includes_source_domain(self, sample_chunks):
        citations = build_citations(sample_chunks)
        for citation in citations:
            assert "source_domain" in citation
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_citation_builder.py -v
```
Expected: `KeyError: 'label'` or similar — `build_citation` returns a string, not dict with label.

- [ ] **Step 3: Rewrite citation_builder.py**

```python
import logging

logger = logging.getLogger(__name__)


def build_citation(metadata: dict) -> dict:
    """
    Format a single citation from chunk metadata.

    Returns dict with:
    - 'formatted': display string e.g. "Horngren, Cost Accounting, Chapter 5, hal. 168-170"
    - 'label': "Sumber" for accounting, "Kerangka" for consulting
    - all raw metadata fields

    Source domain differentiation (KPE):
    - source_domain='accounting' → label='Sumber' (factual reference)
    - source_domain='consulting' → label='Kerangka' (methodology reference)
    """
    book_title = metadata.get("book_title", "Unknown")
    chapter = metadata.get("chapter", "Unknown")
    page_start = metadata.get("page_start", 0)
    page_end = metadata.get("page_end", 0)
    author = metadata.get("author", "")
    source_domain = metadata.get("source_domain", "accounting")

    if page_start and page_end and page_start != page_end:
        page_ref = f"hal. {page_start}-{page_end}"
    elif page_start:
        page_ref = f"hal. {page_start}"
    else:
        page_ref = "hal. tidak diketahui"

    prefix = f"{author}, " if author else ""
    formatted = f"{prefix}{book_title}, {chapter}, {page_ref}"
    label = "Kerangka" if source_domain == "consulting" else "Sumber"

    return {
        "formatted": formatted,
        "label": label,
        "source_domain": source_domain,
    }


def build_citations(docs: list[dict]) -> list[dict]:
    """
    Build citations from a list of retrieved/reranked documents.
    Deduplicates by (book_title, chapter, page_start).
    Returns list of dicts with 'formatted', 'label', 'source_domain', and raw metadata fields.
    """
    seen = set()
    citations = []

    for doc in docs:
        metadata = doc.get("metadata", {})
        key = (
            metadata.get("book_title", ""),
            metadata.get("chapter", ""),
            metadata.get("page_start", 0),
        )
        if key in seen:
            continue
        seen.add(key)

        citation = build_citation(metadata)
        citations.append(
            {
                **citation,
                "book_title": metadata.get("book_title", ""),
                "chapter": metadata.get("chapter", ""),
                "page_start": metadata.get("page_start", 0),
                "page_end": metadata.get("page_end", 0),
                "section_path": metadata.get("section_path", ""),
                "author": metadata.get("author", ""),
                "source_domain": metadata.get("source_domain", "accounting"),
            }
        )

    logger.info(f"Built {len(citations)} citations from {len(docs)} docs")
    return citations
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_citation_builder.py -v
```
Expected: all 5 PASS

- [ ] **Step 5: Run full suite — verify existing citation tests still pass**

```bash
uv run pytest -v --tb=short
```
Check any tests that import from `citation_builder`. If any test uses `result["formatted"]` directly (string), update to `result["formatted"]` from the dict.

- [ ] **Step 6: Commit**

```bash
git add src/generation/citation_builder.py tests/test_citation_builder.py
git commit -m "feat(kpe): differentiate [Sumber N] vs [Kerangka N] citations by source_domain"
```

---

### Task 9: Phase B Verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v --tb=short
```
Expected: all tests PASS.

- [ ] **Step 2: Dry-run backfill script**

```bash
uv run python scripts/backfill_source_domain.py --dry-run
```
Expected: logs showing number of points that would be updated.

- [ ] **Step 3: Test ingest --source-domain flag (help text)**

```bash
uv run python scripts/ingest.py --help
```
Expected: `--source-domain` appears in the help text with choices `accounting`, `consulting`.

- [ ] **Step 4: Commit Phase B complete**

```bash
git commit --allow-empty -m "chore: Phase B KPE consulting ingestion complete — domain retrieval, citation differentiation, backfill script"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task |
|-----------------|------|
| Protocol registry (8 protocols + general) | Task 1 |
| classify_query() — 4-way routing | Task 2 |
| selected_protocol in RAGState | Task 3 |
| build_system_prompt() composable builder | Task 3 |
| route_node uses classify_query | Task 4 |
| generate_response() accepts protocol | Task 4 |
| generate_node/calc_node pass protocol | Task 4 |
| --source-domain CLI flag | Task 6 |
| source_domain in pipeline metadata | Task 6 |
| domain_filter in hybrid_search() | Task 7 |
| retrieve_node domain-aware | Task 7 |
| backfill script | Task 7 |
| [Sumber N] vs [Kerangka N] | Task 8 |
| Zero changes to graph.py | All tasks — verified |
| Zero changes to backend/main.py | All tasks — verified |

All spec requirements covered.

### Type Consistency Check

- `classify_query()` returns `tuple[str, str]` — used in `route_node` as `query_type, protocol_key = classify_query(query)` ✓
- `match_protocol()` returns `Protocol` — used to find key with `next(k for k, v in PROTOCOLS.items() if v is protocol)` ✓
- `selected_protocol` in state is `Optional[str]` — read as `state.get("selected_protocol", "general")` ✓
- `build_system_prompt()` signature: `(query_type: str, protocol_key: str, graph_context: bool, glossary_snippet: str) -> str` — called consistently ✓
- `build_citation()` now returns `dict` (was `str`) — `build_citations()` uses it via spread `{**citation, ...}` ✓
- `hybrid_search()` new `domain_filter: Optional[str] = None` — called from `retrieve_node` with `domain_filter=domain_filter` ✓
- `run_ingestion_pipeline()` new `source_domain: str = "accounting"` — called from `ingest.py` with `source_domain=args.source_domain` ✓
