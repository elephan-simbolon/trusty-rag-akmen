# Phase 1 — UI Review

**Audited:** 2026-03-22
**Baseline:** 01-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured — Playwright browser binaries not installed; code-only audit performed. Dev server confirmed running at localhost:8501.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | All primary copy matches spec; calculation disclaimer (GEN-03) and sidebar live count absent |
| 2. Visuals | 4/4 | Full 4-level hierarchy, semantic roles, focal point clear, loading feedback present |
| 3. Color | 4/4 | All color via config.toml, zero hardcoded hex in Python, spec values match exactly |
| 4. Typography | 4/4 | Exactly 4 roles and 2 weights used; bilingual pattern applied correctly |
| 5. Spacing | 4/4 | height=600 matches spec, no arbitrary values, consistent single-column layout |
| 6. Experience Design | 3/4 | Loading/error/empty states all handled; calculation disclaimer missing; sidebar index hardcoded |

**Overall: 22/24**

---

## Top 3 Priority Fixes

1. **Missing calculation disclaimer** — Users who receive calculation responses have no warning that results require professional verification; violates GEN-03 requirement — Add a conditional `st.info("Verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional.")` block in the Complete state branch of `app/main.py` (line 115–127) when the response contains calculation content, or unconditionally after every assistant response.

2. **Sidebar index count hardcoded as "memuat..."** — The sidebar shows "Indeks aktif: memuat..." permanently; users cannot see whether any textbooks are indexed, which is the first thing an accounting professional will check — Replace `st.caption("Indeks aktif: memuat...")` at `app/main.py:23` with a Qdrant collection count call, or display "Indeks aktif: belum tersedia" as the honest Phase 1 placeholder rather than an infinite loading state.

3. **"Kirim Pertanyaan" primary CTA label not rendered** — The UI-SPEC Copywriting Contract declares "Kirim Pertanyaan" as the primary submit CTA label; Streamlit's `st.chat_input` does not expose a submit button label parameter so this copy is silently dropped — Update the UI-SPEC Copywriting Contract to mark this copy as "not applicable — Streamlit chat_input has no exposed submit label" to prevent future confusion, or add a `st.button("Kirim Pertanyaan")` fallback pattern adjacent to the chat input if a labeled submit is required.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Matches (all verified against UI-SPEC line-by-line):**

| Element | Expected | Actual | Status |
|---------|----------|--------|--------|
| App title | "Trusty RAG — Asisten Akuntansi Biaya" | `st.title("Trusty RAG — Asisten Akuntansi Biaya")` line 17 | PASS |
| App subtitle | "Cari referensi dari textbook akuntansi dengan kutipan sumber yang akurat." | `st.caption(...)` line 18 | PASS |
| Chat input placeholder | "Ketik pertanyaan akuntansi..." | `st.chat_input("Ketik pertanyaan akuntansi...")` line 61 | PASS |
| Loading spinner | "Mencari referensi..." | `st.spinner("Mencari referensi...")` line 91 | PASS |
| Empty state heading | "Belum ada percakapan" | `st.markdown("### Belum ada percakapan")` line 43 | PASS |
| Empty state body | "Ketik pertanyaan akuntansi di bawah..." with example | `st.markdown(...)` lines 44-47 | PASS (minor: example uses "Apa" not "apa" — acceptable case difference) |
| Citation expander label | "Sumber Referensi (N sumber)" | `f"Sumber Referensi ({len(citations)} sumber)"` lines 55, 80, 120 | PASS |
| Error state — API failure | "Permintaan gagal karena gangguan koneksi ke API. Coba lagi dalam beberapa detik." | `st.error(...)` lines 100, 131 | PASS |
| Error state — no results | "Tidak ditemukan referensi relevan untuk pertanyaan ini di korpus textbook yang tersedia." | `no_results_msg` line 108 | PASS |
| Sidebar header | "Status Sistem" | `st.subheader("Status Sistem")` line 22 | PASS |
| page_title | "Trusty RAG — Asisten Akuntansi" | `page_title="Trusty RAG — Asisten Akuntansi"` line 10 | PASS |

**Gaps:**

- **Calculation disclaimer absent** (`app/main.py` — no line): UI-SPEC Copywriting Contract requires "Verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional." on every calculation response (GEN-03). The generate node does not tag responses by complexity type in Phase 1, so the UI cannot conditionally inject this copy. The disclaimer is entirely absent from the UI. Risk: users may rely on calculated figures without professional review.

