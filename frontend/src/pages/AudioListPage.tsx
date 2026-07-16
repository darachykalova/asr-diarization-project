import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

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
const ROW_EXIT_MS = 200;

type SortBy = "uploaded_at" | "duration" | "speakers";
type SortOrder = "asc" | "desc";

const FILTER_PARAM: Record<keyof typeof EMPTY, string> = {
  q: "q", jobIdQ: "job_id_q", speakerId: "speaker_id", speakerName: "speaker_name",
  minSpeakers: "min_speakers", maxSpeakers: "max_speakers",
  durationMin: "duration_min", durationMax: "duration_max",
  status: "status", dateFrom: "date_from", dateTo: "date_to",
};
const FILTER_KEYS = Object.keys(FILTER_PARAM) as Array<keyof typeof EMPTY>;

function filtersFromSearchParams(params: URLSearchParams): typeof EMPTY {
  const f = { ...EMPTY };
  for (const key of FILTER_KEYS) {
    const v = params.get(FILTER_PARAM[key]);
    if (v) f[key] = v;
  }
  return f;
}

function buildUrlParams(filters: typeof EMPTY, sortBy: SortBy, sortOrder: SortOrder, page: number): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    if (filters[key]) params.set(FILTER_PARAM[key], filters[key]);
  }
  if (sortBy !== "uploaded_at") params.set("sort_by", sortBy);
  if (sortOrder !== "desc") params.set("sort_order", sortOrder);
  if (page !== 1) params.set("page", String(page));
  return params;
}

function SortHeader({ col, label, current, order, onClick }: {
  col: SortBy; label: string; current: SortBy; order: SortOrder;
  onClick: (col: SortBy) => void;
}) {
  const active = current === col;
  return (
    <th
      className="text-left px-4 py-3 font-medium"
      aria-sort={active ? (order === "desc" ? "descending" : "ascending") : "none"}
    >
      <button
        type="button"
        onClick={() => onClick(col)}
        title={active ? (order === "desc" ? "Сейчас: по убыванию. Нажмите для сортировки по возрастанию" : "Сейчас: по возрастанию. Нажмите для сортировки по убыванию") : "Нажмите для сортировки"}
        className="inline-flex items-center gap-1 group cursor-pointer select-none rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
      >
        <span className={`${active ? "text-blue-600" : "text-gray-600"} ${active ? "underline underline-offset-2" : "group-hover:underline group-hover:underline-offset-2"}`}>
          {label}
        </span>
        <span className={`text-xs ${active ? "text-blue-500" : "text-gray-400 group-hover:text-gray-600"}`}>
          {active ? (order === "desc" ? "↓" : "↑") : "↕"}
        </span>
      </button>
    </th>
  );
}

