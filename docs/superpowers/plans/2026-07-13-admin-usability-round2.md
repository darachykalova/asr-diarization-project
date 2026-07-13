# Admin Usability Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four usability fixes: a loading spinner on first page load (replacing a blank screen) across 6 pages, a confirmation dialog before blocking a user or changing their role, a broken full-page-reload link fixed to client-side navigation, and a "reset filters" escape hatch on empty search results.

**Architecture:** Pure frontend changes (`frontend/src/`), no backend/API changes. Two new small, dependency-free components (`LoadingSpinner`, `ConfirmDialog`) reused across existing pages.

**Tech Stack:** React + TypeScript + Tailwind CSS (existing stack, no new packages — `animate-spin` is a built-in Tailwind utility, no config needed).

## Global Constraints

- No new npm dependencies.
- `LoadingSpinner` only replaces content during the *first* load of a page (an `initialLoading` flag, separate from any existing `loading` flag used for subsequent searches/actions) — it must not re-appear and hide already-loaded content on every subsequent action (pagination, re-search, block/unblock, etc.), to avoid jarring flicker.
- `ConfirmDialog`'s Cancel button must perform no action at all (not even a partial one) — the underlying state must be completely unchanged if cancelled.
- The "reset filters" button in an empty-results state must only appear when at least one filter is actually set to a non-empty value — never shown on a genuinely filter-less empty list.
- Existing filtering/pagination/sorting/create/patch logic must not change behavior — only loading/confirmation/navigation/empty-state UI changes.

---

### Task 1: `LoadingSpinner` component + wire into 5 pages

**Files:**
- Create: `frontend/src/components/LoadingSpinner.tsx`
- Modify: `frontend/src/pages/AudioListPage.tsx`
- Modify: `frontend/src/pages/CallsListPage.tsx`
- Modify: `frontend/src/pages/AuditLogPage.tsx`
- Modify: `frontend/src/pages/UsersPage.tsx`
- Modify: `frontend/src/pages/AudioDetailPage.tsx`

**Interfaces:**
- Produces: `LoadingSpinner({ label?: string }): JSX.Element`, a self-contained component with no required props. Used by this task's 5 pages and by Task 2's `CallDetailPage` edit.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/LoadingSpinner.tsx`:

```tsx
export function LoadingSpinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-gray-400 text-sm">
      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {label && <span>{label}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Wire into `AudioListPage.tsx`**

Add the import right after the existing `useAuth` import:

```tsx
import { LoadingSpinner } from "../components/LoadingSpinner";
```

Add a new state variable right after `const [showMore, setShowMore] = useState(false);`:

```tsx
  const [initialLoading, setInitialLoading] = useState(true);
```

In `fetchListWith`'s `finally` block, add `setInitialLoading(false);` so it reads:

```tsx
    } finally {
      setLoading(false);
      setInitialLoading(false);
    }
```

Replace this block (currently right after the closing `</form>` of the filters form):

```tsx
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>
      )}

      {data && (
        <>
          <div className="text-sm text-gray-500 mb-2">Найдено: {data.total} записей</div>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Файл / ID</th>
                  <SortHeader col="uploaded_at" label="Дата загрузки" current={sortBy} order={sortOrder} onClick={handleSortClick} />
                  <SortHeader col="duration"    label="Длительность"  current={sortBy} order={sortOrder} onClick={handleSortClick} />
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Статус</th>
                  <SortHeader col="speakers"    label="Спикеры"       current={sortBy} order={sortOrder} onClick={handleSortClick} />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-gray-400">Записей не найдено</td>
                  </tr>
                ) : (
                  data.items.map((item) => (
                    <tr key={item.job_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <Link to={`/audio/${item.job_id}`} className="text-blue-600 hover:underline font-medium">
                          {item.title}
                        </Link>
                        <div className="text-xs text-gray-400 font-mono">{item.job_id}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{fmtDate(item.uploaded_at)}</td>
                      <td className="px-4 py-3 text-gray-600">{fmtDuration(item.duration_sec)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          item.status === "done"       ? "bg-green-100 text-green-700" :
                          item.status === "failed"     ? "bg-red-100 text-red-700" :
                          item.status === "processing" ? "bg-blue-100 text-blue-700" :
                                                         "bg-gray-100 text-gray-600"
                        }`}>
                          {STATUS_LABEL[item.status] ?? item.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{item.speaker_count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button onClick={() => goPage(page - 1)} disabled={page <= 1}
                className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">←</button>
              <span className="text-sm text-gray-600">Страница {data.page} из {data.pages}</span>
              <button onClick={() => goPage(page + 1)} disabled={page >= data.pages}
                className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">→</button>
            </div>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <p className="text-gray-400 text-sm">Нажмите «Найти» для загрузки списка.</p>
      )}