- **Sidebar index count hardcoded** (`app/main.py:23`): Spec requires "Indeks aktif: N dokumen" (dynamic count). Code shows `st.caption("Indeks aktif: memuat...")` which is a permanent loading stub. Strictly a Phase 4 TODO (comment confirms this), but creates an indefinitely misleading state.

- **"Kirim Pertanyaan" primary CTA** (structural gap): The spec Copywriting Contract lists "Kirim Pertanyaan" as the primary CTA copy. `st.chat_input` in Streamlit provides no submit button label property — the submit arrow/icon has no text. This copy cannot be implemented with the current Streamlit native component. The spec should be updated to reflect this constraint.

- **Graph load error copy** (`app/main.py:33`): `st.error(f"Gagal memuat graph RAG: {e}")` is a dynamic f-string error and not from the spec's copywriting contract. Minor: acceptable for an initialization-only edge case.

---

### Pillar 2: Visuals (4/4)

**Visual hierarchy:**
- Display level: `st.title()` line 17 — app title, single use, prominent focal point
- Heading level: `st.subheader()` line 22 — sidebar section header only
- Body level: `st.markdown()` — response prose, consistent usage
- Label level: `st.caption()` — citation metadata, subtitle, sidebar status

The hierarchy is correctly enforced with no level skipping or inversion. The app title is the clear primary focal point. Chat container (`height=600`) provides a bounded visual region separating conversation from input.

**Semantic roles:**
- `st.chat_message("user")` and `st.chat_message("assistant")` — correct semantic role usage per spec; Streamlit renders these with distinct avatar icons automatically
- No icon-only buttons in the implementation (submit arrow is Streamlit native, not a custom icon-only element)

**Loading feedback:**
- `st.spinner("Mencari referensi...")` is inside `st.chat_message("assistant")` block (line 89-91) — loading state is shown within the conversation flow, not as an external overlay. This matches the spec's "spinner inside assistant chat bubble placeholder" interaction state.

**Empty citation expander handling:**
- `if citations:` guard at lines 54 and 119 prevents rendering an empty expander — correct per spec "Expander hidden entirely — do not render empty expander."

**No issues found.** Score: 4/4.

---

### Pillar 3: Color (4/4)

**config.toml values (verified against UI-SPEC):**

| Property | Spec | Actual | Status |
|----------|------|--------|--------|
| base | "dark" | "dark" | PASS |
| primaryColor | "#2563EB" | "#2563EB" | PASS |
| backgroundColor | "#0F172A" | "#0F172A" | PASS |
| secondaryBackgroundColor | "#1E293B" | "#1E293B" | PASS |
| textColor | "#F1F5F9" | "#F1F5F9" | PASS |
| font | "sans serif" | "sans serif" | PASS |

**Hardcoded color audit:**
- Zero hex color literals in `app/main.py` — grep for `#[0-9a-fA-F]{3,8}` returned no matches
- Zero `rgb(` or `rgba(` calls in `app/main.py`
- All color is delegated to Streamlit's theming system via config.toml

**Accent usage:**
- `primaryColor = "#2563EB"` is used by Streamlit for focus rings on the chat input, primary button styling, and interactive element highlights — all appropriate uses per the spec's reserved list
- No custom CSS injecting the accent color onto disallowed elements

**No issues found.** Score: 4/4.

---

### Pillar 4: Typography (4/4)

**Size distribution (verified against UI-SPEC):**

| Spec Role | Expected Element | Actual Element | Status |
|-----------|-----------------|----------------|--------|
| Display | `st.title()` — 28px semibold | Line 17: `st.title(...)` | PASS |
| Heading | `st.subheader()` / `## markdown` — 20px semibold | Line 22: `st.subheader(...)` and line 43: `st.markdown("### ...")` | PASS |
| Body | `st.write()` / `st.markdown()` — 16px regular | Lines 44, 51, 77, 86, 109, 117 | PASS |
| Label | `st.caption()` — 14px regular | Lines 18, 23, 57, 82, 122 | PASS |

Exactly 4 distinct rendered sizes in use — matches the spec's 4-role model.

**Weight usage:**
- 400 (regular): `st.markdown`, `st.caption`, `st.write` — Streamlit default
- 600 (semibold): `st.title`, `st.subheader` — Streamlit default heading weights

Exactly 2 weights — matches the spec's constraint.

**Bilingual pattern:**
- The spec requires English terms in parentheses with italic markdown: `alokasi biaya overhead (*overhead cost allocation*)`. This pattern is enforced in the generator system prompt (config/prompts.py) and rendered via `st.markdown()` which processes italic markdown correctly. The UI correctly uses `st.markdown` for response content (not `st.text`) so markdown rendering is active.

