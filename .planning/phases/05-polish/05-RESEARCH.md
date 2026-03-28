# Phase 5: Polish — Research

**Researched:** 2026-03-27
**Domain:** React 19 + shadcn/ui collapsible UI pattern, citation formatting pipeline
**Confidence:** HIGH

---

## Summary

Phase 5 (UI-03) requires converting the always-visible `CitationList` section inside
`ChatMessage.tsx` into an expandable/collapsible section. The user reads the answer first
and opens sources on demand. This is a **frontend-only change** — the backend citation
pipeline already produces the correct data structure and the `formatted` field already
matches the required format.

The shadcn/ui project uses `radix-ui` (the monorepo re-export package, v1.4.3). Crucially,
`@radix-ui/react-collapsible` v1.1.12 **is already installed** as a transitive dependency
of that package and is exported as `Collapsible` from `radix-ui`. No `npm install` is
needed. A thin `collapsible.tsx` wrapper in `frontend/src/components/ui/` is the only new
file required, following the existing pattern of other shadcn/ui wrappers in this project.

There is one backend concern that needs attention: `generator.py` appends a redundant plain-
text `**Sumber Referensi:**` block to the LLM response text at lines 98-102. This block
appears in the streamed Markdown alongside the structured `CitationList` UI, resulting in
duplicate citation display. Removing that append is a required back-end change for this
phase.

**Primary recommendation:** (1) Create `collapsible.tsx` UI wrapper, (2) replace `CitationList`
with a collapsible version in `ChatMessage.tsx`, (3) strip the redundant citation text
block from `generator.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@radix-ui/react-collapsible` | 1.1.12 | Headless collapsible primitive | Already installed, accessible by default, used via `radix-ui` monorepo |
| `lucide-react` | ^0.575.0 | ChevronDown/ChevronUp toggle icon | Already used throughout the codebase |
| `tailwind-merge` / `cn` | present | Class merging for conditional styles | Already used in all shadcn/ui wrappers |

### No New Dependencies Required
`@radix-ui/react-collapsible` is a transitive dependency of `radix-ui` v1.4.3 which is
already in `package.json`. Import path: `import { Collapsible } from "radix-ui"` or
directly from `@radix-ui/react-collapsible`.

**Installation:** None required.

---

## Architecture Patterns

### Collapsible API (verified from installed type definitions)

The `@radix-ui/react-collapsible` package exports three composable parts:

```typescript
// Source: frontend/node_modules/@radix-ui/react-collapsible/dist/index.d.ts
Collapsible       // Root container — props: open?, defaultOpen?, onOpenChange?, disabled?
CollapsibleTrigger // Button that toggles open state
CollapsibleContent // Panel that shows/hides (animated via data-state="open|closed")
```

The `radix-ui` monorepo package re-exports these as:

```typescript
import { Collapsible } from "radix-ui";
// Then use: Collapsible.Root, Collapsible.Trigger, Collapsible.Content
```

### Recommended UI Wrapper Pattern

Following the project's existing `ui/tooltip.tsx`, `ui/button.tsx` style:

```typescript
// frontend/src/components/ui/collapsible.tsx
// Source pattern: radix-ui docs + existing project wrappers
import { Collapsible } from "radix-ui";
import { cn } from "@/lib/utils";

const CollapsibleRoot = Collapsible.Root;
const CollapsibleTrigger = Collapsible.Trigger;
const CollapsibleContent = Collapsible.Content;

export { CollapsibleRoot, CollapsibleTrigger, CollapsibleContent };
```

### CitationList Replacement Pattern

Replace the current always-visible `CitationList` in `ChatMessage.tsx` with a new
`CollapsibleCitationList` component:

```typescript
// Conceptual pattern only — exact code in PLAN
function CollapsibleCitationList({ citations, text }: { citations: Citation[]; text: string }) {
  const [open, setOpen] = useState(false);
  // ... dedup logic (same as current CitationList) ...
  return (
    <CollapsibleRoot open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button className="flex items-center gap-1 text-xs font-medium text-muted-foreground ...">
          <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
          {open ? "Sembunyikan" : "Lihat"} {items.length} referensi
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <div className="flex flex-col gap-1.5">
          {items.map(...)}
        </div>
      </CollapsibleContent>
    </CollapsibleRoot>
  );
}
```

