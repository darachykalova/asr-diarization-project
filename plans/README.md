# Animation improvement plans

Output of an `improve-animations` audit of `frontend/src` (2026-07-16, commit
`e7616b3`). All findings below were implemented directly in the working tree
the same session, rather than being executed by a separate agent — the plan
docs remain as a record of the exact problem/target/rationale for each.

| # | Title | Severity | Status |
| --- | --- | --- | --- |
| 001 | Progress bars: `transform: scaleX()` instead of `width` | HIGH | DONE |
| 002 | Success/save panels use the established mount-fade | MEDIUM | DONE |
| 003 | Nav "Управление" dropdown gets an anchored entrance | MEDIUM | DONE |

## Findings implemented without a separate plan doc

These were fixed directly (small enough not to warrant a full plan file):

- `frontend/src/pages/SettingsPage.tsx` — `Tooltip` popover now fades+scales
  in from its trigger icon instead of popping instantly.
- `frontend/src/components/MascotCat.tsx`, `frontend/src/components/LoadingSpinner.tsx` —
  infinite looping animations now respect `prefers-reduced-motion`.
- Press-feedback (`active:scale-[0.97]`) and hover-transition sweep across
  ~12 buttons/table rows that had none: `CallsListPage.tsx`, `CallDetailPage.tsx`,
  `AudioDetailPage.tsx`, `UsersPage.tsx`, `AuditLogPage.tsx`, `LoginPage.tsx`,
  `UploadPage.tsx`, `Nav.tsx`.
- Missed-opportunity fixes: spinner→content teleport on `AudioDetailPage.tsx`,
  `CallsListPage.tsx`, `CallDetailPage.tsx` now fades in via a new shared
  `frontend/src/components/FadeIn.tsx`; the transcript reveal on
  `AudioDetailPage.tsx` also fades in through the same component.

## Not implemented

- **`AnalyticsPage.tsx` chart re-render on bucket toggle** (LOW) — decorative
  crossfade for an internal analytics view; left as-is, low leverage.
- **Silent expired-JWT redirect to `/login`** (`AuthContext.tsx`/`ProtectedRoute.tsx`) —
  flagged as a missed opportunity, but it's a UX/messaging fix (needs a
  toast/explanation before redirect), not a pure animation change — out of
  scope for this pass.
