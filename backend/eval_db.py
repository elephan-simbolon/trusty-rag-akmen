"""SQLite-backed eval run storage — pola identik dengan history_db.py."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiosqlite

# Shared intentionally: eval_runs table co-habitats dengan history table di file yang sama.
DB_PATH = Path(__file__).parent / "history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS eval_runs (
  id TEXT PRIMARY KEY,
  run_at TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  results_json TEXT NOT NULL,
  model TEXT NOT NULL,
  query_count INTEGER NOT NULL DEFAULT 20
);
"""


async def _get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute(_CREATE_SQL)
    await db.commit()
    return db


async def save_eval_run(
    summary: dict,
    results: list[dict],
    model: str = "",
) -> str:
    """Simpan satu eval run. Return run_id."""
    db = await _get_db()
    try:
        run_id = "run-" + str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO eval_runs (id, run_at, summary_json, results_json, model, query_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                now,
                json.dumps(summary, ensure_ascii=False),
                json.dumps(results, ensure_ascii=False),
                model,
                summary.get("total_queries", len(results)),
            ),
        )
        await db.commit()
        return run_id
    finally:
        await db.close()


async def list_eval_runs() -> list[dict]:
    """List semua eval runs — metadata saja, tanpa results_json."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT id, run_at, summary_json, model, query_count "
            "FROM eval_runs ORDER BY run_at DESC"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "run_at": r["run_at"],
                "summary": json.loads(r["summary_json"]),
                "model": r["model"],
                "query_count": r["query_count"],
            }
            for r in rows
        ]
    finally:
        await db.close()


async def get_latest_eval_run() -> dict | None:
    """Ambil run terbaru lengkap (summary + results). None jika tabel kosong."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM eval_runs ORDER BY run_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "run_at": row["run_at"],
            "summary": json.loads(row["summary_json"]),
            "results": json.loads(row["results_json"]),
            "model": row["model"],
            "query_count": row["query_count"],
        }
    finally:
        await db.close()


async def get_eval_run(run_id: str) -> dict | None:
    """Ambil satu run by ID. None jika tidak ditemukan."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM eval_runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "run_at": row["run_at"],
            "summary": json.loads(row["summary_json"]),
            "results": json.loads(row["results_json"]),
            "model": row["model"],
            "query_count": row["query_count"],
        }
    finally:
        await db.close()
