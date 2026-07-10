import { useState } from "react";
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
  const [verdict, setVerdict] = useState("");
  const [data, setData] = useState<CallsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(page = 1) {
    setLoading(true);
    const p = new URLSearchParams({ page: String(page), page_size: "20" });
    if (verdict) p.set("verdict", verdict);
    const r = await fetch(`${API_BASE}/v1/admin/calls?${p}`, { headers: { Authorization: `Bearer ${token}` } });
    setData(await r.json());
    setLoading(false);
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Звонки</h1>
      <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Вердикт</label>
          <select value={verdict} onChange={e => setVerdict(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm">
            <option value="">Все</option>
            <option value="scam">Мошенник</option>
            <option value="not_scam">Чисто</option>
            <option value="undetermined">Не определён</option>
          </select>
        </div>
        <button onClick={() => load(1)} disabled={loading}
          className="bg-blue-600 text-white px-5 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Загрузка…" : "Показать"}
        </button>
      </div>
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
        </div>
      )}
    </div>
  );
}
