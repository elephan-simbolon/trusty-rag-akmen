"""CLI entry point for fast-graphrag knowledge graph ingestion.

Reads Phase 1 chunks from a JSON backup file and inserts them into the
fast-graphrag knowledge graph via LLM-based entity extraction.

Default mode: audit (50 chunks) — verify entity extraction quality first.
Full mode: --full flag — ingest all chunks after audit passes.

Book manifest tracking:
  Tracks which book_titles have already been ingested in
  graphrag_storage/ingested_books.json. Re-running on the same book is
  skipped unless --replace is passed.

Usage:
    python scripts/ingest_graphrag.py data/chunks_backup.json
    python scripts/ingest_graphrag.py data/chunks_backup.json --full
    python scripts/ingest_graphrag.py data/chunks_backup.json --replace
    python scripts/ingest_graphrag.py data/chunks_backup.json --full --model deepseek-chat

The chunks JSON must match the Phase 1 backup format:
    [{"text": "...", "metadata": {"book_title": "...", "chapter": "...", ...}}]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

MANIFEST_PATH = Path(settings.graphrag_working_dir) / "ingested_books.json"


def get_ingested_books() -> set:
    """Return set of book titles already ingested into GraphRAG."""
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
    return set()


def mark_book_ingested(book_title: str) -> None:
    """Record a book title as ingested in the GraphRAG manifest."""
    books = get_ingested_books()
    books.add(book_title)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(sorted(books), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Phase 1 chunks into fast-graphrag knowledge graph"
    )
    parser.add_argument(
        "chunks_path",
        help="Path to Phase 1 chunks JSON backup file",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full ingestion (default: 50-chunk audit mode)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Re-ingest book even if already in GraphRAG manifest",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override GraphRAG extraction model (e.g. deepseek-chat). "
        "Defaults to GRAPHRAG_LLM_MODEL in .env.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of documents per insert() call (default: 200). "
        "Smaller batches reduce LLM output size during graph building.",
    )
    args = parser.parse_args()

    chunks_data = json.loads(Path(args.chunks_path).read_text(encoding="utf-8"))
    if chunks_data:
        book_title = chunks_data[0].get("metadata", {}).get("book_title", "unknown")
    else:
        book_title = "unknown"

    ingested = get_ingested_books()
    if book_title in ingested and not args.replace and not args.full:
        print(f"Book '{book_title}' already in GraphRAG manifest. Use --replace to re-ingest.")
        sys.exit(0)

    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_graphrag

    result = ingest_chunks_to_graphrag(
        args.chunks_path, audit_mode=not args.full, llm_model=args.model, batch_size=args.batch_size
    )

    if args.full and result["failed"] == 0:
        mark_book_ingested(book_title)

    print(
        f"\nIngestion complete: {result['ingested']}/{result['total']} chunks ingested, "
        f"{result['failed']} failed"
    )


if __name__ == "__main__":
    main()
