"""Tests for fast-graphrag client factory configuration.

Covers:
- ACCOUNTING_ENTITY_TYPES has 10 domain-specific entity types
- Domain string is non-empty and Indonesian accounting focused
- Settings have graphrag_working_dir and graphrag_llm_model
- build_graphrag_instance returns a GraphRAG instance with correct config
- edge_upsert_policy is EdgeUpsertPolicy_UpsertIfValidNodes (prevents token overflow)
- DeepSeek is used when API key is set, SiliconFlow as fallback
"""

from unittest.mock import MagicMock, patch

import pytest

from src.knowledge_graph.fastgraphrag_client import (
    ACCOUNTING_ENTITY_TYPES,
    DOMAIN,
    EXAMPLE_QUERIES,
)


def test_accounting_entity_types_count():
    """ACCOUNTING_ENTITY_TYPES has exactly 10 entity types."""
    assert len(ACCOUNTING_ENTITY_TYPES) == 10


def test_accounting_entity_types_contains_core_types():
    """ACCOUNTING_ENTITY_TYPES contains essential accounting entity categories."""
    core_types = {"CostType", "CostingMethod", "Formula", "FinancialStatement", "Concept"}
    for t in core_types:
        assert t in ACCOUNTING_ENTITY_TYPES, f"Missing core type: {t}"


def test_domain_string_is_non_empty():
    """DOMAIN string is non-empty and contains accounting context."""
    assert len(DOMAIN) > 0
    assert "akuntansi" in DOMAIN.lower()


def test_example_queries_is_non_empty():
    """EXAMPLE_QUERIES contains multiple sample queries."""
    assert len(EXAMPLE_QUERIES) > 0
    assert "\n" in EXAMPLE_QUERIES


def test_settings_has_graphrag_working_dir():
    """Settings includes graphrag_working_dir with default './graphrag_storage'."""
    from config.settings import settings

    assert hasattr(settings, "graphrag_working_dir")
    assert settings.graphrag_working_dir == "./graphrag_storage"


def test_settings_has_graphrag_llm_model():
    """Settings includes graphrag_llm_model with default 'deepseek-chat'."""
    from config.settings import settings

    assert hasattr(settings, "graphrag_llm_model")
    assert settings.graphrag_llm_model == "deepseek-chat"


@patch("src.knowledge_graph.fastgraphrag_client.GraphRAG")
def test_build_graphrag_instance_returns_graphrag(mock_graphrag_cls):
    """build_graphrag_instance returns a GraphRAG instance."""
    mock_instance = MagicMock()
    mock_graphrag_cls.return_value = mock_instance
    mock_graphrag_cls.Config = MagicMock()

    from src.knowledge_graph.fastgraphrag_client import build_graphrag_instance

    result = build_graphrag_instance()
    assert result is mock_instance
    mock_graphrag_cls.assert_called_once()


@patch("src.knowledge_graph.fastgraphrag_client.GraphRAG")
def test_build_graphrag_passes_entity_types(mock_graphrag_cls):
    """build_graphrag_instance passes ACCOUNTING_ENTITY_TYPES to GraphRAG constructor."""
    mock_graphrag_cls.Config = MagicMock()
    mock_graphrag_cls.return_value = MagicMock()

    from src.knowledge_graph.fastgraphrag_client import build_graphrag_instance

    build_graphrag_instance()
    call_kwargs = mock_graphrag_cls.call_args[1]
    assert call_kwargs["entity_types"] == ACCOUNTING_ENTITY_TYPES


@patch("src.knowledge_graph.fastgraphrag_client.GraphRAG")
def test_build_graphrag_passes_n_checkpoints(mock_graphrag_cls):
    """build_graphrag_instance sets n_checkpoints=2 for crash safety."""
    mock_graphrag_cls.Config = MagicMock()
    mock_graphrag_cls.return_value = MagicMock()

    from src.knowledge_graph.fastgraphrag_client import build_graphrag_instance

    build_graphrag_instance()
    call_kwargs = mock_graphrag_cls.call_args[1]
    assert call_kwargs["n_checkpoints"] == 2


def test_build_graphrag_uses_upsert_if_valid_nodes_policy():
    """build_graphrag_instance uses EdgeUpsertPolicy_UpsertIfValidNodes as edge_upsert_policy.

    This prevents token overflow during graph building phase on large books:
    EdgeUpsertPolicy_UpsertValidAndMergeSimilarByLLM (the default) sends all edges
    in a single LLM prompt which overflows DeepSeek's 12K output token cap.
    EdgeUpsertPolicy_UpsertIfValidNodes skips LLM-based edge merging entirely.
    """
    from fast_graphrag import EdgeUpsertPolicy_UpsertIfValidNodes

    from src.knowledge_graph.fastgraphrag_client import build_graphrag_instance

    grag = build_graphrag_instance()
    assert isinstance(
        grag.state_manager.edge_upsert_policy, EdgeUpsertPolicy_UpsertIfValidNodes
    ), (
        "edge_upsert_policy must be EdgeUpsertPolicy_UpsertIfValidNodes to prevent "
        "token overflow on large ingestions"
    )
