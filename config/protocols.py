"""Protocol Registry for KPE (Knowledge-Protocol Engine).

Defines ProtocolConfig dataclass and PROTOCOL_REGISTRY with 9 accounting protocols.
Each protocol provides keyword sets (Indonesian + English) for rule-based routing
and structured prompt steps for system prompt injection.

PROT-01: Protocol Registry — static data layer, zero LLM calls.
PROT-03: Structured steps injected into system prompt by compose_system_prompt() in Plan 02.

CRITICAL: This module must NOT import from config/glossary.py to avoid circular imports.
Glossary injection is handled in compose_system_prompt() in Plan 02.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolConfig:
    key: str                     # machine identifier, e.g. "cvp"
    display_name: str            # human-readable, e.g. "CVP Analysis"
    keywords_id: frozenset[str]  # Indonesian keywords (lowercase)
    keywords_en: frozenset[str]  # English keywords (lowercase)
    steps: str                   # multi-line prompt text injected into system prompt
    few_shot: str                # one-shot example; empty string if not applicable


PROTOCOL_REGISTRY: dict[str, ProtocolConfig] = {
    "variance_analysis": ProtocolConfig(
        key="variance_analysis",
        display_name="Variance Analysis",
        keywords_id=frozenset([
            "varians", "analisis varians", "varians harga", "varians kuantitas",
            "varians efisiensi", "varians volume", "varians anggaran", "varians overhead",
            "selisih", "menguntungkan", "tidak menguntungkan", "favorable", "unfavorable",
        ]),
        keywords_en=frozenset([
            "variance", "variance analysis", "material price variance",
            "material quantity variance", "labor rate variance",
            "labor efficiency variance", "overhead variance",
            "spending variance", "volume variance", "price variance", "quantity variance",
        ]),
        steps="""Gunakan framework Variance Analysis:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat mengenai jenis atau penyebab varians.]
## Analisis
[Hitung atau jelaskan varians: favorable (F) jika aktual < standar untuk biaya, unfavorable (U) sebaliknya. Tunjukkan rumus: Varians Harga = (Harga Aktual - Harga Standar) × Kuantitas Aktual. Sertakan referensi [Sumber N].]
## Rekomendasi
[Implikasi manajerial: tindakan korektif jika varians signifikan, atau konfirmasi efisiensi jika favorable.]""",
        few_shot="""Contoh output yang diharapkan:
## Jawaban Singkat
Varians harga bahan baku (*material price variance*) yang unfavorable menunjukkan biaya aktual melebihi standar [Sumber 1].
## Analisis
Varians Harga = (Rp 5.200 - Rp 5.000) × 1.000 kg = Rp 200.000 U [Sumber 2].
## Rekomendasi
Manajemen perlu meninjau ulang kontrak pemasok atau mencari alternatif bahan baku.""",
    ),

    "abc": ProtocolConfig(
        key="abc",
        display_name="Activity-Based Costing",
        keywords_id=frozenset([
            "activity-based costing", "kalkulasi biaya berdasarkan aktivitas",
            "pemicu biaya", "cost driver", "aktivitas", "cost pool", "kumpulan biaya",
            "resource driver", "pemicu aktivitas", "activity driver",
            "alokasi berbasis aktivitas",
        ]),
        keywords_en=frozenset([
            "activity based costing", "abc costing", "cost pool",
            "activity cost pool", "resource driver", "activity driver",
        ]),
        steps="""Gunakan framework Activity-Based Costing (ABC):
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat mengenai ABC atau cost driver yang relevan.]
## Analisis
[Jelaskan dua tahap ABC: (1) pembebanan biaya ke cost pool berdasarkan resource driver; (2) pembebanan cost pool ke produk/jasa berdasarkan activity driver. Sertakan rumus activity rate = Total Cost Pool / Total Activity jika relevan. Sertakan [Sumber N].]
## Rekomendasi
[Implikasi manajerial: produk mana yang menyerap biaya aktivitas paling tinggi dan mengapa ABC memberikan gambaran biaya lebih akurat daripada metode tradisional.]""",
        few_shot="",
    ),

    "transfer_pricing": ProtocolConfig(
        key="transfer_pricing",
        display_name="Transfer Pricing",
        keywords_id=frozenset([
            "harga transfer", "transfer pricing", "transfer price", "desentralisasi",
            "pusat laba", "pusat investasi", "harga antar divisi", "laba divisi",
            "penetapan harga transfer", "biaya penuh",
        ]),
        keywords_en=frozenset([
            "transfer pricing", "transfer price", "decentralization", "profit center",
            "investment center", "divisional pricing", "negotiated price",
            "cost-based transfer",
        ]),
        steps="""Gunakan framework Transfer Pricing:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat mengenai metode atau prinsip harga transfer.]
