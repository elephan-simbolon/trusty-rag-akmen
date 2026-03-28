"""Singleton Qdrant client — thread-safe, connection-pooled."""

from qdrant_client import QdrantClient

from config.settings import settings

_client = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        api_key = (
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key.get_secret_value()
            else None
        )
        _client = QdrantClient(url=settings.qdrant_url, api_key=api_key)
    return _client
