# 002 — Give success/save panels the same mount-fade as toasts

- **Status**: DONE (implemented directly in code, not via separate executor)
- **Commit**: e7616b3
- **Severity**: MEDIUM
- **Category**: Cohesion & tokens / Missed opportunities
- **Estimated scope**: 2 files, ~15 lines changed total

## Problem

Two "it worked" panels pop into existence with zero transition, at exactly
the moments (a settings save, an upload finishing) where the codebase's own
established motion convention says this deserves standard animation
(AUDIT.md category 1: "Occasional → Standard animation", category 8: rare/
high-value moments are where delight belongs). Both reinvent ad-hoc
show/hide instead of reusing the mount-fade pattern already established
elsewhere in this codebase.

```tsx
// frontend/src/pages/SettingsPage.tsx:329-333 — current
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 rounded p-3 mb-4 text-sm">
          Настройки сохранены
        </div>
      )}
```

(`success` is a `useState(false)` boolean set to `true` on save and cleared
via `setTimeout(() => setSuccess(false), 3000)` — see
`frontend/src/pages/SettingsPage.tsx:235,273-274`.)

```tsx
// frontend/src/pages/UploadPage.tsx:133-152 — current
      {state === "done" && jobId ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <div className="text-green-600 text-4xl mb-3">✓</div>
          <p className="text-green-800 font-medium mb-1">Файл отправлен в обработку</p>
          <p className="text-sm text-gray-500 mb-4">Job ID: {jobId}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate(`/audio/${jobId}`)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
            >
              Открыть запись
            </button>
            <button
              onClick={() => { setFile(null); setJobId(null); setState("idle"); setProgress(0); }}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
            >
              Загрузить ещё
            </button>
          </div>
        </div>
      ) : (
```

## Target

Both become simple mount-fade wrappers using the exact pattern already used
for toasts: `useState(false)` + `requestAnimationFrame` to flip a `mounted`
flag on the next frame, driving an opacity+translateY transition with this
codebase's established strong ease-out curve.

```tsx
// frontend/src/pages/SettingsPage.tsx — target (new local component + call site)
function SuccessBanner({ show }: { show: boolean }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (!show) { setMounted(false); return; }
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, [show]);

  if (!show) return null;
  return (
    <div
      className={`bg-green-50 border border-green-200 text-green-700 rounded p-3 mb-4 text-sm transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:translate-y-0 ${
        mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
      }`}
    >
      Настройки сохранены
    </div>
  );
}
```

Call site replaces the inline conditional:

```tsx
// frontend/src/pages/SettingsPage.tsx:329-333 — target
      <SuccessBanner show={success} />
```

```tsx
// frontend/src/pages/UploadPage.tsx:133-152 — target (wrap the existing panel, don't rewrite its contents)
function DonePanel({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      className={`transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:translate-y-0 ${
        mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
      }`}
    >
      {children}
    </div>
  );
}

// call site: wrap the existing green panel div's contents in <DonePanel>...</DonePanel>,
// keep every existing className/button/onClick inside unchanged.
```

## Repo conventions to follow

- The rAF mount-flag pattern is established in
  `frontend/src/components/Notifications.tsx` (the `ToastItem` component) and
  `frontend/src/components/ConfirmDialog.tsx` — both use
  `useState(false)` + `useEffect(() => { const id = requestAnimationFrame(() => setMounted(true)); return () => cancelAnimationFrame(id); }, [...])`.
  Copy this exactly; don't invent a different mounting mechanism.
- Duration/easing: `duration-200 ease-[cubic-bezier(0.23,1,0.32,1)]` matches
  every other entrance in this codebase (`ConfirmDialog.tsx`,
  `Notifications.tsx`'s `ToastItem`, `CallSimulatorPage.tsx`'s `LogLine`).
  Do not introduce a different curve or duration.
- `motion-reduce:translate-y-0` neutralizes the movement only, leaving the
  opacity fade intact under `prefers-reduced-motion` — this codebase's
  established accessibility convention (see AUDIT.md category 6: "not zero").

## Steps

1. In `frontend/src/pages/SettingsPage.tsx`, add a `SuccessBanner` component
   (place it near the existing local `Tooltip`/`AsrModelControl` helper
   components, above the main `SettingsPage` export) exactly as shown in
   Target. Import `useEffect` alongside the existing `useState` import at the
   top of the file if not already imported.
2. Replace the `{success && (...)}` block at `SettingsPage.tsx:329-333` with
   `<SuccessBanner show={success} />`.
3. In `frontend/src/pages/UploadPage.tsx`, add a `DonePanel` wrapper
   component exactly as shown in Target (place it near the top of the file,
   above the `UploadPage` export). Import `useEffect` if not already
   imported.
4. Wrap the existing green "done" `<div>` (currently
   `<div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">...</div>`
   at `UploadPage.tsx:134-152`) in `<DonePanel>...</DonePanel>` — do not
   change anything inside that div (keep the ✓, the text, both buttons, and
   their `onClick` handlers exactly as they are).

## Boundaries

- Do NOT add an exit/leave animation — `success` auto-clears via
  `setTimeout` and the upload "done" state is dismissed by navigating away or
  clicking "Загрузить ещё", neither of which needs a coordinated unmount
  animation for this plan's scope. Entrance only.
- Do NOT touch the error banners in either file (`SettingsPage.tsx:326-328`,
  `UploadPage.tsx:243-247`) — out of scope for this plan.
- Do NOT change any button behavior, state variable names, or the save/upload
  logic — visual wrapper only.
- If the current code at either file:line doesn't match the "Problem"
  excerpts above (drift since commit `e7616b3`), STOP and report instead of
  improvising.

## Verification

- **Mechanical**: `cd frontend && npx tsc --noEmit` and `npm run build` both
  clean.
- **Feel check**:
  - On `/settings`, change a setting and save; confirm "Настройки сохранены"
    fades and slides up into place over ~200ms rather than popping in
    instantly, and disappears (still abruptly, per Boundaries) after 3s.
  - On `/upload`, upload a small file; confirm the green success panel fades
    in the same way once the upload completes.
  - In Chrome DevTools → Rendering → toggle `prefers-reduced-motion:
    reduce`; confirm both panels still fade in (opacity) but no longer
    slide (no `translate-y` movement).
  - DevTools Animations panel: set playback to 10% and confirm the two
    coordinated properties (opacity, transform) stay in sync across the full
    200ms — no visible stutter or one property finishing before the other.
- **Done when**: both panels animate in via the shared rAF+transition
  pattern, using the exact `cubic-bezier(0.23,1,0.32,1)` curve, and neither
  file has a bare conditional render with no transition class anymore.
