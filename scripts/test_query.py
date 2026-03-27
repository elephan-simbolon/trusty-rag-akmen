"""CLI tool for testing RAG queries without the Streamlit UI."""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def test_query(query: str, verbose: bool = False) -> dict:
    """Run a single query through the LangGraph pipeline and print results."""
    from src.agents.graph import build_phase3_graph

    graph = build_phase3_graph()
    result = graph.invoke(
        {
            "query": query,
            "conversation_history": [],
            "crag_iterations": 0,
            "crag_grade": None,
        },
        config={"configurable": {"thread_id": "cli-test"}},
    )

    response = result.get("response", "No response")
    citations = result.get("citations", [])
    error = result.get("error")

    print("\n" + "=" * 60)
    print(f"Query: {query}")
    print("=" * 60)

    if error:
        print(f"\nERROR: {error}")

    print(f"\nResponse:\n{response}")

    if citations:
        print(f"\nCitations ({len(citations)}):")
        for cit in citations:
            print(f"  - {cit['formatted']}")

    if verbose:
        print(f"\nFull state: {json.dumps({k: str(v)[:200] for k, v in result.items()}, indent=2)}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Test RAG query pipeline")
    parser.add_argument("query", help="The query to test")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show full state")
    args = parser.parse_args()

    test_query(args.query, verbose=args.verbose)


if __name__ == "__main__":
    main()
