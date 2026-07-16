import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface Summary { total_audio: number; total_transcribed: number; by_status: Record<string, number> }
interface WordCount { word: string; count: number }
interface SpeakerCount { speaker_id: number; name: string; count: number }
interface TimeBucket { bucket: string; count: number }

const STATUS_LABEL: Record<string, string> = {
  queued: "В очереди", processing: "Обрабатывается",
  done: "Готово", failed: "Ошибка", partial: "Частично",
};

function useGet<T>(path: string, token: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(String(e)));
  }, [path, token]);
  return { data, error };
}

function HBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="w-36 text-sm text-gray-700 truncate shrink-0" title={label}>{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
        <div
          className="h-4 w-full bg-blue-400 rounded-full origin-left transition-transform duration-200 ease-linear"
          style={{ transform: `scaleX(${pct / 100})` }}
        />
      </div>
      <span className="w-10 text-xs text-gray-500 text-right shrink-0">{value}</span>
    </div>
  );
}

function VBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex flex-col items-center gap-1 min-w-0">
      <span className="text-xs text-gray-500">{value}</span>
      <div className="w-8 bg-gray-100 rounded-t overflow-hidden flex items-end" style={{ height: 80 }}>
        <div className="w-8 bg-indigo-400 rounded-t" style={{ height: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 rotate-45 origin-left whitespace-nowrap"
            style={{ fontSize: 10 }}>
        {label.length > 6 ? label.slice(5, 10) : label}
      </span>
    </div>
  );
}

export function AnalyticsPage() {
  const { token } = useAuth();
  const [bucket, setBucket] = useState<"day" | "hour">("day");

  const { data: summary, error: summaryErr } = useGet<Summary>("/v1/admin/analytics/summary", token!);
  const { data: words, error: wordsErr } = useGet<WordCount[]>("/v1/admin/analytics/frequent-words?limit=20", token!);
  const { data: speakers } = useGet<SpeakerCount[]>("/v1/admin/analytics/frequent-speakers?limit=10", token!);
  const [uploads, setUploads] = useState<TimeBucket[] | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/v1/admin/analytics/uploads-over-time?bucket=${bucket}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(r => r.json()).then(setUploads).catch(() => setUploads([]));
  }, [bucket, token]);

  const maxWord = words ? Math.max(...words.map(w => w.count), 1) : 1;
  const maxSpk  = speakers ? Math.max(...speakers.map(s => s.count), 1) : 1;
  const maxUp   = uploads ? Math.max(...uploads.map(u => u.count), 1) : 1;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Аналитика</h1>

      {(summaryErr || wordsErr) && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">
          {summaryErr || wordsErr}
        </div>
      )}

      {/* Карточки сводки */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-xs text-gray-500 mb-1">Всего записей</p>
            <p className="text-3xl font-bold text-gray-800">{summary.total_audio}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-xs text-gray-500 mb-1">Транскрибировано</p>
            <p className="text-3xl font-bold text-green-600">{summary.total_transcribed}</p>
          </div>
          {Object.entries(summary.by_status).map(([st, cnt]) => (
            <div key={st} className="bg-white rounded-lg shadow p-4">
              <p className="text-xs text-gray-500 mb-1">{STATUS_LABEL[st] ?? st}</p>
              <p className="text-3xl font-bold text-gray-800">{cnt}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Частые слова */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="font-semibold text-gray-800 mb-4">Частые слова</h2>
          {words && words.length === 0 && (
            <p className="text-gray-400 text-sm">Нет данных</p>
          )}
          {words && words.map(w => (
            <HBar key={w.word} label={w.word} value={w.count} max={maxWord} />
          ))}
        </div>

        {/* Частые спикеры */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="font-semibold text-gray-800 mb-4">Частые спикеры</h2>
          {speakers && speakers.length === 0 && (
            <p className="text-gray-400 text-sm">Нет данных</p>
          )}
          {speakers && speakers.map(s => (
            <HBar key={s.speaker_id} label={s.name} value={s.count} max={maxSpk} />
          ))}
        </div>
      </div>

      {/* Загрузки по времени */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">Загрузки по времени</h2>
          <select
            value={bucket}
            onChange={e => setBucket(e.target.value as "day" | "hour")}
            className="border border-gray-200 rounded px-2 py-1 text-sm"
          >
            <option value="day">По дням</option>
            <option value="hour">По часам</option>
          </select>
        </div>
        {uploads && uploads.length === 0 && (
          <p className="text-gray-400 text-sm">Нет данных</p>
        )}
        {uploads && uploads.length > 0 && (
          <div className="flex items-end gap-1 overflow-x-auto pb-6" style={{ minHeight: 120 }}>
            {uploads.map(u => (
              <VBar
                key={u.bucket}
                value={u.count}
                max={maxUp}
                label={u.bucket}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
