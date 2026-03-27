import logging
from config.glossary import GLOSSARY_REVERSE
from src.llm.client import embed_query

logger = logging.getLogger(__name__)


def expand_query_with_glossary(query: str) -> str:
    """
    Expand Indonesian query with English technical terms from glossary.
    If query contains Indonesian accounting term, append its English equivalent.
    This helps BM25 sparse search find exact English terms in textbooks.
    """
    expanded_terms = []
    query_lower = query.lower()
    for id_term, en_term in GLOSSARY_REVERSE.items():
        if id_term.lower() in query_lower:
            expanded_terms.append(en_term)

    if expanded_terms:
        expansion = " ".join(expanded_terms)
        expanded = f"{query} ({expansion})"
        logger.info(f"Query expanded with glossary terms: {expanded_terms}")
        return expanded
    return query


def preprocess_query(query: str) -> dict:
    """
    Full query preprocessing:
    1. Expand with glossary terms for BM25
    2. Embed with instruction prefix for dense search
    Returns: dict with 'original_query', 'expanded_query', 'query_embedding'
    """
    expanded = expand_query_with_glossary(query)
    embedding = embed_query(query)  # embed_query already adds instruction prefix

    return {
        "original_query": query,
        "expanded_query": expanded,
        "query_embedding": embedding,
    }
