"""Tests untuk src/evaluation/golden_generator.py."""

import json
import pytest
from pathlib import Path


def test_load_golden_answers_returns_dict(tmp_path):
    """load_golden_answers() mengembalikan dict dari file JSON yang ada."""
    from src.evaluation.golden_generator import load_golden_answers

    golden_file = tmp_path / "golden.json"
    data = {
        "generated_at": "2026-03-29T00:00:00Z",
        "model": "test-model",
        "answers": {
            "EVAL-01": {
                "golden_answer": "BEP adalah titik impas.",
                "source_docs": ["Cost Accounting/Chapter 3"],
            }
        },
    }
    golden_file.write_text(json.dumps(data), encoding="utf-8")

    result = load_golden_answers(golden_file)
    assert result["EVAL-01"]["golden_answer"] == "BEP adalah titik impas."


def test_load_golden_answers_returns_empty_if_missing(tmp_path):
    """load_golden_answers() mengembalikan {} jika file tidak ada."""
    from src.evaluation.golden_generator import load_golden_answers

    result = load_golden_answers(tmp_path / "nonexistent.json")
    assert result == {}


def test_build_golden_prompt_contains_query():
    """_build_golden_prompt() menyertakan query dalam prompt yang dihasilkan."""
    from src.evaluation.golden_generator import _build_golden_prompt

    context_block = "[Sumber 1: Cost Accounting]\nBEP adalah titik impas."
    query = "Apa itu break-even point?"
    messages = _build_golden_prompt(query=query, context_block=context_block)

    assert any(query in m["content"] for m in messages)
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
