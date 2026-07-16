# 001 — Animate progress/bar fills via `transform: scaleX()` instead of `width`

- **Status**: DONE (implemented directly in code, not via separate executor)
- **Commit**: e7616b3
- **Severity**: HIGH
- **Category**: Performance
- **Estimated scope**: 2 files, ~10 lines changed total

## Problem

Two bar-fill UIs animate `width` (a layout property — triggers layout + paint +
composite on every frame) through Tailwind's `transition-all` (an unbounded
property list) instead of animating `transform` (composite-only, GPU-friendly).
Both update frequently while visible (upload progress fires many times per
second via XHR progress events; the analytics bars re-render on every data
fetch), so the cost is paid repeatedly at exactly the moment the user is
watching.

```tsx
// frontend/src/pages/AnalyticsPage.tsx:28-39 — current
function HBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="w-36 text-sm text-gray-700 truncate shrink-0" title={label}>{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
        <div className="h-4 bg-blue-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-xs text-gray-500 text-right shrink-0">{value}</span>
    </div>
  );
}
```

```tsx
// frontend/src/pages/UploadPage.tsx:233-238 — current
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
```

## Target

Per AUDIT.md category 2 (Easing & duration), progress-style fills fall under
"Constant motion (marquee, progress) → **`linear`**". Per category 5
(Performance), animate `transform`/`opacity` only, and never use
`transition-all`.

```tsx
// frontend/src/pages/AnalyticsPage.tsx:28-39 — target
function HBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="w-36 text-sm text-gray-700 truncate shrink-0" title={label}>{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
        <div
          className="h-4 w-full bg-blue-400 rounded-full origin-left transition-transform duration-200 ease-linear"
          style={{ transform: `scaleX(${pct / 100})` }}
        />
      </div>
      <span className="w-10 text-xs text-gray-500 text-right shrink-0">{value}</span>
    </div>
  );
}
```

```tsx
// frontend/src/pages/UploadPage.tsx:233-238 — target
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 w-full rounded-full origin-left transition-transform duration-200 ease-linear"
                  style={{ transform: `scaleX(${progress / 100})` }}
                />
              </div>
```

Note: `pct`/`progress` are already 0–100 integers in both files — divide by
100 to get the 0–1 scale factor. `scaleX(0)` at the start is fine here (not
the "appears from nothing" case AUDIT.md warns about — that rule is about
elements popping into existence; this is a fill bar whose empty state is
legitimately zero width).

## Repo conventions to follow

- This codebase always scopes `transition-*` to the exact properties that
  change — never a bare `transition` or `transition-all`. Exemplar:
  `frontend/src/components/ConfirmDialog.tsx` button classes use
  `transition-[background-color,transform]`, not `transition`.
- Tailwind's `origin-left` utility sets `transform-origin: left center` — use
  it instead of an inline style.

## Steps

1. In `frontend/src/pages/AnalyticsPage.tsx`, replace the inner `<div>` of
   `HBar` (currently `className="h-4 bg-blue-400 rounded-full transition-all"
   style={{ width: `${pct}%` }}`) with the target shown above: add `w-full`
   and `origin-left`, replace `transition-all` with
   `transition-transform duration-200 ease-linear`, replace the `width` style
   with `transform: scaleX(${pct / 100})`.
2. In `frontend/src/pages/UploadPage.tsx`, apply the identical change to the
   upload-progress bar's inner `<div>` (the one with
   `style={{ width: \`${progress}%\` }}`).
3. Do not touch `VBar` in `AnalyticsPage.tsx` (the vertical bar chart) — its
   `height` is a one-shot render, not a live-updating fill, and is out of
   scope for this plan.

## Boundaries

- Do NOT touch `VBar` in `AnalyticsPage.tsx` or any other component.
- Do NOT change the `HBar`/`UploadPage` component's props, structure, or the
  surrounding layout — only the inner filled bar's className/style.
- Do NOT add a JS animation library or spring — this is a value-driven CSS
  transition, exactly like the existing `width` version, just retargeted to
  `transform`.
- If the current code at either file:line doesn't match the "Problem"
  excerpt above (drift since commit `e7616b3`), STOP and report instead of
  improvising.

## Verification

- **Mechanical**: `cd frontend && npx tsc --noEmit` (expect no errors) and
  `npm run build` (expect a clean Vite build, same as before).
- **Feel check**:
  - On `/analytics`, confirm the horizontal bars still visually reflect the
    correct proportion (a bar at `value/max = 0.5` still looks half-filled)
    — this is a pure rendering-technique swap, the visible result must be
    pixel-identical to before, just computed via `transform` instead of
    `width`.
  - On `/upload`, start an upload and confirm the progress bar still fills
    smoothly from 0% to 100% with no visual jump or flicker at any point.
  - Open Chrome DevTools → Rendering → "Paint flashing" during an upload;
    confirm the bar's own repaint region no longer triggers a full-row
    layout recalculation (compare before/after using the Performance panel's
    "Layout Shift"/"Recalculate Style" entries during the same upload).
- **Done when**: both bars render correctly at every value from 0–100, the
  build is clean, and neither file contains `transition-all` or a
  `width`-based fill anymore.
