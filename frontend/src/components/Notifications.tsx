import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const POLL_INTERVAL_MS = 15_000;

interface StatusUpdate {
  job_id: string;
  status: "done" | "failed" | "partial";
  finished_at: string | null;
}

interface Toast {
  id: number;
  job_id: string;
  status: "done" | "failed" | "partial";
}

let _toastId = 0;

const STATUS_COLOR: Record<string, string> = {
  done: "bg-green-600",
  failed: "bg-red-600",
  partial: "bg-yellow-500",
};
const STATUS_LABEL: Record<string, string> = {
  done: "Готово",
  failed: "Ошибка",
  partial: "Частично",
};

export function Notifications() {
  const { token } = useAuth();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const lastCheckedRef = useRef<string>(new Date().toISOString());

  const dismiss = (id: number) =>
    setToasts(prev => prev.filter(t => t.id !== id));

  useEffect(() => {
    if (!token) return;

    const poll = async () => {
      try {
        const resp = await fetch(
          `${API_BASE}/v1/admin/audio/updates?since=${encodeURIComponent(lastCheckedRef.current)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!resp.ok) return;
        const data = await resp.json() as { server_time: string; items: StatusUpdate[] };
        lastCheckedRef.current = data.server_time;

        const newToasts: Toast[] = data.items.map(item => ({
          id: ++_toastId,
          job_id: item.job_id,
          status: item.status,
        }));
        if (newToasts.length) {
          setToasts(prev => [...prev, ...newToasts]);
          // автоскрытие через 6 секунд
          newToasts.forEach(t => setTimeout(() => dismiss(t.id), 6_000));
        }
      } catch {
        // polling ошибки молча игнорируем
      }
    };

    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [token]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-center gap-3 text-white text-sm rounded-lg shadow-lg px-4 py-3 ${STATUS_COLOR[t.status]}`}
        >
          <span>
            <span className="font-semibold">{STATUS_LABEL[t.status]}</span>
            {" — "}
            <span className="font-mono text-xs">{t.job_id.slice(0, 8)}</span>
          </span>
          <button
            onClick={() => dismiss(t.id)}
            className="ml-1 opacity-70 hover:opacity-100 text-base leading-none"
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