```

with:

```tsx
      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>
          )}

          {data && (
            <>
              <div className="text-sm text-gray-500 mb-2">Найдено: {data.total} записей</div>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Файл / ID</th>
                      <SortHeader col="uploaded_at" label="Дата загрузки" current={sortBy} order={sortOrder} onClick={handleSortClick} />
                      <SortHeader col="duration"    label="Длительность"  current={sortBy} order={sortOrder} onClick={handleSortClick} />
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Статус</th>
                      <SortHeader col="speakers"    label="Спикеры"       current={sortBy} order={sortOrder} onClick={handleSortClick} />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.items.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-gray-400">Записей не найдено</td>
                      </tr>
                    ) : (
                      data.items.map((item) => (
                        <tr key={item.job_id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3">
                            <Link to={`/audio/${item.job_id}`} className="text-blue-600 hover:underline font-medium">
                              {item.title}
                            </Link>
                            <div className="text-xs text-gray-400 font-mono">{item.job_id}</div>
                          </td>
                          <td className="px-4 py-3 text-gray-600">{fmtDate(item.uploaded_at)}</td>
                          <td className="px-4 py-3 text-gray-600">{fmtDuration(item.duration_sec)}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                              item.status === "done"       ? "bg-green-100 text-green-700" :
                              item.status === "failed"     ? "bg-red-100 text-red-700" :
                              item.status === "processing" ? "bg-blue-100 text-blue-700" :
                                                             "bg-gray-100 text-gray-600"
                            }`}>
                              {STATUS_LABEL[item.status] ?? item.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600">{item.speaker_count}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {data.pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-4">
                  <button onClick={() => goPage(page - 1)} disabled={page <= 1}
                    className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">←</button>
                  <span className="text-sm text-gray-600">Страница {data.page} из {data.pages}</span>
                  <button onClick={() => goPage(page + 1)} disabled={page >= data.pages}
                    className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">→</button>
                </div>
              )}
            </>
          )}

          {!data && !loading && !error && (
            <p className="text-gray-400 text-sm">Нажмите «Найти» для загрузки списка.</p>
          )}
        </>
      )}
```

- [ ] **Step 3: Wire into `CallsListPage.tsx`**

Add the import right after the existing `useAuth` import:

```tsx
import { LoadingSpinner } from "../components/LoadingSpinner";
```

Add a new state variable right after `const [error, setError] = useState<string | null>(null);`:

```tsx
  const [initialLoading, setInitialLoading] = useState(true);
```

In `load`'s `finally` block, add `setInitialLoading(false);` so it reads:

```tsx
    } finally {
      setLoading(false);
      setInitialLoading(false);
    }
```

Replace this block (currently right after the closing `</div>` of the filters bar):

```tsx
      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>}
      {data && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3">Дата</th>
                <th className="text-left px-4 py-3">Источник</th>
                <th className="text-left px-4 py-3">Длит.</th>
                <th className="text-left px-4 py-3">Вердикт</th>
                <th className="text-left px-4 py-3">Сценарий</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.map(c => (
                <tr key={c.call_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/calls/${c.call_id}`} className="text-blue-600 hover:underline">
                      {new Date(c.started_at).toLocaleString("ru-RU")}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{c.source}</td>
                  <td className="px-4 py-3">{c.duration_sec ? `${Math.round(c.duration_sec)} с` : "—"}</td>
                  <td className="px-4 py-3">{VERDICT[c.verdict] ?? c.verdict}</td>
                  <td className="px-4 py-3">{c.scenario ?? "—"}</td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={5} className="text-center py-8 text-gray-400">Звонков нет</td></tr>
              )}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="flex justify-between items-center mt-4 text-sm text-gray-600">
              <button
                disabled={page === 1}
                onClick={() => { const p = page - 1; setPage(p); load(p); }}
                className="px-3 py-1 border rounded disabled:opacity-40"
              >Назад</button>
              <span>Стр. {page} / {data.pages}</span>
              <button
                disabled={page >= data.pages}
                onClick={() => { const p = page + 1; setPage(p); load(p); }}
                className="px-3 py-1 border rounded disabled:opacity-40"
              >Вперёд</button>
            </div>
          )}
        </div>
      )}
