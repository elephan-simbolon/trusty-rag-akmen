---
phase: 01-foundation
plan: 02
subsystem: ingestion/parsing
tags: [pdf-parsing, pymupdf, docling, mineru, vram, vlm, diagram-captioning]
dependency_graph:
  requires: ["01-01"]
  provides: ["01-03", "01-04"]
  affects: ["ingestion pipeline", "chunking", "indexing"]
tech_stack:
  added:
    - "src/ingestion/parsing/router.py"
    - "src/ingestion/parsing/docling_parser.py"
    - "src/ingestion/parsing/mineru_parser.py"
    - "src/ingestion/parsing/gpu_utils.py"
    - "src/ingestion/parsing/vlm_captioner.py"
  patterns:
    - "PyMuPDF triage scan (text density threshold 100 chars/page)"
    - "Subprocess isolation for MinerU (VRAM fragmentation fix #3399)"
    - "gc.collect -> empty_cache -> synchronize VRAM cleanup sequence"
    - "base64 image encoding for VLM API payload"
    - "tenacity @retry with exponential backoff on VLM calls"
key_files:
  created:
    - "src/ingestion/parsing/router.py"
    - "src/ingestion/parsing/docling_parser.py"
    - "src/ingestion/parsing/mineru_parser.py"
    - "src/ingestion/parsing/gpu_utils.py"
    - "src/ingestion/parsing/vlm_captioner.py"
  modified:
    - "tests/test_pdf_parser.py"
    - "tests/test_vram_cleanup.py"
    - "tests/test_diagram_extraction.py"
decisions:
  - "[01-02]: sys.modules patching used to mock docling in tests — docling not installed in dev env, lazy imports inside function body require full module injection"
  - "[01-02]: test_mineru_subprocess_isolation creates expected output .md file before mock subprocess runs — validates path discovery logic independently of MinerU binary"
  - "[01-02]: VLM_CAPTION_PROMPT is English-only output instruction — captions feed into English-indexed vector store for cross-lingual retrieval"
metrics:
  duration: "7 min"
  completed: "2026-03-22T05:46:38Z"
  tasks_completed: 3
  files_created: 5
  files_modified: 3
---

# Phase 01 Plan 02: PDF Parsing Pipeline Summary

**One-liner:** Five-module PDF parsing pipeline with PyMuPDF triage, Docling CUDA text-PDF parser, MinerU subprocess-isolated scanned-PDF parser, VRAM cleanup sequence, and Qwen-VL diagram captioner.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | PyMuPDF triage router + Docling parser | d1565d8 | router.py, docling_parser.py, gpu_utils.py, test_pdf_parser.py |
| 2 | MinerU subprocess parser + VRAM tests | 832fb11 | mineru_parser.py, test_vram_cleanup.py, test_pdf_parser.py |
| 3 | VLM diagram captioner | f80519f | vlm_captioner.py, test_diagram_extraction.py |

## What Was Built

### router.py — PDF Triage
- `classify_pdf()` samples first 5 pages, counts characters, returns `"text-based"` if avg > 100 chars/page else `"scanned"`
- `route_and_parse()` dispatches to Docling or MinerU based on classification, adds `parser_used` and `pdf_path` to result dict

### docling_parser.py — Text-PDF Parser
- `parse_with_docling()` configures Docling with `AcceleratorDevice.CUDA`, 4 threads, and `mode = "accurate"` for table structure
- Always calls `vram_cleanup()` in a `finally` block to ensure VRAM release even on exceptions

### gpu_utils.py — VRAM Management
- Sets `PYTORCH_CUDA_ALLOC_CONF` at module import time (before torch is imported) to prevent fragmentation
- `vram_cleanup()` sequence: `gc.collect()` -> `torch.cuda.empty_cache()` -> `torch.cuda.synchronize()` — order matters per MinerU issue #3399
- `check_vram_free()` returns available VRAM in MB for headroom checks

### mineru_parser.py — Scanned-PDF Parser
- `parse_with_mineru()` runs MinerU as a subprocess with `--backend pipeline` and `--vram 6` flags
- CRITICAL: subprocess isolation prevents VRAM accumulation across books (MinerU issue #3399)
- Passes `PYTORCH_CUDA_ALLOC_CONF` explicitly in subprocess env
- 3600-second timeout per book; `if __name__ == "__main__":` guard for direct subprocess entry

### vlm_captioner.py — Diagram Captioner
- `caption_diagram()` encodes image as base64, detects MIME type from extension, calls Qwen-VL via SiliconFlow
- `@retry` decorator: 3 attempts, 30-120s exponential backoff for rate-limit resilience
- `extract_and_caption_diagrams()` finds all images in a directory and captions each with graceful error fallback

## Verification Results

```
pytest tests/test_pdf_parser.py tests/test_vram_cleanup.py tests/test_diagram_extraction.py -v
7 passed in 1.20s
```

All 7 activated tests pass:
- `test_pymupdf_classifies_text_pdf` — classifies text vs scanned by char density
- `test_docling_parses_text_pdf` — mocked Docling, verifies .md output and vram_cleanup call
- `test_mineru_subprocess_isolation` — verifies --backend pipeline, --vram 6, PYTORCH_CUDA_ALLOC_CONF in env
- `test_vram_cleanup_sequence` — asserts gc.collect -> empty_cache -> synchronize call order
- `test_vram_cleanup_between_parsers` — asserts PYTORCH_CUDA_ALLOC_CONF set at module import
- `test_vlm_captioner_returns_description` — mocked SiliconFlow, verifies model and image_url payload
- `test_diagram_image_extraction` — verifies list of dicts with image_path and caption keys

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Docling import patching in test**
- **Found during:** Task 1 test run
- **Issue:** `parse_with_docling()` uses lazy imports inside function body; `patch("src.ingestion.parsing.docling_parser.DocumentConverter")` fails because the attribute doesn't exist at module level
- **Fix:** Used `sys.modules` injection with `patch.dict` to mock the entire docling module tree, then reloaded the parser module with `importlib.reload()`
- **Files modified:** `tests/test_pdf_parser.py`
- **Commit:** d1565d8

**2. [Rule 2 - Missing] Created gpu_utils.py in Task 1 (not Task 2)**
- **Found during:** Task 1 creation of docling_parser.py
- **Issue:** `docling_parser.py` imports `from src.ingestion.parsing.gpu_utils import vram_cleanup` at module level; gpu_utils had to exist before Task 1 tests could run
- **Fix:** Created `gpu_utils.py` as part of Task 1 commit, ahead of Task 2 schedule
- **Files modified:** `src/ingestion/parsing/gpu_utils.py`
- **Commit:** d1565d8

## Self-Check: PASSED

All created files confirmed present on disk. All task commits verified in git log:
- d1565d8: router.py, docling_parser.py, gpu_utils.py, test_pdf_parser.py
- 832fb11: mineru_parser.py, test_vram_cleanup.py, test_pdf_parser.py (Task 2 stubs)
- f80519f: vlm_captioner.py, test_diagram_extraction.py
