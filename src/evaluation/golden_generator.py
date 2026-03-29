"""Generate dan load golden answers untuk RAGAS Context Recall evaluation.

Golden answers di-generate SATU KALI dari retrieved context menggunakan LLM,
disimpan ke JSON, dan di-reuse untuk semua eval run selanjutnya.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_GOLDEN_PATH = Path(__file__).parent.parent.parent / "data" / "eval" / "golden_answers.json"


def load_golden_answers(path: Path = DEFAULT_GOLDEN_PATH) -> dict[str, dict]:
    """Load golden answers dari JSON file. Return {} jika file tidak ada."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("answers", {})


def _build_golden_prompt(query: str, context_block: str) -> list[dict]:
    """Bangun messages untuk LLM golden answer generation."""
    system = (
        "Kamu adalah ahli akuntansi biaya dan manajemen. "
        "Berdasarkan HANYA potongan textbook berikut, berikan jawaban komprehensif dan akurat. "
        "Jangan tambahkan informasi apapun yang tidak ada di konteks. "
        "Jawab dalam Bahasa Indonesia dengan istilah teknis bahasa Inggris dalam tanda kurung."
    )
    user = (
        f"Konteks dari textbook:\n\n{context_block}\n\n"
        f"Pertanyaan: {query}\n\n"
        "Berikan jawaban lengkap berdasarkan konteks di atas."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_context_block(docs: list[dict]) -> str:
    """Format retrieved docs menjadi context block untuk LLM."""
    parts = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.get("metadata", {})
        header = (
            f"[Sumber {i}: {meta.get('book_title', 'Unknown')}, "
            f"{meta.get('chapter', '')}, "
            f"hal. {meta.get('page_start', '?')}-{meta.get('page_end', '?')}]"
        )
        parts.append(f"{header}\n{doc.get('text', doc.get('content', ''))}")
    return "\n\n".join(parts)


def generate_golden_answers(
    queries: list[dict],
    graph,
    output_path: Path = DEFAULT_GOLDEN_PATH,
    verbose: bool = False,
) -> dict[str, dict]:
    """Generate golden answers untuk semua queries menggunakan retrieved context + LLM.

    Args:
        queries: List query dicts dari eval_queries.json
        graph: Compiled LangGraph Phase 3 graph (sync invoke)
        output_path: Path untuk menyimpan hasil golden answers
        verbose: Print progress per query

    Returns:
        Dict mapping query_id -> {"golden_answer": str, "source_docs": list[str]}
    """
    from src.llm.client import generate as llm_generate
    from config.settings import settings

    answers: dict[str, dict] = {}

    for i, eq in enumerate(queries, start=1):
        qid = eq["id"]
        query = eq["query"]
        if verbose:
            print(f"  [{i:02d}/{len(queries)}] Generating golden for {qid}...", end="", flush=True)

        try:
            result = graph.invoke(
                {
                    "query": query,
                    "conversation_history": [],
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={"configurable": {"thread_id": f"golden-{qid}"}},
            )

            reranked = result.get("reranked_docs") or result.get("retrieved_docs") or []
            top_docs = reranked[:5]
            context_block = _build_context_block(top_docs)

            messages = _build_golden_prompt(query=query, context_block=context_block)
            golden_answer = llm_generate(messages, temperature=0.1)

            source_docs = []
            for doc in top_docs:
                meta = doc.get("metadata", {})
                source_docs.append(
                    f"{meta.get('book_title', 'Unknown')}/"
                    f"{meta.get('chapter', 'Unknown')}/"
                    f"hal. {meta.get('page_start', '?')}-{meta.get('page_end', '?')}"
                )

            answers[qid] = {
                "golden_answer": golden_answer,
                "source_docs": source_docs,
            }

            if verbose:
                print(" OK")

        except Exception as exc:  # noqa: BLE001
            logger.warning("Golden generation failed for %s: %s", qid, exc)
            answers[qid] = {"golden_answer": "", "source_docs": [], "error": str(exc)}
            if verbose:
                print(f" FAILED: {exc}")

    # Simpan ke file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.llm_model,
        "answers": answers,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Golden answers saved to %s (%d entries)", output_path, len(answers))
    return answers
