"""Docling PDF parser with PyPdfium2 backend for memory-safe large PDF processing."""

import logging
from pathlib import Path

from src.ingestion.parsing.gpu_utils import vram_cleanup

logger = logging.getLogger(__name__)


def parse_with_docling(pdf_path: str, output_dir: str) -> dict:
    """Parse a text-based PDF using Docling with CUDA + PyPdfium2 backend."""
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        AcceleratorDevice,
        AcceleratorOptions,
        PdfPipelineOptions,
        RapidOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(
            num_threads=4,
            device=AcceleratorDevice.CUDA,
        ),
        ocr_options=RapidOcrOptions(
            backend="torch",
            lang=["english"],
        ),
        layout_batch_size=4,
        ocr_batch_size=4,
        table_batch_size=4,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )

    try:
        result = converter.convert(pdf_path)
        markdown_text = result.document.export_to_markdown()

        output_path = Path(output_dir) / (Path(pdf_path).stem + ".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_text, encoding="utf-8")

        logger.info(f"Docling parsed {pdf_path}: {len(markdown_text)} chars")
        return {
            "markdown_path": str(output_path),
            "markdown_text": markdown_text,
        }
    finally:
        try:
            result.input._backend.unload()
        except Exception:
            pass
        vram_cleanup()
