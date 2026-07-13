import { useEffect, useState } from "react";
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

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export function AuditLogPage() {
  const { token } = useAuth();
  const [userId, setUserId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AuditLogPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  async function fetchLog(p: number = page) {
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", String(p)); params.set("page_size", "50");
      if (userId.trim()) params.set("user_id", userId.trim());
      if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.set("date_to", new Date(dateTo).toISOString());

      const resp = await fetch(`${API_BASE}/v1/admin/audit-log?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData(await resp.json());
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); setInitialLoading(false); }
  }

  function resetFilters() {
    setUserId(""); setDateFrom(""); setDateTo("");
  }

  const filtersActive = userId !== "" || dateFrom !== "" || dateTo !== "";

  useEffect(() => { fetchLog(1); }, []);

  function handleSearch(e: React.FormEvent) { e.preventDefault(); setPage(1); fetchLog(1); }
  function goPage(p: number) { setPage(p); fetchLog(p); }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Журнал аудита</h1>

      <form onSubmit={handleSearch} className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
        <div className="min-w-36">
          <label className="block text-xs font-medium text-gray-600 mb-1">ID пользователя</label>
          <input
            type="number" value={userId} onChange={e => setUserId(e.target.value)} placeholder="все"
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="min-w-40">
          <label className="block text-xs font-medium text-gray-600 mb-1">Дата с</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div className="min-w-40">
          <label className="block text-xs font-medium text-gray-600 mb-1">Дата по</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <button type="submit" disabled={loading}
          className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {loading ? "Загрузка…" : "Показать"}
        </button>
      </form>

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
    </div>
  );
}