### Tailwind v4 Animation Note

This project uses Tailwind v4 (via `@tailwindcss/vite`). The `transition-transform` and
`rotate-180` utilities work unchanged. For `CollapsibleContent` height animation, Tailwind
v4 does not provide the built-in `data-[state=open]:animate-*` utilities that older shadcn
snippets reference — those require `tw-animate-css` which IS in the project's devDependencies
(`"tw-animate-css": "^1.4.0"`). The `data-[state=open]` and `data-[state=closed]` CSS
attribute selectors are set by Radix automatically and can be targeted in Tailwind v4 via
`data-[state=open]:...` variant syntax.

For a simple height transition, the cleanest approach for this project is:

```css
/* Applied to CollapsibleContent wrapper */
data-[state=closed]:hidden
/* or use overflow-hidden + max-height transition */
```

Simplest reliable pattern: rely on Radix's own CSS variable `--radix-collapsible-content-height`
which is set on the content element, enabling smooth height animation without additional
packages:

```css
/* In tailwind or global CSS */
[data-state=open] { animation: collapsible-down 0.2s ease; }
[data-state=closed] { animation: collapsible-up 0.2s ease; }
```

`tw-animate-css` provides `animate-collapsible-down` and `animate-collapsible-up` classes
that use these variables. Use them directly.

### Anti-Patterns to Avoid
- **Accordion instead of Collapsible:** Don't use `Accordion` — it enforces single-open
  semantics. `Collapsible` is the right primitive for a standalone toggle.
- **Custom useState-based show/hide with `display:none`:** Loses accessibility (ARIA
  `aria-expanded` is handled automatically by Radix). Don't hand-roll this.
- **Importing from `@radix-ui/react-collapsible` directly:** Prefer `radix-ui` monorepo
  import to stay consistent with how `Slot`, `Tooltip`, etc. are imported elsewhere.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Expand/collapse toggle | Custom `useState` + CSS display toggle | `Collapsible` from `radix-ui` | ARIA `aria-expanded`, keyboard (Enter/Space), focus management handled automatically |
| Height animation | JS-measured height with `style.height` | Radix CSS custom property `--radix-collapsible-content-height` | Cross-browser, no layout thrash |
| Icon rotation on open | Manual class toggling | `cn("transition-transform", open && "rotate-180")` | Already established pattern in the codebase (sidebar uses same) |

---

## Scope Analysis

### What Needs to Change

| Layer | Change Required | Scope |
|-------|-----------------|-------|
| `frontend/src/components/ui/collapsible.tsx` | **Create** — thin Radix wrapper | New file, ~15 lines |
| `frontend/src/components/ChatMessage.tsx` | Replace `CitationList` with collapsible version | Modify existing component, ~20 lines changed |
| `src/generation/generator.py` | Remove the `**Sumber Referensi:**` text block appended at lines 98-102 | Backend change, ~5 lines deleted |
| `frontend/src/components/CitationCard.tsx` | No change required | Unchanged |
| `frontend/src/types/sse.ts` | No change required | Unchanged |
| `backend/main.py` | No change required | Unchanged |
| `src/generation/citation_builder.py` | No change required | Unchanged |

### Format String Analysis

**Requirement:** "Horngren, Cost Accounting, Chapter 5, hal. 168-172"

**Current `build_citation()` output:** `"{book_title}, {chapter}, hal. {page_start}-{page_end}"`

Example with actual data: `"Cost Accounting, Chapter 5, hal. 168-170"`

**Gap identified:** The required format in the success criteria includes the **author name**
("Horngren") as a prefix before the book title. The current `build_citation()` function does
NOT include an author field — it only uses `book_title`, `chapter`, and page range.

Investigation of metadata schema (from `conftest.py` `sample_chunks`):

```python
"metadata": {
    "book_title": "Cost Accounting",
    "author": "Horngren",   # <-- field EXISTS in metadata
    "chapter": "Chapter 5",
    ...
}
```

