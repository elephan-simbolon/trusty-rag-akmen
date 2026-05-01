---
phase: 06
slug: kpe-core
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
---

# Phase 06 — KPE Core Validation Strategy

> Per-phase validation contract — retroactively audited 2026-03-30.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pyproject.toml + pytest.ini) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `uv run pytest tests/test_protocol_registry.py tests/test_select_protocol.py tests/test_protocol_selection.py tests/test_protocol_prompts.py tests/test_query_routing.py -q` |
| **Full suite command** | `uv run pytest -m "not integration and not gpu" --tb=no -q` |
| **Estimated runtime** | ~3s (phase tests) / ~20s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run quick run command (phase tests only, ~3s)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must show ≤16 failures (all pre-existing fast_graphrag/langfuse)
- **Max feedback latency:** 3 seconds (phase tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | PROT-01 | unit | `uv run pytest tests/test_protocol_registry.py -q` | ✅ | ✅ green |
| 06-01-02 | 01 | 1 | PROT-02 | unit | `uv run pytest tests/test_select_protocol.py -q` | ✅ | ✅ green |
| 06-02-01 | 02 | 1 | PROT-03, PROT-04 | unit | `uv run pytest tests/test_protocol_prompts.py tests/test_synthesis_generation.py tests/test_multi_source_comparison.py -q` | ✅ | ✅ green |
| 06-02-02 | 02 | 1 | PROT-04 | unit | `uv run pytest tests/test_query_routing.py tests/test_generation.py -q` | ✅ | ✅ green |
| 06-03-01 | 03 | 1 | PROT-01, PROT-02 | unit | `uv run pytest tests/test_protocol_selection.py -q` | ✅ | ✅ green |
| 06-03-02 | 03 | 1 | PROT-03, PROT-04 | unit | `uv run pytest tests/test_protocol_prompts.py tests/test_query_routing.py -q` | ✅ | ✅ green |
| 06-03-03 | 03 | 1 | PROT-01–04 | unit (suite) | `uv run pytest -m "not integration and not gpu" --tb=no -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- `tests/test_protocol_registry.py` — 52 tests, PROT-01
- `tests/test_select_protocol.py` — 18 tests, PROT-02
- `tests/test_protocol_selection.py` — 35 tests, PROT-01, PROT-02
- `tests/test_protocol_prompts.py` — 16 tests, PROT-03, PROT-04
- `tests/test_query_routing.py` — 16 tests, PROT-04 (RAGState.protocol_key, field count)
- `tests/test_generation.py` — 6 tests, PROT-04 (generate_response)
- `tests/test_synthesis_generation.py` — 11 tests, PROT-03, PROT-04
- `tests/test_multi_source_comparison.py` — 9 tests, PROT-03

**Total phase-related tests: 163 passed, 0 failed**

---

## Coverage by Requirement

| Requirement | Description | Test Files | Test Count | Status |
|-------------|-------------|------------|------------|--------|
| PROT-01 | 9-protocol PROTOCOL_REGISTRY with ProtocolConfig frozen dataclass | test_protocol_registry.py, test_protocol_selection.py | 87 | ✅ COVERED |
| PROT-02 | select_protocol() rule-based routing, zero LLM calls, word-boundary guard | test_select_protocol.py, test_protocol_selection.py | 53 | ✅ COVERED |
| PROT-03 | Protocol steps (## Jawaban Singkat, ## Analisis, ## Rekomendasi) in all 9 protocols | test_protocol_registry.py, test_protocol_prompts.py | 68 | ✅ COVERED |
| PROT-04 | compose_system_prompt() 6-block assembly; RAGState.protocol_key wired through route_node → generate_response | test_protocol_prompts.py, test_query_routing.py, test_generation.py, test_synthesis_generation.py, test_multi_source_comparison.py | 58 | ✅ COVERED |

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Audit 2026-03-30

| Metric | Count |
|--------|-------|
| Requirements audited | 4 (PROT-01 through PROT-04) |
| COVERED | 4 |
| PARTIAL | 0 |
| MISSING | 0 |
| Gaps found | 0 |
| Tests generated | 0 (all tests existed from Phase 06 execution) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0: no missing test stubs (all tests written during execution)
- [x] No watch-mode flags
- [x] Feedback latency < 3s (phase tests)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-30
