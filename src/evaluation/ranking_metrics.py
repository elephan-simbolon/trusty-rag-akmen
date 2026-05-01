"""Compute ranking metrics (NDCG, MRR, Recall@K) menggunakan ranx.

Input:
    qrels: dict[query_id, dict[doc_id, relevance]] — binary (0|1)
    run_docs: dict[query_id, list[doc_dict]] — retrieved_docs dari graph.invoke()

Doc ID: str(doc["id"]) — Qdrant point ID.
Score untuk ranx.Run: doc["score"] (RRF-fused score dari hybrid search).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

METRICS = ["ndcg@5", "mrr@5", "recall@5", "recall@10"]


def compute_ranking_metrics(
    qrels: dict[str, dict[str, int]],
    run_docs: dict[str, list[dict[str, Any]]],
) -> dict[str, float]:
    """Hitung ranking metrics dari qrels dan retrieved docs.

    Args:
        qrels: Ground truth relevance per (query_id, doc_id). Nilai 0 atau 1.
            Format: {"EVAL-01": {"12345": 1, "67890": 0}, ...}
        run_docs: Retrieved docs per query_id, berurutan dari score tertinggi.
            Format: {"EVAL-01": [{"id": 12345, "score": 0.9}, ...], ...}

    Returns:
        Dict metrik rata-rata: {"ndcg@5": 0.82, "mrr@5": 0.75, ...}
    """
    from ranx import Qrels, Run, evaluate  # noqa: PLC0415

    # Filter qrels: hanya query yang ada di run_docs dan punya minimal 1 doc relevan
    filtered_qrels: dict[str, dict[str, int]] = {}
    filtered_run: dict[str, dict[str, float]] = {}

    for qid, rel_dict in qrels.items():
        if qid not in run_docs:
            logger.debug("Query %s ada di qrels tapi tidak di run_docs, di-skip", qid)
            continue
        # Hanya sertakan qrels yang punya minimal 1 doc relevan
        relevant_docs = {doc_id: rel for doc_id, rel in rel_dict.items() if rel > 0}
        if not relevant_docs:
            logger.debug("Query %s tidak punya doc relevan di qrels, di-skip", qid)
            continue

        # Build run dict: {doc_id (str): score (float)}
        run_entry: dict[str, float] = {}
        for doc in run_docs[qid]:
            doc_id = str(doc.get("id", ""))
            if doc_id:
                run_entry[doc_id] = float(doc.get("score", 0.0))
        if not run_entry:
            logger.debug("Query %s punya run entry kosong setelah filtering, di-skip", qid)
            continue

        filtered_qrels[qid] = rel_dict  # simpan semua (0 dan 1) untuk ranx
        filtered_run[qid] = run_entry

    if not filtered_qrels:
        logger.warning("Tidak ada query valid untuk evaluasi ranking — semua di-skip")
        return {m: 0.0 for m in METRICS}

    ranx_qrels = Qrels(filtered_qrels)
    ranx_run = Run(filtered_run)

    scores = evaluate(ranx_qrels, ranx_run, METRICS)
    return {k: round(float(v), 4) for k, v in scores.items()}