The `author` field IS present in chunk metadata (confirmed in `conftest.py`). However,
`build_citation()` does not read it, and `build_citations()` does not pass it through to
the returned dict.

**Verdict:** The `formatted` field currently produces `"Cost Accounting, Chapter 5, hal. 168-170"` — it is missing the author prefix. To match the required format exactly ("Horngren, Cost Accounting, Chapter 5, hal. 168-172"), `citation_builder.py` needs a small update to:
1. Read `author` from metadata in `build_citation()`
2. Prepend author if available: `"{author}, {book_title}, {chapter}, hal. X-Y"`
3. Pass `author` field through in `build_citations()` return dict

This is a **backend change** but very small (3-4 lines). The `Citation` TypeScript type in
`sse.ts` would also need an optional `author?: string` field added if the frontend needs to
display the author separately — but for the `formatted` clipboard copy string, this is purely
a backend format fix.

**Note on inline LLM citations:** The system prompts already instruct the LLM to use format
`"Horngren, *Cost Accounting*, Chapter 5, hal. 168-172"` in its generated text (confirmed
in `config/prompts.py` lines 13, 37). The LLM produces inline citations with author names
because it's explicitly prompted. The structured `formatted` field from `citation_builder.py`
is used for the clipboard copy button — it currently lacks the author prefix.

### The Duplicate Citation Problem

`generator.py` lines 98-102 append a plain-text citation block to `response_text`:

```python
if citations:
    citation_lines = [f"- {c['formatted']}" for c in citations]
    citation_block = "\n\n**Sumber Referensi:**\n" + "\n".join(citation_lines)
    full_response = response_text + citation_block
```

This text is streamed as Markdown to the frontend and rendered by `MarkdownContent`. The
`CitationList` (to become collapsible) then renders the same citations again from the
structured SSE `citations` event. With the new collapsible UI, this duplication becomes
more obvious. This append should be **removed from `generator.py`** — the structured
`CitationList` is the canonical citation display.

**Risk:** Removing this append means the inline `[1]`, `[Sumber 1]` markers in the LLM
text will still link to citation cards (the `renderWithCitations` function handles this),
but the redundant `**Sumber Referensi:**` list at the end of the text will be gone. This
is the desired behavior.

---

## Common Pitfalls

### Pitfall 1: Collapsible not closing during streaming phase
**What goes wrong:** `CitationList` is rendered during `phase === "generating"` (no), but
`CitationList` / `CollapsibleCitationList` is only rendered in `phase === "done"` and in
`messages.map()` for history. During streaming, citations haven't arrived yet (they're
sent after the full response text). So the collapsible only appears after `done` phase.
**How to avoid:** No special handling needed — citation SSE event arrives after all text
chunks, before the `done` event. The existing conditional rendering already handles this.

### Pitfall 2: Scroll-to-citation anchor broken after collapsible wrapping
**What goes wrong:** `renderWithCitations()` creates `<a href="#citation-{n-1}">` links
that call `document.getElementById('citation-{n-1}').scrollIntoView()`. If citations are
collapsed, the `id={citation-${index}}` elements don't exist in the DOM (Radix unmounts
collapsed content). Clicking a `[1]` superlink in the text would silently fail.
**How to avoid:** Two options:
  1. Auto-open the collapsible when a citation anchor link is clicked (add an `onClick`
     handler to the trigger button, or expose a ref/callback).
  2. Use `defaultOpen={true}` — start expanded, let user collapse. This is simpler and
     arguably better UX (citations visible by default, collapsible for focus).
