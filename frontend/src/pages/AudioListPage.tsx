import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface AudioListItem {
  job_id: string;
  title: string;
  uploaded_at: string;
  duration_sec: number | null;
  status: string;
  speaker_count: number;
}

interface AudioListResponse {
  items: AudioListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

const STATUS_LABEL: Record<string, string> = {
  queued:     "В очереди",
  processing: "Обрабатывается",
  done:       "Готово",
  failed:     "Ошибка",
  partial:    "Частично",
};

function fmtDuration(sec: number | null): string {
  if (sec == null) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const EMPTY = { q: "", jobIdQ: "", speakerId: "", speakerName: "", minSpeakers: "", maxSpeakers: "", durationMin: "", durationMax: "", status: "", dateFrom: "", dateTo: "" };

type SortBy = "uploaded_at" | "duration" | "speakers";
type SortOrder = "asc" | "desc";

function SortHeader({ col, label, current, order, onClick }: {
  col: SortBy; label: string; current: SortBy; order: SortOrder;
  onClick: (col: SortBy) => void;
}) {
  const active = current === col;
  return (
    <th
      className="text-left px-4 py-3 font-medium cursor-pointer select-none"
      onClick={() => onClick(col)}
      title={active ? (order === "desc" ? "Сейчас: по убыванию. Нажмите для сортировки по возрастанию" : "Сейчас: по возрастанию. Нажмите для сортировки по убыванию") : "Нажмите для сортировки"}
    >
      <span className={`inline-flex items-center gap-1 group ${active ? "text-blue-600" : "text-gray-600"}`}>
        <span className={active ? "underline underline-offset-2" : "group-hover:underline group-hover:underline-offset-2"}>
          {label}
        </span>
        <span className={`text-xs ${active ? "text-blue-500" : "text-gray-400 group-hover:text-gray-600"}`}>
          {active ? (order === "desc" ? "↓" : "↑") : "↕"}
        </span>
      </span>
    </th>
  );
}

export function AudioListPage() {
  const { token } = useAuth();

  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortBy>("uploaded_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [data, setData] = useState<AudioListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set(field: keyof typeof EMPTY) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setFilters((f) => ({ ...f, [field]: e.target.value }));
  }

  function handleSortClick(col: SortBy) {
    const newOrder = sortBy === col && sortOrder === "desc" ? "asc" : "desc";
    setSortBy(col);
    setSortOrder(newOrder);
    setPage(1);
    fetchListWith(1, col, newOrder);
  }

  async function fetchList(p: number = page) {
    return fetchListWith(p, sortBy, sortOrder);
  }

  async function fetchListWith(p: number, sb: SortBy, so: SortOrder) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("page", String(p));
      params.set("page_size", "20");
      if (filters.q.trim())          params.set("q",            filters.q.trim());
      if (filters.jobIdQ.trim())     params.set("job_id_q",     filters.jobIdQ.trim());
      if (filters.speakerId.trim())   params.set("speaker_id",   filters.speakerId.trim());
      if (filters.speakerName.trim()) params.set("speaker_name", filters.speakerName.trim());
      if (filters.minSpeakers)        params.set("min_speakers", filters.minSpeakers);
      if (filters.maxSpeakers)        params.set("max_speakers", filters.maxSpeakers);
      if (filters.durationMin) params.set("duration_min", String(parseFloat(filters.durationMin) * 60));
      if (filters.durationMax) params.set("duration_max", String(parseFloat(filters.durationMax) * 60));
      if (filters.status)            params.set("status",       filters.status);
      if (filters.dateFrom)          params.set("date_from",    new Date(filters.dateFrom).toISOString());
      if (filters.dateTo)            params.set("date_to",      new Date(filters.dateTo).toISOString());
      params.set("sort_by",    sb);
      params.set("sort_order", so);

      const resp = await fetch(`${API_BASE}/v1/admin/audio?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData(await resp.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchList(); }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchList(1);
  }

  function handleReset() {
    setFilters(EMPTY);
    setData(null);
    setPage(1);
  }

  function goPage(p: number) {
    setPage(p);
    fetchList(p);
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Аудиозаписи</h1>

      {/* Фильтры */}
      <form onSubmit={handleSearch} className="bg-white rounded-lg shadow p-5 mb-6">
        <div className="grid grid-cols-4 gap-4">
          {/* Колонка 1 */}
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Поиск по тексту транскрипции</label>
            <input type="text" value={filters.q} onChange={set("q")}
              placeholder="Слово или фраза…"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
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

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Статус</label>
            <select value={filters.status} onChange={set("status")}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Все статусы</option>
              {Object.entries(STATUS_LABEL).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <div className="col-span-2 flex items-end gap-3">
            <button type="submit" disabled={loading}
              className="flex-1 bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {loading ? "Поиск…" : "Найти"}
            </button>
            <button type="button" onClick={handleReset}
              className="px-4 py-2 rounded text-sm text-gray-500 border border-gray-300 hover:bg-gray-50 transition-colors">
              Сбросить
            </button>
          </div>
        </div>
      </form>

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
    </div>
  );
}
