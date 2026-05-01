"""Tests untuk qrels_generator dan ranking_metrics."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests: qrels_generator
# ---------------------------------------------------------------------------


def test_judge_chunk_relevance_returns_1_for_relevant():
    """_judge_chunk_relevance() mengembalikan 1 jika LLM menjawab '1'."""
    from src.evaluation.qrels_generator import _judge_chunk_relevance

    with patch("src.evaluation.qrels_generator.llm_generate", return_value="1"):
        result = _judge_chunk_relevance(query="Apa itu BEP?", chunk_text="BEP adalah titik impas.")
    assert result == 1


def test_judge_chunk_relevance_returns_0_for_irrelevant():
    """_judge_chunk_relevance() mengembalikan 0 jika LLM menjawab '0'."""
    from src.evaluation.qrels_generator import _judge_chunk_relevance

    with patch("src.evaluation.qrels_generator.llm_generate", return_value="0"):
        result = _judge_chunk_relevance(query="Apa itu BEP?", chunk_text="Bab ini membahas sejarah.")
    assert result == 0


def test_judge_chunk_relevance_returns_0_on_unexpected_output():
    """_judge_chunk_relevance() mengembalikan 0 jika LLM output tidak dikenali."""
    from src.evaluation.qrels_generator import _judge_chunk_relevance

    with patch("src.evaluation.qrels_generator.llm_generate", return_value="Ya, relevan"):
        result = _judge_chunk_relevance(query="Apa itu BEP?", chunk_text="Teks apapun.")
    assert result == 0


def test_load_qrels_returns_dict(tmp_path):
    """load_qrels() mengembalikan dict qrels dari file JSON."""
    from src.evaluation.qrels_generator import load_qrels

    qrels_file = tmp_path / "qrels.json"
    data = {
        "generated_at": "2026-04-04T00:00:00Z",
        "model": "test",
        "qrels": {"EVAL-01": {"123": 1, "456": 0}},
    }
    qrels_file.write_text(json.dumps(data), encoding="utf-8")

    result = load_qrels(qrels_file)
    assert result["EVAL-01"]["123"] == 1
    assert result["EVAL-01"]["456"] == 0


def test_load_qrels_returns_empty_if_missing(tmp_path):
    """load_qrels() mengembalikan {} jika file tidak ada."""
    from src.evaluation.qrels_generator import load_qrels

    result = load_qrels(tmp_path / "nonexistent.json")
    assert result == {}


# ---------------------------------------------------------------------------
# Tests: ranking_metrics
# ---------------------------------------------------------------------------


@pytest.mark.timeout(120)
def test_compute_ranking_metrics_basic():
    """compute_ranking_metrics() mengembalikan dict dengan 4 metrik float."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    # qrels: EVAL-01 → doc "1" relevan, doc "2" tidak
    qrels = {"EVAL-01": {"1": 1, "2": 0, "3": 1}}

    # run_docs: retrieved_docs per query; doc "1" di posisi pertama (score tertinggi)
    run_docs = {
        "EVAL-01": [
            {"id": 1, "score": 0.9},  # doc "1", relevan, rank 1
            {"id": 2, "score": 0.7},  # doc "2", tidak relevan, rank 2
            {"id": 3, "score": 0.5},  # doc "3", relevan, rank 3
        ]
    }

    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    assert "ndcg@5" in result
    assert "mrr@5" in result
    assert "recall@5" in result
    assert "recall@10" in result
    # Semua metrik harus float dalam range [0, 1]
    for key, val in result.items():
        assert isinstance(val, float), f"{key} bukan float: {val}"
        assert 0.0 <= val <= 1.0, f"{key}={val} di luar range [0,1]"


@pytest.mark.timeout(120)
def test_compute_ranking_metrics_perfect_ranking():
    """Jika doc relevan ada di rank 1, MRR@5 harus 1.0 dan NDCG@5 tinggi."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    qrels = {"EVAL-01": {"10": 1}}
    run_docs = {
        "EVAL-01": [
            {"id": 10, "score": 0.99},  # relevan, rank 1
            {"id": 20, "score": 0.50},
        ]
    }

    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    assert result["mrr@5"] == 1.0
    assert result["ndcg@5"] == 1.0
    assert result["recall@5"] == 1.0


@pytest.mark.timeout(120)
def test_compute_ranking_metrics_no_relevant_docs():
    """Jika tidak ada doc relevan di qrels, semua metrik harus 0.0."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    qrels = {"EVAL-01": {"10": 0, "20": 0}}
    run_docs = {
        "EVAL-01": [
            {"id": 10, "score": 0.9},
            {"id": 20, "score": 0.5},
        ]
    }

    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)

    assert result["ndcg@5"] == 0.0
    assert result["mrr@5"] == 0.0
    assert result["recall@5"] == 0.0
    assert result["recall@10"] == 0.0


@pytest.mark.timeout(120)
def test_compute_ranking_metrics_query_not_in_run():
    """Query yang ada di qrels tapi tidak di run_docs di-skip tanpa error."""
    from src.evaluation.ranking_metrics import compute_ranking_metrics

    qrels = {"EVAL-01": {"1": 1}, "EVAL-02": {"2": 1}}
    run_docs = {
        "EVAL-01": [{"id": 1, "score": 0.9}],
        # EVAL-02 tidak ada di run_docs
    }

    # Tidak boleh raise exception
    result = compute_ranking_metrics(qrels=qrels, run_docs=run_docs)
    assert "ndcg@5" in result
