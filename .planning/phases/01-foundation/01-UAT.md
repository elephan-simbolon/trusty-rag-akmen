---
status: resolved
phase: 01-foundation
source: 01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md, 01-06-SUMMARY.md
started: 2026-03-22T07:00:00Z
updated: 2026-03-22T11:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running Streamlit server. Dari terminal baru di direktori project, jalankan: `uv run pytest --co -q` (pytest collect tanpa ImportError). Kemudian jalankan: `uv run streamlit run app/main.py` — server boot tanpa errors, UI muncul di localhost:8501 dengan judul "Trusty RAG Akmen".
result: pass

### 2. Project Structure & Dependencies Terpasang
expected: Direktori project memiliki struktur lengkap: `src/llm/`, `src/ingestion/parsing/`, `src/ingestion/chunking/`, `src/ingestion/indexing/`, `src/retrieval/`, `src/agents/`, `src/generation/`, `config/`, `app/`, `scripts/`, `tests/`. File `pyproject.toml` ada dengan semua dependencies (langgraph, qdrant-client, mineru, docling, dll). File `.env.example` ada sebagai template konfigurasi API keys.
result: pass

### 3. Konfigurasi Settings Berjalan Tanpa .env
expected: Jalankan `uv run python -c "from config.settings import Settings; s = Settings(); print('OK', s.embedding_model)"`. Harus mencetak "OK" diikuti nama model embedding — tidak ada error `ValidationError` meski file `.env` kosong atau belum dikonfigurasi.
result: pass

### 4. Glosarium Bilingual Tersedia (125 Istilah)
expected: Jalankan `uv run python -c "from config.glossary import GLOSSARY, GLOSSARY_REVERSE; print(len(GLOSSARY), len(GLOSSARY_REVERSE))"`. Output harus menampilkan dua angka ≥ 125. Contoh istilah: `GLOSSARY['cost accounting']` harus mengembalikan terjemahan Indonesia seperti 'akuntansi biaya'.
result: pass

### 5. Semua Test Suite Lulus (pytest)
expected: Jalankan `uv run pytest -v --tb=short`. Semua test yang aktif harus pass (bukan skip). Tidak ada `FAILED` atau `ERROR`. Summary akhir menunjukkan angka passed ≥ 14.
result: pass

### 6. PDF Parsing — Klasifikasi Text vs Scanned
expected: Jalankan `uv run python -c "from src.ingestion.parsing.router import classify_pdf; print('classify_pdf OK')"`. Harus print OK tanpa ImportError.
result: pass

### 7. Chunking Pipeline — Import Chain Berjalan
expected: Jalankan `uv run python -c "from src.ingestion.chunking.metadata_enricher import enrich_metadata, validate_metadata; print('chunking OK')"`. Harus print OK.
result: pass

### 8. Ingestion Pipeline CLI Tersedia
expected: Jalankan `uv run python scripts/ingest.py --help`. Harus menampilkan usage/help text — tidak ada ModuleNotFoundError atau ImportError.
result: pass

### 9. LangGraph Query Pipeline Terinisialisasi
expected: Jalankan `uv run python -c "from src.agents.graph import build_phase1_graph; g = build_phase1_graph(); print('graph OK', type(g).__name__)"`. Harus print "graph OK CompiledStateGraph".
result: pass

### 10. Streamlit UI — Dark Theme & Teks Indonesia
expected: Buka browser ke `localhost:8501`. Halaman menampilkan: (1) background gelap, (2) judul "Trusty RAG — Asisten Akuntansi Biaya", (3) subtitle Indonesia, (4) chat input placeholder Indonesia, (5) sidebar "Status Sistem", (6) empty state dengan contoh query.
result: pass

### 11. Streamlit UI — Error Handling Bahasa Indonesia
expected: Di chat UI, masukkan pertanyaan tanpa `.env` dikonfigurasi. UI harus menampilkan pesan error dalam Bahasa Indonesia, tidak crash/freeze — tetap responsif setelah error.
result: issue
reported: "UI menampilkan spinner 'Mencari referensi...' dan tidak responsif selama beberapa menit — tenacity retry (5 attempts × 60-300s backoff) memblokir UI sebelum pesan error Indonesia akhirnya muncul. Error handling kode sudah benar, tapi user experience freeze terlalu lama."
severity: minor

## Summary

total: 11
passed: 10
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "UI menampilkan pesan error Bahasa Indonesia segera setelah API gagal, tanpa freeze berkepanjangan"
  status: resolved
  reason: "User reported: UI freeze selama beberapa menit karena tenacity retry (5 attempts × 60-300s backoff) memblokir sebelum error handler muncul"
  severity: minor
  test: 11
  root_cause: "rerank() di src/llm/client.py:139 didekorasi @retry(**_RETRY_CONFIG) — konfigurasi batch dengan stop=5, wait=60-300s — padahal dipanggil dari Streamlit main thread. _UI_RETRY_CONFIG (stop=2, wait=2-10s) sudah ada tapi belum dipakai di rerank(). Worst-case freeze: 5 retries × 300s = ~17 menit."
  artifacts:
    - path: "src/llm/client.py"
      issue: "rerank() pada baris 139 menggunakan @retry(**_RETRY_CONFIG) instead of @retry(**_UI_RETRY_CONFIG)"
    - path: "src/agents/nodes.py"
      issue: "rerank_node fallback try/except aktif setelah tenacity exhausted, bukan sebelum"
    - path: "app/main.py"
      issue: "graph.invoke() dipanggil sinkron di UI thread tanpa thread pool"
  missing:
    - "Ganti @retry(**_RETRY_CONFIG) menjadi @retry(**_UI_RETRY_CONFIG) pada fungsi rerank() di src/llm/client.py:139"
  debug_session: ".planning/debug/ui-freeze-tenacity-retry.md"
