"""Tests untuk src/evaluation/ragas_runner.py."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def test_aggregate_metrics_overall():
    """_aggregate_metrics() menghitung rata-rata 4 metrics dari per-query results."""
    from src.evaluation.ragas_runner import _aggregate_metrics

    results = [
        {"id": "EVAL-01", "difficulty": "Simple",
         "context_precision": 0.8, "context_recall": 0.9,
         "answer_faithfulness": 1.0, "answer_relevance": 0.85,
         "retrieval_pass": True},
        {"id": "EVAL-02", "difficulty": "Simple",
         "context_precision": 0.6, "context_recall": 0.7,
         "answer_faithfulness": 0.8, "answer_relevance": 0.75,
         "retrieval_pass": False},
    ]
    summary = _aggregate_metrics(results)

    assert abs(summary["context_precision"] - 0.7) < 0.01
    assert abs(summary["context_recall"] - 0.8) < 0.01
    assert abs(summary["answer_faithfulness"] - 0.9) < 0.01
    assert abs(summary["answer_relevance"] - 0.8) < 0.01
    assert summary["total_queries"] == 2


def test_aggregate_metrics_per_difficulty():
    """_aggregate_metrics() mengisi per_difficulty breakdown."""
    from src.evaluation.ragas_runner import _aggregate_metrics

    results = [
        {"id": "EVAL-01", "difficulty": "Simple",
         "context_precision": 1.0, "context_recall": 1.0,
         "answer_faithfulness": 1.0, "answer_relevance": 1.0,
         "retrieval_pass": True},
        {"id": "EVAL-04", "difficulty": "Calculation",
         "context_precision": 0.5, "context_recall": 0.5,
         "answer_faithfulness": 0.5, "answer_relevance": 0.5,
         "retrieval_pass": True},
    ]
    summary = _aggregate_metrics(results)

    assert "per_difficulty" in summary
    assert "Simple" in summary["per_difficulty"]
    assert "Calculation" in summary["per_difficulty"]
    assert summary["per_difficulty"]["Simple"]["context_precision"] == 1.0


def test_load_partial_results_empty(tmp_path):
    """load_partial_results() mengembalikan [] jika file tidak ada."""
    from src.evaluation.ragas_runner import load_partial_results

    result = load_partial_results(tmp_path / "nonexistent.json")
    assert result == []


def test_load_partial_results_existing(tmp_path):
    """load_partial_results() mengembalikan list dari file yang ada."""
    from src.evaluation.ragas_runner import load_partial_results

    partial_file = tmp_path / "partial.json"
    data = [{"id": "EVAL-01", "context_precision": 0.8}]
    partial_file.write_text(json.dumps(data), encoding="utf-8")

    result = load_partial_results(partial_file)
    assert len(result) == 1
    assert result[0]["id"] == "EVAL-01"
