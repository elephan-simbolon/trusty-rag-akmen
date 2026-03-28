---
plan: 05-02
phase: 05-polish
status: complete
completed: 2026-03-28T00:00:00Z
tasks: 1
files_modified: 5
---

# Plan 05-02 Summary: Collapsible Citation Panel + Gap Fix

## What Was Built

Replaced always-visible `CitationList` with a collapsible `CollapsibleCitationList` component. Citations now appear collapsed by default below the answer text, revealed on user demand. Gap fix applied: CitationCard now shows author prefix before book title.

## Accomplishments

- **collapsible.tsx** — New thin Radix UI wrapper exporting `CollapsibleRoot`, `CollapsibleTrigger`, `CollapsibleContent` (follows existing tooltip.tsx pattern)
- **CollapsibleCitationList** — Replaces `CitationList` in `ChatMessage.tsx`; collapsed by default with "Lihat N referensi" toggle button; smooth animate-collapsible-down/up transition
- **Anchor auto-open** — Clicking inline `[Sumber N]` superscript links auto-opens collapsed citations via `openCitationsRef`, then scrolls to target CitationCard after 200ms animation delay
- **Author prefix in CitationCard** — `CitationCard.tsx` now renders `citation.author + ", "` prefix before `book_title` when author field is present
- **Citation interface** — `sse.ts` Citation type includes `author?: string` field (optional for backward compatibility with cached responses)
- Both history turns and the active done-phase turn use `CollapsibleCitationList`

## Files Modified

- `frontend/src/components/ui/collapsible.tsx` (created)
- `frontend/src/components/ChatMessage.tsx` (refactored)
- `frontend/src/components/CitationCard.tsx` (author prefix fix)
- `frontend/src/types/sse.ts` (author field added)
- `.planning/phases/05-polish/05-UAT.md` (gap recorded and resolved)

## Verification

- TypeScript compiles without errors (`npx tsc --noEmit` clean)
- UAT Phase 05: 4 passed, 1 issue (gap closed by commit 0598e93)
- All collapsible toggle, history turns, and citation format tests passed
