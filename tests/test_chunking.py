import pytest
from src.ingestion.chunking.structure_splitter import split_by_headings
from src.ingestion.chunking.content_splitter import split_narrative, split_large_table
from src.ingestion.chunking.hierarchy_builder import build_hierarchy
from src.ingestion.chunking.formula_indexer import create_formula_index
from src.ingestion.chunking.metadata_enricher import enrich_metadata, validate_metadata


def test_heading_hierarchy_split():
    """CHUNK-02: Primary split by heading hierarchy preserves Part > Chapter > Section breadcrumb."""
    md = "# Chapter 5\n\nIntro text\n\n## Section A\n\nSection A text\n\n### Subsection\n\nSub text"
    sections = split_by_headings(md)
    assert len(sections) == 3
    # sections[1] is "Section A" with breadcrumb ["Chapter 5", "Section A"]
    assert "Chapter 5" in sections[1].breadcrumb
    assert "Section A" in sections[1].breadcrumb
    # sections[2] is "Subsection" with 3 breadcrumb entries
    assert len(sections[2].breadcrumb) == 3


def test_narrative_chunk_size():
    """CHUNK-03: Narrative text chunks are <= 512 tokens with 75-token overlap."""
    # Create a 3000-char narrative string
    text = "Break-even point is the volume of sales. " * 75  # ~3000 chars
    chunks = split_narrative(text, max_tokens=512, overlap_tokens=75)
    max_chars = 512 * 4
    for chunk in chunks:
        assert len(chunk) <= max_chars
    assert len(chunks) >= 2


def test_table_header_repeat():
    """CHUNK-03: Large tables split with header row repeated on each chunk."""
    header = "| Col A | Col B | Col C |"
    separator = "| --- | --- | --- |"
    data_rows = [f"| Row {i} | Val {i} | X{i} |" for i in range(30)]
    table = "\n".join([header, separator] + data_rows)

    result = split_large_table(table, max_rows=20)
    assert len(result) == 2
    # Both chunks start with same header line
    assert result[0].startswith(header)
    assert result[1].startswith(header)
    # Both chunks contain the separator
    assert separator in result[0]
    assert separator in result[1]


def test_hierarchy_builder_parent_child():
    """CHUNK-04: HierarchicalNodeParser creates parent (1000-1500t) and child (200-512t) nodes."""
    # Create 6 chunk dicts with ~300-token texts (~1200 chars each).
    # Each chunk is ~312 tokens; 1500 // 312 = 4 chunks per parent max.
    # With 6 chunks: first parent gets 4 children, second parent gets 2 children.
    chunks = [
        {
            "text": ("Break-even analysis text. " * 50),  # ~1250 chars ~312 tokens
            "metadata": {"book_title": "Cost Accounting", "chapter": "Chapter 5", "content_type": "narrative_text"}
        }
        for _ in range(6)
    ]
    nodes = build_hierarchy(chunks)

    # There should be parent nodes (at least 2 since 6 chunks exceed 1500t limit)
    parent_nodes = [n for n in nodes if n.node_type == "parent"]
    assert len(parent_nodes) >= 2

    # Child nodes have parent_id set
    child_nodes = [n for n in nodes if n.node_type == "child"]
    assert len(child_nodes) >= 2
    for child in child_nodes:
        assert child.parent_id is not None

    # First parent (with multiple children) has longer text than any single child
    first_parent = parent_nodes[0]
    first_parent_children = [c for c in child_nodes if c.parent_id == first_parent.chunk_id]
    assert len(first_parent_children) >= 2
    assert len(first_parent.text) > len(first_parent_children[0].text)


def test_formula_index_creation():
    """CHUNK-07: Formula index chunk per chapter lists key formulas with LaTeX + natural language description."""
    chunks = [
        {
            "text": "The BEP formula is: $$BEP = FC / (P - VC)$$ This is the break-even point formula.",
            "metadata": {"content_type": "formula"}
        },
        {
            "text": "Narrative text about cost accounting principles without any formula.",
            "metadata": {"content_type": "narrative_text"}
        },
        {
            "text": "Contribution margin: $$CM = P - VC$$ measures the profit per unit sold.",
            "metadata": {"content_type": "formula"}
        },
    ]
    result = create_formula_index(chunks, chapter="Chapter 5", book_title="Cost Accounting")

    assert result is not None
    assert "Formula Index" in result["text"]
    assert "$$BEP" in result["text"]
    assert "$$CM" in result["text"]
    assert result["metadata"]["content_type"] == "formula_index"
    assert result["metadata"]["is_formula_index"] is True


def test_metadata_enrichment():
    """CHUNK-08: Metadata enricher extracts page range, strips markers, attaches all required fields."""
    chunk_text = (
        "<!-- PAGE_START:168 -->\n"
        "Break-even point is the volume of sales at which total revenue equals total cost.\n"
        "<!-- PAGE_START:170 -->\n"
        "Further discussion of BEP continues here."
    )
    result = enrich_metadata(
        chunk_text,
        book_title="Cost Accounting",
        chapter="Chapter 5",
        section_path="Chapter 5 > BEP",
    )

    assert result["metadata"]["page_start"] == 168
    assert result["metadata"]["page_end"] == 170
    assert "<!-- PAGE_START" not in result["text"]
    assert result["metadata"]["book_title"] == "Cost Accounting"
    # All required metadata fields must be present
    missing = validate_metadata(result)
    assert missing == []
