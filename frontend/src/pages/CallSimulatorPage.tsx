import { useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_CALL_AGENT_WS ?? "ws://localhost:8100/ws/call";

export function CallSimulatorPage() {
  const [active, setActive] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  function pushLog(line: string) { setLog(l => [...l, line]); }

  async function start() {
    setLog([]); setActive(true);
    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = async (ev) => {
      if (typeof ev.data === "string") {
        const msg = JSON.parse(ev.data);
        if (msg.type === "agent_text") pushLog(`Агент: ${msg.text}`);
        if (msg.type === "hangup") { pushLog("— Агент завершил звонок —"); stop(); }
      } else {
        const ctx = ctxRef.current!;
        const buf = await ctx.decodeAudioData(ev.data.slice(0));
        const src = ctx.createBufferSource();
        src.buffer = buf; src.connect(ctx.destination); src.start();
      }
    };

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
  }

  function stop() {
    setActive(false);
    wsRef.current?.close();
    streamRef.current?.getTracks().forEach(t => t.stop());
    ctxRef.current?.close();
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Симулятор звонка</h1>
      <p className="text-sm text-gray-500 mb-4">
        Нажмите «Позвонить», говорите в микрофон как мошенник — агент ответит голосом.
      </p>
      {!active
        ? <button onClick={start} className="bg-green-600 text-white px-6 py-2.5 rounded-lg">Позвонить</button>
        : <button onClick={stop} className="bg-red-600 text-white px-6 py-2.5 rounded-lg">Завершить</button>}
      <div className="mt-4 bg-white rounded-lg shadow p-4 min-h-40 space-y-1">
        {log.map((l, i) => <div key={i} className="text-sm">{l}</div>)}
      </div>
    </div>
  );
}
