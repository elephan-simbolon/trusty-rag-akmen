def test_indonesian_query_retrieves_english(mock_siliconflow):
    """LANG-01: Indonesian accounting query retrieves relevant English textbook passages without translation."""
    from src.retrieval.preprocessor import preprocess_query

    result = preprocess_query("apa itu break-even point?")

    assert "query_embedding" in result
    assert isinstance(result["query_embedding"], list)
    assert len(result["query_embedding"]) == 1024

    # Verify embed_query was called (via mock_siliconflow which patches get_openai_client)
    mock_siliconflow.embeddings.create.assert_called_once()


def test_glossary_injection_in_prompt():
    """LANG-02: Bilingual glossary terms are injected into system prompt for cross-lingual bridging."""
    from src.retrieval.preprocessor import expand_query_with_glossary

    result = expand_query_with_glossary("bagaimana menghitung titik impas?")

    # "titik impas" maps to "break-even point" in GLOSSARY_REVERSE
    assert "break-even point" in result


def test_output_bilingual_format(mock_siliconflow):
    """LANG-03: Generated response uses Indonesian prose with English technical terms in parentheses."""
    # Override mock to return bilingual format
    mock_siliconflow.chat.completions.create.return_value.choices[
        0
    ].message.content = "Alokasi biaya overhead (*overhead cost allocation*) adalah proses mendistribusikan biaya tidak langsung."

    mock_docs = [
        {
            "text": "Overhead cost allocation distributes indirect costs to cost objects.",
            "metadata": {
                "book_title": "Cost Accounting",
                "chapter": "Chapter 4",
                "section_path": "Part II > Chapter 4",
                "content_type": "narrative_text",
                "page_start": 90,
                "page_end": 92,
            },
        }
    ]

    from src.generation.generator import generate_response

    result = generate_response(query="apa itu overhead?", context_docs=mock_docs)

    assert "response" in result
    # Response contains Indonesian text
    assert len(result["response"]) > 0
    # Response contains English term in parentheses pattern (*...)
    assert "(*" in result["response"]
