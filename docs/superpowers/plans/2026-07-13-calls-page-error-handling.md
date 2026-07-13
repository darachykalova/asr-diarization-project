# CallsListPage Error Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `CallsListPage.tsx` silently shows nothing if its fetch fails — port the existing try/catch + red error-banner pattern already used in `AuditLogPage.tsx` and `AudioListPage.tsx`.

**Architecture:** Single-file frontend change, no backend/API changes. Copies an existing, already-proven pattern verbatim — no new design decisions.

**Tech Stack:** React + TypeScript + Tailwind CSS (existing stack, no new packages).

## Global Constraints

- No new npm dependencies.
- The error banner's markup/classes must match the existing pattern in `AuditLogPage.tsx` exactly (`bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm`) for visual consistency across pages.
- Existing filter/pagination behavior (`filters.verdict`, `filters.scenario`, `page`) must not change — only error handling is added.
- Task 1's `useEffect(() => { load(); }, []);` (already committed, currently at line 33) must remain intact and unchanged.

---

### Task 1: Add try/catch + error banner to `CallsListPage.tsx`

**Files:**
- Modify: `frontend/src/pages/CallsListPage.tsx`

**Interfaces:** None — internal component state only (`error`).

- [ ] **Step 1: Add `error` state**

Change line 21 from:

```tsx
  const [loading, setLoading] = useState(false);
```

to:

```tsx
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
```

- [ ] **Step 2: Wrap `load` in try/catch/finally**

Replace the entire `load` function (currently lines 23-31):

```tsx
  async function load(p = 1) {
    setLoading(true);
    const params = new URLSearchParams({ page: String(p), page_size: "20" });
    if (filters.verdict) params.set("verdict", filters.verdict);
    if (filters.scenario) params.set("scenario", filters.scenario);
    const r = await fetch(`${API_BASE}/v1/admin/calls?${params}`, { headers: { Authorization: `Bearer ${token}` } });
    setData(await r.json());
    setLoading(false);
  }
```

with:

```tsx
  async function load(p = 1) {
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "20" });
      if (filters.verdict) params.set("verdict", filters.verdict);
      if (filters.scenario) params.set("scenario", filters.scenario);
      const r = await fetch(`${API_BASE}/v1/admin/calls?${params}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }
```

- [ ] **Step 3: Add the error banner to the JSX**

Immediately before the `{data && (` block (currently line 61), add:

```tsx
      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>}
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CallsListPage.tsx
git commit -m "fix(admin): show error banner on CallsListPage fetch failure"
```

---

### Task 2: Build, deploy, and manual verification

**Files:** None — this task only runs commands and verifies behavior.

**Depends on:** Task 1.

- [ ] **Step 1: Rebuild and restart the frontend container**

```bash
docker compose build frontend
docker compose up -d frontend
```

- [ ] **Step 2: Manual verification**

1. Open «Звонки» normally — confirm it still loads and behaves exactly as before (filters, pagination, no visible error banner).
2. Force a failure to confirm the banner actually appears — e.g. temporarily stop the `api` container (`docker compose stop api`) and reload «Звонки»: a red banner with an error message should appear instead of a silent blank page.
3. Restart `api` (`docker compose start api`) and confirm «Звонки» loads normally again afterward.

- [ ] **Step 3: Commit** (only if step 2 required fixes; otherwise nothing to commit)