**No issues found.** Score: 4/4.

---

### Pillar 5: Spacing (4/4)

**Spec-defined spacing values:**

| Spec Element | Expected | Actual | Status |
|--------------|----------|--------|--------|
| Chat container height | `height=600` | `st.container(height=600)` line 39 | PASS |
| Layout | Single-page, no routing | Single `app/main.py`, no `st.navigation` or page routing | PASS |
| Chat area location | Below title, above input | `chat_container` defined line 39, input at line 60 | PASS |

**Arbitrary value audit:**
- No CSS injection (`st.markdown("<style>...")`) found in `app/main.py`
- No `unsafe_allow_html=True` usage with custom spacing values
- No pixel or rem values in Python source

**Column usage:**
- No `st.columns()` call — single column layout throughout. This is consistent with the spec's single-page layout and the chat UI's linear conversation flow pattern.

**Streamlit spacing scale adherence:**
- The spec's logical scale (xs through 3xl mapped to Streamlit API parameters) is honored because the code uses Streamlit's default container and message spacing without override. No custom gap parameters that would conflict with the declared scale.

**No issues found.** Score: 4/4.

---

### Pillar 6: Experience Design (3/4)

**State coverage analysis:**

| State | Spec Requirement | Implementation | Status |
|-------|-----------------|----------------|--------|
| Loading | `st.spinner("Mencari referensi...")` inside assistant bubble | Lines 89-91: spinner inside `st.chat_message("assistant")` | PASS |
| Error — API failure | `st.error(...)` with Indonesian message | Lines 100, 131: correct message | PASS |
| Error — graph init | Graceful `st.error` + `st.stop()` | Lines 33-34 | PASS |
| Empty state | "Belum ada percakapan" with example | Lines 42-47 | PASS |
| Input disabled during loading | `disabled=st.session_state.processing` | Line 62 | PASS |
| No results | Indonesian message, no hallucination | Lines 107-113 | PASS |
| Citation — no citations | Expander hidden | `if citations:` guards lines 54, 119 | PASS |
| Chat history persistence | `st.session_state.messages` list | Lines 28, 49 | PASS |
| Double-submission prevention | `st.session_state.processing` flag | Lines 36, 66, 70, 138 | PASS |
| Calculation disclaimer | "Verifikasi hasil..." per GEN-03 | **Not implemented** | FAIL |
| Sidebar live count | Dynamic "Indeks aktif: N dokumen" | **Hardcoded "memuat..."** | PARTIAL |

**Gaps:**

1. **Calculation disclaimer (GEN-03):** The UI-SPEC Copywriting Contract explicitly requires "Verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional." on every calculation response. No conditional or unconditional rendering of this disclaimer exists in `app/main.py`. In Phase 1, where complexity routing is not yet active, displaying this disclaimer on every assistant response would be the safe default.

2. **Sidebar index count:** `st.caption("Indeks aktif: memuat...")` at line 23 is a permanent stub. While the TODO comment acknowledges this is Phase 4 work, "memuat..." implies an in-progress load that never resolves, which is potentially confusing. A static placeholder like "Indeks aktif: belum dikonfigurasi" would be more accurate for the current state.

**Strengths:**
- The `st.rerun()` calls at lines 67 and 139 correctly manage Streamlit's re-execution model for state transitions
- The processing flag architecture prevents the double-submission problem that commonly affects Streamlit chat UIs
- Both `try/except` blocks (lines 30-34 and 92-136) use `except Exception as e` with specific Indonesian error messages rather than silent failures

---

## Registry Safety

No shadcn registry initialized (`components.json` not found). All UI components are Streamlit native. Registry audit: not applicable.

---

## Files Audited

- `D:/trusty-rag-akmen/app/main.py` — Primary Streamlit chat UI (140 lines)
- `D:/trusty-rag-akmen/.streamlit/config.toml` — Theme configuration (7 lines)
- `D:/trusty-rag-akmen/scripts/test_query.py` — CLI query tool (55 lines, no UI surface)
- `D:/trusty-rag-akmen/.planning/phases/01-foundation/01-UI-SPEC.md` — Design contract (audit baseline)
- `D:/trusty-rag-akmen/.planning/phases/01-foundation/01-06-SUMMARY.md` — Execution summary (implementation reference)
- `D:/trusty-rag-akmen/.planning/phases/01-foundation/01-06-PLAN.md` — Plan with UI-SPEC acceptance criteria
