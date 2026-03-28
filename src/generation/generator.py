import logging
from config.prompts import SYSTEM_PROMPT_GENERATOR, SYSTEM_PROMPT_SYNTHESIS, SYSTEM_PROMPT_GENERATOR_CALCULATION
from config.glossary import GLOSSARY
from src.llm.client import generate
from src.generation.citation_builder import build_citations
from src.monitoring.langfuse_client import update_token_usage

logger = logging.getLogger(__name__)


def _build_glossary_snippet(max_terms: int = 50) -> str:
    """Build a compact glossary snippet for the system prompt."""
    terms = list(GLOSSARY.items())[:max_terms]
    return "\n".join(f"- {en} = {id_}" for en, id_ in terms)


def _build_context_block(docs: list[dict]) -> str:
    """Build context block from retrieved documents for the LLM."""
    blocks = []
    for i, doc in enumerate(docs, 1):
        meta = doc.get("metadata", {})
        source = f"{meta.get('book_title', 'Unknown')}, {meta.get('chapter', '')}, hal. {meta.get('page_start', '?')}"
        blocks.append(f"[Sumber {i}: {source}]\n{doc['text']}")
    return "\n\n---\n\n".join(blocks)


def generate_response(
    query: str,
    context_docs: list[dict],
    graph_context: str = "",
    query_type: str = "Simple",
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Generate a bilingual response (Indonesian prose + English technical terms)
    with citations from retrieved context.

    Phase 3: query_type selects the prompt variant:
    - "Calculation" → SYSTEM_PROMPT_GENERATOR_CALCULATION (step-by-step + disclaimer)
    - Other + graph_context → SYSTEM_PROMPT_SYNTHESIS (multi-source attribution)
    - Other + no graph_context → SYSTEM_PROMPT_GENERATOR (standard)

    conversation_history injects last 5 turns (10 messages) for follow-up support (UI-02).
    Backward compatible: callers not providing new params get previous behavior.

    Returns: dict with 'response' (str) and 'citations' (list[dict]).
    """
    glossary_snippet = _build_glossary_snippet()
    context_block = _build_context_block(context_docs)

    # Phase 3: Select prompt variant by query_type
    if query_type == "Calculation":
        system_prompt = SYSTEM_PROMPT_GENERATOR_CALCULATION.format(
            glossary_snippet=glossary_snippet
        )
    elif graph_context:
        system_prompt = SYSTEM_PROMPT_SYNTHESIS.format(glossary_snippet=glossary_snippet)
    else:
        system_prompt = SYSTEM_PROMPT_GENERATOR.format(glossary_snippet=glossary_snippet)

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
