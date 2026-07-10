import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const MODELS = [
  { value: "", label: "Авто (по качеству аудио)" },
  { value: "tiny", label: "Tiny — быстро, ниже качество" },
  { value: "base", label: "Base — баланс скорости и качества" },
  { value: "large-v2", label: "Large-v2 — максимальное качество" },
];

const LANGUAGES = [
  { value: "auto",  label: "Авто-определение" },
  { value: "ru",    label: "Русский" },
  { value: "uk",    label: "Украинский" },
  { value: "be",    label: "Белорусский" },
  { value: "kk",    label: "Казахский" },
  { value: "en",    label: "Английский" },
  { value: "de",    label: "Немецкий" },
  { value: "fr",    label: "Французский" },
  { value: "es",    label: "Испанский" },
  { value: "it",    label: "Итальянский" },
  { value: "pt",    label: "Португальский" },
  { value: "pl",    label: "Польский" },
  { value: "nl",    label: "Нидерландский" },
  { value: "cs",    label: "Чешский" },
  { value: "sk",    label: "Словацкий" },
  { value: "tr",    label: "Турецкий" },
  { value: "ar",    label: "Арабский" },
  { value: "fa",    label: "Персидский" },
  { value: "hi",    label: "Хинди" },
  { value: "zh",    label: "Китайский" },
  { value: "ja",    label: "Японский" },
  { value: "ko",    label: "Корейский" },
  { value: "vi",    label: "Вьетнамский" },
  { value: "id",    label: "Индонезийский" },
  { value: "ms",    label: "Малайский" },
  { value: "th",    label: "Тайский" },
  { value: "el",    label: "Греческий" },
  { value: "bg",    label: "Болгарский" },
  { value: "hr",    label: "Хорватский" },
  { value: "sr",    label: "Сербский" },
  { value: "ro",    label: "Румынский" },
  { value: "hu",    label: "Венгерский" },
  { value: "fi",    label: "Финский" },
  { value: "sv",    label: "Шведский" },
  { value: "no",    label: "Норвежский" },
  { value: "da",    label: "Датский" },
  { value: "he",    label: "Иврит" },
];

type UploadState = "idle" | "uploading" | "done" | "error";

export function UploadPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [model, setModel] = useState("");
  const [language, setLanguage] = useState("auto");
  const [state, setState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !token) return;

    setState("uploading");
    setProgress(0);
    setError(null);

    const form = new FormData();
    form.append("file", file);
    if (model) form.append("whisper_model", model);
    form.append("language", language);

    // Используем XMLHttpRequest для отслеживания прогресса
    return new Promise<void>((resolve) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/v1/admin/audio/upload`);
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);

      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) {
          setProgress(Math.round((ev.loaded / ev.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status === 202) {
          const data = JSON.parse(xhr.responseText);
          setJobId(data.job_id);
          setState("done");
        } else {
          let msg = `Ошибка ${xhr.status}`;
          try {
            const err = JSON.parse(xhr.responseText);
            msg = err.detail ?? msg;
          } catch {}
          setError(msg);
          setState("error");
        }
        resolve();
      };

      xhr.onerror = () => {
        setError("Сетевая ошибка — проверьте подключение");
        setState("error");
        resolve();
      };

      xhr.send(form);
    });
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Загрузить аудио</h1>

      {state === "done" && jobId ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <div className="text-green-600 text-4xl mb-3">✓</div>
          <p className="text-green-800 font-medium mb-1">Файл отправлен в обработку</p>
          <p className="text-sm text-gray-500 mb-4">Job ID: {jobId}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate(`/audio/${jobId}`)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
            >
              Открыть запись
            </button>
            <button
              onClick={() => { setFile(null); setJobId(null); setState("idle"); setProgress(0); }}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
            >
              Загрузить ещё
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Дроп-зона */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              dragging
                ? "border-blue-400 bg-blue-50"
                : file
                ? "border-green-400 bg-green-50"
                : "border-gray-300 hover:border-gray-400 bg-white"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".mp3,.wav,.ogg,.flac,.m4a,.webm,.mp4,.aac,.opus"
              className="hidden"
              onChange={(e) => { if (e.target.files?.[0]) setFile(e.target.files[0]); }}
            />
            {file ? (
              <div>
                <div className="text-green-600 text-2xl mb-1">🎵</div>
                <p className="font-medium text-gray-800">{file.name}</p>
                <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(1)} МБ</p>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  className="mt-2 text-xs text-red-500 hover:underline"
                >
                  Убрать
                </button>
              </div>
            ) : (
              <div>
                <div className="text-gray-400 text-3xl mb-2">📁</div>
                <p className="text-gray-600">Перетащи файл или нажми для выбора</p>
                <p className="text-xs text-gray-400 mt-1">MP3, WAV, OGG, FLAC, M4A, WEBM — до 2 ГБ</p>
              </div>
            )}
          </div>

          {/* Модель */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Модель Whisper</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {MODELS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          {/* Язык */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Язык</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          {/* Прогресс */}
          {state === "uploading" && (
            <div>
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Загрузка...</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Ошибка */}
          {state === "error" && error && (
            <div className="bg-red-50 border border-red-200 rounded px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!file || state === "uploading"}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            {state === "uploading" ? "Загружается..." : "Отправить на транскрипцию"}
          </button>
        </form>
      )}
    </div>
  );
}
