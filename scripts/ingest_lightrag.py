"""CLI entry point for LightRAG knowledge graph ingestion.

Reads Phase 1 chunks from a JSON backup file and inserts them into the
LightRAG knowledge graph via Qwen3-30B-A3B entity extraction.

Default mode: audit (50 chunks) — verify entity extraction quality first.
Full mode: --full flag — ingest all chunks after audit passes.
Resume mode: --resume flag — process PENDING/FAILED docs without re-enqueuing.

Book manifest tracking (INGEST-06 / Pitfall 4):
  Tracks which book_titles have already been ingested into LightRAG in
  lightrag_storage/ingested_books.json. Re-running on the same book is
  skipped unless --replace is passed (avoids redundant entity extraction
  which is expensive in SiliconFlow API credits).

Usage:
    python scripts/ingest_lightrag.py data/chunks_backup.json
    python scripts/ingest_lightrag.py data/chunks_backup.json --full
    python scripts/ingest_lightrag.py data/chunks_backup.json --replace
    python scripts/ingest_lightrag.py data/chunks_backup.json --resume

The chunks JSON must match the Phase 1 backup format:
    [{"text": "...", "metadata": {"book_title": "...", "chapter": "...", ...}}]
"""

import argparse
import asyncio
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

MANIFEST_PATH = Path(settings.lightrag_working_dir) / "ingested_books.json"


def get_ingested_books() -> set:
    """Return set of book titles already ingested into LightRAG."""
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
    return set()


def mark_book_ingested(book_title: str) -> None:
    """Record a book title as ingested in the LightRAG manifest."""
    books = get_ingested_books()
    books.add(book_title)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(sorted(books), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Phase 1 chunks into LightRAG knowledge graph"
    )
    parser.add_argument(
        "chunks_path",
        nargs="?",
        default=None,
        help="Path to Phase 1 chunks JSON backup file (not required for --clean-duplicates)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full ingestion (default: 50-chunk audit mode)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Re-ingest book even if already in LightRAG manifest",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted ingestion — process PENDING/FAILED docs without re-enqueuing. "
        "Run --clean-duplicates first if previous --full created duplicate records.",
    )
    parser.add_argument(
        "--clean-duplicates",
        action="store_true",
        help="Remove dup- FAILED records from doc_status created by re-enqueue",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override LightRAG extraction model (e.g. deepseek-chat, Qwen/Qwen3-30B-A3B-Instruct-2507). "
        "Defaults to LIGHTRAG_LLM_MODEL in .env.",
    )
    args = parser.parse_args()

    # --- Early-exit commands (no chunks_path needed) ---

    if args.clean_duplicates:
        from src.knowledge_graph.graph_ingestion import clean_duplicate_doc_status

        removed = asyncio.run(clean_duplicate_doc_status())
        print(f"\nCleaned {removed} duplicate records from doc_status")
        sys.exit(0)

    if args.resume:
        # Resume path: reprocess PENDING/FAILED docs from doc_status — no file needed
        from src.knowledge_graph.graph_ingestion import resume_lightrag_ingestion

        result = asyncio.run(resume_lightrag_ingestion(llm_model=args.model))
        print(
            f"\nResume complete: {result['ingested']}/{result['total']} chunks processed, "
            f"{result['real_failed']} failed, {result['duplicates']} duplicates"
        )
        sys.exit(0)

    # --- Ingestion commands (chunks_path required) ---

    if not args.chunks_path:
        parser.error("chunks_path is required (unless using --resume or --clean-duplicates)")

    # Read chunks to extract book_title from first chunk metadata
    chunks_data = json.loads(Path(args.chunks_path).read_text(encoding="utf-8"))
    if chunks_data:
        book_title = chunks_data[0].get("metadata", {}).get("book_title", "unknown")
    else:
        book_title = "unknown"

    # Book manifest check (INGEST-06): skip if already ingested unless --replace/--full
    ingested = get_ingested_books()
    if book_title in ingested and not args.replace and not args.full:
        print(f"Book '{book_title}' already in LightRAG manifest. Use --replace to re-ingest.")
        sys.exit(0)

    # Ingestion path: enqueue + process from chunks file
    from src.knowledge_graph.graph_ingestion import ingest_chunks_to_lightrag

    result = asyncio.run(
        ingest_chunks_to_lightrag(args.chunks_path, audit_mode=not args.full, llm_model=args.model)
    )

    # Record book as ingested only if processing completed with no failures (Pitfall 6)
    if args.full and result["failed"] == 0:
        mark_book_ingested(book_title)

    print(
        f"\nIngestion complete: {result['ingested']}/{result['total']} chunks ingested, "
        f"{result['real_failed']} failed, {result['duplicates']} duplicates"
    )


if __name__ == "__main__":
    main()
