"""Orchestrator untuk RAGAS-style evaluation menggunakan ragas library.

Menjalankan 4 metrics (Context Precision, Context Recall, Faithfulness,
Answer Relevance) secara sequential per query menggunakan SiliconFlow
sebagai LLM judge backend.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RAGAS_OUTPUT = Path(__file__).parent.parent.parent / "data" / "eval" / "ragas_results.json"
DEFAULT_PARTIAL_OUTPUT = Path(__file__).parent.parent.parent / "data" / "eval" / "ragas_results_partial.json"

# Jumlah konteks yang dikirim ke RAGAS judge — harus sama dengan reranker_top_k_output
# dari config/settings.py agar skor mencerminkan apa yang sebenarnya dikembalikan ke user
RAGAS_CONTEXT_WINDOW = 5


def load_partial_results(path: Path) -> list[dict]:
    """Load partial checkpoint results. Return [] jika file tidak ada atau corrupt."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logger.warning("Partial checkpoint file corrupted, starting fresh: %s", exc)
        return []


def _save_partial(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _aggregate_metrics(results: list[dict], ranking_metrics: dict | None = None) -> dict:
    """Hitung summary metrics dari per-query results.

    Args:
        results: Per-query RAGAS results.
        ranking_metrics: Optional dict dari compute_ranking_metrics() —
            jika diset, ranking metrics di-merge ke dalam summary.
    """
    metrics = ["context_precision", "context_recall", "answer_faithfulness", "answer_relevance"]

    # Overall averages (skip None values)
    overall = {}
    for m in metrics:
        vals = [r[m] for r in results if r.get(m) is not None]
        overall[m] = round(sum(vals) / len(vals), 4) if vals else None

    # Retrieval accuracy (citation pass rate)
    passed = sum(1 for r in results if r.get("retrieval_pass"))
    overall["retrieval_accuracy"] = round(passed / len(results), 4) if results else None
    overall["total_queries"] = len(results)

    # Per-difficulty breakdown
    per_difficulty: dict[str, dict] = {}
    for r in results:
        diff = r.get("difficulty", "Unknown")
        if diff not in per_difficulty:
            per_difficulty[diff] = {m: [] for m in metrics}
        for m in metrics:
            if r.get(m) is not None:
                per_difficulty[diff][m].append(r[m])

    overall["per_difficulty"] = {
        diff: {m: round(sum(vals) / len(vals), 4) if vals else None for m, vals in diff_data.items()}
        for diff, diff_data in per_difficulty.items()
    }

    # Merge ranking metrics jika tersedia
    if ranking_metrics:
        overall.update(ranking_metrics)

    return overall


def _build_context_strings(docs: list[dict]) -> list[str]:
    """Konversi retrieved docs ke list of strings untuk ragas."""
    result = []
    for doc in docs:
        text = doc.get("text") or doc.get("content") or ""
        result.append(text)
    return result


async def _score_single_query(
    query: str,
    response: str,
    retrieved_contexts: list[str],
    golden_answer: str,
    llm,
    embeddings,
    inter_judge_delay: float = 2.0,
) -> dict[str, float | None]:
    """Jalankan 4 ragas metrics untuk satu query. Return dict scores.

    ragas 0.4.x API: setiap metric punya .ascore(**kwargs) dengan signature berbeda.
    SingleTurnSample tidak dipakai — tiap metric menerima field langsung.
    """
    from ragas.metrics.collections import (
        ContextPrecisionWithoutReference,
        ContextRecall,
        Faithfulness,
        AnswerRelevancy,
    )

    scores: dict[str, float | None] = {
        "context_precision": None,
        "context_recall": None,
        "answer_faithfulness": None,
        "answer_relevance": None,
    }

    # Context Precision: ascore(user_input, response, retrieved_contexts)
    try:
        scorer = ContextPrecisionWithoutReference(llm=llm)
        result = await scorer.ascore(
            user_input=query,
            response=response,
            retrieved_contexts=retrieved_contexts,
        )
        scores["context_precision"] = round(float(result), 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Context Precision scoring failed: %s", exc)
    await asyncio.sleep(inter_judge_delay)

    # Context Recall: ascore(user_input, retrieved_contexts, reference)
    try:
        scorer = ContextRecall(llm=llm)
        result = await scorer.ascore(
            user_input=query,
            retrieved_contexts=retrieved_contexts,
            reference=golden_answer,
        )
        scores["context_recall"] = round(float(result), 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Context Recall scoring failed: %s", exc)
    await asyncio.sleep(inter_judge_delay)

    # Faithfulness: ascore(user_input, response, retrieved_contexts)
    try:
        scorer = Faithfulness(llm=llm)
        result = await scorer.ascore(
            user_input=query,
            response=response,
            retrieved_contexts=retrieved_contexts,
        )
        scores["answer_faithfulness"] = round(float(result), 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Answer Faithfulness scoring failed: %s", exc)
    await asyncio.sleep(inter_judge_delay)

    # AnswerRelevancy: butuh embeddings di __init__, ascore(user_input, response)
    try:
        scorer = AnswerRelevancy(llm=llm, embeddings=embeddings)
        result = await scorer.ascore(
            user_input=query,
            response=response,
        )
        scores["answer_relevance"] = round(float(result), 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Answer Relevance scoring failed: %s", exc)

    return scores


async def run_ragas_evaluation(
    queries: list[dict],
    golden_answers: dict[str, dict],
    graph: Any,  # CompiledStateGraph — harus expose .invoke()
    output_path: Path = DEFAULT_RAGAS_OUTPUT,
    partial_path: Path = DEFAULT_PARTIAL_OUTPUT,
    batch_size: int | None = None,
    resume: bool = False,
    inter_query_delay: float = 5.0,
    inter_judge_delay: float = 2.0,
    verbose: bool = False,
    ranking_metrics: dict | None = None,
) -> dict:
    """Jalankan RAGAS evaluation untuk semua (atau batch) queries.

    Args:
        queries: List dicts dari eval_queries.json
        golden_answers: Dict dari golden_generator.load_golden_answers()
        graph: Compiled LangGraph Phase 3 graph (sync invoke)
        output_path: Path untuk menyimpan hasil akhir
        partial_path: Path untuk checkpoint per-query
        batch_size: Jika set, hanya proses N queries pertama
        resume: Jika True, skip queries yang sudah ada di partial_path
        inter_query_delay: Detik antar query (mitigasi rate limit)
        inter_judge_delay: Detik antar judge call dalam satu query
        verbose: Print progress detail

    Returns:
        Dict dengan summary + results
    """
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.embeddings import OpenAIEmbeddings
    from config.settings import settings

    # Setup ragas LLM + embeddings dengan SiliconFlow client
    client = AsyncOpenAI(
        api_key=settings.siliconflow_api_key.get_secret_value(),
        base_url=settings.siliconflow_base_url,
    )
    # max_tokens=4096: ragas default 1024 terlalu kecil untuk ContextRecall dan Faithfulness
    ragas_llm = llm_factory(settings.llm_model, client=client, max_tokens=4096)
    ragas_embeddings = OpenAIEmbeddings(client=client, model=settings.embedding_model)

    # Load partial checkpoint jika resume
    completed_results: list[dict] = load_partial_results(partial_path) if resume else []
    completed_ids = {r["id"] for r in completed_results}

    # Batching
    target_queries = queries[:batch_size] if batch_size else queries

    results = list(completed_results)

    for i, eq in enumerate(target_queries, start=1):
        qid = eq["id"]

        if qid in completed_ids:
            if verbose:
                print(f"  [{i:02d}/{len(target_queries)}] {qid}: SKIP (sudah selesai)")
            continue

        print(f"  [{i:02d}/{len(target_queries)}] {qid}: {eq['query'][:55]}...", end="", flush=True)
        t0 = time.time()

        # Invoke graph
        try:
            graph_result = graph.invoke(
                {
                    "query": eq["query"],
                    "conversation_history": [],
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={"configurable": {"thread_id": f"ragas-{qid}"}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph invoke failed for %s: %s", qid, exc)
            results.append({"id": qid, "query": eq["query"], "difficulty": eq["difficulty"],
                            "context_precision": None, "context_recall": None,
                            "answer_faithfulness": None, "answer_relevance": None,
                            "retrieval_pass": False, "error": str(exc)})
            _save_partial(results, partial_path)
            print(f" ERROR: {exc}")
            continue

        response = graph_result.get("response") or ""
        reranked = graph_result.get("reranked_docs") or graph_result.get("retrieved_docs") or []
        citations = graph_result.get("citations") or []
        crag_grade = graph_result.get("crag_grade")
        query_type = graph_result.get("query_type")

        # Citation pass/fail (existing metric)
        cited_books = {c.get("book_title", "") for c in citations}
        retrieval_pass = any(b in cited_books for b in eq.get("expected_books", []))

        # Contexts untuk ragas
        retrieved_contexts = _build_context_strings(reranked[:RAGAS_CONTEXT_WINDOW])
        golden = golden_answers.get(qid, {}).get("golden_answer", "")

        # Jalankan 4 ragas metrics
        scores = await _score_single_query(
            query=eq["query"],
            response=response,
            retrieved_contexts=retrieved_contexts,
            golden_answer=golden,
            llm=ragas_llm,
            embeddings=ragas_embeddings,
            inter_judge_delay=inter_judge_delay,
        )

        elapsed = time.time() - t0
        entry = {
            "id": qid,
            "query": eq["query"],
            "difficulty": eq["difficulty"],
            "context_precision": scores["context_precision"],
            "context_recall": scores["context_recall"],
            "answer_faithfulness": scores["answer_faithfulness"],
            "answer_relevance": scores["answer_relevance"],
            "retrieval_pass": retrieval_pass,
            "crag_grade": crag_grade,
            "query_type": query_type,
        }
        results.append(entry)
        _save_partial(results, partial_path)

        print(f" OK ({elapsed:.0f}s) | prec={scores['context_precision']} rec={scores['context_recall']} faith={scores['answer_faithfulness']} rel={scores['answer_relevance']}")

        if i < len(target_queries):
            await asyncio.sleep(inter_query_delay)

    # Aggregate
    summary = _aggregate_metrics(results, ranking_metrics=ranking_metrics)

    output_data = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # Hapus partial file jika selesai penuh
    if not batch_size or len(results) >= len(queries):
        if partial_path.exists():
            partial_path.unlink()

    return output_data
