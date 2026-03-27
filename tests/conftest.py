import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a minimal test PDF for triage testing."""
    pdf_file = tmp_path / "test_textbook.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test content")
    return pdf_file


@pytest.fixture
def sample_markdown():
    """Sample parsed Markdown with page markers and mixed content."""
    return '''# Chapter 5: Break-Even Analysis
<!-- PAGE_START:168 -->
Break-even point (*titik impas*) adalah volume penjualan di mana total revenue sama dengan total cost.

## Formula BEP

<!-- PAGE_START:169 -->
$$BEP = \\frac{Fixed\\ Cost}{Price - Variable\\ Cost\\ per\\ Unit}$$

Penjelasan: BEP unit dihitung dengan membagi biaya tetap total dengan margin kontribusi per unit.

## Tabel Contoh

| Item | Amount |
| --- | --- |
| Fixed Cost | 100,000 |
| Variable Cost/Unit | 20 |
| Selling Price/Unit | 50 |
| BEP Units | 3,333 |

<!-- PAGE_START:170 -->
## Contoh Soal

PT Maju memiliki biaya tetap Rp 100.000.000 dan margin kontribusi per unit Rp 30.000. Hitung BEP.
'''


@pytest.fixture
def mock_siliconflow():
    """Mock SiliconFlow API client for embedding, generation, and reranking."""
    with patch("src.llm.client.get_openai_client") as mock:
        client = MagicMock()
        # Mock embedding response
        embed_response = MagicMock()
        embed_item = MagicMock()
        embed_item.embedding = [0.1] * 1024
        embed_response.data = [embed_item]
        client.embeddings.create.return_value = embed_response
        # Mock chat completion response
        chat_response = MagicMock()
        chat_choice = MagicMock()
        chat_choice.message.content = "Test response with citation: Horngren, *Cost Accounting*, Chapter 5, hal. 168-170"
        chat_response.choices = [chat_choice]
        client.chat.completions.create.return_value = chat_response
        mock.return_value = client
        yield client


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for indexing and search tests."""
    client = MagicMock()
    client.collection_exists.return_value = False
    # Mock search results
    search_result = MagicMock()
    search_result.id = "chunk-001"
    search_result.score = 0.92
    search_result.payload = {
        "text": "Break-even point is the volume...",
        "book_title": "Cost Accounting",
        "chapter": "Chapter 5",
        "section_path": "Part II > Chapter 5 > Break-Even Analysis",
        "content_type": "narrative_text",
        "page_start": 168,
        "page_end": 170,
    }
    client.query_points.return_value = MagicMock(points=[search_result])
    yield client


@pytest.fixture
def sample_chunks():
    """Sample chunk dicts with full metadata."""
    return [
        {
            "text": "Break-even point is the volume of sales at which total revenue equals total cost.",
            "metadata": {
                "book_title": "Cost Accounting",
                "author": "Horngren",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5 > Break-Even Analysis",
                "content_type": "narrative_text",
                "page_start": 168,
                "page_end": 170,
            }
        },
        {
            "text": "$$BEP = \\frac{Fixed Cost}{Price - Variable Cost per Unit}$$\nBEP unit dihitung dengan membagi biaya tetap total dengan margin kontribusi per unit.",
            "metadata": {
                "book_title": "Cost Accounting",
                "author": "Horngren",
                "chapter": "Chapter 5",
                "section_path": "Part II > Chapter 5 > Break-Even Analysis > Formula BEP",
                "content_type": "formula",
                "page_start": 169,
                "page_end": 169,
            }
        },
    ]