## Analisis
[Jelaskan metode yang relevan: harga pasar (market price), biaya penuh (full cost), biaya variabel plus markup, atau harga negosiasi. Evaluasi dampak terhadap motivasi divisi penjual dan pembeli. Sertakan [Sumber N].]
## Rekomendasi
[Implikasi manajerial: metode mana yang mendorong keselarasan kepentingan (goal congruence) antara divisi dan perusahaan secara keseluruhan.]""",
        few_shot="",
    ),

    "relevant_costing": ProtocolConfig(
        key="relevant_costing",
        display_name="Relevant Costing",
        keywords_id=frozenset([
            "biaya relevan", "relevant cost", "biaya diferensial", "differential cost",
            "keputusan make or buy", "make or buy", "keputusan khusus", "special order",
            "pesanan khusus", "avoidable cost", "biaya terhindarkan", "sunk cost",
            "biaya tertanam", "incremental", "inkremental", "tambahan", "eliminasi produk",
        ]),
        keywords_en=frozenset([
            "relevant cost", "differential cost", "make or buy", "special order",
            "avoidable cost", "sunk cost", "incremental cost",
            "product elimination", "dropping a segment",
        ]),
        steps="""Gunakan framework Relevant Costing:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat: identifikasi biaya atau pendapatan yang relevan vs tidak relevan untuk keputusan ini.]
## Analisis
[Pisahkan: (1) Relevant costs — biaya yang berbeda antar alternatif dan akan terjadi di masa depan; (2) Irrelevant costs — sunk cost dan biaya yang sama di semua alternatif. Tunjukkan analisis diferensial jika data tersedia. Sertakan [Sumber N].]
## Rekomendasi
[Rekomendasi keputusan berdasarkan analisis diferensial: pilih alternatif dengan total relevant cost terendah atau contribution margin tertinggi.]""",
        few_shot="",
    ),

    "product_profitability": ProtocolConfig(
        key="product_profitability",
        display_name="Product Profitability",
        keywords_id=frozenset([
            "profitabilitas produk", "laba produk", "margin per produk", "bauran produk",
            "product mix", "product line", "segmen", "pelaporan segmen", "lini produk",
            "kontribusi per produk", "pendapatan per produk", "analisis produk",
            "profitabilitas",
        ]),
        keywords_en=frozenset([
            "product profitability", "product mix", "product line analysis",
            "segment reporting", "segment margin", "contribution by product",
            "product performance",
        ]),
        steps="""Gunakan framework Product Profitability:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat mengenai profitabilitas atau bauran produk yang dianalisis.]
## Analisis
[Hitung atau jelaskan: contribution margin per produk, segment margin, atau return on sales per lini produk. Bandingkan antar produk/segmen jika relevan. Sertakan [Sumber N].]
## Rekomendasi
[Implikasi manajerial: produk atau segmen mana yang sebaiknya diprioritaskan, dikurangi, atau dieliminasi berdasarkan data profitabilitas.]""",
        few_shot="",
    ),

    "budgeting": ProtocolConfig(
        key="budgeting",
        display_name="Budgeting",
        keywords_id=frozenset([
            "anggaran", "budgeting", "budget", "master budget", "anggaran induk",
            "anggaran fleksibel", "flexible budget", "anggaran statis", "static budget",
            "anggaran penjualan", "anggaran produksi", "anggaran bahan baku",
            "anggaran kas", "cash budget", "penganggaran", "anggaran operasional",
            "variance anggaran", "budget variance",
        ]),
        keywords_en=frozenset([
            "budget", "budgeting", "master budget", "flexible budget", "static budget",
            "sales budget", "production budget", "cash budget", "capital budget",
            "operating budget", "budgetary control",
        ]),
        steps="""Gunakan framework Budgeting:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat mengenai jenis anggaran atau proses penganggaran yang ditanyakan.]