**Recommendation:** Default to `open={false}` (collapsed), and in the anchor click handler
in `renderWithCitations`, also trigger `setOpen(true)` before scrolling. This requires
lifting the `open` state up to the parent or using a shared ref. The simplest fix is:
keep `defaultOpen={false}` and modify the `onClick` in `renderWithCitations` to first open
the section, then scroll after a brief delay. However, this requires `open` state to be
accessible from `renderWithCitations`. The cleanest solution is to wrap `CitationList` in a
component with its own `open` state and pass a callback to `renderWithCitations` — but this
complicates the data flow. **Simplest viable approach:** Start with `defaultOpen={false}`,
and the scroll-on-click anchor links simply open the section if closed (handle via
`setOpen(true)` in the anchor's `onClick`). This requires passing `setOpen` into
`renderWithCitations` or converting it to a hook/context. Given scope, the **recommended
pragmatic choice** is to auto-open on anchor click with a small state-lifting change in
`ChatMessage.tsx`.

### Pitfall 3: Animation not working in Tailwind v4
**What goes wrong:** Standard shadcn/ui collapsible snippets use keyframes like
`animate-collapsible-down` / `animate-collapsible-up` that rely on `tw-animate-css`. If
that package is not imported in the global CSS, animations silently fail and content just
snaps open/closed.
**How to avoid:** Check that `tw-animate-css` is imported in `frontend/src/index.css` or
`frontend/src/App.tsx`. Since it's in devDependencies, it must be explicitly imported.
If not imported, either add the import or skip height animation (use
`data-[state=closed]:hidden` for simplicity — no animation, just show/hide).

### Pitfall 4: History view citations not collapsible
**What goes wrong:** `CitationList` is used in two places in `ChatMessage.tsx`: (1) inside
`messages.map()` for history turns, and (2) for the current `phase === "done"` turn. Both
must be updated to use the new collapsible component — the history turns should also have
collapsible citations.
**How to avoid:** Replace ALL occurrences of `<CitationList ... />` in `ChatMessage.tsx`,
not just the one in the `phase === "done"` block.

---

## Code Examples

### Radix Collapsible — Minimal verified API
```typescript
// Source: frontend/node_modules/@radix-ui/react-collapsible/dist/index.d.ts
import { Collapsible } from "radix-ui";

<Collapsible.Root open={open} onOpenChange={setOpen}>
  <Collapsible.Trigger>Toggle</Collapsible.Trigger>
  <Collapsible.Content>
    {/* content unmounts when closed by default */}
  </Collapsible.Content>
</Collapsible.Root>
```

### Existing project import pattern (consistent with tooltip.tsx)
```typescript
// frontend/src/components/ui/tooltip.tsx uses:
import { Tooltip } from "radix-ui";
// So collapsible should use:
import { Collapsible } from "radix-ui";
```

### ChevronDown rotation pattern (consistent with sidebar.tsx)
```typescript
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

<ChevronDown className={cn("h-3 w-3 transition-transform duration-200", open && "rotate-180")} />
```

### citation_builder.py — Author-aware format (fix required)
```python
# Current (line 24 in citation_builder.py):
return f"{book_title}, {chapter}, {page_ref}"

# Required (adding author prefix when available):
author = metadata.get("author", "")
prefix = f"{author}, " if author else ""
return f"{prefix}{book_title}, {chapter}, {page_ref}"
```

---

## Recommended Plan Breakdown

Two plans are sufficient for this phase:

**Plan A — Backend: citation format fix + remove duplicate text block**
- Fix `citation_builder.py`: add author prefix to `build_citation()`, pass `author` through in `build_citations()`.
- Remove the `**Sumber Referensi:**` text append from `generator.py` (lines 98-102).
- Update `tests/test_generation.py`: existing test `test_citation_format_in_response` must be updated to expect author prefix in `formatted` field, or a new test added.
- Risk: LOW — pure backend, no UI changes.

**Plan B — Frontend: collapsible CitationList**
- Create `frontend/src/components/ui/collapsible.tsx` wrapper.
- Replace `CitationList` with `CollapsibleCitationList` in `ChatMessage.tsx` (both usages).
- Handle anchor-click auto-open (lift open state or pass callback into `renderWithCitations`).
- Verify `tw-animate-css` is imported in global CSS; if not, add it or use simple show/hide.
- Risk: LOW — isolated UI component change, no API changes.

**Execution order:** Plan A first (fixes backend data), then Plan B (uses clean data in UI).
Plans are independent but Plan A's author fix makes the clipboard copy text in `CitationCard`
match the required format, which is a success criterion.

---

## Validation Architecture

`nyquist_validation` is enabled (`true` in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run pytest) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_generation.py -x` |
| Full suite command | `uv run pytest -m "not integration and not gpu"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-03 (backend part) | `formatted` field includes author prefix: "Horngren, Cost Accounting, Chapter 5, hal. 168-170" | unit | `uv run pytest tests/test_generation.py -x` | Exists, needs update |
| UI-03 (backend part) | `generator.py` does NOT append `**Sumber Referensi:**` block to response text | unit | `uv run pytest tests/test_generation.py::test_citation_format_in_response -x` | New test needed |
| UI-03 (frontend) | CollapsibleCitationList renders toggle button when citations exist | manual | n/a — React component test requires Vitest/jsdom not present | Wave 0 gap |
| UI-03 (frontend) | Citations panel is collapsed by default | manual | n/a | n/a |

**Frontend test note:** There is no Vitest or Jest setup in `frontend/`. Frontend validation
is manual (visual inspection in dev mode). Backend citation format is testable via pytest.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_generation.py -x`
- **Per wave merge:** `uv run pytest -m "not integration and not gpu"`
- **Phase gate:** Full backend suite green + manual UI smoke test before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_generation.py` — update `test_citation_format_in_response` to assert author prefix in `formatted` field
- [ ] `tests/test_generation.py` — add `test_no_citation_text_block_in_response` asserting `**Sumber Referensi:**` not in response text

---

## Environment Availability

Step 2.6: All dependencies are already installed. No external tooling required beyond what
is already present.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `@radix-ui/react-collapsible` | Collapsible UI | Yes (transitive) | 1.1.12 | — |
| `lucide-react` | ChevronDown icon | Yes | ^0.575.0 | — |
| `tw-animate-css` | Height animation | Yes (devDep) | ^1.4.0 | Use `data-[state=closed]:hidden` |
| `radix-ui` monorepo | Import path | Yes | 1.4.3 | — |

---

## Open Questions

1. **Author field availability in production data**
   - What we know: `author` field exists in `conftest.py` sample_chunks metadata and is
     defined in the metadata schema.
   - What's unclear: Whether all indexed Qdrant chunks actually have `author` populated
     (depends on what was stored during ingestion). If `author` is absent for a chunk,
     `build_citation()` should gracefully omit the prefix.
   - Recommendation: The `build_citation()` fix must handle `author` being empty/None
     gracefully — `prefix = f"{author}, " if author else ""` covers this.

2. **Scroll-to-anchor UX with collapsed citations**
   - What we know: `renderWithCitations` calls `document.getElementById(...).scrollIntoView()`
     which fails silently if the element is unmounted (Radix removes content from DOM when
     closed).
   - What's unclear: Whether this is a real UX problem or an edge case. Users are unlikely
     to click `[1]` in text without noticing the collapsible button below.
   - Recommendation: For Phase 5 scope, add `onClick` to trigger open state before scrolling.
     Accept a slight delay (e.g., `setTimeout(() => scrollIntoView(), 150)` after opening).

---

## Sources

### Primary (HIGH confidence)
- `frontend/node_modules/@radix-ui/react-collapsible/dist/index.d.ts` — Collapsible API
  (Root, Trigger, Content props) confirmed from installed package
- `frontend/node_modules/radix-ui/src/index.ts` — confirmed `Collapsible` is exported from
  `radix-ui` monorepo package
- `frontend/src/components/ChatMessage.tsx` — current `CitationList` implementation
- `frontend/src/components/CitationCard.tsx` — current card structure
- `frontend/src/types/sse.ts` — `Citation` type definition
- `src/generation/citation_builder.py` — `build_citation()` format logic
- `src/generation/generator.py` — redundant citation text block (lines 98-102)
- `config/prompts.py` — LLM citation format instructions
- `tests/test_generation.py` — existing citation unit tests
- `frontend/package.json` — confirmed `tw-animate-css` in devDependencies

### Secondary (MEDIUM confidence)
- `tests/conftest.py` — `author` field present in sample_chunks metadata, confirming
  `author` is part of the metadata schema

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies verified from installed node_modules
- Architecture: HIGH — Radix API verified from installed type definitions
- Backend format gap: HIGH — traced from `build_citation()` source + test assertions
- Animation pattern: MEDIUM — `tw-animate-css` in devDeps, import status in global CSS not verified

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable dependencies, no fast-moving ecosystem)
