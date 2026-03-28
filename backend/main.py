"""FastAPI backend wrapping the LangGraph RAG pipeline with SSE streaming."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.models import QueryRequest, HealthResponse
from backend.history_db import save_history, list_history, get_history_detail, delete_history, update_feedback, update_title
from src.services.graph_service import get_graph, set_lightrag
from src.monitoring.langfuse_client import get_langfuse_handler
from config.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown LightRAG singleton in the FastAPI event loop."""
    from src.knowledge_graph.lightrag_client import build_lightrag_instance
    logger.info("Initializing LightRAG instance...")
    rag = await build_lightrag_instance()
    await rag.initialize_storages()
    set_lightrag(rag)
    logger.info("LightRAG ready.")
    yield
    set_lightrag(None)
    logger.info("Shutting down LightRAG...")
    await rag.finalize_storages()


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

        history_id = await save_history(request.question, response, citations, query_type, crag_grade)

        yield _sse_event("done", {
            "history_id": history_id,
            "query_type": query_type,
            "crag_grade": crag_grade,
        })

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
