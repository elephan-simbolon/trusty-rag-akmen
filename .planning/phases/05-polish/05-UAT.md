---
status: complete
phase: 05-polish
source: [05-01-SUMMARY.md, 05-02-PLAN.md]
started: 2026-03-28T00:00:00Z
updated: 2026-03-28T01:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Citations Collapsed by Default
expected: Setelah respons selesai (done phase), panel sitasi tampil collapsed dengan tombol "Lihat N referensi" di bawah teks jawaban. Sitasi tidak langsung terlihat — harus diklik dulu untuk membuka.
result: pass

### 2. Toggle Button Expand/Collapse
expected: Klik tombol "Lihat N referensi" → panel sitasi terbuka dengan animasi smooth. Tombol berubah jadi "Sembunyikan N referensi". Klik lagi → panel tertutup.
result: pass

### 3. Inline Anchor Auto-Open Citations
expected: Klik superscript [1] di dalam teks jawaban → panel sitasi otomatis terbuka (jika sebelumnya collapsed) lalu scroll ke CitationCard yang sesuai.
result: skipped
reason: LLM tidak menghasilkan format [1] superscript — prompt hanya menginstruksikan format "Horngren, Cost Accounting, Chapter 5..." langsung di teks. Kode anchor handler ada di ChatMessage.tsx (regex `/\[\d+\]|\[Sumber\s+\d+[^\]]*\]/`) tapi tidak pernah terpicu karena LLM tidak menghasilkan pola tersebut. Fitur tidak bisa diuji end-to-end.

### 4. Author Prefix in Citation Format
expected: CitationCard menampilkan format dengan author prefix, contoh: "Horngren, Cost Accounting, Chapter 5, hal. 168-172". Bukan hanya "Cost Accounting, Chapter 5, hal. 168-172" tanpa nama pengarang.
result: issue
reported: "CitationCard hanya menampilkan book_title tanpa author prefix. Contoh: '[1] Cost Accounting' bukan '[1] Horngren, Cost Accounting'. CitationCard.tsx baris 38 hanya render citation.book_title, tidak menggunakan citation.author atau citation.formatted."
severity: major

### 5. No Duplicate "Sumber Referensi" Block
expected: Di bawah teks jawaban tidak ada blok teks "**Sumber Referensi:**" yang merupakan duplikat. Sitasi hanya muncul di CollapsibleCitationList, bukan juga di body teks.
result: pass

### 6. History Turns Also Use Collapsible
expected: Turn percakapan sebelumnya (history) juga memiliki panel sitasi collapsible yang sama. Bukan static list.
result: pass

## Summary

total: 6
passed: 4
issues: 1
pending: 0
skipped: 1

## Gaps

- truth: "CitationCard menampilkan author prefix: 'Horngren, Cost Accounting, Chapter 5, hal. 168-172'"
  status: failed
  reason: "CitationCard.tsx baris 38 hanya render citation.book_title. Backend sudah mengirim author field via build_citations() (Plan 05-01), tapi CitationCard tidak menggunakannya. Fix: tampilkan citation.author + citation.book_title, atau gunakan citation.formatted langsung."
  severity: major
  test: 4
  artifacts:
    - frontend/src/components/CitationCard.tsx:38
    - src/generation/citation_builder.py (author field sudah ada)
  missing:
    - CitationCard perlu render author prefix sebelum book_title
