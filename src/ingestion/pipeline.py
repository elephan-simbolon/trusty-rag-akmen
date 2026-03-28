"""End-to-end ingestion pipeline: PDF -> parse -> chunk -> embed+upload -> Qdrant."""

import json
import logging
from functools import partial
from pathlib import Path

from config.settings import settings
from src.ingestion.chunking.classifier import classify_element
from src.ingestion.chunking.content_splitter import split_content_by_type
from src.ingestion.chunking.formula_indexer import create_formula_index
from src.ingestion.chunking.hierarchy_builder import build_hierarchy
from src.ingestion.chunking.metadata_enricher import enrich_metadata
from src.ingestion.chunking.structure_splitter import split_by_headings
from src.ingestion.indexing.embedder import embed_chunks_batch
from src.ingestion.indexing.qdrant_uploader import (
    check_book_exists,
    create_collection,
    delete_book,
    health_check,
    upload_batch,
)
from src.ingestion.parsing.router import route_and_parse
from src.ingestion.parsing.vlm_captioner import extract_and_caption_diagrams
from src.services.qdrant_service import get_qdrant_client

logger = logging.getLogger(__name__)


def run_ingestion_pipeline(
    pdf_path: str,
    output_dir: str = "data/parsed",
    chunks_dir: str = "data/chunks",
    book_title: str = "",
    checkpoint_dir: str = "data/checkpoints",
    replace_existing: bool = False,
    use_contextual: bool = False,
) -> dict:
    """End-to-end ingestion: PDF -> parse -> chunk -> embed+upload to Qdrant."""
    pdf_stem = Path(pdf_path).stem
    if not book_title:
        book_title = pdf_stem

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(chunks_dir).mkdir(parents=True, exist_ok=True)
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

    # Incremental ingestion guard (INGEST-06)
    client = get_qdrant_client()
    if health_check(client):
        if client.collection_exists(settings.qdrant_collection_name):
            if check_book_exists(client, book_title):
                if not replace_existing:
                    logger.warning(
                        f"SKIPPED: Book '{book_title}' already exists. Use --replace to re-ingest."
                    )
                    return {
                        "pdf_path": str(pdf_path),
                        "parser_used": "skipped",
                        "total_chunks": 0,
                        "formula_index_chunks": 0,
                        "diagram_captions": 0,
                        "uploaded_points": 0,
                        "skipped": True,
                    }
                logger.info(f"Replacing existing book '{book_title}' — deleting old chunks...")
                delete_book(client, book_title)

    # Delete stale checkpoint when replacing — old checkpoint indices are invalid
    checkpoint_path = str(Path(checkpoint_dir) / f"{pdf_stem}_embed_checkpoint.json")
    if replace_existing:
        cp = Path(checkpoint_path)
        if cp.exists():
            cp.unlink()
            logger.info(f"Deleted stale checkpoint: {checkpoint_path}")

    # Step 1: Parse
    logger.info(f"[1/9] Parsing {pdf_path}...")
    parse_result = route_and_parse(pdf_path, output_dir)
    markdown_text = parse_result["markdown_text"]
    parser_used = parse_result["parser_used"]
    logger.info(f"Parsed with {parser_used}: {len(markdown_text)} chars")

    # Step 2: Diagram captioning
    logger.info("[2/9] Extracting and captioning diagrams...")
    diagram_captions = extract_and_caption_diagrams(output_dir)
    logger.info(f"Captioned {len(diagram_captions)} diagrams")

    # Step 3: Split by headings
    logger.info("[3/9] Splitting by heading hierarchy...")
    sections = split_by_headings(markdown_text, book_title=book_title)
    logger.info(f"Found {len(sections)} sections")

    # Step 4: Classify and split by content type
    logger.info("[4/9] Classifying and splitting by content type...")
    all_chunks = []
    for section in sections:
        content_type = classify_element(section.content)
        sub_chunks = split_content_by_type(section.content, content_type)
        section_path = " > ".join(section.breadcrumb) if section.breadcrumb else section.title
        chapter = section.breadcrumb[1] if len(section.breadcrumb) > 1 else section.title
        for sub in sub_chunks:
            enriched = enrich_metadata(
                chunk_text=sub,
                book_title=book_title,
                chapter=chapter,
                section_path=section_path,
                content_type=content_type.value,
            )
            all_chunks.append(enriched)

    for dc in diagram_captions:
        if not dc["caption"].startswith("[Captioning failed"):
            all_chunks.append(
                {
                    "text": dc["caption"],
                    "metadata": {
                        "book_title": book_title,
                        "chapter": "Diagrams",
                        "section_path": f"{book_title} > Diagrams",
                        "content_type": "diagram",
                        "page_start": 0,
                        "page_end": 0,
                    },
                }
            )

    logger.info(f"Total chunks after splitting: {len(all_chunks)}")

    # Step 5: Build parent-child hierarchy
    logger.info("[5/9] Building parent-child hierarchy...")
    hierarchy_nodes = build_hierarchy(all_chunks)
    child_chunks = [
        {"text": n.text, "metadata": n.metadata} for n in hierarchy_nodes if n.node_type == "child"
    ]
    if not child_chunks:
        child_chunks = all_chunks
    logger.info(f"Child chunks for indexing: {len(child_chunks)}")

    parent_texts: dict[str, str] = {}
    if use_contextual:
        for node in hierarchy_nodes:
            if node.node_type == "parent":
                section_path = node.metadata.get("section_path", "")
                if section_path:
                    parent_texts[section_path] = node.text
        logger.info(f"Collected {len(parent_texts)} parent texts for contextual embedding")

    # Step 6: Create formula index chunks
    logger.info("[6/9] Creating formula index chunks...")
    chapters = set()
    for chunk in child_chunks:
        ch = chunk.get("metadata", {}).get("chapter", "")
        if ch:
            chapters.add(ch)

    formula_chunks = []
    for ch in chapters:
        ch_chunks = [c for c in child_chunks if c.get("metadata", {}).get("chapter") == ch]
        fi = create_formula_index(ch_chunks, chapter=ch, book_title=book_title)
        if fi:
            formula_chunks.append(fi)
    child_chunks.extend(formula_chunks)
    logger.info(f"Added {len(formula_chunks)} formula index chunks")

    # Step 7: Save chunks locally (backup before embedding)
    chunks_file = Path(chunks_dir) / f"{pdf_stem}_chunks.json"
    serializable = [{"text": c["text"], "metadata": c["metadata"]} for c in child_chunks]
    chunks_file.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[7/9] Saved {len(child_chunks)} chunks to {chunks_file}")

    # Step 8+9: Embed and upload per batch (checkpoint resume safe)
    logger.info("[8/9] Embedding and uploading chunks...")
    client = get_qdrant_client()
    if not health_check(client):
        raise ConnectionError("Qdrant health check failed — cannot upload")
    create_collection(client)

    total = embed_chunks_batch(
        child_chunks,
        batch_size=16,
        checkpoint_path=checkpoint_path,
        upload_fn=partial(upload_batch, client),
        use_contextual_window=use_contextual,
        parent_texts=parent_texts if use_contextual else None,
    )
    logger.info(f"[9/9] Embedded and uploaded {total} chunks")

    return {
        "pdf_path": str(pdf_path),
        "parser_used": parser_used,
        "total_chunks": len(child_chunks),
        "formula_index_chunks": len(formula_chunks),
        "diagram_captions": len(diagram_captions),
        "uploaded_points": total,
    }