```

with:

```tsx
      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>}
          {data && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3">Дата</th>
                    <th className="text-left px-4 py-3">Источник</th>
                    <th className="text-left px-4 py-3">Длит.</th>
                    <th className="text-left px-4 py-3">Вердикт</th>
                    <th className="text-left px-4 py-3">Сценарий</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.map(c => (
                    <tr key={c.call_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <Link to={`/calls/${c.call_id}`} className="text-blue-600 hover:underline">
                          {new Date(c.started_at).toLocaleString("ru-RU")}
                        </Link>
                      </td>
                      <td className="px-4 py-3">{c.source}</td>
                      <td className="px-4 py-3">{c.duration_sec ? `${Math.round(c.duration_sec)} с` : "—"}</td>
                      <td className="px-4 py-3">{VERDICT[c.verdict] ?? c.verdict}</td>
                      <td className="px-4 py-3">{c.scenario ?? "—"}</td>
                    </tr>
                  ))}
                  {data.items.length === 0 && (
                    <tr><td colSpan={5} className="text-center py-8 text-gray-400">Звонков нет</td></tr>
                  )}
                </tbody>
              </table>
              {data.pages > 1 && (
                <div className="flex justify-between items-center mt-4 text-sm text-gray-600">
                  <button
                    disabled={page === 1}
                    onClick={() => { const p = page - 1; setPage(p); load(p); }}
                    className="px-3 py-1 border rounded disabled:opacity-40"
                  >Назад</button>
                  <span>Стр. {page} / {data.pages}</span>
                  <button
                    disabled={page >= data.pages}
                    onClick={() => { const p = page + 1; setPage(p); load(p); }}
                    className="px-3 py-1 border rounded disabled:opacity-40"
                  >Вперёд</button>
                </div>
              )}
            </div>
          )}
        </>
      )}
```

- [ ] **Step 4: Wire into `AuditLogPage.tsx`**

Add the import right after the existing `useAuth` import:

```tsx
import { LoadingSpinner } from "../components/LoadingSpinner";
```

Add a new state variable right after `const [error, setError] = useState<string | null>(null);`:

```tsx
  const [initialLoading, setInitialLoading] = useState(true);
```

In `fetchLog`'s `finally` block, add `setInitialLoading(false);` so it reads:

```tsx
    finally { setLoading(false); setInitialLoading(false); }
```

Replace this block (currently right after the closing `</form>` of the filters form):

```tsx
      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>}

      {data && (
        <>
          <div className="text-sm text-gray-500 mb-2">Событий: {data.total}</div>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Время</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Пользователь</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Действие</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Запись</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.length === 0 ? (
                  <tr><td colSpan={4} className="text-center py-8 text-gray-400">Нет событий</td></tr>
                ) : data.items.map(item => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">{fmtDate(item.created_at)}</td>
                    <td className="px-4 py-3 font-medium">{item.user_login}</td>
                    <td className="px-4 py-3">
                      <span className="bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded text-xs font-medium">
                        {item.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.job_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button onClick={() => goPage(page - 1)} disabled={page <= 1}
                className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">←</button>
              <span className="text-sm text-gray-600">Страница {data.page} из {data.pages}</span>
              <button onClick={() => goPage(page + 1)} disabled={page >= data.pages}
                className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">→</button>
            </div>
          )}
        </>
      )}
      {!data && !loading && !error && (
        <p className="text-gray-400 text-sm">Нажмите «Показать» для загрузки журнала.</p>
      )}
```

with:

```tsx
      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>}

          {data && (
            <>
              <div className="text-sm text-gray-500 mb-2">Событий: {data.total}</div>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Время</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Пользователь</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Действие</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Запись</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.items.length === 0 ? (
                      <tr><td colSpan={4} className="text-center py-8 text-gray-400">Нет событий</td></tr>
                    ) : data.items.map(item => (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-600">{fmtDate(item.created_at)}</td>
                        <td className="px-4 py-3 font-medium">{item.user_login}</td>
                        <td className="px-4 py-3">
                          <span className="bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded text-xs font-medium">
                            {item.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.job_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {data.pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-4">
                  <button onClick={() => goPage(page - 1)} disabled={page <= 1}
                    className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">←</button>
                  <span className="text-sm text-gray-600">Страница {data.page} из {data.pages}</span>
                  <button onClick={() => goPage(page + 1)} disabled={page >= data.pages}
                    className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">→</button>
                </div>
              )}
            </>
          )}
        </>
      )}
