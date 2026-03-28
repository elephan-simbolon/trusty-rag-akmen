from pathlib import Path
from unittest.mock import MagicMock, patch


def test_pymupdf_classifies_text_pdf(tmp_path):
    """INGEST-03: PyMuPDF correctly classifies text-based vs scanned PDF."""
    import pymupdf

    from src.ingestion.parsing.router import classify_pdf

    # Create a text-heavy PDF with enough characters per page
    text_pdf_path = tmp_path / "text_book.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    # Insert substantial text (well over 100 chars) so it classifies as text-based
    long_text = (
        "This is a sample accounting textbook page about cost accounting. "
        "Break-even analysis is a technique for studying the relationship "
        "between fixed costs, variable costs, profits and sales volume. "
        "The break-even point is where total revenue equals total cost. "
        "Fixed costs remain constant regardless of output level. "
        "Variable costs change proportionally with output changes. "
    )
    page.insert_text((50, 100), long_text)
    doc.save(str(text_pdf_path))
    doc.close()

    result = classify_pdf(text_pdf_path)
    assert result == "text-based", f"Expected 'text-based', got '{result}'"

    # Create an image-heavy PDF with minimal text (simulated scanned PDF)
    scanned_pdf_path = tmp_path / "scanned_book.pdf"
    doc2 = pymupdf.open()
    doc2.new_page()  # blank page — 0 chars
    doc2.save(str(scanned_pdf_path))
    doc2.close()

    result2 = classify_pdf(scanned_pdf_path)
    assert result2 == "scanned", f"Expected 'scanned', got '{result2}'"


def test_docling_parses_text_pdf(tmp_path):
    """INGEST-01: Docling parses a text-based PDF and returns structured Markdown."""
    import sys

    sample_markdown = (
        "# Chapter 5: Break-Even Analysis\n\nBreak-even point is where revenue equals cost.\n"
    )
    pdf_path = str(tmp_path / "test.pdf")
    output_dir = str(tmp_path / "output")

    # Build mock result that the converter will return
    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = sample_markdown

    # Build mock converter
    mock_converter = MagicMock()
    mock_converter.convert.return_value = mock_result
    mock_converter_cls = MagicMock(return_value=mock_converter)

    # Build mock AcceleratorDevice enum
    mock_accelerator_device = MagicMock()
    mock_accelerator_device.CUDA = "cuda"

    # Build mock modules for docling (not installed in test env)
    mock_docling_converter = MagicMock()
    mock_docling_converter.DocumentConverter = mock_converter_cls

    mock_input_format = MagicMock()
    mock_input_format.PDF = "pdf"

    mock_docling_base = MagicMock()
    mock_docling_base.InputFormat = mock_input_format

    mock_pipeline_options_mod = MagicMock()
    mock_pipeline_options_mod.PdfPipelineOptions = MagicMock()
    mock_pipeline_options_mod.AcceleratorOptions = MagicMock()
    mock_pipeline_options_mod.AcceleratorDevice = mock_accelerator_device

    fake_modules = {
        "docling": MagicMock(),
        "docling.document_converter": mock_docling_converter,
        "docling.datamodel": MagicMock(),
        "docling.datamodel.base_models": mock_docling_base,
        "docling.datamodel.pipeline_options": mock_pipeline_options_mod,
        "docling.backend": MagicMock(),
        "docling.backend.pypdfium2_backend": MagicMock(),
    }

    # Inject mock modules and reload docling_parser so it picks them up
    with patch.dict(sys.modules, fake_modules):
        # Force reimport of docling_parser with the mocked modules
        import importlib

        import src.ingestion.parsing.docling_parser as dp_module

        importlib.reload(dp_module)

        with patch.object(dp_module, "vram_cleanup") as mock_cleanup:
            result = dp_module.parse_with_docling(pdf_path, output_dir)

    # Verify return dict has required keys
    assert "markdown_path" in result, "Result must contain 'markdown_path'"
    assert "markdown_text" in result, "Result must contain 'markdown_text'"
    assert result["markdown_text"] == sample_markdown

    # Verify the .md file was written to disk
    md_file = Path(result["markdown_path"])
    assert md_file.exists(), f"Markdown file should exist at {md_file}"
    assert md_file.read_text(encoding="utf-8") == sample_markdown

    # Verify vram_cleanup was called (always in finally block)
    mock_cleanup.assert_called_once()


def test_mineru_subprocess_isolation(tmp_path):
    """INGEST-02: MinerU runs in a subprocess to avoid VRAM fragmentation (issue #3399)."""
    from unittest.mock import MagicMock

    from src.ingestion.parsing.mineru_parser import parse_with_mineru

    pdf_path = str(tmp_path / "scanned_book.pdf")
    output_dir = str(tmp_path / "output")

    # Create dummy PDF file so path is valid
    Path(pdf_path).write_bytes(b"%PDF-1.4 minimal")

    # Create the expected MinerU output markdown file
    # MinerU outputs to {output_dir}/{pdf_stem}*.md
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    expected_md = output_path / "scanned_book.md"
    expected_md.write_text("# Parsed Content\n\nScanned book content.", encoding="utf-8")

    # Mock subprocess.run to return success
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    captured_env = {}

    def fake_subprocess_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        return mock_result

    with patch(
        "src.ingestion.parsing.mineru_parser.subprocess.run", side_effect=fake_subprocess_run
    ) as mock_run:
        result = parse_with_mineru(pdf_path, output_dir)

    # Assert subprocess was called
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd = call_args[0][0]  # first positional arg is the command list

    # Assert -b pipeline flag is present (MinerU 2.7.6 uses short -b flag)
    assert "-b" in cmd, "Command must include -b flag"
    backend_idx = cmd.index("-b")
    assert cmd[backend_idx + 1] == "pipeline", "Backend must be 'pipeline', not 'auto'"

    # Assert --vram 6 flag is present
    assert "--vram" in cmd, "Command must include --vram flag"
    vram_idx = cmd.index("--vram")
    assert cmd[vram_idx + 1] == "6", "VRAM must be set to 6 GB"

    # Assert PYTORCH_CUDA_ALLOC_CONF is in the env passed to subprocess
    assert "PYTORCH_CUDA_ALLOC_CONF" in captured_env, (
        "PYTORCH_CUDA_ALLOC_CONF must be passed in subprocess env"
    )

    # Assert result has correct keys
    assert "markdown_path" in result
    assert "markdown_text" in result
    assert result["markdown_text"] == "# Parsed Content\n\nScanned book content."
