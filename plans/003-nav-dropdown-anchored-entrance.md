# 003 — Anchor the "Управление" nav dropdown to its trigger with a real entrance

- **Status**: DONE (implemented directly in code, not via separate executor)
- **Commit**: e7616b3
- **Severity**: MEDIUM
- **Category**: Physicality & origin
- **Estimated scope**: 1 file, ~20 lines changed

## Problem

The only trigger-anchored popover in the app currently mounts/unmounts with
a hard cut — no opacity/scale transition, and no `transform-origin` tying it
to the button that opened it. Per AUDIT.md category 3, popovers/dropdowns
should scale from their trigger, and a pure show/hide with no motion misses
the "spatial consistency" purpose (AUDIT.md category 1) that would otherwise
tell the user where this menu came from.

```tsx
// frontend/src/components/Nav.tsx:80-111 — current
        {management.length > 0 && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className={`text-sm transition-colors flex items-center gap-1 ${
                managementActive
                  ? "text-white underline underline-offset-4"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Управление <span className="text-xs">▾</span>
            </button>
            {menuOpen && (
              <div className="absolute left-0 top-full mt-2 bg-gray-800 border border-gray-700 rounded shadow-lg py-1 min-w-40 z-50">
                {management.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMenuOpen(false)}
                    className={`block px-4 py-2 text-sm transition-colors ${
                      location.pathname.startsWith(item.path)
                        ? "text-white bg-gray-700"
                        : "text-gray-300 hover:bg-gray-700 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
```

## Target

Keep the menu always mounted while `menuOpen` is true (same as today — this
plan does not add a leave animation, see Boundaries), but drive its
appearance through a `visible` flag set one frame after mount via
`requestAnimationFrame`, anchored at the top-left (where the trigger sits),
scaling from `0.95` (never `scale(0)` — AUDIT.md category 3) with opacity.

```tsx
// frontend/src/components/Nav.tsx — target
        {management.length > 0 && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className={`text-sm transition-colors flex items-center gap-1 ${
                managementActive
                  ? "text-white underline underline-offset-4"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Управление{" "}
              <span className={`text-xs transition-transform duration-150 ease-out ${menuOpen ? "rotate-180" : ""}`}>▾</span>
            </button>
            {menuOpen && <NavDropdown management={management} location={location} onNavigate={() => setMenuOpen(false)} />}
          </div>
        )}
```

Add a small local component (same file) that owns the mount-flag:

```tsx
// frontend/src/components/Nav.tsx — new component, place above `export function Nav()`
function NavDropdown({
  management, location, onNavigate,
}: {
  management: NavItem[];
  location: ReturnType<typeof useLocation>;
  onNavigate: () => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      className={`absolute left-0 top-full mt-2 bg-gray-800 border border-gray-700 rounded shadow-lg py-1 min-w-40 z-50 origin-top-left transition-[opacity,transform] duration-150 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:scale-100 ${
        visible ? "opacity-100 scale-100" : "opacity-0 scale-95"
      }`}
    >
      {management.map((item) => (
        <Link
          key={item.path}
          to={item.path}
          onClick={onNavigate}
          className={`block px-4 py-2 text-sm transition-colors ${
            location.pathname.startsWith(item.path)
              ? "text-white bg-gray-700"
              : "text-gray-300 hover:bg-gray-700 hover:text-white"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}
```

The chevron rotation (`rotate-180` on open) is a small bonus state-indication
fix bundled into this plan since it touches the same trigger button.

## Repo conventions to follow

- rAF mount-flag pattern: same as `ConfirmDialog.tsx` (`useState(false)` +
  `requestAnimationFrame` in a `useEffect`). Copy it exactly.
- Entrance curve/duration: this codebase uses
  `ease-[cubic-bezier(0.23,1,0.32,1)]` for entrances; dropdowns per AUDIT.md
  category 2 duration table get 150–250ms — this plan uses 150ms (the fast
  end, since it's a frequently-visible piece of chrome, not a rare modal).
- `scale-95` (never `scale(0)`) + `origin-top-left` (the menu hangs below-left
  of its trigger) — matches AUDIT.md category 3 exactly.

## Steps

1. In `frontend/src/components/Nav.tsx`, add the `NavDropdown` component
   shown in Target, placed above `export function Nav()`. It needs
   `useEffect` imported alongside the existing `useState`/`useRef` import at
   the top of the file (add `useEffect` to the existing
   `import { useEffect, useRef, useState } from "react";` line — check
   whether `useEffect` is already imported first; if the current import is
   `import { useRef, useState } from "react";`, add `useEffect` to it).
2. Replace the inline `{menuOpen && (<div className="absolute ...">...)}`
   block (currently `Nav.tsx:92-109`) with
   `{menuOpen && <NavDropdown management={management} location={location} onNavigate={() => setMenuOpen(false)} />}`.
3. Update the chevron span (currently `<span className="text-xs">▾</span>` at
   `Nav.tsx:90`) to the target version with the conditional `rotate-180` and
   `transition-transform duration-150 ease-out`.

## Boundaries

- Do NOT add a leave/exit animation — `menuOpen` still flips straight to
  `false` and the dropdown unmounts instantly on close (same as today); only
  the entrance gets motion. This matches the existing click-outside-to-close
  behavior (`Nav.tsx:37-45`) without touching that logic.
- Do NOT touch the primary nav links (`Nav.tsx:63-78`) or the logout button
  — out of scope for this plan (see plan 004-button-press-feedback-sweep for
  those, if selected separately).
- Do NOT add a component library (Radix/Headless UI) — this stays hand-rolled
  CSS, consistent with the rest of the app.
- If the current code doesn't match the "Problem" excerpt above (drift since
  commit `e7616b3`), STOP and report instead of improvising.

## Verification

- **Mechanical**: `cd frontend && npx tsc --noEmit` and `npm run build` both
  clean.
- **Feel check**:
  - Log in as a `super_admin` (the only role that sees "Управление"), click
    the button, and confirm the menu grows in from its top-left corner
    (near the button) rather than fading in place from its center.
  - Confirm the chevron flips to point up while the menu is open, and back
    down when closed.
  - Click outside the menu to close it; confirm it disappears (no exit
    animation expected per Boundaries — this is fine).
  - Toggle `prefers-reduced-motion: reduce` in DevTools Rendering tab;
    confirm the menu still fades in (opacity) but no longer scales up from
    95%.
- **Done when**: opening "Управление" shows a scale+fade entrance anchored at
  the trigger, the chevron rotates, and reduced-motion users still get an
  opacity cue.
