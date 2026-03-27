"""Pydantic models for the FastAPI backend."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    history_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    graph_loaded: bool
    embedding_model: str
    llm_model: str
