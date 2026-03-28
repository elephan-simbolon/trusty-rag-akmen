# Phase 5: Polish — Validation Architecture

**Generated:** 2026-03-27
**Updated:** 2026-03-28
**Source:** 05-RESEARCH.md "Validation Architecture" section
**nyquist_validation:** enabled
**nyquist_compliant:** true (backend); manual-only (frontend — no Vitest setup)

---

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (uv run pytest) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_generation.py -x` |
| Full suite command | `uv run pytest -m "not integration and not gpu"` |
| Frontend compile check | `cd frontend && npx tsc --noEmit` |

---

## Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | Status |
|--------|----------|-----------|-------------------|--------|
| UI-03 (backend) | `formatted` field includes author prefix: "Horngren, Cost Accounting, Chapter 5, hal. 168-170" | unit | `uv run pytest tests/test_generation.py::test_citation_format_in_response -x` | COVERED ✓ |
| UI-03 (backend) | `build_citations` returns dicts with `author` key populated from metadata | unit | `uv run pytest tests/test_generation.py::test_build_citations_includes_author_field -x` | COVERED ✓ |
| UI-03 (backend) | `build_citation` gracefully omits author when metadata lacks author field | unit | `uv run pytest tests/test_generation.py::test_citation_format_without_author -x` | COVERED ✓ |
| UI-03 (backend) | Empty string author treated same as absent (no leading comma) | unit | `uv run pytest tests/test_generation.py::test_citation_format_empty_author -x` | COVERED ✓ |
| UI-03 (backend) | `generator.py` does NOT append `**Sumber Referensi:**` block to response text | unit | `uv run pytest tests/test_generation.py::test_no_citation_text_block_in_response -x` | COVERED ✓ |
| UI-03 (frontend) | CollapsibleCitationList renders toggle button when citations exist | manual | n/a (no Vitest/jsdom setup in frontend/) | MANUAL-ONLY |
| UI-03 (frontend) | Citations panel is collapsed by default | manual | n/a | MANUAL-ONLY |
| UI-03 (frontend) | Inline [Sumber N] anchor click auto-opens collapsed citations | manual | n/a | MANUAL-ONLY |
| UI-03 (frontend) | Citation TypeScript type includes optional `author` field | compile | `cd frontend && npx tsc --noEmit` | COVERED ✓ |

---

## Manual-Only Items

Frontend component tests require Vitest + jsdom setup (not currently available in `frontend/`). These are validated via UAT checkpoint:human-verify in Plan 05-02:

| Item | Validated By | Result |
|------|--------------|--------|
| CollapsibleCitationList toggle | UAT Test 2 (checkpoint in 05-02) | pass |
| Citations collapsed by default | UAT Test 1 | pass |
| Inline anchor auto-open | UAT Test 3 | skipped — LLM doesn't emit [N] pattern |
| CitationCard author prefix | UAT Test 4 → fixed commit 0598e93 | pass |
| No duplicate Sumber Referensi | UAT Test 5 | pass |
| History turns use collapsible | UAT Test 6 | pass |

---

## Sampling Rate

| Trigger | Command | Scope |
|---------|---------|-------|
| Per task commit | `uv run pytest tests/test_generation.py -x` | Changed test file |
| Per wave merge | `uv run pytest -m "not integration and not gpu"` | Full backend suite |
| Phase gate | Full backend suite green + manual UI smoke test | Before `/gsd:verify-work` |

---

## Plan Coverage

| Plan | Req IDs | Test Types | Notes |
|------|---------|------------|-------|
| 05-01 | UI-03 (backend) | unit (pytest) | TDD: all 4 new tests written and passing |
| 05-02 | UI-03 (frontend) | compile (tsc) + manual (checkpoint) | No automated component tests available |

---

## Validation Audit 2026-03-28

| Metric | Count |
|--------|-------|
| Gaps found (Wave 0) | 4 backend + 3 frontend |
| Resolved (automated) | 4 backend + 1 frontend (tsc) |
| Resolved (manual UAT) | 5 frontend items |
| Escalated to manual-only | 3 frontend (Vitest not available) |
| Final nyquist compliance | Backend: full ✓ / Frontend: manual-only |