```

(Note: the `!data && !loading && !error` hint paragraph is intentionally dropped here — once `initialLoading` becomes `false`, `data` is always set for a successful load, and this fallback text would now be unreachable dead code in the normal flow. This mirrors the same dead-code observation already made about `AudioListPage`'s equivalent hint in [[2026-07-13-admin-ux-clarity-pass-design]], but that one is left as harmless leftover; here we're already rewriting this exact block, so remove it instead of preserving unreachable code.)

- [ ] **Step 5: Wire into `UsersPage.tsx`**

Add the import right after the existing `useAuth` import:

```tsx
import { LoadingSpinner } from "../components/LoadingSpinner";
```

Add a new state variable right after `const [error, setError] = useState<string | null>(null);`:

```tsx
  const [initialLoading, setInitialLoading] = useState(true);
```

Replace the `load` function:

```tsx
  async function load() {
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setUsers(await resp.json());
    } catch (e) {
      setError(String(e));
    }
  }
```

with:

```tsx
  async function load() {
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setUsers(await resp.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setInitialLoading(false);
    }
  }
```

Replace this block (currently right after the error banner, through the end of the table):

```tsx
      {/* Форма создания */}
      <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-40">
          <label className="block text-xs font-medium text-gray-600 mb-1">Логин</label>
          <input
            value={login} onChange={e => setLogin(e.target.value)} required
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex-1 min-w-40">
          <label className="block text-xs font-medium text-gray-600 mb-1">Пароль</label>
          <input
            type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="min-w-36">
          <label className="block text-xs font-medium text-gray-600 mb-1">Роль</label>
          <select
            value={role} onChange={e => setRole(e.target.value as "moderator" | "super_admin")}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="moderator">Модератор</option>
            <option value="super_admin">Супер-Админ</option>
          </select>
        </div>
        <button
          type="submit" disabled={creating}
          className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {creating ? "Создаётся…" : "Создать"}
        </button>
      </form>

      {/* Таблица */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Логин</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Роль</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Статус</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Создан</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-8 text-gray-400">Пусто</td></tr>
            ) : users.map(u => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{u.login}</td>
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    onChange={e => patchUser(u.id, { role: e.target.value })}
                    className="border border-gray-200 rounded px-2 py-0.5 text-xs"
                  >
                    <option value="moderator">Модератор</option>
                    <option value="super_admin">Супер-Админ</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                    u.is_blocked ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                  }`}>
                    {u.is_blocked ? "Заблокирован" : "Активен"}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(u.created_at)}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => patchUser(u.id, { is_blocked: !u.is_blocked })}
                    className={`text-xs px-2 py-1 rounded transition-colors ${
                      u.is_blocked
                        ? "bg-green-50 text-green-700 hover:bg-green-100"
                        : "bg-red-50 text-red-700 hover:bg-red-100"
                    }`}
                  >
                    {u.is_blocked ? "Разблокировать" : "Заблокировать"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
```

with:

