"""SQLite-backed chat history for single-user local deployment."""

import json
import aiosqlite
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS history (
  id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  citations TEXT NOT NULL DEFAULT '[]',
  query_type TEXT,
  crag_grade TEXT,
  feedback INTEGER,
  created_at TEXT NOT NULL
);
"""


async def _get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute(_CREATE_SQL)
    await db.commit()
    return db


async def save_history(question: str, answer: str, citations: list, query_type: str | None, crag_grade: str | None) -> str:
    db = await _get_db()
    try:
        hid = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO history (id, question, answer, citations, query_type, crag_grade, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hid, question, answer, json.dumps(citations, ensure_ascii=False), query_type, crag_grade, now),
        )
        await db.commit()
        return hid
    finally:
        await db.close()


async def list_history(page: int = 1, per_page: int = 20) -> dict:
    db = await _get_db()
    try:
        offset = (page - 1) * per_page
        cursor = await db.execute("SELECT COUNT(*) FROM history")
        total = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT id, question, answer, citations, feedback, created_at FROM history ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        )
        rows = await cursor.fetchall()
        data = []
        for r in rows:
            data.append({
                "id": r["id"],
                "question": r["question"],
                "answer_preview": r["answer"][:100],
                "citations_count": len(json.loads(r["citations"])),
                "feedback": r["feedback"],
                "created_at": r["created_at"],
            })
        return {"data": data, "total": total, "page": page, "per_page": per_page}
    finally:
        await db.close()


async def get_history_detail(history_id: str) -> dict | None:
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM history WHERE id = ?", (history_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "answer_preview": row["answer"][:100],
            "citations": json.loads(row["citations"]),
            "citations_count": len(json.loads(row["citations"])),
            "query_type": row["query_type"],
            "crag_grade": row["crag_grade"],
            "feedback": row["feedback"],
            "created_at": row["created_at"],
        }
    finally:
        await db.close()


async def delete_history(history_id: str) -> bool:
    db = await _get_db()
    try:
        cursor = await db.execute("DELETE FROM history WHERE id = ?", (history_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_feedback(history_id: str, feedback: int) -> bool:
    db = await _get_db()
    try:
        cursor = await db.execute("UPDATE history SET feedback = ? WHERE id = ?", (feedback, history_id))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_title(history_id: str, title: str) -> bool:
    db = await _get_db()
    try:
        cursor = await db.execute("UPDATE history SET question = ? WHERE id = ?", (title, history_id))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
