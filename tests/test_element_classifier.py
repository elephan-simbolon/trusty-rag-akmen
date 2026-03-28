from src.ingestion.chunking.classifier import ContentType, classify_element


def test_classify_narrative():
    """CHUNK-01: Element classifier correctly identifies narrative_text content type."""
    text = "Break-even point is the volume of sales at which total revenue equals total cost."
    assert classify_element(text) == ContentType.NARRATIVE_TEXT


def test_classify_table():
    """CHUNK-01: Element classifier correctly identifies table content type."""
    table = (
        "| Item | Amount | Unit |\n"
        "| --- | --- | --- |\n"
        "| Fixed Cost | 100,000 | IDR |\n"
        "| Variable Cost/Unit | 20 | IDR |\n"
        "| Selling Price/Unit | 50 | IDR |\n"
    )
    assert classify_element(table) == ContentType.TABLE


def test_classify_formula():
    """CHUNK-01: Element classifier correctly identifies formula content type (LaTeX markers)."""
    text = "$$BEP = \\frac{FC}{P - VC}$$\nExplanation text about the formula."
    assert classify_element(text) == ContentType.FORMULA


def test_classify_diagram():
    """CHUNK-01: Element classifier correctly identifies diagram content type."""
    text = "Figure 5.1: Cost Behavior Diagram"
    assert classify_element(text) == ContentType.DIAGRAM


def test_classify_example_problem():
    """CHUNK-01: Element classifier correctly identifies example_problem content type."""
    text = "Example 5.3: Calculate the BEP for PT Maju with fixed costs of Rp 100,000,000."
    assert classify_element(text) == ContentType.EXAMPLE_PROBLEM
