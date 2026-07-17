import { useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_CALL_AGENT_WS ?? "ws://localhost:8100/ws/call";

type LogKind = "agent" | "system" | "error";
interface LogEntry { text: string; kind: LogKind; time: string; }

function nowLabel() {
  return new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function CallSimulatorPage() {
  const [active, setActive] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [log, setLog] = useState<LogEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const activeRef = useRef(false);

  function pushLog(text: string, kind: LogKind = "agent") {
    setLog(l => [...l, { text, kind, time: nowLabel() }]);
  }

  async function start() {
    setConnecting(true);
    setLog([]); setActive(true); activeRef.current = true;
    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = async (ev) => {
      if (typeof ev.data === "string") {
        const msg = JSON.parse(ev.data);
        if (msg.type === "agent_text") pushLog(`Агент: ${msg.text}`);
        if (msg.type === "hangup") { pushLog("— Агент завершил звонок —", "system"); stop(); }
      } else {
        const ctx = ctxRef.current;
        // Аудио от агента может прилететь раньше, чем разрешение на микрофон
        // будет получено и AudioContext создастся — в этом случае просто
        // пропускаем кадр, воспроизводить всё равно ещё некуда.
        if (!ctx) return;
        const buf = await ctx.decodeAudioData(ev.data.slice(0));
        const src = ctx.createBufferSource();
        src.buffer = buf; src.connect(ctx.destination); src.start();
      }
    };

    ws.onerror = () => { pushLog("Ошибка подключения к агенту", "error"); stop(); };
    ws.onclose = () => { if (activeRef.current) { pushLog("Соединение прервано", "error"); setActive(false); activeRef.current = false; } };

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = new AudioContext({ sampleRate: 16000 });
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(4096, 1, 1);
      source.connect(proc); proc.connect(ctx.destination);
      proc.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const f32 = e.inputBuffer.getChannelData(0);
        const i16 = new Int16Array(f32.length);
        for (let i = 0; i < f32.length; i++) {
          const s = Math.max(-1, Math.min(1, f32[i]));
          i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        ws.send(i16.buffer);
      };
    } catch (err) {
      pushLog("Ошибка микрофона: " + String(err), "error");
      stop();
    } finally {
      setConnecting(false);
    }
  }

  function stop() {
    setActive(false); activeRef.current = false;
    wsRef.current?.close();
    streamRef.current?.getTracks().forEach(t => t.stop());
    ctxRef.current?.close();
  }

  function handleStopClick() {
    pushLog("— Звонок завершён —", "system");
    stop();
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Симулятор звонка</h1>
      <p className="text-sm text-gray-500 mb-4">
        Нажмите «Позвонить», говорите в микрофон как мошенник — агент ответит голосом. Микрофон и аудио уходят на реальный бэкенд.
      </p>
      <div className="flex items-center gap-3">
        <button
          onClick={active ? handleStopClick : start}
          disabled={connecting}
          className={`text-white px-6 py-2.5 rounded-lg active:scale-[0.97] transition-[background-color,transform] duration-200 ease-out motion-reduce:active:scale-100 disabled:opacity-60 ${
            active ? "bg-gray-700 hover:bg-gray-800" : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          {connecting ? "Соединение…" : active ? "Завершить" : "Позвонить"}
        </button>
        {active && (
          <span className="flex items-center gap-1.5 text-xs text-red-600">
            <span className="w-2 h-2 rounded-full bg-red-600 animate-pulse motion-reduce:animate-none" />
            В звонке
          </span>
        )}
      </div>
      <div className="mt-4 bg-white rounded-lg shadow p-4 min-h-40 max-h-96 overflow-y-auto space-y-1">
        {log.length === 0 ? (
          <p className="text-sm text-gray-400">Здесь появится расшифровка звонка</p>
        ) : (
          log.map((entry, i) => <LogLine key={i} entry={entry} />)
        )}
      </div>
    </div>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      className={`flex items-baseline gap-2 text-sm transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:translate-y-0 ${
        mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
      } ${
        entry.kind === "error" ? "text-red-700 bg-red-50 rounded px-2 py-1" :
        entry.kind === "system" ? "text-gray-500 italic" :
        "text-gray-800"
      }`}
    >
      <span className="text-gray-400 text-xs tabular-nums shrink-0">{entry.time}</span>
      <span>{entry.text}</span>
    </div>
  );
}
