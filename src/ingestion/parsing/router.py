"""PDF routing: PyMuPDF triage → Docling (text-based) or MinerU (scanned), with mutual fallback."""

import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


def classify_pdf(pdf_path: str | Path) -> str:
    """Classify PDF as 'text-based' or 'scanned' via PyMuPDF text density sampling."""
    doc = pymupdf.open(str(pdf_path))
    sample_pages = min(5, len(doc))
    total_chars = sum(len(doc[i].get_text()) for i in range(sample_pages))
    doc.close()
    avg_chars = total_chars / max(sample_pages, 1)
    classification = "text-based" if avg_chars > 100 else "scanned"
    logger.info(f"PDF {pdf_path}: {avg_chars:.0f} chars/page avg -> {classification}")
    return classification


def route_and_parse(pdf_path: str | Path, output_dir: str | Path) -> dict:
    """Route PDF to parser with mutual fallback per Trusty_RAG_Akmen.md Section D."""
    from src.ingestion.parsing.docling_parser import parse_with_docling
    from src.ingestion.parsing.mineru_parser import parse_with_mineru

    pdf_type = classify_pdf(pdf_path)
    primary, fallback = (
        (parse_with_docling, parse_with_mineru)
        if pdf_type == "text-based"
        else (parse_with_mineru, parse_with_docling)
    )
    primary_name = "docling" if pdf_type == "text-based" else "mineru"
    fallback_name = "mineru" if pdf_type == "text-based" else "docling"

    try:
        result = primary(str(pdf_path), str(output_dir))
        result["parser_used"] = primary_name
    except Exception as e:
        logger.warning(
            f"{primary_name} failed for {pdf_path}: {e} — falling back to {fallback_name}"
        )
        result = fallback(str(pdf_path), str(output_dir))
        result["parser_used"] = fallback_name

    result["pdf_path"] = str(pdf_path)
    return result
