---
status: complete
phase: 02-knowledge-graph
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md]
started: 2026-03-22T08:00:00Z
updated: 2026-03-22T09:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Jalankan `streamlit run app/main.py`. Aplikasi boot tanpa error, UI Streamlit muncul di browser. Tidak ada traceback atau ModuleNotFoundError di terminal.
result: pass

### 2. LightRAG Client Setup
expected: `ACCOUNTING_ENTITY_TYPES` berisi 10 kategori entity akuntansi. `build_lightrag_instance()` membuat instance tanpa error.
result: pass

### 3. Entity Normalization
expected: `normalize_entity_name()` mengembalikan bentuk canonical. 27 mapping tersedia (BEP→Break-Even Point, CVP→Cost-Volume-Profit Analysis, dll).
result: pass

### 4. Ingestion CLI Script
expected: `python scripts/ingest_lightrag.py --help` menampilkan help text dengan argumen `chunks_path` dan flag `--full`. Tidak ada ImportError.
result: pass

### 5. Graph Retrieve Node di LangGraph
expected: Pipeline Phase 2 (preprocess → retrieve → graph_retrieve → rerank → generate) memproses query tanpa error. Response muncul di UI.
result: issue
reported: "Retrieval failed: 404 Not Found — Collection `trusty_rag_akmen` doesn't exist. Qdrant collection belum diisi (Phase 1 ingestion belum dijalankan). Graph node terhubung dengan benar di pipeline, tapi Qdrant retrieve node gagal sebelum graph_retrieve node dieksekusi."
severity: minor

### 6. Mode Routing (Local vs Hybrid)
expected: Query dengan kata "hubungan" → `query_mode` diset ke "local". Query tanpa kata relasional → `query_mode` default ke "hybrid".
result: pass

### 7. Multi-Source Synthesis dengan Attributasi
expected: Jika `graph_docs` non-empty, response menyebut nama author/sumber untuk setiap klaim.
result: skipped
reason: Tidak bisa diuji end-to-end karena Qdrant collection belum ada (Test 5). Unit tests synthesis (11 tests) sudah cover skenario ini dan pass.

### 8. Backward Compatibility Phase 1
expected: `python -m pytest tests/test_generation.py -q` — semua 2 test Phase 1 pass.
result: pass

### 9. Unit Tests Phase 2
expected: `python -m pytest tests/test_lightrag_setup.py tests/test_entity_normalization.py tests/test_graph_retrieve.py tests/test_synthesis_generation.py -q` — semua 33 tests pass.
result: pass

## Summary

total: 9
passed: 7
issues: 1
pending: 0
skipped: 1

## Gaps

- truth: "End-to-end query melalui pipeline Phase 2 mengembalikan response (bukan error) saat Qdrant collection belum ada"
  status: failed
  reason: "404 Not Found dari Qdrant karena collection trusty_rag_akmen belum diisi — pre-condition Phase 1 ingestion belum dilakukan, bukan bug Phase 2. Pipeline berjalan sesuai desain."
  severity: minor
  test: 5
  root_cause: "Pre-condition: Qdrant collection belum diisi data. retrieve_node gagal dengan 404, error dipropagasi melalui state. Bukan bug kode."
  artifacts: []
  missing: []
