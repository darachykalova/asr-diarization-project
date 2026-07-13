import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface CallItem {
  call_id: string; source: string; started_at: string;
  duration_sec: number | null; verdict: string;
  scenario: string | null; confidence: number;
}
interface CallsResponse { items: CallItem[]; page: number; pages: number; total: number; }

const VERDICT = { scam: "🔴 Мошенник", not_scam: "🟢 Чисто", undetermined: "⚪ Не определён" } as Record<string,string>;

export function CallsListPage() {
  const { token } = useAuth();
  const [filters, setFilters] = useState({ verdict: "", scenario: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CallsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Звонки</h1>
      <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Вердикт</label>
          <select value={filters.verdict} onChange={e => setFilters(f => ({ ...f, verdict: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2 text-sm">
            <option value="">Все</option>
            <option value="scam">Мошенник</option>
            <option value="not_scam">Чисто</option>
            <option value="undetermined">Не определён</option>
          </select>
        </div>
        <input
          type="text"
          placeholder="Сценарий"
          value={filters.scenario}
          onChange={(e) => setFilters(f => ({ ...f, scenario: e.target.value }))}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button onClick={() => { setPage(1); load(1); }} disabled={loading}
          className="bg-blue-600 text-white px-5 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Загрузка…" : "Показать"}
        </button>
      </div>
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
    </div>
  );
}
