---
target: frontend/src/pages/AudioListPage.tsx
total_score: 23
p0_count: 2
p1_count: 2
timestamp: 2026-07-16T11-43-01Z
slug: frontend-src-pages-audiolistpage-tsx
---
Method: dual-agent (isolated sub-agents)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Re-search/sort gives no in-table loading cue (only the submit button label changes) |
| 2 | Match Between System and Real World | 3 | Filter says "Длительность от (мин)" but table displays m:ss — minor unit mismatch |
| 3 | User Control and Freedom | 2 | No undo after delete; filters reset on back-navigation |
| 4 | Consistency and Standards | 3 | Row-level "Удалить" is a bare underlined link, not DESIGN.md's `button-danger-ghost` spec |
| 5 | Error Prevention | 2 | Confirm dialog can show a raw UUID with no human-recognizable anchor (date/duration) |
| 6 | Recognition Rather Than Recall | 2 | Filters/sort/page live only in component state, not the URL — nothing to recall a search by |
| 7 | Flexibility and Efficiency of Use | 1 | No bulk select/delete, no keyboard shortcuts, no saved filters, no export |
| 8 | Aesthetic and Minimalist Design | 4 | Clean, single accent, flat cards, no clutter |
| 9 | Error Recovery | 2 | Error banner shows a raw `String(e)` exception, not a friendly message |
| 10 | Help and Documentation | 1 | No inline help beyond a native `title` tooltip on sort headers |
| **Total** | | **23/40** | **Acceptable — significant improvements needed before users are happy** |

## Anti-Patterns Verdict

**LLM assessment**: No AI-slop tells here — flat cards, one blue accent, real status colors, no gradients/hero type. If anything it under-decorates, matching DESIGN.md's own admission that the system reads as "competent and slightly under-designed."

**Deterministic scan**: CLI mode (`detect.mjs --json` on the file alone) returned 0 findings — it only meaningfully analyzes rendered markup. The browser-injected detector found 23 hits: 20× `low-contrast` (all the same source line — the `job_id` sub-label, `text-gray-400` on white, 2.5:1 ratio, needs 4.5:1 — one real defect repeated once per table row), 1× `cramped-padding`, 1× `single-font`, 1× `nested-cards`.

**False positives** (confirmed by re-reading the surrounding code): `single-font: only font is apple color emoji` is a detector artifact matching an emoji fallback font, not a real typography problem. `nested-cards` on the `<thead>` is a standard table-header background/border treatment, not a composition issue. The `cramped-padding` hit is minor and not corroborated by the design review.

**Visual overlay**: findings were captured via console output during a temporary injection; the live-server was stopped afterward (required cleanup), so no overlay persists in the browser now.

## Overall Impression

This page is honest, uncluttered, and true to the "Duty Desk" personality — the biggest gap isn't visual, it's that the one genuinely irreversible action on the page (delete) has a confirm dialog with no focus trap, verified live: Tab from the open dialog lands on a background table row, not Cancel/Delete. That's a real risk sitting right at the highest-stakes moment on the page, undercutting exactly the "confidence via clarity" goal PRODUCT.md sets.

## What's Working

- The "Ещё фильтры" grid-template-rows collapse (`AudioListPage.tsx:230-234`) is a genuinely tasteful progressive-disclosure pattern, not a jarring show/hide.
- `ConfirmDialog`'s danger/non-danger branching and scale+fade entrance match DESIGN.md's modal and press-feedback rules exactly.
- Status badges pair a text label with a soft-tint/deep-text color, never color alone.

## Priority Issues

**[P0] ConfirmDialog has no focus trap**
- Why it matters: verified live — pressing Tab once while the delete-confirm dialog is open moves focus to a background row link, not Cancel/Delete. A keyboard or screen-reader user can act on the wrong element mid-delete-flow.
- Fix: trap focus inside the dialog (first focusable element → Cancel/Delete), restore focus to the trigger on close, add `role="dialog" aria-modal="true"`.
- Suggested command: `/impeccable harden`

**[P0] Sort headers are unreachable by keyboard**
- Why it matters: `SortHeader`'s `<th onClick>` (AudioListPage.tsx:60-74) has no focusable element inside it — confirmed absent from the accessibility tree. Sam (keyboard/screen-reader user) cannot sort the table at all.
- Fix: put a real `<button>` inside the `<th>` with a visible focus ring.
- Suggested command: `/impeccable harden`

**[P1] Delete-confirm message can show a bare UUID**
- Why it matters: when a recording has no real filename, the confirm text reads `«d0a92fb8-38b2-…» будет удалена без возможности восстановления` — no recognizable anchor (date/duration) for the one deliberate "are you sure" check on an irreversible action.
- Fix: always include upload date + duration in the confirm message regardless of title.
- Suggested command: `/impeccable clarify`

**[P1] No bulk actions, no persisted search state**
- Why it matters: a moderator triaging under time pressure re-enters every filter after opening a transcript and hitting back; no checkbox/bulk-delete exists for handling a batch of flagged recordings.
- Fix: sync filters/sort/page to the URL query string; add row checkboxes + bulk delete.
- Suggested command: `/impeccable optimize`

**[P2] `job_id` sub-label fails contrast (2.5:1, needs 4.5:1)**
- Why it matters: detector-confirmed, real, and repeats once per visible row (20× on a full page) — `text-gray-400` on white under every filename is borderline unreadable, especially for low-vision users.
- Fix: use DESIGN.md's `muted-text` (`#6b7280`) or darker instead of the lighter gray for this label.
- Suggested command: `/impeccable audit`

## Persona Red Flags

**Alex (Power User)**: no bulk delete (no checkboxes in the DOM), no keyboard shortcut to focus search, pagination is prev/next-only with no jump-to-page, no CSV/export action anywhere on the page.

**Sam (Accessibility-dependent)**: the sort-header keyboard gap and the ConfirmDialog focus-trap gap (both reproduced live) block full keyboard-only completion of the page's core flow. Status badges are fine (text + color), but the sort-direction indicator is mouse-hover/tooltip-only and never reaches assistive tech since the header isn't focusable.

## Minor Observations

- Row-level "Удалить" is a bare text link, not the `button-danger-ghost` component spec `ConfirmDialog`'s own button correctly follows — a design-system consistency gap.
- Error banner shows a raw exception string (`String(e)`) instead of a friendly message.
- No in-table loading indicator during re-search — only the submit button's label changes.
- The advanced filter panel, once opened, is one flat 9-field grid with no sub-grouping (Identity / Shape / Time) — contributes to a "critical" cognitive-load checklist score (4/8 items failed: chunking, grouping, minimal-choices, working-memory), though the panel being collapsed by default and using progressive disclosure meaningfully softens this.
- Duration filter is entered in minutes but the table displays m:ss — a small unit mismatch.

## Questions to Consider

- What if the 9-field advanced panel became 3 labeled clusters (Identity / Shape / Time) instead of one flat grid — would that alone fix the chunking failure without adding UI chrome?
- What if filters lived in the URL, so "share this exact search" became free and back-navigation stopped silently discarding a moderator's work?
- What if the delete confirm always showed duration + upload date regardless of title, so the "are you sure" moment never depends on whether the file happened to get a real name?
