"""Generate qrels (ground truth relevance) menggunakan LLM-as-judge.

Qrels di-generate SATU KALI dari retrieved_docs per query,
disimpan ke qrels.json, dan di-reuse di semua eval run selanjutnya.

Doc ID menggunakan str(doc["id"]) — Qdrant point ID, unik per chunk.
Relevance: binary (1=relevan, 0=tidak relevan).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_QRELS_PATH = Path(__file__).parent.parent.parent / "data" / "eval" / "qrels.json"

_JUDGE_SYSTEM = (
    "Kamu adalah evaluator sistem information retrieval. "
    "Tugasmu menilai apakah sebuah potongan teks relevan untuk menjawab pertanyaan. "
    "Jawab HANYA dengan angka: 1 jika relevan, 0 jika tidak relevan. "
    "Tidak ada penjelasan, tidak ada teks lain."
)

# Module-level import agar nama 'llm_generate' terdaftar di namespace modul ini
# dan bisa di-patch via patch("src.evaluation.qrels_generator.llm_generate").
# Graceful degradation: jika live services tidak tersedia saat import, tetap None
# dan akan gagal saat dipanggil (yang sudah di-handle via try/except di caller).
try:
    from src.llm.client import generate as llm_generate
except Exception:  # noqa: BLE001
    llm_generate = None  # type: ignore[assignment]


def _judge_chunk_relevance(query: str, chunk_text: str) -> int:
    """Panggil LLM judge untuk satu (query, chunk) pair. Return 1 atau 0."""
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Pertanyaan: {query}\n\n"
                f"Potongan teks:\n{chunk_text[:1500]}\n\n"
                "Jawab 1 (relevan) atau 0 (tidak relevan):"
            ),
        },
    ]
    try:
        raw = llm_generate(messages, temperature=0.0, max_tokens=4)
        return 1 if raw.strip().startswith("1") else 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM judge failed, defaulting to 0: %s", exc)
        return 0


def load_qrels(path: Path = DEFAULT_QRELS_PATH) -> dict[str, dict[str, int]]:
    """Load qrels dari JSON file. Return {} jika file tidak ada."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("qrels", {})


def generate_qrels(
    queries: list[dict],
    graph,
    output_path: Path = DEFAULT_QRELS_PATH,
    batch_size: int | None = None,
    verbose: bool = False,
) -> dict[str, dict[str, int]]:
    """Generate qrels via LLM judge untuk semua (atau batch) queries.

    Args:
        queries: List query dicts dari eval_queries.json.
            Wajib punya: "id" (str), "query" (str).
        graph: Compiled LangGraph Phase 3 graph (sync .invoke()).
        output_path: Path untuk menyimpan qrels.json.
        batch_size: Jika diset, hanya proses N queries pertama.
        verbose: Print progress per query.

    Returns:
        Dict mapping query_id -> {doc_id: relevance_score (0|1)}
    """
    target_queries = queries[:batch_size] if batch_size is not None else queries
    qrels: dict[str, dict[str, int]] = {}

    for i, eq in enumerate(target_queries, start=1):
        qid = eq["id"]
        query = eq["query"]

        if verbose:
            print(f"  [{i:02d}/{len(target_queries)}] {qid}: invoking graph...", end="", flush=True)

        try:
            result = graph.invoke(
                {
                    "query": query,
                    "conversation_history": [],
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={"configurable": {"thread_id": f"qrels-{qid}"}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph invoke failed for %s: %s", qid, exc)
            qrels[qid] = {}
            if verbose:
                print(f" GRAPH ERROR: {exc}")
            continue

        retrieved = result.get("retrieved_docs") or []
        query_qrels: dict[str, int] = {}

        for doc in retrieved:
            doc_id = str(doc.get("id", ""))
            if not doc_id:
                continue
            chunk_text = doc.get("text") or doc.get("content") or ""
            relevance = _judge_chunk_relevance(query=query, chunk_text=chunk_text)
            query_qrels[doc_id] = relevance

        qrels[qid] = query_qrels
        n_relevant = sum(1 for v in query_qrels.values() if v == 1)

        if verbose:
            print(f" {len(query_qrels)} docs judged, {n_relevant} relevant")

    # Simpan ke file
    from config.settings import settings  # noqa: PLC0415

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.llm_model,
        "qrels": qrels,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Qrels saved to %s (%d queries)", output_path, len(qrels))
    return qrels
