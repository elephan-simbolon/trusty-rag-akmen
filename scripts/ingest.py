"""CLI entry point for ingesting PDF textbooks into the RAG pipeline.

Usage:
    python scripts/ingest.py path/to/textbook.pdf
    python scripts/ingest.py data/pdfs/ --book-title "Cost Accounting"
    python scripts/ingest.py book1.pdf book2.pdf --output-dir data/parsed
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging before imports so module-level loggers are configured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDF textbooks into Trusty RAG Akmen"
    )
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        help="Path(s) to PDF files or directory containing PDFs",
    )
    parser.add_argument(
        "--output-dir",
        default="data/parsed",
        help="Directory for parsed output (default: data/parsed)",
    )
    parser.add_argument(
        "--book-title",
        default="",
        help="Book title for metadata (default: derived from filename)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing book chunks in Qdrant (delete old + re-ingest). Without this flag, ingesting an already-indexed book raises an error.",
    )
    parser.add_argument(
        "--contextual",
        action="store_true",
        help="Enable contextual window embedding: prepend parent section text to each chunk before embedding (CHUNK-05). Increases embedding token cost ~15-25%%.",
    )
    args = parser.parse_args()

    # Collect PDF files
    pdf_files = []
    for p in args.pdf_paths:
        path = Path(p)
        if path.is_dir():
            pdf_files.extend(sorted(path.glob("*.pdf")))
        elif path.suffix.lower() == ".pdf":
            pdf_files.append(path)
        else:
            logger.warning(f"Skipping non-PDF: {path}")

    if not pdf_files:
        logger.error("No PDF files found")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDF(s) to ingest")

    from src.ingestion.pipeline import run_ingestion_pipeline

    success_count = 0
    for pdf in pdf_files:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Ingesting: {pdf}")
        logger.info(f"{'=' * 60}")
        try:
            result = run_ingestion_pipeline(
                pdf_path=str(pdf),
                output_dir=args.output_dir,
                book_title=args.book_title or pdf.stem,
                replace_existing=args.replace,
                use_contextual=args.contextual,
            )
            if result.get("skipped"):
                logger.info(f"SKIPPED: {pdf} — already in Qdrant")
            else:
                logger.info(f"SUCCESS: {result}")
                success_count += 1
        except Exception as e:
            logger.error(f"FAILED: {pdf} — {e}")
            continue

    logger.info(f"\nCompleted: {success_count}/{len(pdf_files)} PDFs ingested successfully")


if __name__ == "__main__":
    main()
