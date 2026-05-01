---
status: complete
phase: 06-kpe-core
source: 06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md
started: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Protocol Registry — 9 protokol tersedia
expected: Import PROTOCOL_REGISTRY dari config.protocols. Registry berisi tepat 9 kunci: variance_analysis, abc, transfer_pricing, relevant_costing, product_profitability, budgeting, cost_classification, cvp, general. Setiap protokol memiliki field steps berisi ## Jawaban Singkat, ## Analisis, ## Rekomendasi.
result: pass

### 2. select_protocol() — routing berbasis keyword
expected: Panggil select_protocol() dengan berbagai query. "jelaskan break-even point" → cvp. "hitung varians harga bahan baku" → variance_analysis. "apa itu activity-based costing?" → abc. "apa itu akuntansi manajemen?" → general. Query kosong "" → general.
result: pass

### 3. Word-boundary guard untuk keyword pendek
expected: Panggil select_protocol("kontrak ABC dengan vendor lainnya"). Hasilnya BUKAN "abc" — guard mencegah false positive karena "ABC" muncul sebagai singkatan non-accounting. Hasilnya general atau protokol lain yang relevan.
result: pass

### 4. compose_system_prompt() — blok tersusun berurutan
expected: Panggil compose_system_prompt(protocol_key="cvp", glossary_snippet="BEP: break-even point", is_calculation=False, has_graph_context=False). Output berisi: persona block, rules block ([Sumber N], "Jawab dalam bahasa Indonesia"), CVP section headers (## Jawaban Singkat dll), glossary di akhir. TIDAK ada "knowledge graph" (has_graph_context=False).
result: pass

### 5. compose_system_prompt() — calculation block dan synthesis block
expected: Panggil dengan is_calculation=True, has_graph_context=True. Output mengandung: disclaimer kalkulasi (dari _CALCULATION_BLOCK), frasa "knowledge graph" (dari _SYNTHESIS_BLOCK), DAN tetap mengandung protocol steps. Semua blok hadir secara aditif.
result: pass

### 6. RAGState memiliki field protocol_key
expected: Import RAGState dari src.agents.state. Field "protocol_key" ada di RAGState.__annotations__. Total field RAGState = 15.
result: pass

### 7. Alur end-to-end: route_node menyimpan protocol_key ke state
expected: Pada LangGraph pipeline, setelah route_node dieksekusi dengan query "jelaskan break-even point", state["protocol_key"] == "cvp". Artinya select_protocol() dipanggil di route_node dan hasilnya disimpan ke RAGState.
result: pass

### 8. generate_response() menggunakan protocol_key dari state
expected: Saat generate_node atau generate_calc_node dipanggil, generate_response() menerima protocol_key dari state (bukan hardcoded). System prompt yang dihasilkan berbeda untuk query CVP vs query general — membuktikan compose_system_prompt() digunakan, bukan konstanta lama.
result: pass

### 9. Deprecated constants masih bisa diimport
expected: from config.prompts import SYSTEM_PROMPT_GENERATOR, SYSTEM_PROMPT_GENERATOR_CALCULATION, SYSTEM_PROMPT_SYNTHESIS — ketiga import ini tidak raise error. Nilai masing-masing adalah string (backward-compatible).
result: pass

### 10. Unit test suite berjalan: 316+ passed, 0 regresi baru
expected: Jalankan: uv run pytest -m "not integration and not gpu" --tb=no -q. Hasilnya: minimal 316 passed. 16 failures yang ada adalah pre-existing (fast_graphrag tidak terinstall + langfuse config). Zero regresi baru dari perubahan fase 06.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
