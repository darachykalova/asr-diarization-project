---
target: frontend/src/pages/SettingsPage.tsx
total_score: 25
p0_count: 1
p1_count: 2
timestamp: 2026-07-16T14-41-22Z
slug: frontend-src-pages-settingspage-tsx
---
Method: dual-agent (isolated sub-agents)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No unsaved-changes indicator; save equally enabled with 0 or 6 edits |
| 2 | Match Between System and Real World | 3 | Language list ordered by English name — reads randomly in Russian |
| 3 | User Control and Freedom | 2 | No reset/cancel; nav away silently loses edits |
| 4 | Consistency and Standards | 3 | Save button lacked press feedback; ring/border token drift vs DESIGN.md |
| 5 | Error Prevention | 2 | Out-of-range shows inline but save still fires (server 422); formats uncheck-all lied |
| 6 | Recognition Rather Than Recall | 3 | Great inline range hints, but all explanatory copy hover-only |
| 7 | Flexibility and Efficiency of Use | 2 | Single bottom save; no Ctrl+S/per-field save |
| 8 | Aesthetic and Minimalist Design | 4 | Clean, flat, on-system |
| 9 | Error Recovery | 1 | Failed save rendered String(e) at page top, off-screen from the button |
| 10 | Help and Documentation | 3 | Genuinely excellent hint copy, mouse-only delivery |
| **Total** | | **25/40** | **Acceptable** |

## Anti-Patterns Verdict

**LLM assessment**: not slop — expert Russian hint copy and typed per-setting controls show real product thinking; remaining tells were structural defaults (hover-only tooltips, token drift).

**Deterministic scan**: CLI found 1 `gray-on-color` at the tooltip trigger — confirmed false positive (blue bg is hover-only and text turns blue simultaneously). Browser scan found 3× `low-contrast` on the "Допустимо: X – Y" hints (gray-400 on white, 2.5:1) — real, fixed.

## Priority Issues (all fixed same-session, commit 4f48f78)

- **[P0]** Tooltips and labels invisible to assistive tech (mouseenter-only spans, no htmlFor, unannounced banners). Fixed: keyboard-focusable tooltip buttons, real labels, live regions, aria-invalid.
- **[P1]** No dirty state — save always enabled, edits silently lost on unload. Fixed: disabled-when-clean save, "Изменено: N", beforeunload guard.
- **[P1]** Formats uncheck-all snapped back to all-checked (display lied about the empty-is-valid contract). Fixed: honest empty state with explanatory line; API contract untouched.
- **[P2]** Failed save undiagnosable (String(e) at page top). Fixed: humanized role="alert" message next to the save button; load errors stay at top as separate state.
- **[P2]** Flat ungrouped list + mis-sorted language dropdown. Fixed: three labeled sections + Прочее; ru/uk/be/en pinned atop the select.
- Detector contrast on range hints fixed (gray-500); token drift and press feedback aligned to DESIGN.md.

## Persona Red Flags

**Alex**: had no way to verify a save "took" beyond a 3-second banner, and the save button gave no signal about pending edits (fixed via dirty counter/disabled state).
**Sam**: couldn't reach any hint, heard unnamed inputs, and never heard success/failure (fixed via the a11y bundle).

## Minor Observations

- Loading state now uses the shared LoadingSpinner (was bare "Загрузка…" text).
- Tooltip fixed w-72 may clip near viewport edge (not addressed — low value).
- Mascot overlap noted app-wide; most dissonant here (not addressed).

## Questions to Consider

- What if each setting saved itself with per-row confirmation — would a global save button need to exist?
- What if the success banner echoed the diff ("max_upload_size_mb: 2048 → 4096") tying into the audit log?
