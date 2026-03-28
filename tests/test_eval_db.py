"""Tests untuk backend/eval_db.py — SQLite CRUD eval_runs."""

import json
import pytest


@pytest.mark.asyncio
async def test_save_and_get_latest_eval_run(tmp_path, monkeypatch):
    """save_eval_run() menyimpan run, get_latest_eval_run() mengembalikannya."""
    import backend.eval_db as eval_db

    monkeypatch.setattr(eval_db, "DB_PATH", tmp_path / "eval_test.db")

    summary = {
        "context_precision": 0.82,
        "context_recall": 0.75,
        "answer_faithfulness": 0.91,
        "answer_relevance": 0.88,
        "retrieval_accuracy": 0.85,
        "total_queries": 2,
    }
    results = [
        {"id": "EVAL-01", "difficulty": "Simple", "context_precision": 0.8},
        {"id": "EVAL-02", "difficulty": "Medium", "context_precision": 0.7},
    ]

    run_id = await eval_db.save_eval_run(summary=summary, results=results)
    assert run_id.startswith("run-")

    latest = await eval_db.get_latest_eval_run()
    assert latest is not None
    assert latest["id"] == run_id
    assert latest["summary"]["context_precision"] == 0.82
    assert len(latest["results"]) == 2


@pytest.mark.asyncio
async def test_list_eval_runs(tmp_path, monkeypatch):
    """list_eval_runs() mengembalikan metadata tanpa results."""
    import backend.eval_db as eval_db

    monkeypatch.setattr(eval_db, "DB_PATH", tmp_path / "eval_test2.db")

    summary = {"context_precision": 0.8, "total_queries": 1}
    results = [{"id": "EVAL-01"}]

    await eval_db.save_eval_run(summary=summary, results=results)
    await eval_db.save_eval_run(summary=summary, results=results)

    runs = await eval_db.list_eval_runs()
    assert len(runs) == 2
    assert "results" not in runs[0]  # metadata only


@pytest.mark.asyncio
async def test_get_latest_eval_run_empty(tmp_path, monkeypatch):
    """get_latest_eval_run() mengembalikan None jika tabel kosong."""
    import backend.eval_db as eval_db

    monkeypatch.setattr(eval_db, "DB_PATH", tmp_path / "eval_empty.db")

    result = await eval_db.get_latest_eval_run()
    assert result is None
