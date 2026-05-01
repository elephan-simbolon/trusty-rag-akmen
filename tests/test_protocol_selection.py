"""Tests for Phase 6 protocol selection: PROT-01 and PROT-02.

select_protocol() must use zero LLM calls and correctly route to one of
9 accounting protocols (or General fallback) via keyword matching.

All tests are pure unit — no live services, no mocks needed.
"""

import pytest

from src.retrieval.query_classifier import is_calculation_query, select_protocol


class TestSelectProtocol:
    """PROT-02: Zero-LLM protocol selection via keyword matching.

    Each parametrized case verifies that the correct protocol_key is returned
    for a representative query from that accounting domain.
    """

    @pytest.mark.parametrize(
        "query,expected",
        [
            # CVP Analysis
            ("jelaskan break-even point", "cvp"),
            ("apa itu titik impas?", "cvp"),
            ("hitung margin kontribusi produk A", "cvp"),
            ("cost-volume-profit analysis dalam akuntansi manajemen", "cvp"),
            # Variance Analysis
            ("jelaskan varians harga bahan baku", "variance_analysis"),
            ("analisis varians efisiensi tenaga kerja langsung", "variance_analysis"),
            ("apa yang dimaksud favorable variance?", "variance_analysis"),
            ("hitung varians overhead pabrik", "variance_analysis"),
            # Activity-Based Costing
            ("jelaskan activity-based costing secara lengkap", "abc"),
            ("apa itu cost driver dalam sistem biaya aktivitas?", "abc"),
            ("bagaimana menentukan activity cost pool?", "abc"),
            # Transfer Pricing
            ("bagaimana harga transfer ditetapkan antar divisi?", "transfer_pricing"),
            ("metode transfer pricing untuk pusat laba", "transfer_pricing"),
            ("apa itu profit center dalam desentralisasi?", "transfer_pricing"),
            # Relevant Costing
            ("biaya relevan dalam keputusan make or buy", "relevant_costing"),
            ("apa yang dimaksud biaya diferensial untuk pesanan khusus?", "relevant_costing"),
            ("identifikasi sunk cost dalam keputusan eliminasi produk", "relevant_costing"),
            # Product Profitability
            ("analisis profitabilitas produk lini A vs B", "product_profitability"),
            ("bagaimana mengevaluasi profitabilitas segmen usaha?", "product_profitability"),
            ("pelaporan segmen untuk bauran produk perusahaan", "product_profitability"),
            # Budgeting
            ("bagaimana menyusun master budget perusahaan manufaktur?", "budgeting"),
            ("jelaskan perbedaan flexible budget dan static budget", "budgeting"),
            ("proses penganggaran kas (cash budget) bulanan", "budgeting"),
            # Cost Classification
            ("apa perbedaan biaya tetap dan biaya variabel?", "cost_classification"),
            ("jelaskan jenis-jenis biaya produksi: biaya langsung dan tidak langsung", "cost_classification"),
            ("apa yang dimaksud conversion cost dan prime cost?", "cost_classification"),
            # General fallback — no specific accounting protocol keywords
            ("apa itu akuntansi manajemen?", "general"),
            ("jelaskan konsep dasar akuntansi biaya secara umum", "general"),
            ("perbedaan akuntansi keuangan dan manajemen", "general"),
            # Edge cases
            ("", "general"),
        ],
    )
    def test_protocol_selection(self, query: str, expected: str) -> None:
        """Each query routes to the expected protocol_key (PROT-01, PROT-02)."""
        assert select_protocol(query) == expected, (
            f"Query {query!r} → {select_protocol(query)!r}, expected {expected!r}"
        )

    def test_word_boundary_guard_abc(self) -> None:
        """'kontrak ABC dengan vendor' must NOT match ABC costing protocol (Pitfall 6).

        'abc' is a 3-char abbreviation; without word-boundary guard it matches
        as a substring of unrelated words or as an acronym in unrelated contexts.
        """
        result = select_protocol("kontrak ABC dengan vendor lainnya")
        assert result != "abc", (
            f"False positive: 'kontrak ABC dengan vendor' should not match abc protocol, got {result!r}"
        )

    def test_variance_anggaran_routes_to_variance_not_budgeting(self) -> None:
        """'varians anggaran' must match variance_analysis, not budgeting.

        variance_analysis has higher priority than budgeting in _PROTOCOL_PRIORITY.
        'varians' (variance_analysis keyword) appears before 'anggaran' (budgeting keyword)
        in priority traversal.
        """
        result = select_protocol("jelaskan varians anggaran yang terjadi bulan ini")
        assert result == "variance_analysis", (
            f"Expected variance_analysis for 'varians anggaran' query, got {result!r}"
        )

    def test_calculation_query_still_gets_protocol(self) -> None:
        """Calculation queries receive a protocol_key — the two classifiers are independent.

        is_calculation_query and select_protocol both run against the same query string.
        A BEP calculation query should be is_calculation=True AND protocol_key='cvp'.

        Note: query uses 'titik impas' (cvp keyword) rather than 'fixed cost'
        (cost_classification keyword) to avoid shadowing by higher-priority protocol.
        """
        query = "hitung titik impas jika total biaya 100000 dan margin kontribusi 30000"
        assert is_calculation_query(query) is True, "Expected is_calculation_query=True"
        assert select_protocol(query) == "cvp", (
            f"Expected select_protocol='cvp' for BEP calculation query, got {select_protocol(query)!r}"
        )

    def test_cost_classification_before_cvp_for_generic_cost_terms(self) -> None:
        """'biaya tetap' routes to cost_classification, not cvp.

        cost_classification has higher priority than cvp in _PROTOCOL_PRIORITY.
        Generic cost type questions are caught by cost_classification first.
        """
        result = select_protocol("apa itu biaya tetap dalam perilaku biaya?")
        assert result == "cost_classification", (
            f"Expected cost_classification for 'biaya tetap' query, got {result!r}"
        )

    def test_all_protocol_keys_are_reachable(self) -> None:
        """Every protocol in PROTOCOL_REGISTRY (except general) is reachable via select_protocol.

        Verifies no protocol is shadowed entirely by a higher-priority protocol.
        """
        from config.protocols import PROTOCOL_REGISTRY

        reachable_via_specific_queries = {
            "variance_analysis": "analisis varians efisiensi",
            "abc": "sistem activity-based costing untuk cost driver",
            "transfer_pricing": "penetapan harga transfer antar divisi",
            "relevant_costing": "relevant cost untuk pesanan khusus",
            "product_profitability": "profitabilitas produk lini bisnis",
            "budgeting": "penyusunan anggaran kas perusahaan",
            "cost_classification": "klasifikasi biaya produk dan periode",
            "cvp": "titik impas break-even point",
        }
        for expected_key, query in reachable_via_specific_queries.items():
            result = select_protocol(query)
            assert result == expected_key, (
                f"Protocol {expected_key!r} unreachable: query {query!r} → {result!r}"
            )
