import logging
import asyncio
import concurrent.futures

from src.agents.state import RAGState
from src.retrieval.preprocessor import preprocess_query
from src.retrieval.vector_search import hybrid_search
from src.retrieval.reranker import rerank_results
from src.retrieval.query_classifier import is_calculation_query
from src.generation.generator import generate_response
from src.llm.client import generate as llm_generate
from config.settings import settings

logger = logging.getLogger(__name__)

_lightrag_instance = None


def _run_async(coro):
    """Run async coroutine from sync context, even inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _get_lightrag():
    """Lazy singleton — avoid initializing at import time (heavy async startup)."""
    global _lightrag_instance
    if _lightrag_instance is None:
        from src.knowledge_graph.lightrag_client import build_lightrag_instance
        _lightrag_instance = _run_async(build_lightrag_instance())
    return _lightrag_instance


def route_node(state: RAGState) -> dict:
    """Classify query type and reset CRAG state for this turn."""
    query = state["query"]

    if is_calculation_query(query):
        return {
            "query_type": "Calculation",
            "llm_call_count": 0,
            "crag_iterations": 0,
            "crag_grade": None,
        }

    return {
        "query_type": "Simple",
        "llm_call_count": 0,
        "crag_iterations": 0,
        "crag_grade": None,
    }


def preprocess_node(state: RAGState) -> dict:
    """Preprocess query: glossary expansion + embedding with instruction prefix."""
    try:
        result = preprocess_query(state["query"])
        return {
            "expanded_query": result["expanded_query"],
            "query_embedding": result["query_embedding"],
        }
    except Exception as e:
        logger.error(f"Preprocess failed: {e}")
        return {"error": f"Preprocessing failed: {e}"}


def retrieve_node(state: RAGState) -> dict:
    """Retrieve documents via hybrid search (dense + BM25)."""
    if state.get("error"):
        return {}
    try:
        results = hybrid_search(
            query_embedding=state["query_embedding"],
            query_text=state.get("expanded_query", state["query"]),
            top_k=settings.reranker_top_k_input,
        )
        return {"retrieved_docs": results}
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {"error": f"Retrieval failed: {e}"}


def graph_retrieve_node(state: RAGState) -> dict:
    """Retrieve context from LightRAG knowledge graph (hybrid or local mode)."""
    if state.get("error"):
        return {}

    query = state["query"]
    rag = _get_lightrag()

    RELATIONAL_KEYWORDS = [
        "prerequisite", "prasyarat", "hubungan", "relasi",
        "sebelum", "setelah", "dasar dari", "basis of",
    ]
    query_lower = query.lower()
    if any(kw in query_lower for kw in RELATIONAL_KEYWORDS):
        mode = "local"
    else:
        mode = state.get("query_mode") or "hybrid"

    try:
        from lightrag import QueryParam
        graph_result = _run_async(
            rag.aquery(query, param=QueryParam(mode=mode))
        )

        graph_docs = [{
            "text": graph_result,
            "metadata": {
                "book_title": "Knowledge Graph",
                "chapter": "Multi-source synthesis",
                "content_type": "graph_context",
                "page_start": 0,
                "page_end": 0,
                "section_path": f"LightRAG/{mode} mode",
            },
            "score": 1.0,
        }]

        return {"graph_docs": graph_docs, "query_mode": mode}

    except Exception as e:
        logger.error(f"Graph retrieval failed: {e}")
        return {"graph_docs": []}


def rerank_node(state: RAGState) -> dict:
    """Rerank retrieved documents using Qwen3-Reranker-8B."""
    if state.get("error") or not state.get("retrieved_docs"):
        return {}
    try:
        reranked = rerank_results(
            query=state["query"],
            search_results=state["retrieved_docs"],
            top_k=settings.reranker_top_k_output,
        )
        return {"reranked_docs": reranked}
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return {"reranked_docs": state["retrieved_docs"][:settings.reranker_top_k_output]}


def generate_node(state: RAGState) -> dict:
    """Generate bilingual response with citations and accumulate conversation history."""
    if state.get("error"):
        return {
            "response": f"Terjadi kesalahan: {state['error']}",
            "citations": [],
        }

    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    if not docs:
        gap_msg = (
            "Tidak ditemukan referensi relevan untuk pertanyaan ini "
            "di korpus textbook yang tersedia setelah pencarian ulang."
        )
        return {
            "response": gap_msg,
            "citations": [],
            "conversation_history": [
                {"role": "user", "content": state["query"]},
                {"role": "assistant", "content": gap_msg},
            ],
        }

    graph_context = ""
    graph_docs = state.get("graph_docs") or []
    if graph_docs:
        graph_context = "\n\n".join(doc["text"] for doc in graph_docs if doc.get("text"))

    query_type = state.get("query_type", "Simple")
    history = state.get("conversation_history") or []

    try:
        result = generate_response(
            query=state["query"],
            context_docs=docs,
            graph_context=graph_context,
            query_type=query_type,
            conversation_history=history,
        )
        llm_count = state.get("llm_call_count", 0) + 1
        logger.info(
            "llm_call_count=%d query_type=%s node=generate_node",
            llm_count,
            query_type,
        )
        return {
            "response": result["response"],
            "citations": result["citations"],
            "llm_call_count": llm_count,
            "conversation_history": [
                {"role": "user", "content": state["query"]},
                {"role": "assistant", "content": result["response"]},
            ],
        }
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return {
            "response": f"Gagal menghasilkan respons: {e}",
            "citations": [],
        }


def crag_grade_node(state: RAGState) -> dict:
    """Grade retrieval quality using rerank_score thresholds (0.5/0.2)."""
    reranked = state.get("reranked_docs") or []
    iterations = state.get("crag_iterations", 0)

    if not reranked:
        grade = "INCORRECT"
    else:
        max_score = max(doc.get("rerank_score", 0.0) for doc in reranked)
        if max_score >= 0.5:
            grade = "CORRECT"
        elif max_score >= 0.2:
            grade = "AMBIGUOUS"
        else:
            grade = "INCORRECT"

    return {"crag_grade": grade, "crag_iterations": iterations + 1}


def crag_router(state: RAGState) -> str:
    """Route to generate/reformulate based on CRAG grade (max 2 iterations)."""
    grade = state.get("crag_grade", "CORRECT")
    iterations = state.get("crag_iterations", 0)
    query_type = state.get("query_type", "Simple")

    if grade == "CORRECT" or iterations >= 2:
        return "generate_calc" if query_type == "Calculation" else "generate"
    return "reformulate"


def reformulate_node(state: RAGState) -> dict:
    """Reformulate query via LLM when CRAG grade is AMBIGUOUS/INCORRECT."""
    original_query = state["query"]
    llm_count = state.get("llm_call_count", 0)

    reformulation_prompt = [
        {
            "role": "system",
            "content": (
                "Kamu adalah asisten yang membantu mereformulasi pertanyaan akuntansi "
                "agar lebih spesifik dan mudah dicari di textbook. Tulis ulang pertanyaan "
                "berikut dengan kata kunci yang lebih tepat. Jawab HANYA dengan pertanyaan "
                "baru, tanpa penjelasan."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Pertanyaan awal: {original_query}\n\n"
                "Tulis ulang pertanyaan ini agar lebih spesifik:"
            ),
        },
    ]

    try:
        reformulated = llm_generate(reformulation_prompt, temperature=0.3)
        logger.info(f"Query reformulated: '{original_query}' -> '{reformulated}'")
        return {"query": reformulated.strip(), "llm_call_count": llm_count + 1}
    except Exception as e:
        logger.error(f"Reformulation failed: {e}, keeping original query")
        return {"query": original_query, "llm_call_count": llm_count}


def generate_calc_node(state: RAGState) -> dict:
    """Generate calculation-specific response with step-by-step format."""
    if state.get("error"):
        return {
            "response": f"Terjadi kesalahan: {state['error']}",
            "citations": [],
        }

    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    if not docs:
        return {
            "response": (
                "Tidak ditemukan referensi relevan untuk pertanyaan ini "
                "di korpus textbook yang tersedia."
            ),
            "citations": [],
        }

    graph_context = ""
    graph_docs = state.get("graph_docs") or []
    if graph_docs:
        graph_context = "\n\n".join(doc["text"] for doc in graph_docs if doc.get("text"))

    try:
        result = generate_response(
            query=state["query"],
            context_docs=docs,
            graph_context=graph_context,
            query_type="Calculation",
        )
        llm_count = state.get("llm_call_count", 0) + 1
        logger.info(
            "llm_call_count=%d query_type=%s node=generate_calc_node",
            llm_count,
            "Calculation",
        )
        return {
            "response": result["response"],
            "citations": result["citations"],
            "llm_call_count": llm_count,
            "conversation_history": [
                {"role": "user", "content": state["query"]},
                {"role": "assistant", "content": result["response"]},
            ],
        }
    except Exception as e:
        logger.error(f"Calculation generation failed: {e}")
        return {
            "response": f"Gagal menghasilkan respons kalkulasi: {e}",
            "citations": [],
        }
