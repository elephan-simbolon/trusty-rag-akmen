"""FastAPI backend wrapping the LangGraph RAG pipeline with SSE streaming."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.eval_db import (
    get_latest_eval_run,
    list_eval_runs,
    save_eval_run,
)
from backend.history_db import (
    delete_history,
    get_history_detail,
    list_history,
    save_history,
    update_feedback,
    update_title,
)
from backend.models import HealthResponse, QueryRequest
from config.settings import settings
from src.monitoring.langfuse_client import get_langfuse_handler
from src.services.graph_service import get_graph, set_graphrag

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown GraphRAG singleton."""
    from src.knowledge_graph.fastgraphrag_client import build_graphrag_instance

    logger.info("Initializing GraphRAG instance...")
    grag = build_graphrag_instance()
    set_graphrag(grag)
    logger.info("GraphRAG ready.")
    yield
    set_graphrag(None)
    logger.info("GraphRAG shutdown.")


app = FastAPI(title="Trusty RAG Akmen API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    graph = get_graph()
    return HealthResponse(
        status="ok",
        graph_loaded=graph is not None,
        embedding_model=settings.embedding_model,
        llm_model=settings.llm_model,
    )


@app.post("/api/query")
async def query_sse(request: QueryRequest):
    session_id = request.session_id or str(uuid4())

    async def event_stream():
        yield _sse_event("status", {"message": "Mencari referensi..."})

        try:
            graph = get_graph()
            handler = get_langfuse_handler()
            callbacks = [handler] if handler else []
            result = await graph.ainvoke(
                {
                    "query": request.question,
                    "crag_iterations": 0,
                    "crag_grade": None,
                },
                config={
                    "configurable": {"thread_id": session_id},
                    "callbacks": callbacks,
                    "metadata": {
                        "langfuse_session_id": session_id,
                        "langfuse_user_id": "default",
                    },
                },
            )
        except Exception as e:
            logger.error(f"Graph invoke failed: {e}")
            yield _sse_event("error", {"message": "Terjadi kesalahan saat memproses pertanyaan."})
            return

        error = result.get("error")
        response = result.get("response", "")
        citations = result.get("citations", [])
        query_type = result.get("query_type")
        crag_grade = result.get("crag_grade")

        if error:
            yield _sse_event("error", {"message": str(error)})
            return

        if not response:
            yield _sse_event("not_found", {"message": "Tidak ditemukan referensi relevan."})
            return

        if query_type:
            yield _sse_event("query_type", {"query_type": query_type})

        yield _sse_event("status", {"message": "Menyusun jawaban..."})

        chunk_size = 20
        for i in range(0, len(response), chunk_size):
            yield _sse_event("text", {"content": response[i : i + chunk_size]})
            await asyncio.sleep(0.015)

        if citations:
            yield _sse_event("citations", {"data": citations})

        history_id = await save_history(
            request.question, response, citations, query_type, crag_grade
        )

        yield _sse_event(
            "done",
            {
                "history_id": history_id,
                "query_type": query_type,
                "crag_grade": crag_grade,
            },
        )

    return EventSourceResponse(event_stream())


# --- History endpoints ---


@app.get("/api/history")
async def get_history_list(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)):
    return await list_history(page, per_page)


@app.get("/api/history/{history_id}")
async def get_history(history_id: str):
    detail = await get_history_detail(history_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Not found")
    return detail


@app.delete("/api/history/{history_id}")
async def delete_history_item(history_id: str):
    ok = await delete_history(history_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True}


class FeedbackBody(BaseModel):
    feedback: int


@app.patch("/api/history/{history_id}/feedback")
async def patch_feedback(history_id: str, body: FeedbackBody):
    if body.feedback not in (1, -1):
        raise HTTPException(status_code=422, detail="feedback must be 1 or -1")
    ok = await update_feedback(history_id, body.feedback)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True, "feedback": body.feedback}


class TitleBody(BaseModel):
    title: str


@app.patch("/api/history/{history_id}/title")
async def patch_title(history_id: str, body: TitleBody):
    trimmed = body.title.strip()
    if not trimmed:
        raise HTTPException(status_code=422, detail="title must not be empty")
    ok = await update_title(history_id, trimmed)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True, "title": trimmed}


def _sse_event(event_type: str, data: dict) -> dict:
    """Format an SSE event payload."""
    return {"data": json.dumps({"type": event_type, **data}, ensure_ascii=False)}


# --- Eval endpoints ---


class EvalRunBody(BaseModel):
    summary: dict
    results: list[dict]
    model: str = ""


@app.post("/api/eval/runs")
async def post_eval_run(body: EvalRunBody):
    run_id = await save_eval_run(
        summary=body.summary,
        results=body.results,
        model=body.model,
    )
    return {"run_id": run_id, "success": True}


@app.get("/api/eval/runs/latest")
async def get_eval_run_latest():
    run = await get_latest_eval_run()
    if run is None:
        raise HTTPException(status_code=404, detail="Belum ada eval run")
    return run


@app.get("/api/eval/runs")
async def get_eval_runs_list():
    runs = await list_eval_runs()
    return {"data": runs, "total": len(runs)}


# --- Static file serving for production builds ---

_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if _DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = _DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_DIST_DIR / "index.html"))
