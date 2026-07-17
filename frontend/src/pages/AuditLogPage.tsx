import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface AuditLogItem {
  id: number;
  user_id: number;
  user_login: string;
  job_id: string;
  action: string;
  created_at: string;
}

interface AuditLogPage {
  items: AuditLogItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

interface AdminUserOption {
  id: number;
  login: string;
}

// Известные действия журнала: подпись + окраска по смыслу
// (красный = разрушительное, серый = чтение; жёлтый «на всё подряд» был ошибкой)
const ACTION_BADGE: Record<string, { label: string; cls: string }> = {
  delete: { label: "Удаление записи", cls: "bg-red-100 text-red-700" },
  reveal: { label: "Просмотр транскрипции", cls: "bg-gray-100 text-gray-700" },
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export function AuditLogPage() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [userId, setUserId] = useState(() => searchParams.get("user_id") ?? "");
  const [dateFrom, setDateFrom] = useState(() => searchParams.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(() => searchParams.get("date_to") ?? "");
  const [page, setPage] = useState(() => Number(searchParams.get("page")) || 1);
  const [data, setData] = useState<AuditLogPage | null>(null);
  const [userOptions, setUserOptions] = useState<AdminUserOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  function syncUrl(p: number, uid: string, dFrom: string, dTo: string) {
    const params = new URLSearchParams();
    if (uid) params.set("user_id", uid);
    if (dFrom) params.set("date_from", dFrom);
    if (dTo) params.set("date_to", dTo);
    if (p !== 1) params.set("page", String(p));
    setSearchParams(params, { replace: true });
  }

  async function fetchLog(p: number = page, overrides?: { userId?: string; dateFrom?: string; dateTo?: string }) {
    const uid = overrides?.userId ?? userId;
    const dFrom = overrides?.dateFrom ?? dateFrom;
    const dTo = overrides?.dateTo ?? dateTo;
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", String(p)); params.set("page_size", "50");
      if (uid.trim()) params.set("user_id", uid.trim());
      if (dFrom) params.set("date_from", new Date(dFrom).toISOString());
      if (dTo) params.set("date_to", new Date(dTo).toISOString());

      const resp = await fetch(`${API_BASE}/v1/admin/audit-log?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData(await resp.json());
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); setInitialLoading(false); }
  }

  function resetFilters() {
    setUserId(""); setDateFrom(""); setDateTo("");
    setPage(1);
    syncUrl(1, "", "", "");
    fetchLog(1, { userId: "", dateFrom: "", dateTo: "" });
  }

  const filtersActive = userId !== "" || dateFrom !== "" || dateTo !== "";

  useEffect(() => {
    fetchLog(page);
    // Список пользователей для фильтра; при ошибке фильтр просто остаётся пустым
    fetch(`${API_BASE}/v1/admin/users`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => (r.ok ? r.json() : []))
      .then((list: AdminUserOption[]) => setUserOptions(list))
      .catch(() => {});
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    syncUrl(1, userId, dateFrom, dateTo);
    fetchLog(1);
  }

  function goPage(p: number) {
    setPage(p);
    syncUrl(p, userId, dateFrom, dateTo);
    fetchLog(p);
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Журнал аудита</h1>

      <form onSubmit={handleSearch} className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
        <div className="min-w-44">
          <label htmlFor="audit-user" className="block text-xs font-medium text-gray-600 mb-1">Пользователь</label>
          <select
            id="audit-user" value={userId} onChange={e => setUserId(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Все</option>
            {userOptions.map(u => (
              <option key={u.id} value={String(u.id)}>{u.login}</option>
            ))}
          </select>
        </div>
        <div className="min-w-40">
          <label htmlFor="audit-date-from" className="block text-xs font-medium text-gray-600 mb-1">Дата с</label>
          <input id="audit-date-from" type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div className="min-w-40">
          <label htmlFor="audit-date-to" className="block text-xs font-medium text-gray-600 mb-1">Дата по</label>
          <input id="audit-date-to" type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <button type="submit" disabled={loading}
          className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 active:scale-[0.97] transition-[background-color,opacity,transform] motion-reduce:active:scale-100">
          {loading ? "Загрузка…" : "Показать"}
        </button>
      </form>

      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>}

          {data && (
            <>
              <div className="text-sm text-gray-500 mb-2">Событий: {data.total}</div>
              <div className="bg-white rounded-lg shadow overflow-x-auto">
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
                      <tr>
                        <td colSpan={4} className="text-center py-8 text-gray-500">
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
                    ) : data.items.map(item => {
                      const badge = ACTION_BADGE[item.action] ?? { label: item.action, cls: "bg-gray-100 text-gray-700" };
                      return (
                        <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3 font-mono text-xs text-gray-600">{fmtDate(item.created_at)}</td>
                          <td className="px-4 py-3 font-medium">{item.user_login}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${badge.cls}`}>
                              {badge.label}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-gray-500">{item.job_id}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {data.pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-4">
                  <button onClick={() => goPage(page - 1)} disabled={page <= 1}
                    className="px-3 py-2 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">←</button>
                  <span className="text-sm text-gray-600">Страница {data.page} из {data.pages}</span>
                  <button onClick={() => goPage(page + 1)} disabled={page >= data.pages}
                    className="px-3 py-2 rounded border text-sm disabled:opacity-40 hover:bg-gray-100">→</button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
