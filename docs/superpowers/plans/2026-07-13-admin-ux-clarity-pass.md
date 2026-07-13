# Admin UX Clarity Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three targeted UX fixes in the existing admin frontend: list pages load their data automatically instead of requiring a button click, the audio list's 11-field filter form collapses the rarely-used fields behind "Ещё фильтры", and the super-admin's 8-item nav bar groups admin-only pages under a "Управление" dropdown.

**Architecture:** Pure frontend changes (`frontend/src/`), no backend/API changes. Each fix follows a pattern already established elsewhere in this codebase (`useEffect` auto-load already used in `UsersPage`/`AnalyticsPage`; collapsible sections and dropdowns are new but built with plain React state, no new dependencies — the project has none beyond `react-router-dom` and `@tanstack/react-query`).

**Tech Stack:** React + TypeScript + Tailwind CSS (existing stack, no new packages).

## Global Constraints

- No new npm dependencies — build dropdown/collapsible behavior with plain `useState`/`useRef`/`useEffect`, matching the project's existing dependency-free component style.
- The frontend has no automated test suite (confirmed: no `test`/`vitest`/`jest` in `package.json`) — each task's verification is `npx tsc --noEmit` (must pass with zero errors) plus a described manual check; final cross-task manual verification happens once all tasks land.
- Existing filtering/pagination/sorting logic must not change behavior — only visibility/layout changes.
- Role-based visibility of nav items is unchanged — a `moderator` must see exactly the same 4 items as before, with no empty "Управление" button appearing for them.

---

### Task 1: Auto-load list pages on mount

**Files:**
- Modify: `frontend/src/pages/CallsListPage.tsx`
- Modify: `frontend/src/pages/AuditLogPage.tsx`
- Modify: `frontend/src/pages/AudioListPage.tsx`

**Interfaces:** None — this task touches only internal component lifecycle, no exported interfaces change.

- [ ] **Step 1: Add auto-load to `CallsListPage.tsx`**

Change the import on line 1 from:

```tsx
import { useState } from "react";
```

to:

```tsx
import { useEffect, useState } from "react";
```

