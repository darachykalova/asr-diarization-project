import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface AudioItem {
  job_id: string;
  title: string;
  uploaded_at: string;
  duration_sec: number | null;
  status: string;
  speaker_count: number;
}

interface SpeakerInfo {
  speaker: string;
  speaker_id: number | null;
  display_name: string | null;
}

interface SegmentItem {
  start: number;
  end: number;
  speaker: string;
  text: string;
}

interface RevealedTranscript {
  job_id: string;
  language: string | null;
  speakers: SpeakerInfo[];
  segments: SegmentItem[];
}

function fmtTime(sec: number): string {
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

const STATUS_LABEL: Record<string, string> = {
  queued: "В очереди", processing: "Обрабатывается",
  done: "Готово", failed: "Ошибка", partial: "Частично",
};

// Цвет бейджа спикера по порядковому номеру
const SPEAKER_COLORS = [
  "bg-blue-100 text-blue-800",
  "bg-purple-100 text-purple-800",
  "bg-green-100 text-green-800",
  "bg-orange-100 text-orange-800",
  "bg-pink-100 text-pink-800",
];

export function AudioDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { token } = useAuth();

  const [item, setItem] = useState<AudioItem | null>(null);
  const [itemError, setItemError] = useState<string | null>(null);

  const [revealed, setRevealed] = useState<RevealedTranscript | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [revealError, setRevealError] = useState<string | null>(null);

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
      .catch((e) => setItemError(String(e)));
  }, [jobId, token]);

  async function handleReveal() {
    if (!jobId) return;
    setRevealing(true);
    setRevealError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/v1/admin/audio/${jobId}/transcript:reveal`,
        { method: "POST", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      setRevealed(await resp.json());
    } catch (e) {
      setRevealError(String(e));
    } finally {
      setRevealing(false);
    }
  }

  const speakerColorMap: Record<string, string> = {};
  revealed?.speakers.forEach((s, i) => {
    speakerColorMap[s.speaker] = SPEAKER_COLORS[i % SPEAKER_COLORS.length];
  });

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Хлебные крошки */}
      <nav className="text-sm text-gray-500 mb-4">
        <Link to="/audio" className="hover:text-gray-700">← Аудиозаписи</Link>
      </nav>

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
    </div>
  );
}