export function AudioListPage() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [filters, setFilters] = useState(() => filtersFromSearchParams(searchParams));
  const [page, setPage] = useState(() => Number(searchParams.get("page")) || 1);
  const [sortBy, setSortBy] = useState<SortBy>(() => (searchParams.get("sort_by") as SortBy) || "uploaded_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>(() => (searchParams.get("sort_order") as SortOrder) || "desc");
  const [data, setData] = useState<AudioListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMore, setShowMore] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<AudioListItem | null>(null);
  const [removingIds, setRemovingIds] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  function set(field: keyof typeof EMPTY) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setFilters((f) => ({ ...f, [field]: e.target.value }));
  }

  function handleSortClick(col: SortBy) {
    const newOrder = sortBy === col && sortOrder === "desc" ? "asc" : "desc";
    setSortBy(col);
    setSortOrder(newOrder);
    setPage(1);
    setSearchParams(buildUrlParams(filters, col, newOrder, 1), { replace: true });
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
      setSelectedIds(new Set());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
      setInitialLoading(false);
    }
  }

  async function handleDelete(jobId: string) {
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/audio/${jobId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      setRemovingIds((prev) => new Set(prev).add(jobId));
      setTimeout(() => {
        setData((d) =>
          d
            ? { ...d, items: d.items.filter((i) => i.job_id !== jobId), total: d.total - 1 }
            : d
        );
  setRemovingIds((prev) => {
          const next = new Set(prev);
          next.delete(jobId);
          return next;
        });
      }, ROW_EXIT_MS);
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleBulkDelete() {
    setError(null);
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        const resp = await fetch(`${API_BASE}/v1/admin/audio/${id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return id;
      })
    );
    const succeeded = results
      .filter((r): r is PromiseFulfilledResult<string> => r.status === "fulfilled")
      .map((r) => r.value);
    const failedCount = ids.length - succeeded.length;

    if (succeeded.length > 0) {
      setRemovingIds((prev) => new Set([...prev, ...succeeded]));
      setTimeout(() => {
        setData((d) =>
          d
            ? { ...d, items: d.items.filter((i) => !succeeded.includes(i.job_id)), total: d.total - succeeded.length }
            : d
        );
        setRemovingIds((prev) => {
          const next = new Set(prev);
          succeeded.forEach((id) => next.delete(id));
          return next;
        });
      }, ROW_EXIT_MS);
    }
    setSelectedIds(new Set());
    setBulkDeleteOpen(false);
    if (failedCount > 0) setError(`Не удалось удалить ${failedCount} из ${ids.length} записей`);
  }

  function toggleSelected(jobId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }

  function toggleSelectAll() {
    if (!data) return;
    setSelectedIds((prev) => {
      const allSelected = data.items.length > 0 && data.items.every((i) => prev.has(i.job_id));
      return allSelected ? new Set() : new Set(data.items.map((i) => i.job_id));
    });
  }

  useEffect(() => { fetchList(); }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setSearchParams(buildUrlParams(filters, sortBy, sortOrder, 1), { replace: true });
    fetchList(1);
  }

  function handleReset() {
    setFilters(EMPTY);
    setData(null);
    setPage(1);
    setSearchParams(new URLSearchParams(), { replace: true });
  }

  const filtersActive = Object.values(filters).some((v) => v !== "");

  function goPage(p: number) {
    setPage(p);
    setSearchParams(buildUrlParams(filters, sortBy, sortOrder, p), { replace: true });
    fetchList(p);
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Аудиозаписи</h1>

      {/* Фильтры */}
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

        <div
          className={`grid overflow-hidden transition-[grid-template-rows] duration-[250ms] ease-[cubic-bezier(0.23,1,0.32,1)] ${
            showMore ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          }`}
        >
          <div className="overflow-hidden">
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
          </div>
        </div>
      </form>

      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>
          )}

          {data && (
            <>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-gray-500">Найдено: {data.total} записей</div>
                {selectedIds.size > 0 && (
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-gray-600">Выбрано: {selectedIds.size}</span>
                    <button
                      onClick={() => setBulkDeleteOpen(true)}
                      className="text-red-600 hover:underline active:scale-[0.97] transition-transform motion-reduce:active:scale-100"
                    >
                      Удалить выбранное
                    </button>
                    <button
                      onClick={() => setSelectedIds(new Set())}
                      className="text-gray-500 hover:underline active:scale-[0.97] transition-transform motion-reduce:active:scale-100"
                    >
                      Отменить выбор
                    </button>
                  </div>
                )}
              </div>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="w-10 px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label="Выбрать все записи на странице"
                          checked={data.items.length > 0 && data.items.every((i) => selectedIds.has(i.job_id))}
                          onChange={toggleSelectAll}
                        />
                      </th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Файл / ID</th>
                      <SortHeader col="uploaded_at" label="Дата загрузки" current={sortBy} order={sortOrder} onClick={handleSortClick} />
                      <SortHeader col="duration"    label="Длительность"  current={sortBy} order={sortOrder} onClick={handleSortClick} />
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Статус</th>
                      <SortHeader col="speakers"    label="Спикеры"       current={sortBy} order={sortOrder} onClick={handleSortClick} />
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Действия</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.items.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center py-8 text-gray-400">
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
                    ) : (
                      data.items.map((item) => (
                        <tr
                          key={item.job_id}
                          className={`hover:bg-gray-50 transition-opacity duration-[200ms] ease-[cubic-bezier(0.23,1,0.32,1)] ${
                            removingIds.has(item.job_id) ? "opacity-0" : "opacity-100"
                          }`}
                        >
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              aria-label={`Выбрать «${item.title}»`}
                              checked={selectedIds.has(item.job_id)}
                              onChange={() => toggleSelected(item.job_id)}
                            />
                          </td>
                          <td className="px-4 py-3">
                            <Link to={`/audio/${item.job_id}`} className="text-blue-600 hover:underline font-medium">
                              {item.title}
                            </Link>
                            <div className="text-xs text-gray-500 font-mono">{item.job_id}</div>
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
                          <td className="px-4 py-3">
                            <button
                              onClick={() => setPendingDelete(item)}
                              className="text-red-600 hover:underline text-sm"
                            >
                              Удалить
                            </button>
                          </td>
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
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Удалить аудиозапись?"
        message={
          pendingDelete
            ? `«${pendingDelete.title}» (загружена ${fmtDate(pendingDelete.uploaded_at)}, ${fmtDuration(pendingDelete.duration_sec)}) будет удалена без возможности восстановления.`
            : ""
        }
        confirmLabel="Удалить"
        danger
        onConfirm={() => {
          if (pendingDelete) handleDelete(pendingDelete.job_id);
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
      <ConfirmDialog
        open={bulkDeleteOpen}
        title="Удалить выбранные записи?"
        message={`${selectedIds.size} ${selectedIds.size === 1 ? "запись будет удалена" : "записей будет удалено"} без возможности восстановления.`}
        confirmLabel="Удалить"
        danger
        onConfirm={handleBulkDelete}
        onCancel={() => setBulkDeleteOpen(false)}
      />
    </div>
  );
}
