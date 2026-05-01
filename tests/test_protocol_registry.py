"""Tests for config/protocols.py — PROT-01: Protocol Registry.

These tests verify that PROTOCOL_REGISTRY has all required keys,
ProtocolConfig is immutable, and all protocols have the required section headers.
"""

import pytest
from config.protocols import PROTOCOL_REGISTRY, ProtocolConfig


class TestProtocolConfig:
    """ProtocolConfig dataclass constraints."""

    def test_protocol_config_is_frozen(self):
        """ProtocolConfig must be frozen (immutable)."""
        proto = PROTOCOL_REGISTRY["general"]
        with pytest.raises((AttributeError, TypeError)):
            proto.key = "modified"  # type: ignore[misc]

    def test_protocol_config_fields(self):
        """ProtocolConfig must have required fields."""
        proto = PROTOCOL_REGISTRY["cvp"]
        assert hasattr(proto, "key")
        assert hasattr(proto, "display_name")
        assert hasattr(proto, "keywords_id")
        assert hasattr(proto, "keywords_en")
        assert hasattr(proto, "steps")
        assert hasattr(proto, "few_shot")


class TestProtocolRegistryKeys:
    """PROTOCOL_REGISTRY must have exactly 9 keys."""

    EXPECTED_KEYS = {
        "variance_analysis",
        "abc",
        "transfer_pricing",
        "relevant_costing",
        "product_profitability",
        "budgeting",
        "cost_classification",
        "cvp",
        "general",
    }

    def test_exact_keys(self):
        """PROTOCOL_REGISTRY must have exactly the 9 expected keys."""
        assert set(PROTOCOL_REGISTRY.keys()) == self.EXPECTED_KEYS

    def test_no_extra_keys(self):
        """No extra keys beyond the 9 expected."""
        assert len(PROTOCOL_REGISTRY) == 9

    def test_all_values_are_protocol_config(self):
        """All values must be ProtocolConfig instances."""
        for key, proto in PROTOCOL_REGISTRY.items():
            assert isinstance(proto, ProtocolConfig), f"{key} is not ProtocolConfig"


class TestGeneralProtocol:
    """General protocol must have empty keyword frozensets."""

    def test_general_keywords_id_empty(self):
        """general.keywords_id must be empty frozenset."""
        assert PROTOCOL_REGISTRY["general"].keywords_id == frozenset()

    def test_general_keywords_en_empty(self):
        """general.keywords_en must be empty frozenset."""
        assert PROTOCOL_REGISTRY["general"].keywords_en == frozenset()

    def test_general_key_field(self):
        """general.key must equal 'general'."""
        assert PROTOCOL_REGISTRY["general"].key == "general"


class TestProtocolSectionHeaders:
    """All protocols must contain required section headers in steps."""

    @pytest.mark.parametrize("key", [
        "variance_analysis", "abc", "transfer_pricing", "relevant_costing",
        "product_profitability", "budgeting", "cost_classification", "cvp", "general",
    ])
    def test_has_jawaban_singkat(self, key):
        """steps must contain ## Jawaban Singkat."""
        assert "## Jawaban Singkat" in PROTOCOL_REGISTRY[key].steps, \
            f"{key} missing ## Jawaban Singkat"

    @pytest.mark.parametrize("key", [
        "variance_analysis", "abc", "transfer_pricing", "relevant_costing",
        "product_profitability", "budgeting", "cost_classification", "cvp", "general",
    ])
    def test_has_analisis(self, key):
        """steps must contain ## Analisis."""
        assert "## Analisis" in PROTOCOL_REGISTRY[key].steps, \
            f"{key} missing ## Analisis"

    @pytest.mark.parametrize("key", [
        "variance_analysis", "abc", "transfer_pricing", "relevant_costing",
        "product_profitability", "budgeting", "cost_classification", "cvp", "general",
    ])
    def test_has_rekomendasi(self, key):
        """steps must contain ## Rekomendasi."""
        assert "## Rekomendasi" in PROTOCOL_REGISTRY[key].steps, \
            f"{key} missing ## Rekomendasi"


class TestNoGlossaryImport:
    """config/protocols.py must NOT import from config/glossary.py."""

    def test_no_glossary_import(self):
        """protocols.py source must not have an import statement referencing glossary."""
        import inspect
        import config.protocols as mod
        source = inspect.getsource(mod)
        # Check no actual import line references glossary (comments are OK)
        import_lines = [
            line.strip() for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        for line in import_lines:
            assert "glossary" not in line, \
                f"config/protocols.py must not import from config/glossary.py, found: {line}"


class TestKeywordFrozensets:
    """All non-general protocols must have non-empty keyword frozensets."""

    NON_GENERAL_KEYS = [
        "variance_analysis", "abc", "transfer_pricing", "relevant_costing",
        "product_profitability", "budgeting", "cost_classification", "cvp",
    ]

    @pytest.mark.parametrize("key", NON_GENERAL_KEYS)
    def test_keywords_id_non_empty(self, key):
        """keywords_id must be non-empty for non-general protocols."""
        assert len(PROTOCOL_REGISTRY[key].keywords_id) > 0, \
            f"{key}.keywords_id is empty"

    @pytest.mark.parametrize("key", NON_GENERAL_KEYS)
    def test_keywords_en_non_empty(self, key):
        """keywords_en must be non-empty for non-general protocols."""
        assert len(PROTOCOL_REGISTRY[key].keywords_en) > 0, \
            f"{key}.keywords_en is empty"
