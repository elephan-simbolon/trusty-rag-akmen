# Phase 3 — UI Review

**Audited:** 2026-03-22
**Baseline:** 03-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured (no dev server running on ports 3000, 5173, or 8080)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Contract copy nearly exact; no-results path in main.py drops the "setelah pencarian ulang" suffix specified in contract |
| 2. Visuals | 4/4 | Visual hierarchy contract fully met; badge renders before prose; empty state uses editorial layout; no icon-only buttons |
| 3. Color | 4/4 | All hardcoded colors are design-token values; accent usage matches reserved list; amber-400 correctly isolated to rate-limit only |
| 4. Typography | 3/4 | Six distinct font-sizes in use (0.78rem, 0.82rem, 0.9rem, 0.95rem, 1rem, 1.5rem) against a contract of four roles; 0.9rem on empty-state body is not in the declared type scale |
| 5. Spacing | 4/4 | All Phase 3 additions use standard-scale values; carry-forward off-scale values (0.3rem, 0.45rem, 0.75rem) are pre-declared debt documented in the spec |
| 6. Experience Design | 3/4 | Loading, error, empty, and disabled states all covered; CRAG reformulation notice CSS class exists but no render_crag_reformulation_notice() function is wired in the UI; rate-limit warning CSS exists but no 429-triggered render path in main.py |

**Overall: 21/24**

---

## Top 3 Priority Fixes

1. **CRAG reformulation notice and rate-limit warning are CSS-only — no render path wired** — Users see no indication when CRAG is re-querying (loop iteration 2) or when a 429 throttle occurs; the agentic behavior is invisible — Wire `render_crag_reformulation_notice()` inside the spinner block in `app/main.py` (show when `result.get("crag_iterations", 0) > 1`) and add a `render_rate_limit_warning()` call in the `except` block that catches `httpx.HTTPStatusError` with status 429.

2. **No-results copy in `app/main.py:104` truncates the contract phrase** — The contract specifies "Tidak ditemukan referensi relevan untuk pertanyaan ini di korpus textbook yang tersedia setelah pencarian ulang." but the main.py renders "Tidak ditemukan referensi relevan untuk pertanyaan ini di korpus textbook yang tersedia." (missing "setelah pencarian ulang") — Update line 104-106 in `app/main.py` to include the full phrase so users understand the CRAG loop already exhausted its attempts.

3. **Empty-state body text uses 0.9rem — outside the four-role type scale** — The contract declares four roles at 15px/12px/13px/24px; `.empty-state p` at 0.9rem (≈14.4px) is an undeclared fifth size — Change `.empty-state p { font-size: 0.9rem }` in `app/styles/main.css:128` to `font-size: 0.95rem` (the declared body/prose token) to eliminate the phantom size.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

Contract compliance is strong overall. All high-frequency strings match exactly:

| Contract Element | Implemented | Match |
|-----------------|-------------|-------|
| Chat input placeholder | "Ketik pertanyaan akuntansi..." | PASS (`main.py:63`) |
| Spinner — standard | "Mencari referensi..." | PASS (`main.py:80`) |
| Spinner — calculation | "Menghitung..." | PASS (`main.py:80`) |
| Empty state heading | "Belum ada percakapan" | PASS (`chat.py:55`) |
| Empty state body — calculation example | "Hitung BEP dengan fixed cost 100.000 dan contribution margin 20.000." | PASS (`chat.py:59`) |
| Disclaimer (GEN-03) | "Verifikasi hasil dengan sumber resmi — bukan pengganti akuntan profesional." | PASS (`chat.py:69`) |
| Citation expander | "Sumber Referensi ({N} sumber)" | PASS (`chat.py:77`) |
| Sidebar phase label | "Trusty RAG · Phase 3 · Agentic + CRAG" | PASS (`sidebar.py:22`) |
| Turn counter | "Percakapan: {N} pertanyaan" | PASS (`sidebar.py:16`) |
| Reset button | "Mulai ulang percakapan" | PASS (`sidebar.py:18`) |
| Error — API failure | "Permintaan gagal karena gangguan koneksi ke API. Coba lagi dalam beberapa detik." | PASS (`main.py:98-99`) |
| Badge — Kalkulasi | "Kalkulasi" | PASS (`chat.py:12`) |
| Badge — Analisis | "Analisis" | PASS (`chat.py:13`) |
| Badge — Mendalam | "Mendalam" | PASS (`chat.py:14`) |

**One gap found:**

