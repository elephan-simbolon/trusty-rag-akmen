---
status: complete
phase: 08-consulting-book-ingestion
source: [08-01-SUMMARY.md, 08-02-SUMMARY.md]
started: 2026-03-30T04:02:37Z
updated: 2026-03-30T04:06:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Flag --no-vlm tersedia di CLI
expected: Jalankan `uv run python scripts/ingest.py --help` — output menampilkan flag `--no-vlm` dalam daftar argumen yang tersedia.
result: pass

### 2. Flag --author tersedia di CLI
expected: Jalankan `uv run python scripts/ingest.py --help` — output menampilkan flag `--author` dengan deskripsinya.
result: pass

### 3. Unit tests consulting semua hijau
expected: Jalankan `uv run pytest tests/test_consulting_ingestion.py -v` — semua 9 test pass (4 VLM gate + 5 author field), tidak ada failures.
result: pass

### 4. Consulting chunks ada di Qdrant dengan metadata lengkap
expected: Qdrant collection berisi ≥10,000 chunks dengan `source_domain='consulting'`. Setiap chunk memiliki field `author`, `book_title`, `source_domain`, `chapter` dalam payload.
result: pass

### 5. Query consulting mengembalikan label [Kerangka N]
expected: Query "apa itu issue tree dalam consulting?" menghasilkan respons dengan citation label `[Kerangka 1]`, `[Kerangka 2]`, dst. — bukan `[Sumber N]`.
result: pass

### 6. Query akuntansi tetap mengembalikan [Sumber N]
expected: Query tentang topik akuntansi (misal break-even point, biaya variabel, dll.) tetap menghasilkan citation label `[Sumber N]` — tidak berubah menjadi `[Kerangka N]`.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
