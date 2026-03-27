from src.llm.client import embed_query, embed_document
from config.settings import settings


def test_query_embedding_has_prefix(mock_siliconflow):
    """INDEX-05: embed_query() prepends instruction prefix before calling the embedding API."""
    embed_query("apa itu break-even point?")
    call_args = mock_siliconflow.embeddings.create.call_args
    # The input passed to the API must include the instruction prefix
    assert settings.embedding_query_instruction in call_args.kwargs.get("input", call_args.args[0] if call_args.args else "")
    # Also verify dimensions were passed correctly
    assert call_args.kwargs.get("dimensions") == 1024 or call_args.kwargs.get("dimensions") == settings.embedding_dimensions


def test_document_embedding_no_prefix(mock_siliconflow):
    """INDEX-05: embed_document() does NOT prepend any prefix (asymmetric embedding strategy)."""
    embed_document("Break-even point is...")
    call_args = mock_siliconflow.embeddings.create.call_args
    input_text = call_args.kwargs.get("input", call_args.args[0] if call_args.args else "")
    # Document path must NOT include the instruction prefix
    assert "Instruct:" not in input_text


def test_embed_query_uses_ui_retry_config():
    """UAT-11 gap: embed_query harus pakai fast-fail retry agar UI tidak freeze."""
    import src.llm.client as client_mod
    ui_cfg = client_mod._UI_RETRY_CONFIG
    # Fast-fail: maksimal 2 attempts
    assert ui_cfg["stop"].max_attempt_number == 2, (
        "embed_query harus stop setelah 2 attempts (bukan 5) agar UI tidak freeze"
    )
    # Fast-fail: backoff pendek (min 2s, max 10s)
    assert ui_cfg["wait"].min == 2, "wait min harus 2s untuk UI context"
    assert ui_cfg["wait"].max == 10, "wait max harus 10s untuk UI context"
    # Pastikan _RETRY_CONFIG (batch ingestion) tidak berubah
    batch_cfg = client_mod._RETRY_CONFIG
    assert batch_cfg["stop"].max_attempt_number == 5, (
        "_RETRY_CONFIG untuk batch ingestion harus tetap 5 attempts"
    )


def test_batch_functions_keep_slow_retry():
    """embed_batch dan embed_document harus tetap pakai _RETRY_CONFIG (lambat) untuk ingestion."""
    import src.llm.client as client_mod
    ui_cfg = client_mod._UI_RETRY_CONFIG
    batch_cfg = client_mod._RETRY_CONFIG
    assert ui_cfg["stop"].max_attempt_number != batch_cfg["stop"].max_attempt_number, (
        "_UI_RETRY_CONFIG dan _RETRY_CONFIG harus berbeda — keduanya identik berarti fix tidak diterapkan"
    )
