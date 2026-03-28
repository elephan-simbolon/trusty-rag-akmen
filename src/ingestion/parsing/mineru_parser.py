import json
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_with_mineru(pdf_path: str, output_dir: str) -> dict:
    """
    Parse a scanned/complex PDF using MinerU in an isolated subprocess.
    CRITICAL: Each book MUST run in a separate subprocess to prevent VRAM accumulation.
    Uses --backend pipeline (NOT auto) and --vram 6 for GTX 1660 Ti.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512,expandable_segments:True"

    # MinerU 2.7.6 rebrand: magic_pdf.cli → mineru executable
    mineru_exe = str(Path(sys.executable).parent / "mineru")
    cmd = [
        mineru_exe,
        "-p",
        str(pdf_path),
        "-o",
        str(output_dir),
        "-b",
        "pipeline",  # NEVER "auto" on GTX 1660 Ti — silent CPU fallback
        "--vram",
        "6",  # 6 GB VRAM limit
        "-d",
        "cuda",
        "-l",
        "en",  # English textbooks
    ]

    logger.info(f"MinerU subprocess: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=3600,  # 1 hour per book
    )

    if result.returncode != 0:
        logger.error(f"MinerU failed: {result.stderr}")
        raise RuntimeError(f"MinerU failed for {pdf_path}: {result.stderr[:500]}")

    # MinerU outputs to {output_dir}/{pdf_stem}/auto/{pdf_stem}.md
    pdf_stem = Path(pdf_path).stem
    markdown_candidates = list(output_path.rglob(f"{pdf_stem}*.md"))
    if not markdown_candidates:
        raise FileNotFoundError(
            f"MinerU produced no Markdown output for {pdf_path} in {output_dir}"
        )

    markdown_path = markdown_candidates[0]
    markdown_text = markdown_path.read_text(encoding="utf-8")

    logger.info(f"MinerU parsed {pdf_path}: {len(markdown_text)} chars -> {markdown_path}")
    return {
        "markdown_path": str(markdown_path),
        "markdown_text": markdown_text,
    }


# Entry point for subprocess isolation (run as module)
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = parse_with_mineru(args.input, args.output)
    print(json.dumps(result))
