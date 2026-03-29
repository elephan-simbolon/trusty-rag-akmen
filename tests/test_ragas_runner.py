"""Tests untuk src/evaluation/ragas_runner.py."""

import json
import sys
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
    assert abs(summary["retrieval_accuracy"] - 0.5) < 0.01


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


def _build_ragas_sys_modules_patch():
    """Buat mock sys.modules entries untuk lazy imports ragas/openai/config.settings.

    run_ragas_evaluation() menggunakan `from X import Y` di dalam function body.
    Satu-satunya cara meng-intercept-nya tanpa menjalankan kode asli adalah dengan
    meng-inject modul dummy ke sys.modules SEBELUM fungsi dipanggil.
    """
    mock_settings_obj = MagicMock()
    mock_settings_obj.siliconflow_api_key.get_secret_value.return_value = "test-key"
    mock_settings_obj.siliconflow_base_url = "https://api.siliconflow.cn/v1"
    mock_settings_obj.llm_model = "Qwen/Qwen3-8B"

    # Mock modul openai
    mock_openai_mod = MagicMock()
    mock_openai_mod.AsyncOpenAI = MagicMock(return_value=MagicMock())

    # Mock modul ragas.llms
    mock_ragas_llms_mod = MagicMock()
    mock_ragas_llms_mod.llm_factory = MagicMock(return_value=MagicMock())

    # Mock modul ragas.embeddings
    mock_ragas_embeddings_mod = MagicMock()
    mock_ragas_embeddings_mod.OpenAIEmbeddings = MagicMock(return_value=MagicMock())

    # Mock modul config.settings
    mock_config_settings_mod = MagicMock()
    mock_config_settings_mod.settings = mock_settings_obj

    return {
        "openai": mock_openai_mod,
        "ragas": MagicMock(),
        "ragas.llms": mock_ragas_llms_mod,
        "ragas.embeddings": mock_ragas_embeddings_mod,
        "config.settings": mock_config_settings_mod,
    }


@pytest.mark.asyncio
async def test_run_ragas_evaluation_resume_skips_completed(tmp_path):
    """run_ragas_evaluation() skip queries yang sudah ada di partial_path saat resume=True."""
    from src.evaluation.ragas_runner import run_ragas_evaluation

    partial_path = tmp_path / "partial.json"
    output_path = tmp_path / "output.json"

    # EVAL-01 sudah selesai
    partial_data = [{
        "id": "EVAL-01", "query": "Q1", "difficulty": "Simple",
        "context_precision": 0.8, "context_recall": 0.9,
        "answer_faithfulness": 1.0, "answer_relevance": 0.85,
        "retrieval_pass": True,
    }]
    partial_path.write_text(json.dumps(partial_data), encoding="utf-8")

    queries = [
        {"id": "EVAL-01", "query": "Q1", "difficulty": "Simple", "expected_books": []},
        {"id": "EVAL-02", "query": "Q2", "difficulty": "Medium", "expected_books": []},
    ]

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "response": "test answer",
        "reranked_docs": [],
        "citations": [],
        "crag_grade": None,
        "query_type": "Simple",
    }

    sys_mods_patch = _build_ragas_sys_modules_patch()
    with patch.dict(sys.modules, sys_mods_patch), \
         patch("src.evaluation.ragas_runner._score_single_query", new=AsyncMock(return_value={
             "context_precision": 0.7, "context_recall": 0.8,
             "answer_faithfulness": 0.9, "answer_relevance": 0.85,
         })):
        result = await run_ragas_evaluation(
            queries=queries,
            golden_answers={},
            graph=mock_graph,
            output_path=output_path,
            partial_path=partial_path,
            resume=True,
            inter_query_delay=0,
            inter_judge_delay=0,
        )

    # EVAL-01 skip, EVAL-02 processed
    assert mock_graph.invoke.call_count == 1  # hanya EVAL-02
    assert len(result["results"]) == 2  # EVAL-01 dari partial + EVAL-02 baru


@pytest.mark.asyncio
async def test_run_ragas_evaluation_batch_size_limits_queries(tmp_path):
    """run_ragas_evaluation() hanya proses N queries jika batch_size diset."""
    from src.evaluation.ragas_runner import run_ragas_evaluation

    output_path = tmp_path / "output.json"

    queries = [
        {"id": f"EVAL-0{i}", "query": f"Q{i}", "difficulty": "Simple", "expected_books": []}
        for i in range(1, 6)
    ]

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "response": "answer",
        "reranked_docs": [],
        "citations": [],
        "crag_grade": None,
        "query_type": "Simple",
    }

    sys_mods_patch = _build_ragas_sys_modules_patch()
    with patch.dict(sys.modules, sys_mods_patch), \
         patch("src.evaluation.ragas_runner._score_single_query", new=AsyncMock(return_value={
             "context_precision": 0.8, "context_recall": 0.8,
             "answer_faithfulness": 0.8, "answer_relevance": 0.8,
         })):
        result = await run_ragas_evaluation(
            queries=queries,
            golden_answers={},
            graph=mock_graph,
            output_path=output_path,
            partial_path=tmp_path / "partial.json",
            batch_size=2,
            inter_query_delay=0,
            inter_judge_delay=0,
        )

    assert mock_graph.invoke.call_count == 2  # hanya 2 dari 5
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_run_ragas_evaluation_graph_failure_appends_error_entry(tmp_path):
    """Jika graph.invoke gagal, tetap append error entry dengan retrieval_pass=False."""
    from src.evaluation.ragas_runner import run_ragas_evaluation

    output_path = tmp_path / "output.json"
    queries = [{"id": "EVAL-01", "query": "Q1", "difficulty": "Simple", "expected_books": []}]

    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("graph crash")

    sys_mods_patch = _build_ragas_sys_modules_patch()
    with patch.dict(sys.modules, sys_mods_patch):
        result = await run_ragas_evaluation(
            queries=queries,
            golden_answers={},
            graph=mock_graph,
            output_path=output_path,
            partial_path=tmp_path / "partial.json",
            inter_query_delay=0,
            inter_judge_delay=0,
        )

    assert len(result["results"]) == 1
    assert result["results"][0]["retrieval_pass"] is False
    assert "error" in result["results"][0]
