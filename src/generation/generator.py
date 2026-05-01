import logging

from config.glossary import GLOSSARY
from config.prompts import compose_system_prompt
from src.generation.citation_builder import build_citations
from src.llm.client import generate
from src.monitoring.langfuse_client import update_token_usage

logger = logging.getLogger(__name__)


def _build_glossary_snippet(max_terms: int = 50) -> str:
    """Return first N glossary terms as newline-delimited 'en = id' string."""
    terms = list(GLOSSARY.items())[:max_terms]
    return "\n".join(f"- {en} = {id_}" for en, id_ in terms)


def _build_context_block(docs: list[dict]) -> str:
    """Build numbered context block; consulting → [Kerangka N], accounting → [Sumber N] (RETR-03)."""
    blocks = []
    for i, doc in enumerate(docs, 1):
        meta = doc.get("metadata", {})
        domain = meta.get("source_domain", "accounting")
        label = "Kerangka" if domain == "consulting" else "Sumber"
        source = f"{meta.get('book_title', 'Unknown')}, {meta.get('chapter', '')}, hal. {meta.get('page_start', '?')}"
        blocks.append(f"[{label} {i}: {source}]\n{doc['text']}")
    return "\n\n---\n\n".join(blocks)


def generate_response(
    query: str,
    context_docs: list[dict],
    graph_context: str = "",
    query_type: str = "Simple",
    conversation_history: list[dict] | None = None,
    protocol_key: str = "general",  # Phase 6: protocol-driven prompt composition
) -> dict:
    """Return {'response': str, 'citations': list} from retrieved docs using modular prompt composition."""
    glossary_snippet = _build_glossary_snippet()
    context_block = _build_context_block(context_docs)

    # Phase 6: Modular prompt composition via KPE protocol registry (PROT-04)
    system_prompt = compose_system_prompt(
        protocol_key=protocol_key,
        glossary_snippet=glossary_snippet,
        is_calculation=(query_type == "Calculation"),
        has_graph_context=bool(graph_context),
    )

    # Phase 3: Conversation history — last 5 turns (10 messages max)
    history = (conversation_history or [])[-10:]

    # Build user content per prompt variant
    if query_type == "Calculation":
        user_content = f"Konteks dari textbook:\n\n{context_block}\n\nPertanyaan: {query}"
    elif graph_context:
        user_content = (
            f"Konteks dari knowledge graph:\n{graph_context}\n\n"
            f"Konteks dari textbook passages:\n{context_block}\n\n"
            f"Pertanyaan: {query}\n\n"
            "Instruksi: Sebutkan secara eksplisit sumber textbook (nama pengarang) "
            "untuk setiap klaim yang berbeda antara penulis."
        )
    else:
        user_content = f"Konteks dari textbook:\n\n{context_block}\n\nPertanyaan: {query}"

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_content},
    ]

    llm_result = generate(messages, temperature=0.3, return_usage=True)
    if isinstance(llm_result, dict):
        response_text = llm_result["text"]
        usage = llm_result.get("usage", {})
        if usage:
            update_token_usage(
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
            )
    else:
        response_text = llm_result
    citations = build_citations(context_docs)

    return {
        "response": response_text,
        "citations": citations,
    }
