---
target: frontend/src/pages/LoginPage.tsx
total_score: 24
p0_count: 1
p1_count: 2
timestamp: 2026-07-16T14-27-25Z
slug: frontend-src-pages-loginpage-tsx
---
Method: dual-agent (isolated sub-agents)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Button swaps to "Вход…" + disables, but no spinner/aria-busy |
| 2 | Match Between System and Real World | 2 | Backend's English "Invalid credentials" leaked onto an all-Russian screen |
| 3 | User Control and Freedom | 2 | No forgot-password path or guidance after repeated failures |
| 4 | Consistency and Standards | 3 | Card used shadow-md, off DESIGN.md's Card tier |
| 5 | Error Prevention | 1 | Only native HTML required; no capslock warning or reveal toggle |
| 6 | Recognition Rather Than Recall | 4 | autoComplete username/current-password correctly wired |
| 7 | Flexibility and Efficiency of Use | 3 | Enter-to-submit and autofill both work |
| 8 | Aesthetic and Minimalist Design | 4 | Appropriately bare — two fields, one button |
| 9 | Error Recovery | 1 | Generic unlocalized error, no aria-live, no field-level indication |
| 10 | Help and Documentation | 1 | Zero on-screen guidance after failures |
| **Total** | | **24/40** | **Acceptable** |

## Anti-Patterns Verdict

**LLM assessment**: reads as the generic centered-card-on-gray login template every AI scaffold produces; even the shadow token didn't match the project's own DESIGN.md.

**Deterministic scan**: CLI clean (0 findings). Browser injection was attempted but inconclusive (script request hung in pending, no detector global appeared) — reported honestly as a failed injection, not a clean pass.

## Priority Issues (all fixed same-session, commit 8655030)

- **[P0]** Labels not programmatically associated with inputs (no htmlFor/id) — screen readers announced two unlabeled textboxes. Fixed.
- **[P1]** Backend "Invalid credentials" (English) overrode the Russian fallback — verified live with curl; error line had no aria-live. Fixed: normalized client-side + role="alert".
- **[P1]** No recovery path after a failed login. Fixed: static help line pointing at the platform administrator.
- **[P2]** No field-level error indication. Fixed: red border on both inputs while the error is shown.
- **[P3]** shadow-md → shadow per DESIGN.md Card tier. Fixed; also added aria-busy on the submit button.

## Persona Red Flags

**Jordan**: mistyped password produced an English error with no guidance and no field indication (now fixed).
**Sam**: unlabeled inputs + unannounced error made a failed submit invisible to a screen reader (now fixed).

## Minor Observations

- No capslock indicator on the password field (not addressed — low value for an internal tool).
- Native browser required-validation bubble is browser-locale-dependent (accepted).

## Questions to Consider

- What if the shadow/label/error-announcement patterns were pulled into a shared FormField primitive so this class of bug can't recur?
- What if the error state distinguished a typo from a disabled account without leaking which credential was wrong?