## Analisis
[Jelaskan komponen atau langkah penyusunan anggaran yang relevan. Untuk flexible budget: tunjukkan perbedaan dengan static budget pada berbagai level aktivitas. Sertakan [Sumber N].]
## Rekomendasi
[Implikasi manajerial: bagaimana anggaran ini digunakan untuk pengendalian biaya (budgetary control) dan evaluasi kinerja.]""",
        few_shot="",
    ),

    "cost_classification": ProtocolConfig(
        key="cost_classification",
        display_name="Cost Classification",
        keywords_id=frozenset([
            "klasifikasi biaya", "jenis biaya", "biaya tetap", "biaya variabel",
            "biaya semi-variabel", "mixed cost", "biaya campuran", "biaya langsung",
            "biaya tidak langsung", "biaya produk", "biaya periode", "product cost",
            "period cost", "biaya overhead pabrik", "manufacturing overhead",
            "perilaku biaya", "cost behavior", "step cost", "biaya bertahap",
            "prime cost", "conversion cost", "biaya utama", "biaya konversi",
        ]),
        keywords_en=frozenset([
            "cost classification", "cost behavior", "fixed cost", "variable cost",
            "mixed cost", "step cost", "product cost", "period cost", "direct cost",
            "indirect cost", "manufacturing overhead", "prime cost", "conversion cost",
        ]),
        steps="""Gunakan framework Cost Classification:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat: identifikasi jenis biaya dan karakteristik utamanya.]
## Analisis
[Jelaskan klasifikasi biaya berdasarkan perilaku (tetap/variabel/campuran), fungsi (produk/periode), atau keterlacakan (langsung/tidak langsung). Berikan contoh konkret dari konteks industri manufaktur. Sertakan [Sumber N].]
## Rekomendasi
[Implikasi manajerial: mengapa klasifikasi biaya ini penting untuk pengambilan keputusan atau penetapan harga.]""",
        few_shot="",
    ),

    "cvp": ProtocolConfig(
        key="cvp",
        display_name="CVP Analysis",
        keywords_id=frozenset([
            "cvp", "bep", "break-even", "break even", "titik impas",
            "margin kontribusi", "leverage operasi", "margin keamanan",
            "volume laba", "cost-volume-profit", "biaya-volume-laba",
            "contribution margin", "titik pulang pokok",
        ]),
        keywords_en=frozenset([
            "cost volume profit", "breakeven", "break even point",
            "contribution margin ratio", "margin of safety",
            "operating leverage", "cvp analysis",
        ]),
        steps="""Gunakan framework CVP Analysis:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat mengenai hubungan biaya-volume-laba atau titik impas.]
## Analisis
[Jelaskan hubungan biaya-volume-laba. Sertakan rumus BEP jika relevan: BEP (unit) = Fixed Cost / Contribution Margin per Unit; BEP (Rp) = Fixed Cost / Contribution Margin Ratio. Sertakan [Sumber N].]
## Rekomendasi
[Implikasi manajerial dari analisis CVP untuk pengambilan keputusan: target laba, margin of safety, atau dampak perubahan harga/volume.]""",
        few_shot="""Contoh output yang diharapkan:
## Jawaban Singkat
Break-even point (*titik impas*) adalah volume penjualan di mana total revenue sama dengan total cost [Sumber 1].
## Analisis
BEP (unit) = Fixed Cost / Contribution Margin per Unit = Rp 100.000.000 / Rp 30.000 = 3.333 unit [Sumber 2].
## Rekomendasi
Manajemen sebaiknya memantau margin of safety agar volume penjualan tidak mendekati titik impas.""",
    ),

    "general": ProtocolConfig(
        key="general",
        display_name="General",
        keywords_id=frozenset(),
        keywords_en=frozenset(),
        steps="""Jawab pertanyaan akuntansi secara terstruktur:
## Jawaban Singkat
[Jawab pertanyaan dalam 1-2 kalimat.]
## Analisis
[Jelaskan konsep, metode, atau prinsip yang relevan dengan referensi sumber [Sumber N].]
## Rekomendasi
[Implikasi praktis atau langkah selanjutnya jika relevan.]""",
        few_shot="",
    ),
}
