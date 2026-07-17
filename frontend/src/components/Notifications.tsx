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
  leaving?: boolean;
}

const TOAST_EXIT_MS = 200;

let _toastId = 0;

const STATUS_COLOR: Record<string, string> = {
  done: "bg-green-600",
  failed: "bg-red-600",
  // yellow-500 с белым текстом не проходит контраст (~1.9:1); на сплошном
  // тосте (не soft-tint бейдже) нужен более тёмный жёлтый
  partial: "bg-yellow-700",
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

  const dismiss = (id: number) => {
    setToasts(prev => prev.map(t => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), TOAST_EXIT_MS);
  };

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

  return (
    <div
      className="fixed bottom-28 right-4 z-50 flex flex-col gap-2 items-end"
      role="status"
      aria-live="polite"
    >
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const shown = mounted && !toast.leaving;

  return (
    <div
      className={`flex items-center gap-3 text-white text-sm rounded-lg shadow-lg px-4 py-3 transition-[opacity,transform] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:translate-y-0 ${
        shown ? "opacity-100 translate-y-0" : "opacity-0 translate-y-[20%]"
      } ${STATUS_COLOR[toast.status]}`}
    >
      <span>
        <span className="font-semibold">{STATUS_LABEL[toast.status]}</span>
        {" — "}
        <span className="font-mono text-xs">{toast.job_id.slice(0, 8)}</span>
      </span>
      <button
        onClick={onDismiss}
        className="ml-1 opacity-70 hover:opacity-100 text-base leading-none"
        aria-label="Закрыть"
      >
        ×
      </button>
    </div>
  );
}
