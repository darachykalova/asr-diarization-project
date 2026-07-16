import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { FadeIn } from "../components/FadeIn";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface Ev { at: number; speaker: string; text: string; scam_delta: number; }
interface Detail {
  call: { call_id: string; verdict: string; scenario: string | null; confidence: number;
    ended_reason: string | null; summary: string | null; duration_sec: number | null;
    job_id: string | null; };
  events: Ev[];
}

export function CallDetailPage() {
  const { callId } = useParams();
  const { token } = useAuth();
  const [d, setD] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const r = await fetch(`${API_BASE}/v1/admin/calls/${callId}`, { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) setD(await r.json());
  }
  useEffect(() => { load(); }, [callId]);

  async function regen() {
    setBusy(true);
    await fetch(`${API_BASE}/v1/admin/calls/${callId}/summary`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` },
    });
    await load(); setBusy(false);
  }

  if (!d) return <div className="p-6"><LoadingSpinner /></div>;
  const c = d.call;
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <FadeIn>
      <h1 className="text-2xl font-bold mb-4">Звонок</h1>
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <div className="text-lg font-medium mb-2">
          {c.verdict === "scam" ? "🔴 Мошенник" : c.verdict === "not_scam" ? "🟢 Чисто" : "⚪ Не определён"}
          {c.scenario && <span className="text-gray-500 text-sm ml-2">({c.scenario}, {c.confidence}%)</span>}
        </div>
        <div className="bg-gray-50 rounded p-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-medium text-gray-500">Краткая выжимка</span>
            <button onClick={regen} disabled={busy}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50 transition-opacity active:scale-[0.97] motion-reduce:active:scale-100">
              {busy ? "Генерация…" : "Обновить"}
            </button>
          </div>
          <p className="text-sm text-gray-800">{c.summary ?? "Выжимка ещё не готова."}</p>
        </div>
        {c.job_id && (
          <Link to={`/audio/${c.job_id}`}
             className="inline-block mt-3 text-sm text-blue-600 hover:underline">
            Открыть запись и полную транскрипцию →
          </Link>
        )}
      </div>
      <div className="bg-white rounded-lg shadow divide-y divide-gray-100">
        {d.events.map((e, i) => (
          <div key={i} className={`p-3 flex gap-3 ${e.scam_delta > 0 ? "bg-red-50" : ""}`}>
            <span className="text-xs text-gray-400 w-12">{e.at.toFixed(1)}с</span>
            <span className={`text-xs font-medium w-16 ${e.speaker === "agent" ? "text-blue-600" : "text-gray-700"}`}>
              {e.speaker === "agent" ? "Агент" : "Звонящий"}
            </span>
            <span className="text-sm flex-1">{e.text}</span>
            {e.scam_delta > 0 && <span className="text-xs text-red-500">+{e.scam_delta}</span>}
          </div>
        ))}
      </div>
      </FadeIn>
    </div>
  );
}