- **No-results copy** (`main.py:104-106`): "Tidak ditemukan referensi relevan untuk pertanyaan ini di korpus textbook yang tersedia." — The contract specifies this phrase must end with "setelah pencarian ulang." (acknowledging CRAG exhaustion). The implementation omits the suffix. The backend `generate_node` in `nodes.py` emits the correct full phrase, but the `elif not response:` branch in `main.py` composes its own shorter version, which can display when the response field is empty before `generate_node` fires.

- **Rate-limit copy** ("Permintaan ditunda — mencoba kembali secara otomatis.") is absent from `app/main.py`. The CSS class `.rate-limit-warning` exists in `main.css` but no Python code emits this string or applies the class, so users never see the amber 429 indicator.

- **CRAG spinner variant** ("Mencari ulang referensi...") is absent from `app/main.py`. The spinner dynamically selects "Menghitung..." vs "Mencari referensi..." but has no third branch for CRAG re-retrieval iterations.

No generic English labels (Submit, OK, Cancel, Save) found anywhere in the app files.

### Pillar 2: Visuals (4/4)

The visual hierarchy contract is fully met:

- **Primary focal point:** `st.chat_message("assistant")` is the dominant surface — badge renders before prose, disclaimer and citations are subordinate and muted.
- **Badge placement:** `render_query_type_badge()` is called as the first statement in both `render_message()` (`chat.py:31`) and `render_assistant_response()` (`chat.py:44`), ensuring the badge always appears above the prose body.
- **Simple queries:** No badge renders for `query_type == "Simple"` (`chat.py:8`), keeping the common path visually clean.
- **Empty state:** Editorial centered layout with `padding: 3.5rem 2rem` and Playfair Display heading matches the spec's 48px top/bottom rhythm.
- **No icon-only buttons:** All interactive elements use text labels ("Mulai ulang percakapan"). No bare icon buttons that would require aria-labels.
- **Sidebar subordination:** `st.caption()` is used for the turn counter and phase label — muted, 12px — correctly subordinate to the main chat surface.

The `render_crag_reformulation_notice()` and `render_rate_limit_warning()` functions are not implemented (CSS-only), but their absence does not create a visual hierarchy violation — it is a missing state, scored under Experience Design.

### Pillar 3: Color (4/4)

All color usage is on-contract. Hardcoded hex values found in `main.css`:

| Value | Location | Contract Status |
|-------|----------|----------------|
| `#2563EB` | `:root` token definition | Correct — token declaration only |
| `#F1F5F9` | Sidebar h3 fill + gradient | Correct — primary text color |
| `#93C5FD` | App title gradient + badge calc color | Correct — both are spec-declared |
| `#F59E0B` | `.rate-limit-warning` | Correct — amber-400, reserved for 429 only |

Accent `#2563EB` is used exclusively on: citation expander border, disclaimer left-border, user message bubble border/tint, and the calc badge border/fill — matching the six reserved uses in the spec. No accent appears on body text, general borders, or sidebar backgrounds.

No new off-scale colors introduced. The `rgba(148, 163, 184, 0.08)` on `.query-type-badge--medium/complex` is a close-enough variant of the `--color-border-subtle` token (0.12 alpha) and consistent with the secondary text palette.

Registry audit: No shadcn initialized (no `components.json`). No third-party registries. Registry audit skipped.

### Pillar 4: Typography (3/4)

**Declared type roles vs. implemented sizes:**

| Contract Role | Declared Size | Implemented |
|--------------|--------------|-------------|
| Body / chat prose | 0.95rem (15px) | 0.95rem — PASS (`main.css:69`) |
| Label / badge / status | 0.78rem (12px) | 0.78rem — PASS (`main.css:99, 156, 180, 191`) |
| Citation / mono | 0.82rem (13px) | 0.82rem — PASS (`main.css:84`) |
| Heading / display | 1.5rem (24px) | 1.5rem — PASS (`main.css:117`) |

**Undeclared sizes in use:**

- `0.9rem` at `main.css:128` (`.empty-state p`) — not in the four-role scale. This is 14.4px, landing between body (15px) and citation (13px) with no declared role. The empty state body text should use `0.95rem` to align with the body/prose role.
- `1rem` at `main.css:144` (sidebar `h3`) — not in the four-role scale but used for a non-body, non-display heading. This is a minor pragmatic choice for sidebar subheader sizing and has minimal visual impact.

**Weights in use:**