```tsx
      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {/* Форма создания */}
          <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-40">
              <label className="block text-xs font-medium text-gray-600 mb-1">Логин</label>
              <input
                value={login} onChange={e => setLogin(e.target.value)} required
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1 min-w-40">
              <label className="block text-xs font-medium text-gray-600 mb-1">Пароль</label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8}
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="min-w-36">
              <label className="block text-xs font-medium text-gray-600 mb-1">Роль</label>
              <select
                value={role} onChange={e => setRole(e.target.value as "moderator" | "super_admin")}
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="moderator">Модератор</option>
                <option value="super_admin">Супер-Админ</option>
              </select>
            </div>
            <button
              type="submit" disabled={creating}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {creating ? "Создаётся…" : "Создать"}
            </button>
          </form>

          {/* Таблица */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Логин</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Роль</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Статус</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Создан</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.length === 0 ? (
                  <tr><td colSpan={5} className="text-center py-8 text-gray-400">Пусто</td></tr>
                ) : users.map(u => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{u.login}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={e => patchUser(u.id, { role: e.target.value })}
                        className="border border-gray-200 rounded px-2 py-0.5 text-xs"
                      >
                        <option value="moderator">Модератор</option>
                        <option value="super_admin">Супер-Админ</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.is_blocked ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                      }`}>
                        {u.is_blocked ? "Заблокирован" : "Активен"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{fmtDate(u.created_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => patchUser(u.id, { is_blocked: !u.is_blocked })}
                        className={`text-xs px-2 py-1 rounded transition-colors ${
                          u.is_blocked
                            ? "bg-green-50 text-green-700 hover:bg-green-100"
                            : "bg-red-50 text-red-700 hover:bg-red-100"
                        }`}
                      >
                        {u.is_blocked ? "Разблокировать" : "Заблокировать"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
```

(This step's block will be edited AGAIN by Task 3 — Task 3 adds the `ConfirmDialog` and changes the `onClick` handlers on the role `<select>` and the block/unblock `<button>` inside this same table. Apply Task 1 first.)

- [ ] **Step 6: Wire into `AudioDetailPage.tsx`**

Add the import right after the existing `useAuth` import:

```tsx
import { LoadingSpinner } from "../components/LoadingSpinner";
```

Add a new state variable right after `const [itemError, setItemError] = useState<string | null>(null);`:

```tsx
  const [initialLoading, setInitialLoading] = useState(true);
```

Add `.finally(() => setInitialLoading(false))` to the existing fetch chain in the `useEffect`, so it reads:

```tsx
  useEffect(() => {
    if (!jobId) return;
    fetch(`${API_BASE}/v1/admin/audio/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setItem)
      .catch((e) => setItemError(String(e)))
      .finally(() => setInitialLoading(false));
  }, [jobId, token]);
```

Replace this block (the whole return statement's body except the breadcrumb `<nav>`):

```tsx
      {itemError && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4">
          {itemError}
        </div>
      )}

      {/* Метаданные */}
      {item && (
        <div className="bg-white rounded-lg shadow p-5 mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-800">{item.title}</h1>
              <p className="text-xs text-gray-400 mt-0.5">{item.job_id}</p>
            </div>
            <span className={`mt-1 inline-block px-2.5 py-1 rounded-full text-xs font-medium ${
              item.status === "done"       ? "bg-green-100 text-green-700" :
              item.status === "failed"     ? "bg-red-100 text-red-700" :
              item.status === "processing" ? "bg-blue-100 text-blue-700" :
                                             "bg-gray-100 text-gray-600"
            }`}>
              {STATUS_LABEL[item.status] ?? item.status}
            </span>
          </div>
          <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <dt className="text-gray-500 text-xs">Дата загрузки</dt>
              <dd className="font-medium">{fmtDate(item.uploaded_at)}</dd>
            </div>
            <div>
              <dt className="text-gray-500 text-xs">Длительность</dt>
              <dd className="font-medium">
                {item.duration_sec != null ? fmtTime(item.duration_sec) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500 text-xs">Спикеры</dt>
              <dd className="font-medium">{item.speaker_count}</dd>
            </div>
          </dl>
        </div>
      )}

      {/* Блок транскрипции */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">Транскрипция</h2>
          {!revealed && (
            <button
              onClick={handleReveal}
              disabled={revealing || item?.status !== "done"}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {revealing ? "Загружается…" : "Развернуть"}
            </button>
          )}
        </div>

        {item?.status !== "done" && !revealed && (
          <p className="text-gray-400 text-sm">
            Транскрипция доступна только для завершённых записей.
          </p>
        )}

        {revealError && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm mb-3">
            {revealError}
          </div>
        )}

        {!revealed && item?.status === "done" && !revealing && !revealError && (
          <p className="text-gray-400 text-sm italic">
            Текст транскрипции скрыт. Нажмите «Развернуть» для просмотра.
          </p>
        )}

        {/* Сегменты по спикерам */}
        {revealed && (
          <>
            {/* Легенда спикеров */}
            {revealed.speakers.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-5">
                {revealed.speakers.map((s) => (
                  <span
                    key={s.speaker}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${speakerColorMap[s.speaker]}`}
                  >
                    {s.display_name ?? s.speaker}
                    {s.display_name && (
                      <span className="opacity-60">({s.speaker})</span>
                    )}
                  </span>
                ))}
              </div>
            )}

            {/* Сегменты */}
            <div className="space-y-2">
              {revealed.segments.map((seg, i) => (
                <div key={i} className="flex gap-3 text-sm">
                  <span className="text-gray-400 font-mono text-xs mt-0.5 w-20 shrink-0">
                    {fmtTime(seg.start)}
                  </span>
                  <span
                    className={`text-xs font-medium px-1.5 py-0.5 rounded shrink-0 self-start ${speakerColorMap[seg.speaker] ?? "bg-gray-100 text-gray-600"}`}
                  >
                    {revealed.speakers.find((s) => s.speaker === seg.speaker)?.display_name ?? seg.speaker}
                  </span>
                  <span className="text-gray-800 leading-relaxed">{seg.text}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
```

with the same content wrapped in the `initialLoading` ternary:

```tsx
      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {itemError && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4">
              {itemError}
            </div>
          )}

          {/* Метаданные */}
          {item && (
            <div className="bg-white rounded-lg shadow p-5 mb-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-xl font-bold text-gray-800">{item.title}</h1>
                  <p className="text-xs text-gray-400 mt-0.5">{item.job_id}</p>
                </div>
                <span className={`mt-1 inline-block px-2.5 py-1 rounded-full text-xs font-medium ${
                  item.status === "done"       ? "bg-green-100 text-green-700" :
                  item.status === "failed"     ? "bg-red-100 text-red-700" :
                  item.status === "processing" ? "bg-blue-100 text-blue-700" :
                                                 "bg-gray-100 text-gray-600"
                }`}>
                  {STATUS_LABEL[item.status] ?? item.status}
                </span>
              </div>
              <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div>
                  <dt className="text-gray-500 text-xs">Дата загрузки</dt>
                  <dd className="font-medium">{fmtDate(item.uploaded_at)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Длительность</dt>
                  <dd className="font-medium">
                    {item.duration_sec != null ? fmtTime(item.duration_sec) : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Спикеры</dt>
                  <dd className="font-medium">{item.speaker_count}</dd>
                </div>
              </dl>
            </div>
          )}

          {/* Блок транскрипции */}
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-800">Транскрипция</h2>
              {!revealed && (
                <button
                  onClick={handleReveal}
                  disabled={revealing || item?.status !== "done"}
                  className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {revealing ? "Загружается…" : "Развернуть"}
                </button>
              )}
            </div>

            {item?.status !== "done" && !revealed && (
              <p className="text-gray-400 text-sm">
                Транскрипция доступна только для завершённых записей.
              </p>
            )}

            {revealError && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 text-sm mb-3">
                {revealError}
              </div>
            )}

            {!revealed && item?.status === "done" && !revealing && !revealError && (
              <p className="text-gray-400 text-sm italic">
                Текст транскрипции скрыт. Нажмите «Развернуть» для просмотра.
              </p>
            )}

            {/* Сегменты по спикерам */}
            {revealed && (
              <>
                {/* Легенда спикеров */}
                {revealed.speakers.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-5">
                    {revealed.speakers.map((s) => (
                      <span
                        key={s.speaker}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${speakerColorMap[s.speaker]}`}
                      >
                        {s.display_name ?? s.speaker}
                        {s.display_name && (
                          <span className="opacity-60">({s.speaker})</span>
                        )}
                      </span>
                    ))}
                  </div>
                )}

                {/* Сегменты */}
                <div className="space-y-2">
                  {revealed.segments.map((seg, i) => (
                    <div key={i} className="flex gap-3 text-sm">
                      <span className="text-gray-400 font-mono text-xs mt-0.5 w-20 shrink-0">
                        {fmtTime(seg.start)}
                      </span>
                      <span
                        className={`text-xs font-medium px-1.5 py-0.5 rounded shrink-0 self-start ${speakerColorMap[seg.speaker] ?? "bg-gray-100 text-gray-600"}`}
                      >
                        {revealed.speakers.find((s) => s.speaker === seg.speaker)?.display_name ?? seg.speaker}
                      </span>
                      <span className="text-gray-800 leading-relaxed">{seg.text}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </>
      )}
```

- [ ] **Step 7: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/LoadingSpinner.tsx frontend/src/pages/AudioListPage.tsx frontend/src/pages/CallsListPage.tsx frontend/src/pages/AuditLogPage.tsx frontend/src/pages/UsersPage.tsx frontend/src/pages/AudioDetailPage.tsx
git commit -m "feat(admin): show a loading spinner on first page load instead of a blank screen"
```

---

### Task 2: Fix `CallDetailPage` — spinner + broken link

**Files:**
- Modify: `frontend/src/pages/CallDetailPage.tsx`

**Interfaces:**
- Consumes: `LoadingSpinner` (Task 1).

**Depends on:** Task 1 (uses `LoadingSpinner`).

- [ ] **Step 1: Fix the imports**

Replace:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
```

with:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
```

- [ ] **Step 2: Swap the loading text for the spinner**

Replace:

```tsx
  if (!d) return <div className="p-6 text-gray-400">Загрузка…</div>;
```

with:

```tsx
  if (!d) return <div className="p-6"><LoadingSpinner /></div>;
```

- [ ] **Step 3: Fix the broken full-page-reload link**

Replace:

```tsx
        {c.job_id && (
          <a href={`/audio/${c.job_id}`}
             className="inline-block mt-3 text-sm text-blue-600 hover:underline">
            Открыть запись и полную транскрипцию →
          </a>
        )}
```

with:

```tsx
        {c.job_id && (
          <Link to={`/audio/${c.job_id}`}
             className="inline-block mt-3 text-sm text-blue-600 hover:underline">
            Открыть запись и полную транскрипцию →
          </Link>
        )}
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CallDetailPage.tsx
git commit -m "fix(admin): use client-side navigation on CallDetailPage, add loading spinner"
```

---

### Task 3: `ConfirmDialog` component + wire into `UsersPage`

**Files:**
- Create: `frontend/src/components/ConfirmDialog.tsx`
- Modify: `frontend/src/pages/UsersPage.tsx`

**Interfaces:**
- Produces: `ConfirmDialog({ open, title, message, confirmLabel, danger, onConfirm, onCancel }): JSX.Element | null`.

**Depends on:** Task 1 (this task edits the same `UsersPage.tsx` table block that Task 1 already rewrote — apply after Task 1).

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ConfirmDialog.tsx`:

```tsx
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open, title, message, confirmLabel = "Подтвердить", danger, onConfirm, onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onCancel}>
      <div
        className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-800 mb-2">{title}</h3>
        <p className="text-sm text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded text-sm text-gray-600 border border-gray-300 hover:bg-gray-50 transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded text-sm text-white transition-colors ${
              danger ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire it into `UsersPage.tsx`**

Add the import right after the `LoadingSpinner` import (added in Task 1):

```tsx
import { ConfirmDialog } from "../components/ConfirmDialog";
```

Add new state right after the existing `patchUser`-related state (right after `const [creating, setCreating] = useState(false);`):

```tsx
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    message: string;
    confirmLabel: string;
    danger: boolean;
    onConfirm: () => void;
  } | null>(null);
```

Add two new helper functions right after the existing `patchUser` function:

```tsx
  function askBlockConfirm(u: AdminUser) {
    setConfirmAction({
      title: u.is_blocked ? "Разблокировать пользователя?" : "Заблокировать пользователя?",
      message: u.is_blocked
        ? `${u.login} снова сможет войти в систему.`
        : `${u.login} больше не сможет войти в систему.`,
      confirmLabel: u.is_blocked ? "Разблокировать" : "Заблокировать",
      danger: !u.is_blocked,
      onConfirm: () => {
        patchUser(u.id, { is_blocked: !u.is_blocked });
        setConfirmAction(null);
      },
    });
  }

  function askRoleConfirm(u: AdminUser, newRole: string) {
    setConfirmAction({
      title: "Сменить роль пользователя?",
      message: `${u.login}: роль изменится на «${ROLE_LABEL[newRole] ?? newRole}».`,
      confirmLabel: "Сменить роль",
      danger: false,
      onConfirm: () => {
        patchUser(u.id, { role: newRole });
        setConfirmAction(null);
      },
    });
  }
```

In the table (inside the `initialLoading ? ... : (...)` block from Task 1), change the role `<select>`'s `onChange` from:

```tsx
                    onChange={e => patchUser(u.id, { role: e.target.value })}
```

to:

```tsx
                    onChange={e => askRoleConfirm(u, e.target.value)}
```

And change the block/unblock `<button>`'s `onClick` from:

```tsx
                    onClick={() => patchUser(u.id, { is_blocked: !u.is_blocked })}
```

to:

```tsx
                    onClick={() => askBlockConfirm(u)}
```

Finally, add the dialog itself right before the component's closing `</div>` (the outermost wrapper `<div className="p-6 max-w-5xl mx-auto">`'s closing tag):

```tsx
      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction?.title ?? ""}
        message={confirmAction?.message ?? ""}
        confirmLabel={confirmAction?.confirmLabel}
        danger={confirmAction?.danger}
        onConfirm={() => confirmAction?.onConfirm()}
        onCancel={() => setConfirmAction(null)}
      />
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ConfirmDialog.tsx frontend/src/pages/UsersPage.tsx
git commit -m "feat(admin): confirm before blocking a user or changing their role"
```

---

### Task 4: "Сбросить фильтры" in empty search results

**Files:**
- Modify: `frontend/src/pages/AudioListPage.tsx`
- Modify: `frontend/src/pages/CallsListPage.tsx`
- Modify: `frontend/src/pages/AuditLogPage.tsx`

**Interfaces:** None — internal component logic only.

**Depends on:** Task 1 (edits the same files Task 1 already rewrote — apply after Task 1).

- [ ] **Step 1: `AudioListPage.tsx`**

Add a computed value right after the `handleReset` function:

```tsx
  const filtersActive = Object.values(filters).some((v) => v !== "");
```

Change the empty-row cell from:

```tsx
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-gray-400">Записей не найдено</td>
                      </tr>
```

to:

```tsx
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-gray-400">
                          <p>Записей не найдено</p>
                          {filtersActive && (
                            <button
                              onClick={handleReset}
                              className="mt-2 text-sm text-blue-600 hover:underline"
                            >
                              Сбросить фильтры
                            </button>
                          )}
                        </td>
                      </tr>
```

- [ ] **Step 2: `CallsListPage.tsx`**

Add a reset function and a computed value right after the `load` function:

```tsx
  function resetFilters() {
    setFilters({ verdict: "", scenario: "" });
  }

  const filtersActive = filters.verdict !== "" || filters.scenario !== "";
```

Change the empty-row cell from:

```tsx
                  {data.items.length === 0 && (
                    <tr><td colSpan={5} className="text-center py-8 text-gray-400">Звонков нет</td></tr>
                  )}
```

to:

```tsx
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-gray-400">
                        <p>Звонков нет</p>
                        {filtersActive && (
                          <button
                            onClick={resetFilters}
                            className="mt-2 text-sm text-blue-600 hover:underline"
                          >
                            Сбросить фильтры
                          </button>
                        )}
                      </td>
                    </tr>
                  )}
```

- [ ] **Step 3: `AuditLogPage.tsx`**

Add a reset function and a computed value right after the `fetchLog` function:

```tsx
  function resetFilters() {
    setUserId(""); setDateFrom(""); setDateTo("");
  }

  const filtersActive = userId !== "" || dateFrom !== "" || dateTo !== "";
```

Change the empty-row cell from:

```tsx
                    {data.items.length === 0 ? (
                      <tr><td colSpan={4} className="text-center py-8 text-gray-400">Нет событий</td></tr>
                    ) : data.items.map(item => (
```

to:

```tsx
                    {data.items.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="text-center py-8 text-gray-400">
                          <p>Нет событий</p>
                          {filtersActive && (
                            <button
                              onClick={resetFilters}
                              className="mt-2 text-sm text-blue-600 hover:underline"
                            >
                              Сбросить фильтры
                            </button>
                          )}
                        </td>
                      </tr>
                    ) : data.items.map(item => (
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit code 0

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AudioListPage.tsx frontend/src/pages/CallsListPage.tsx frontend/src/pages/AuditLogPage.tsx
git commit -m "feat(admin): offer to reset filters when a filtered search finds nothing"
```

---

### Task 5: Build, deploy, and manual verification

**Files:** None — this task only runs commands and verifies behavior.

**Depends on:** Tasks 1-4.

- [ ] **Step 1: Rebuild and restart the frontend container**

```bash
docker compose build frontend
docker compose up -d frontend
```

- [ ] **Step 2: Manual verification checklist**

Open `http://localhost:4000` (or the port from `FRONTEND_PORT` in `.env`):

1. **Loading spinner:** Open «Аудиозаписи», «Звонки», «Журнал аудита», «Пользователи», any audio record's detail page, any call's detail page — each briefly shows a spinning icon instead of a blank screen on first load, then shows content normally. Trigger a subsequent action (e.g. a new search, pagination, blocking a user) — the spinner must NOT reappear over already-loaded content.
2. **Confirm dialog:** On «Пользователи», click «Заблокировать» on a user — a dialog appears asking to confirm; click «Отмена» — nothing happens, the user stays unblocked. Click «Заблокировать» again and this time confirm — the user becomes blocked. Try changing a user's role via the dropdown — same confirm/cancel behavior.
3. **Fixed link:** Open a call's detail page (`/calls/<id>`) that has an associated audio record, open DevTools Network tab, click «Открыть запись и полную транскрипцию →» — confirm there is NO full-document navigation/reload (no new `document` request), only the SPA route changes.
4. **Reset filters on empty results:** On «Аудиозаписи», set a filter that matches nothing (e.g. a nonsense value in «Поиск по тексту»), submit — confirm a «Сбросить фильтры» button appears next to «Записей не найдено», and clicking it clears the filter fields. Repeat briefly for «Звонки» and «Журнал аудита».

- [ ] **Step 3: Commit** (only if step 2 required fixes; otherwise nothing to commit)
