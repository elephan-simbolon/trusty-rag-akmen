"""Tests for Phase 6 modular prompt composition: PROT-03 and PROT-04.

compose_system_prompt() must build prompts from atomic blocks in the correct order.
All tests are pure unit — no LLM calls, no live services.
"""

import pytest

from config.prompts import compose_system_prompt

_DUMMY_GLOSSARY = "fixed cost = biaya tetap\nvariable cost = biaya variabel"


class TestComposeSystemPrompt:
    """PROT-04: Modular prompt composition replaces 3 static hardcoded prompts."""

    def test_output_contains_persona_block(self) -> None:
        """Every composed prompt must begin with the persona block."""
        result = compose_system_prompt("general", _DUMMY_GLOSSARY)
        assert "asisten akuntansi biaya dan manajemen" in result

    def test_output_contains_rules_block(self) -> None:
        """Every composed prompt must contain core citation rules."""
        result = compose_system_prompt("general", _DUMMY_GLOSSARY)
        assert "[Sumber N]" in result
        assert "Jawab dalam bahasa Indonesia" in result

    def test_output_contains_protocol_steps_for_cvp(self) -> None:
        """CVP protocol steps must appear in the composed prompt (PROT-03)."""
        result = compose_system_prompt("cvp", _DUMMY_GLOSSARY)
        assert "## Jawaban Singkat" in result
        assert "## Analisis" in result
        assert "## Rekomendasi" in result
        assert "CVP Analysis" in result or "cost-volume-profit" in result.lower() or "titik impas" in result.lower()

    def test_output_contains_protocol_steps_for_variance_analysis(self) -> None:
        """Variance Analysis protocol steps must appear (PROT-03)."""
        result = compose_system_prompt("variance_analysis", _DUMMY_GLOSSARY)
        assert "## Jawaban Singkat" in result
        assert "Variance Analysis" in result or "varians" in result.lower()

    def test_all_protocols_produce_section_headers(self) -> None:
        """All 9 protocols must produce ## Jawaban Singkat, ## Analisis, ## Rekomendasi (PROT-03)."""
        from config.protocols import PROTOCOL_REGISTRY

        for key in PROTOCOL_REGISTRY:
            result = compose_system_prompt(key, _DUMMY_GLOSSARY)
            assert "## Jawaban Singkat" in result, f"{key}: missing ## Jawaban Singkat"
            assert "## Analisis" in result, f"{key}: missing ## Analisis"
            assert "## Rekomendasi" in result, f"{key}: missing ## Rekomendasi"

    def test_glossary_appears_in_output(self) -> None:
        """Glossary snippet must appear at the end of the composed prompt."""
        result = compose_system_prompt("general", _DUMMY_GLOSSARY)
        assert "Glosarium istilah:" in result
        assert "fixed cost = biaya tetap" in result

    def test_calculation_block_is_additive(self) -> None:
        """is_calculation=True adds calculation rules WITHOUT removing protocol steps (Pitfall 2)."""
        result = compose_system_prompt("cvp", _DUMMY_GLOSSARY, is_calculation=True)
        # Calculation block present
        assert "Verifikasi hasil dengan sumber resmi" in result
        assert "rumus \u2192 substitusi \u2192 hasil" in result
        # Protocol steps still present (not overwritten)
        assert "## Jawaban Singkat" in result
        assert "## Rekomendasi" in result

    def test_calculation_block_absent_when_not_calculation(self) -> None:
        """is_calculation=False must not include the calculation disclaimer."""
        result = compose_system_prompt("cvp", _DUMMY_GLOSSARY, is_calculation=False)
        assert "Verifikasi hasil dengan sumber resmi" not in result

    def test_synthesis_block_added_when_has_graph_context(self) -> None:
        """has_graph_context=True must add synthesis rules for relational queries."""
        result = compose_system_prompt("variance_analysis", _DUMMY_GLOSSARY, has_graph_context=True)
        assert "knowledge graph" in result
        assert "query relasional" in result or "query perbandingan" in result

    def test_synthesis_block_absent_when_no_graph_context(self) -> None:
        """has_graph_context=False must not include synthesis rules."""
        result = compose_system_prompt("variance_analysis", _DUMMY_GLOSSARY, has_graph_context=False)
        assert "knowledge graph" not in result

    def test_unknown_protocol_key_falls_back_to_general(self) -> None:
        """Unknown protocol_key must silently fall back to 'general' — no KeyError."""
        result = compose_system_prompt("nonexistent_protocol_xyz", _DUMMY_GLOSSARY)
        assert "## Jawaban Singkat" in result
        assert "## Analisis" in result

    def test_block_order_is_correct(self) -> None:
        """Block order: persona → rules → protocol_steps → glossary (PROT-04).

        Verifies relative position of known anchors within the composed string.
        """
        result = compose_system_prompt("general", _DUMMY_GLOSSARY)
        pos_persona = result.index("asisten akuntansi biaya")
        pos_rules = result.index("[Sumber N]")
        pos_steps = result.index("## Jawaban Singkat")
        pos_glossary = result.index("Glosarium istilah:")
        assert pos_persona < pos_rules, "Persona must come before rules"
        assert pos_rules < pos_steps, "Rules must come before protocol steps"
        assert pos_steps < pos_glossary, "Protocol steps must come before glossary"

    def test_calculation_block_before_protocol_steps_when_is_calculation(self) -> None:
        """Calculation block must appear before protocol steps in the output."""
        result = compose_system_prompt("cvp", _DUMMY_GLOSSARY, is_calculation=True)
        pos_calc = result.index("Verifikasi hasil dengan sumber resmi")
        pos_steps = result.index("## Jawaban Singkat")
        assert pos_calc < pos_steps, "Calculation block must precede protocol steps"

    def test_cvp_few_shot_present_in_output(self) -> None:
        """CVP protocol has a non-empty few_shot example that must appear in the output."""
        result = compose_system_prompt("cvp", _DUMMY_GLOSSARY)
        # CVP few_shot contains this specific example line
        assert "BEP (unit) = Fixed Cost / Contribution Margin per Unit" in result

    def test_general_few_shot_absent_from_output(self) -> None:
        """General protocol has empty few_shot — no example block appended."""
        result = compose_system_prompt("general", _DUMMY_GLOSSARY)
        # BEP example text from CVP few_shot must NOT appear in general output
        assert "BEP (unit) = Fixed Cost / Contribution Margin per Unit" not in result

    def test_deprecated_constants_still_importable(self) -> None:
        """SYSTEM_PROMPT_GENERATOR, SYSTEM_PROMPT_GENERATOR_CALCULATION, SYSTEM_PROMPT_SYNTHESIS
        must remain importable (Pitfall 4 — backward compatibility)."""
        from config.prompts import (  # noqa: F401
            SYSTEM_PROMPT_GENERATOR,
            SYSTEM_PROMPT_GENERATOR_CALCULATION,
            SYSTEM_PROMPT_SYNTHESIS,
        )
        from config.prompts import SYSTEM_PROMPT_GENERATOR as spg
        assert isinstance(spg, str), "SYSTEM_PROMPT_GENERATOR must be a string"
