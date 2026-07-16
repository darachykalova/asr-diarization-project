---
target: frontend/src/pages/UsersPage.tsx
total_score: 25
p0_count: 1
p1_count: 2
timestamp: 2026-07-16T19-37-58Z
slug: frontend-src-pages-userspage-tsx
---
Method: dual-agent, degraded detector (⚠️ Assessment B terminated early on a session limit after reporting "3 anti-patterns found" without detail; CLI re-run pending)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Role/block patches had zero pending state and zero success feedback |
| 2 | Match Between System and Real World | 3 | Empty state was a bare "Пусто"; errors surfaced as raw Error: HTTP 500 |
| 3 | User Control and Freedom | 3 | Confirms with Cancel/Esc exist; unblock is reversible |
| 4 | Consistency and Standards | 3 | Row role-select had no focus ring, border token drift |
| 5 | Error Prevention | 1 | No self-block/self-demote guard in UI; Chrome autofilled the admin's own login+password into the create form |
| 6 | Recognition Rather Than Recall | 3 | No "(вы)" marker on own row; created password vanishes with no copy affordance |
| 7 | Flexibility and Efficiency of Use | 2 | No refocus after create; no search/filter |
| 8 | Aesthetic and Minimalist Design | 4 | Cleanly on-system |
| 9 | Error Recovery | 2 | One shared top banner, String(e) prefix leaked, no role="alert" |
| 10 | Help and Documentation | 2 | 8-char password minimum invisible until native validation fired |
| **Total** | | **25/40** | **Acceptable** |

## Anti-Patterns Verdict

**LLM assessment**: not slop — follows the documented system; gaps were omissions, not template filler. ConfirmDialog (focus trap, aria-modal, Esc, focus restore) called out as genuinely good.

**Deterministic scan**: degraded — the detector agent reported "3 anti-patterns found" via browser injection but terminated on a session limit before detailing them. Based on sibling pages, likely candidates are low-contrast gray-400 text instances; a follow-up `/impeccable audit` can confirm.

## Priority Issues (all frontend fixes applied same-session)

- **[P0]** Self-lockout was one confirm away: own row showed an enabled block button and live role select; with ≥2 super_admins the backend permits self-block → instant session kill (server guard only covers the last-active-super_admin case, database/crud.py:662-687). Fixed in UI: own row is marked "(вы)", role select disabled, block button replaced with an em-dash. **Remaining (backend, not done): add a self-patch guard in the PATCH /v1/admin/users/{id} route.**
- **[P1]** Browser autofill poisoned the create form with the admin's own login+password (observed live). Fixed: autocomplete="off" on form/login, "new-password" on password, distinct name attrs.
- **[P1]** Silent mutations. Fixed: per-row busy state disables controls mid-PATCH, success notice "Пользователь X создан" (role="status" live region), error banner now role="alert" without the String(e) prefix.
- **[P2]** Unlabeled controls. Fixed: htmlFor/id on form fields; per-row aria-labels naming the affected login on the role select and block button; focus ring + border token aligned on the row select.
- **[P3]** Mute copy. Fixed: real empty-state sentence; "Минимум 8 символов" hint under the password (aria-describedby).
- Also: demoting a super_admin now renders the confirm in danger styling; login field refocuses after successful create.

## Persona Red Flags

**Alex**: serial account creation fought autofill and left focus stranded (both fixed); no copy-credentials affordance (not addressed — see What if).
**Sam**: anonymous textboxes, indistinguishable per-row controls, unannounced banners (all fixed).

## Minor observations

- fmtDate renders "Invalid Date" on malformed input (not addressed).
- No search/pagination — fine at current scale.
- No show-password toggle (not addressed).

## Questions to Consider

- What if creation returned a one-time credentials card (login + password + copy button)?
- What if promoting to super_admin required retyping the login?