- `400` (regular) — all body, label, badge, citation, CRAG notice, rate-limit warning — PASS
- `600` (semibold) — display headings — PASS
- `700` (bold) — `h1` app title only — This is listed in `@import` (Playfair Display 700 is loaded) and used on the app title. The contract declares 600 as the heading weight; the `h1` uses 700, which is one weight above. This is a minor deviation but adds visual impact to the title only, which is acceptable given the gradient treatment.

Total distinct font sizes: 6 (0.78, 0.82, 0.9, 0.95, 1.0, 1.5). Contract implied 4 roles. Two extra sizes (0.9rem, 1rem) exist.

### Pillar 5: Spacing (4/4)

**Phase 3 additions — all on-scale:**

| CSS Rule | Value | Scale Token | Status |
|----------|-------|-------------|--------|
| `.query-type-badge` padding | 0.25rem 0.5rem (4px/8px) | xs/sm | PASS |
| `.query-type-badge` margin-bottom | 0.5rem (8px) | sm | PASS |
| `.crag-reformulation-notice` padding | 0.5rem 1rem (8px/16px) | sm/md | PASS |
| `.crag-reformulation-notice` margin-bottom | 0.5rem (8px) | sm | PASS |
| `.rate-limit-warning` padding | 0.25rem 0 (4px/0) | xs | PASS |
| `.rate-limit-warning` margin-top | 0.25rem (4px) | xs | PASS |

**Pre-existing debt (documented carry-forwards — not scored against Phase 3):**

| Value | Rule | Spec Status |
|-------|------|-------------|
| 0.3rem (≈5px) | `.citation-item` vertical padding | Carry-forward, documented |
| 0.45rem (≈7px) | `.disclaimer-gen03` vertical padding | Carry-forward, documented |
| 0.75rem (12px) | `stChatMessage` margin-bottom | Carry-forward, documented |

No arbitrary `[Npx]` or `[Nrem]` Tailwind values exist (project uses plain CSS). No new off-scale spacing values introduced in Phase 3.

### Pillar 6: Experience Design (3/4)

**States covered:**

| State | Implementation | Evidence |
|-------|----------------|---------|
| Loading / processing | `st.spinner()` with dynamic label; input `disabled=True` | `main.py:64, 81` |
| Error — graph init | `st.error()` + `st.stop()` | `main.py:47-48` |
| Error — API failure | `st.error()` with bilingual message | `main.py:97-100, 122-125` |
| Empty state | `render_empty_state()` with editorial copy | `main.py:56`, `chat.py:51-62` |
| Empty/no-results | Fallback response rendered | `main.py:102-108` |
| Disabled state | Chat input disabled during processing | `main.py:64` |
| Conversation reset | `_reset_conversation()` clears messages + new session_id | `main.py:27-30` |
| Error stored in history | Error messages stored in `st.session_state.messages` | `main.py:101, 126-131` |

**States missing or incomplete:**

1. **CRAG reformulation notice not rendered** — `app/main.py` has no code path that calls `render_crag_reformulation_notice()` or shows "Mencari ulang referensi...". The CSS class `.crag-reformulation-notice` is defined and the spec requires it for iteration 1 of the CRAG loop. Users processing ambiguous queries have no visibility into the re-retrieval happening. The spinner continues to show the initial label ("Mencari referensi...") with no update to signal retry behavior.

2. **Rate-limit warning not rendered** — No code in `app/main.py` catches `httpx.HTTPStatusError` with `status_code == 429` at the UI layer and renders the amber warning. The backend `_log_rate_limit` in `client.py` logs the event to the server console, but no user-visible indicator is shown. The `.rate-limit-warning` CSS class exists but is dead code from the UI's perspective.

3. **Error messages stored as raw `f"Error: {e}"` strings** — `main.py:101` and `main.py:128` store `content: f"Error: {error}"` / `content: f"Error: {e}"` in the message history. When the chat is replayed, `render_message()` will display the raw Python exception string to the user. This should use the same bilingual error copy shown in `st.error()`, not the exception string.

---

## Files Audited

- `D:/trusty-rag-akmen/app/main.py`
- `D:/trusty-rag-akmen/app/components/chat.py`
- `D:/trusty-rag-akmen/app/components/sidebar.py`
- `D:/trusty-rag-akmen/app/components/styles.py`
- `D:/trusty-rag-akmen/app/styles/main.css`
- `D:/trusty-rag-akmen/.planning/phases/03-agentic-orchestration/03-UI-SPEC.md`
- `D:/trusty-rag-akmen/.planning/phases/03-agentic-orchestration/03-04-PLAN.md`
- `D:/trusty-rag-akmen/.planning/phases/03-agentic-orchestration/03-04-SUMMARY.md`
