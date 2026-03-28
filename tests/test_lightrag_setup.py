"""Unit tests for LightRAG client module setup and configuration.

Tests verify:
- ACCOUNTING_ENTITY_TYPES count and content
- EmbeddingFunc dimension configuration (SiliconFlow Qwen3-Embedding-8B, 1024 dim)
- Settings extension with lightrag_working_dir
- Async function signatures for LLM and embedding functions
- LightRAG constructor parameters: max_async=16, max_parallel_insert=4,
  entity_extract_max_gleaning=0, no insert_batch_size in addon_params
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from config.settings import settings
from src.knowledge_graph.lightrag_client import (
    ACCOUNTING_ENTITY_TYPES,
    embedding_func,
)


def test_accounting_entity_types_count():
    assert len(ACCOUNTING_ENTITY_TYPES) == 10


def test_accounting_entity_types_contains_core_types():
    assert "CostType" in ACCOUNTING_ENTITY_TYPES
    assert "CostingMethod" in ACCOUNTING_ENTITY_TYPES
    assert "Formula" in ACCOUNTING_ENTITY_TYPES


def test_embedding_func_has_correct_dim():
    assert embedding_func.embedding_dim == 1024


def test_settings_has_lightrag_working_dir():
    assert hasattr(settings, "lightrag_working_dir")
    assert settings.lightrag_working_dir == "./lightrag_storage"


@patch("src.knowledge_graph.lightrag_client.LightRAG")
def test_llm_model_func_is_async(mock_lightrag_cls):
    """LLM func passed to LightRAG constructor must be an async coroutine function."""
    mock_instance = MagicMock()
    mock_instance.initialize_storages = AsyncMock()
    mock_lightrag_cls.return_value = mock_instance
    from src.knowledge_graph.lightrag_client import build_lightrag_instance

    asyncio.run(build_lightrag_instance())
    kwargs = mock_lightrag_cls.call_args[1]
    assert inspect.iscoroutinefunction(kwargs["llm_model_func"])


@patch("src.knowledge_graph.lightrag_client.LightRAG")
def test_lightrag_config_max_async(mock_lightrag_cls):
    """build_lightrag_instance passes llm_model_max_async=16."""
    mock_instance = MagicMock()
    mock_instance.initialize_storages = AsyncMock()
    mock_lightrag_cls.return_value = mock_instance
    from src.knowledge_graph.lightrag_client import build_lightrag_instance

    asyncio.run(build_lightrag_instance())
    kwargs = mock_lightrag_cls.call_args[1]
    assert kwargs["llm_model_max_async"] == 16


@patch("src.knowledge_graph.lightrag_client.LightRAG")
def test_lightrag_config_max_parallel_insert(mock_lightrag_cls):
    """build_lightrag_instance passes max_parallel_insert=4."""
    mock_instance = MagicMock()
    mock_instance.initialize_storages = AsyncMock()
    mock_lightrag_cls.return_value = mock_instance
    from src.knowledge_graph.lightrag_client import build_lightrag_instance

    asyncio.run(build_lightrag_instance())
    kwargs = mock_lightrag_cls.call_args[1]
    assert kwargs["max_parallel_insert"] == 4


@patch("src.knowledge_graph.lightrag_client.LightRAG")
def test_lightrag_config_gleaning_zero(mock_lightrag_cls):
    """build_lightrag_instance passes entity_extract_max_gleaning=0."""
    mock_instance = MagicMock()
    mock_instance.initialize_storages = AsyncMock()
    mock_lightrag_cls.return_value = mock_instance
    from src.knowledge_graph.lightrag_client import build_lightrag_instance

    asyncio.run(build_lightrag_instance())
    kwargs = mock_lightrag_cls.call_args[1]
    assert kwargs["entity_extract_max_gleaning"] == 0


@patch("src.knowledge_graph.lightrag_client.LightRAG")
def test_lightrag_config_no_insert_batch_size_in_addon(mock_lightrag_cls):
    """addon_params must NOT contain insert_batch_size (silently ignored bug)."""
    mock_instance = MagicMock()
    mock_instance.initialize_storages = AsyncMock()
    mock_lightrag_cls.return_value = mock_instance
    from src.knowledge_graph.lightrag_client import build_lightrag_instance

    asyncio.run(build_lightrag_instance())
    kwargs = mock_lightrag_cls.call_args[1]
    assert "insert_batch_size" not in kwargs["addon_params"]


@patch("src.knowledge_graph.lightrag_client.LightRAG")
def test_build_lightrag_does_not_call_initialize_storages(mock_lightrag_cls):
    """build_lightrag_instance() must NOT call initialize_storages() internally.

    FLAG-2: The FastAPI lifespan context manager in backend/main.py is the sole
    correct call site for rag.initialize_storages(). Calling it inside the factory
    causes double initialization on every startup.
    """
    mock_instance = MagicMock()
    mock_instance.initialize_storages = AsyncMock()
    mock_lightrag_cls.return_value = mock_instance

    from src.knowledge_graph.lightrag_client import build_lightrag_instance

    asyncio.run(build_lightrag_instance())

    mock_instance.initialize_storages.assert_not_called()