Then, immediately after the closing `}` of the `load` function (currently ending at line 31, right before the `return (` of the component's JSX), add:

```tsx
  useEffect(() => { load(); }, []);
```

- [ ] **Step 2: Add auto-load to `AuditLogPage.tsx`**

Change the import on line 1 from:

```tsx
import { useState } from "react";
```

to:

```tsx
import { useEffect, useState } from "react";
```

Then, immediately after the closing `}` of the `fetchLog` function (currently ending at line 56, right before `function handleSearch`), add:

```tsx
  useEffect(() => { fetchLog(1); }, []);
```

- [ ] **Step 3: Add auto-load to `AudioListPage.tsx`**

Change the import on line 1 from:

```tsx
import { useState } from "react";
```

to:

```tsx
import { useEffect, useState } from "react";
```

Then, immediately after the closing `}` of the `fetchListWith` function (currently ending at line 133, right before `function handleSearch`), add:

```tsx
  useEffect(() => { fetchList(); }, []);
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0 (no type errors)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CallsListPage.tsx frontend/src/pages/AuditLogPage.tsx frontend/src/pages/AudioListPage.tsx
git commit -m "feat(admin): auto-load call/audit/audio lists on page open"
```

---

### Task 2: Collapsible "Ещё фильтры" on the audio list page

**Files:**
- Modify: `frontend/src/pages/AudioListPage.tsx`

**Interfaces:** None — internal component state only (`showMore`).

**Depends on:** Task 1 (this task edits the same file; apply after Task 1's `useEffect` addition is already in place).

- [ ] **Step 1: Add `showMore` state**

In the component body, right after the existing state declarations (after `const [error, setError] = useState<string | null>(null);`), add:

```tsx
  const [showMore, setShowMore] = useState(false);
```

- [ ] **Step 2: Replace the filter form**

Replace the entire `<form onSubmit={handleSearch} ...> ... </form>` block (currently spanning from `<form onSubmit={handleSearch} className="bg-white rounded-lg shadow p-5 mb-6">` through its matching closing `</form>`, right before the `{error && (...)}` block) with:

```tsx
      <form onSubmit={handleSearch} className="bg-white rounded-lg shadow p-5 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[240px]">
            <label className="block text-xs font-medium text-gray-500 mb-1">Поиск по тексту транскрипции</label>
            <input type="text" value={filters.q} onChange={set("q")}
              placeholder="Слово или фраза…"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="w-48">
            <label className="block text-xs font-medium text-gray-500 mb-1">Статус</label>
            <select value={filters.status} onChange={set("status")}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Все статусы</option>
              {Object.entries(STATUS_LABEL).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {loading ? "Поиск…" : "Найти"}
          </button>
          <button type="button" onClick={handleReset}
            className="px-4 py-2 rounded text-sm text-gray-500 border border-gray-300 hover:bg-gray-50 transition-colors">
            Сбросить
          </button>
          <button type="button" onClick={() => setShowMore((v) => !v)}
            className="text-sm text-blue-600 hover:underline ml-auto">
            {showMore ? "Скрыть фильтры ▲" : "Ещё фильтры ▾"}
          </button>
        </div>

        {showMore && (
          <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">ID записи</label>
              <input type="text" value={filters.jobIdQ} onChange={set("jobIdQ")}
                placeholder="Часть или полный UUID…"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Имя спикера</label>
              <input type="text" value={filters.speakerName} onChange={set("speakerName")}
                placeholder="Часть имени…"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">ID спикера</label>
              <input type="number" value={filters.speakerId} onChange={set("speakerId")}
                placeholder="—" min="1"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Спикеров от</label>
              <input type="number" value={filters.minSpeakers} onChange={set("minSpeakers")}
                placeholder="—" min="0"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Спикеров до</label>
              <input type="number" value={filters.maxSpeakers} onChange={set("maxSpeakers")}
                placeholder="—" min="0"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Длительность от (мин)</label>
              <input type="number" value={filters.durationMin} onChange={set("durationMin")}
                placeholder="—" min="0" step="0.5"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Длительность до (мин)</label>
              <input type="number" value={filters.durationMax} onChange={set("durationMax")}
                placeholder="—" min="0" step="0.5"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Дата с</label>
              <input type="date" value={filters.dateFrom} onChange={set("dateFrom")}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Дата по</label>
              <input type="date" value={filters.dateTo} onChange={set("dateTo")}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
        )}
      </form>
```

This preserves every existing field, its `value`/`onChange`/`placeholder`/validation attributes exactly as they were — only the wrapping layout and visibility changed. `handleSearch`, `handleReset`, `set(...)`, `STATUS_LABEL` are all pre-existing and unchanged.

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AudioListPage.tsx
git commit -m "feat(admin): collapse rarely-used audio filters behind 'Ещё фильтры'"
```

---

### Task 3: "Управление" dropdown in the nav bar

**Files:**
- Modify: `frontend/src/components/Nav.tsx`

**Interfaces:** None — internal component only.

- [ ] **Step 1: Replace the full file**

Replace the entire contents of `frontend/src/components/Nav.tsx` with:

```tsx
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { type Role, useAuth } from "../auth/AuthContext";

interface NavItem {
  path: string;
  label: string;
  roles: Role[];
}

const PRIMARY_ITEMS: NavItem[] = [
  { path: "/upload",    label: "Загрузить",    roles: ["moderator", "super_admin"] },
  { path: "/audio",     label: "Аудиозаписи",  roles: ["moderator", "super_admin"] },
  { path: "/calls",     label: "Звонки",       roles: ["moderator", "super_admin"] },
  { path: "/analytics", label: "Аналитика",    roles: ["moderator", "super_admin"] },
];

const MANAGEMENT_ITEMS: NavItem[] = [
  { path: "/users",     label: "Пользователи",  roles: ["super_admin"] },
  { path: "/audit-log", label: "Журнал аудита", roles: ["super_admin"] },
  { path: "/settings",  label: "Настройки",     roles: ["super_admin"] },
  { path: "/simulator", label: "Симулятор",     roles: ["super_admin"] },
];

const ROLE_LABEL: Record<Role, string> = {
  moderator:   "Модератор",
  super_admin: "Супер-Админ",
};

export function Nav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!user) return null;

  const primary = PRIMARY_ITEMS.filter((item) => item.roles.includes(user.role));
  const management = MANAGEMENT_ITEMS.filter((item) => item.roles.includes(user.role));
  const managementActive = management.some((item) => location.pathname.startsWith(item.path));

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <nav className="bg-gray-800 text-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/audio" className="font-bold text-lg tracking-tight hover:text-gray-300 transition-colors">Аудио-Админка</Link>

        {primary.map((item) => {
          const active = location.pathname.startsWith(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`text-sm transition-colors ${
                active
                  ? "text-white underline underline-offset-4"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {item.label}
            </Link>
          );
        })}

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
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-400">
          {user.login}{" "}
          <span className="text-gray-500">({ROLE_LABEL[user.role]})</span>
        </span>

        <button
          onClick={handleLogout}
          className="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded transition-colors"
        >
          Выйти
        </button>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Nav.tsx
git commit -m "feat(admin): group admin-only nav items under 'Управление' dropdown"
```

---

### Task 4: Build, deploy, and end-to-end manual verification

**Files:** None — this task only runs commands and verifies behavior.

**Depends on:** Tasks 1, 2, 3.

- [ ] **Step 1: Rebuild and restart the frontend container**

```bash
docker compose build frontend
docker compose up -d frontend
```

- [ ] **Step 2: Manual verification checklist**

Open `http://localhost:4000` (or the port from `FRONTEND_PORT` in `.env`) and confirm:

1. **Auto-load:** Open «Аудиозаписи», «Звонки», «Журнал аудита» — each shows data immediately, without clicking any button.
2. **Collapsible filters:** On «Аудиозаписи», only «Поиск по тексту транскрипции», «Статус», «Найти», «Сбросить», and «Ещё фильтры ▾» are visible by default. Click «Ещё фильтры ▾» — the 8 remaining fields (ID записи, имя/ID спикера, спикеров от/до, длительность от/до, даты) appear, and the button label changes to «Скрыть фильтры ▲». Enter a value in one of the hidden fields, submit — confirm it actually filters results (the hidden fields still work, only visibility changed).
3. **Управление dropdown (super_admin):** Logged in as `admin`/`Admin1234!`, the nav bar shows Загрузить/Аудиозаписи/Звонки/Аналитика plus a «Управление ▾» button. Click it — Пользователи/Журнал аудита/Настройки/Симулятор appear in a dropdown. Click one — navigates there, dropdown closes, and «Управление» is visually highlighted (active) while on any of those 4 pages. Click elsewhere on the page — dropdown closes without navigating.
4. **Управление dropdown (moderator, if a moderator account is available):** No «Управление» button appears at all — nav looks exactly as before this change.

- [ ] **Step 3: Commit** (only if step 2 required fixes; otherwise nothing to commit — Tasks 1-3 already committed the code)

If manual verification passes with no changes needed, this task requires no additional commit.
