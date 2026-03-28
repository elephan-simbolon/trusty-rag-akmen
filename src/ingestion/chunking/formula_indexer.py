import logging
import re

logger = logging.getLogger(__name__)

FORMULA_PATTERN = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)


def create_formula_index(
    chunks: list[dict],
    chapter: str,
    book_title: str,
) -> dict | None:
    """
    Create a formula index chunk for a chapter — lists all formulas
    with LaTeX + surrounding natural language description.
    Returns: dict with 'text' and 'metadata' keys, or None if no formulas found.

    The formula index chunk is a high-relevance retrieval target for
    Calculation-type queries (Phase 3 routing).
    """
    formulas = []
    for chunk in chunks:
        content_type = chunk.get("metadata", {}).get("content_type", "")
        text = chunk.get("text", "")

        if content_type == "formula" or FORMULA_PATTERN.search(text):
            # Extract each formula block
            matches = FORMULA_PATTERN.findall(text)
            for match in matches:
                latex = match.strip()
                # Get context around the formula (preceding sentence)
                idx = text.find(f"$${match}$$")
                context_start = max(0, idx - 200)
                context_end = min(len(text), idx + len(match) + 200)
                context = text[context_start:context_end].strip()
                formulas.append(
                    {
                        "latex": latex,
                        "context": context,
                    }
                )

    if not formulas:
        return None

    # Build the formula index text
    lines = [f"# Formula Index — {chapter}"]
    for i, f in enumerate(formulas, 1):
        lines.append(f"\n## Formula {i}")
        lines.append(f"$${f['latex']}$$")
        lines.append(f"Context: {f['context']}")

    formula_index_text = "\n".join(lines)

    return {
        "text": formula_index_text,
        "metadata": {
            "book_title": book_title,
            "chapter": chapter,
            "section_path": f"{chapter} > Formula Index",
            "content_type": "formula_index",
            "page_start": 0,
            "page_end": 0,
            "is_formula_index": True,
        },
    }
