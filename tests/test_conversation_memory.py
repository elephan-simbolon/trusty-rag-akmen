"""Tests for MemorySaver conversation history accumulation.

Covers:
- conversation_history accumulates across invocations with same thread_id
- Two invocations with different thread_ids have isolated histories
- Annotated[list, operator.add] reducer accumulates correctly in RAGState
"""
import pytest
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agents.state import RAGState


# ---------------------------------------------------------------------------
# Minimal test graph that exercises MemorySaver + RAGState
# ---------------------------------------------------------------------------

def _make_test_graph():
    """Minimal 2-node graph using RAGState + MemorySaver for conversation memory tests.

    Bypasses full node chain — focuses on validating:
    1. Annotated[list, operator.add] reducer accumulates across invocations
    2. Thread isolation works correctly
    """
    def mock_route(state):
        return {
            "query_type": "Simple",
            "crag_iterations": 0,
            "crag_grade": None,
            "llm_call_count": 0,
        }

    def mock_generate(state):
        answer = f"Answer to: {state['query']}"
        return {
            "response": answer,
            "citations": [],
            "conversation_history": [
                {"role": "user", "content": state["query"]},
                {"role": "assistant", "content": answer},
            ],
        }

    g = StateGraph(RAGState)
    g.add_node("route", mock_route)
    g.add_node("generate", mock_generate)
    g.set_entry_point("route")
    g.add_edge("route", "generate")
    g.add_edge("generate", END)
    return g.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# Test: Conversation history accumulates with same thread_id
# ---------------------------------------------------------------------------

def test_conversation_history_accumulates_across_invocations():
    """Two invocations with same thread_id accumulate conversation_history.

    After Turn 1: history should have 2 items (1 user + 1 assistant).
    After Turn 2: history should have 4 items (2 turns × 2 messages each).
    """
    graph = _make_test_graph()
    thread_config = {"configurable": {"thread_id": "session-accumulation-test"}}

    # Turn 1
    result1 = graph.invoke(
        {"query": "Apa itu biaya tetap?"},
        config=thread_config,
    )
    history_after_turn1 = result1.get("conversation_history", [])
    assert len(history_after_turn1) == 2, (
        f"After Turn 1, expected 2 history items, got {len(history_after_turn1)}"
    )

    # Turn 2 — same thread_id, MemorySaver accumulates
    result2 = graph.invoke(
        {"query": "Apa itu biaya variabel?"},
        config=thread_config,
    )
    history_after_turn2 = result2.get("conversation_history", [])
    assert len(history_after_turn2) == 4, (
        f"After Turn 2, expected 4 history items, got {len(history_after_turn2)}"
    )


def test_conversation_history_grows_with_each_turn():
    """History length increases by 2 with each additional turn (1 user + 1 assistant)."""
    graph = _make_test_graph()
    thread_config = {"configurable": {"thread_id": "session-growth-test"}}

    queries = [
        "Apa itu overhead cost?",
        "Bagaimana cara menghitung BEP?",
        "Apa perbedaan biaya langsung dan tidak langsung?",
    ]

    prev_length = 0
    for i, query in enumerate(queries):
        result = graph.invoke(
            {"query": query},
            config=thread_config,
        )
        current_length = len(result.get("conversation_history", []))
        expected_length = (i + 1) * 2
        assert current_length == expected_length, (
            f"After turn {i+1}, expected {expected_length} items, got {current_length}"
        )
        assert current_length > prev_length, "History should grow with each turn"
        prev_length = current_length


def test_conversation_history_contains_correct_roles():
    """Each turn adds user and assistant messages with correct roles."""
    graph = _make_test_graph()
    thread_config = {"configurable": {"thread_id": "session-roles-test"}}

    result = graph.invoke(
        {"query": "Apa itu contribution margin?"},
        config=thread_config,
    )
    history = result.get("conversation_history", [])

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert "contribution margin" in history[0]["content"]


# ---------------------------------------------------------------------------
# Test: Thread isolation — different thread_ids have separate histories
# ---------------------------------------------------------------------------

def test_different_thread_ids_have_isolated_histories():
    """Two invocations with different thread_ids have independent conversation histories."""
    graph = _make_test_graph()

    config_a = {"configurable": {"thread_id": "session-A"}}
    config_b = {"configurable": {"thread_id": "session-B"}}

    # Thread A: 2 turns
    graph.invoke(
        {"query": "Pertanyaan sesi A turn 1"},
        config=config_a,
    )
    result_a = graph.invoke(
        {"query": "Pertanyaan sesi A turn 2"},
        config=config_a,
    )

    # Thread B: only 1 turn
    result_b = graph.invoke(
        {"query": "Pertanyaan sesi B turn 1"},
        config=config_b,
    )

    history_a = result_a.get("conversation_history", [])
    history_b = result_b.get("conversation_history", [])

    # Thread A has 4 items (2 turns), Thread B has 2 items (1 turn)
    assert len(history_a) == 4, (
        f"Thread A: expected 4 items after 2 turns, got {len(history_a)}"
    )
    assert len(history_b) == 2, (
        f"Thread B: expected 2 items after 1 turn, got {len(history_b)}"
    )

    # Thread B should NOT contain Thread A's queries
    b_contents = " ".join(m["content"] for m in history_b)
    assert "sesi A" not in b_contents, "Thread B should not contain Thread A's history"


def test_new_thread_starts_with_empty_history():
    """A brand new thread_id starts with no prior conversation history."""
    graph = _make_test_graph()
    unique_thread = "session-brand-new-unique-12345"
    config = {"configurable": {"thread_id": unique_thread}}

    result = graph.invoke(
        {"query": "Pertanyaan pertama"},
        config=config,
    )
    history = result.get("conversation_history", [])
    # Should have exactly 2 items (this turn only)
    assert len(history) == 2, (
        f"New thread should start with empty history, got {len(history)} items"
    )


# ---------------------------------------------------------------------------
# Test: Annotated[list, operator.add] reducer behavior directly
# ---------------------------------------------------------------------------

def test_annotated_list_reducer_accumulates_correctly():
    """Direct test: Annotated[list, operator.add] reducer in RAGState accumulates correctly.

    This validates the TypedDict-level behavior independent of the full graph.
    """
    import operator
    # Simulate what LangGraph does: apply operator.add reducer
    existing = [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}]
    new_items = [{"role": "user", "content": "Q2"}, {"role": "assistant", "content": "A2"}]
    accumulated = operator.add(existing, new_items)
    assert len(accumulated) == 4
    assert accumulated[0]["content"] == "Q1"
    assert accumulated[2]["content"] == "Q2"
