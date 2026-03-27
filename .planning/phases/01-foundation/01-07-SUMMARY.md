---
phase: 01-foundation
plan: 07
subsystem: llm/client
tags: [tenacity, retry, streamlit, ui, gap-closure]

# Dependency graph
requires:
  - phase: 01-06
    provides: app/main.py dengan try/except error handler yang sudah benar
provides:
  - _UI_RETRY_CONFIG fast-fail (2 attempts, 2-10s) di src/llm/client.py
  - embed_query dan generate menggunakan _UI_RETRY_CONFIG
  - 2 test baru memverifikasi split retry strategy
affects: [UI responsiveness, error handling flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Split retry strategy: _RETRY_CONFIG (lambat) untuk batch ingestion, _UI_RETRY_CONFIG (cepat) untuk UI-facing functions"
    - "TDD: test merah dulu (AttributeError _UI_RETRY_CONFIG), lalu implementasi membuat hijau"
    - "Inspeksi tenacity config via client_mod._UI_RETRY_CONFIG dict langsung — tidak pakai mock karena fixture memotong sebelum retry bekerja"

key-files:
  modified:
    - src/llm/client.py
    - tests/test_embedding.py

key-decisions:
  - "_UI_RETRY_CONFIG hanya pada embed_query dan generate — dua fungsi yang dipanggil dari LangGraph nodes via Streamlit UI"
  - "embed_batch, embed_document, rerank tetap _RETRY_CONFIG — batch ingestion memerlukan retry panjang untuk SiliconFlow rate limit nyata"
  - "Worst-case wait setelah fix: 2 attempts x 10s max = ~20 detik, di bawah threshold 30 detik"

requirements-completed: [UI-01]
gap-closed: "UAT Test 11 — UI freeze akibat tenacity retry terlalu panjang"

# Metrics
duration: 5min
completed: 2026-03-22
---

# Phase 01 Plan 07: UI Retry Fix Summary

**Gap closure: tambah _UI_RETRY_CONFIG (2 attempts, 2-10s) untuk embed_query dan generate — menghilangkan UI freeze hingga 5 menit saat API tidak terkonfigurasi**

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-03-22
- **Tasks:** 1 (TDD)
- **Files modified:** 2

## Accomplishments

- `_UI_RETRY_CONFIG` ditambahkan di `src/llm/client.py` setelah `_RETRY_CONFIG` dengan `stop_after_attempt(2)` dan `wait_exponential(min=2, max=10)`
- `embed_query` dan `generate` kini menggunakan `@retry(**_UI_RETRY_CONFIG)` — worst-case wait ~20 detik
- `embed_document`, `embed_batch`, `rerank` tetap `@retry(**_RETRY_CONFIG)` — tidak ada perubahan pada pipeline ingestion batch
- 2 test baru di `tests/test_embedding.py` memverifikasi split strategy secara eksplisit
- 35 test lulus, tidak ada regresi

## Task Commits

1. **fix(01-07): fast-fail UI retry config untuk embed_query dan generate** — `23c381b`

## Root Cause

Log dari RAG.txt mengkonfirmasi: 5 retry × 60s = ~5 menit freeze sebelum `AuthenticationError` di-reraise ke handler `app/main.py` yang sudah benar.

## Self-Check: PASSED

- FOUND: _UI_RETRY_CONFIG di src/llm/client.py
- FOUND: test_embed_query_uses_ui_retry_config di tests/test_embedding.py
- FOUND: commit 23c381b di git log
- ALL: 35 pytest passed

---
*Phase: 01-foundation*
*Completed: 2026-03-22*
