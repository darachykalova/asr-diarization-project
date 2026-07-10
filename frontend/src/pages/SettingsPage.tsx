import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface Setting {
  key: string;
  value: string;
  value_type: string;
  updated_at: string | null;
}

// Метаданные для каждой настройки: как показать и что объяснить
const SETTING_META: Record<string, {
  label: string;
  hint: string;
  control: "asr_model" | "language" | "number" | "formats" | "text";
  unit?: string;
  placeholder?: string;
  min?: number;
  max?: number;
}> = {
  default_asr_model: {
    label: "Модель распознавания речи",
    hint: "Определяет точность и скорость обработки аудио. «Авто» — система сама выбирает модель по качеству звука. «Быстрая» обрабатывает быстро, но менее точна. «Точная» даёт лучший результат, но требует больше времени.",
    control: "asr_model",
  },
  default_language: {
    label: "Язык распознавания по умолчанию",
    hint: "Язык, который будет использоваться если при загрузке файла язык не указан. «Автоопределение» — система сама распознаёт язык аудио. Явный выбор языка ускоряет обработку и повышает точность.",
    control: "language",
  },
  max_upload_size_mb: {
    label: "Максимальный размер загружаемого файла",
    hint: "Файлы тяжелее этого предела не будут приняты системой. Слишком большой лимит может перегрузить сервер при одновременной загрузке нескольких файлов.",
    control: "number",
    unit: "МБ",
    placeholder: "2048",
    min: 1,
    max: 10240,
  },
  max_speakers: {
    label: "Максимальное количество спикеров",
    hint: "Ограничивает сколько разных голосов система ищет в одной записи. Пустое значение — без ограничений. Если в записи 2 человека, поставьте 2 — это повысит точность диаризации.",
    control: "number",
    unit: "чел.",
    placeholder: "без ограничения",
    min: 1,
    max: 50,
  },
  allowed_formats: {
    label: "Разрешённые форматы файлов",
    hint: "Файлы в других форматах будут отклонены при загрузке. Снимите галочку с форматов, которые не нужны или могут создавать проблемы.",
    control: "formats",
  },
  audit_log_retention_days: {
    label: "Срок хранения журнала аудита",
    hint: "Записи о том, кто и когда открывал транскрипции, хранятся указанное количество дней. После истечения срока они автоматически удаляются. 0 — хранить бессрочно.",
    control: "number",
    unit: "дней",
    placeholder: "90",
    min: 0,
    max: 3650,
  },
};

const ALL_FORMATS = ["mp3", "wav", "ogg", "flac", "m4a", "webm", "mp4", "aac", "opus"];

function Tooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block ml-1.5 align-middle">
      <span
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-200 text-gray-500 text-xs cursor-help hover:bg-blue-100 hover:text-blue-600 transition-colors"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >?</span>
      {show && (
        <span className="absolute left-6 top-0 z-50 w-72 bg-gray-800 text-white text-xs rounded-lg px-3 py-2 shadow-lg leading-relaxed">
          {text}
        </span>
      )}
    </span>
  );
}

function AsrModelControl({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300">
      <option value="">Авто (по качеству звука)</option>
      <option value="tiny">Быстрая (tiny)</option>
      <option value="base">Средняя (base)</option>
      <option value="large-v2">Точная (large-v2)</option>
    </select>
  );
}

const WHISPER_LANGUAGES: [string, string][] = [
  ["af", "Африкаанс"],
  ["ar", "Арабский"],
  ["hy", "Армянский"],
  ["az", "Азербайджанский"],
  ["be", "Белорусский"],
  ["bs", "Боснийский"],
  ["bg", "Болгарский"],
  ["ca", "Каталанский"],
  ["zh", "Китайский"],
  ["hr", "Хорватский"],
  ["cs", "Чешский"],
  ["da", "Датский"],
  ["nl", "Нидерландский"],
  ["en", "Английский"],
  ["et", "Эстонский"],
  ["fi", "Финский"],
  ["fr", "Французский"],
  ["gl", "Галисийский"],
  ["de", "Немецкий"],
  ["el", "Греческий"],
  ["he", "Иврит"],
  ["hi", "Хинди"],
  ["hu", "Венгерский"],
  ["is", "Исландский"],
  ["id", "Индонезийский"],
  ["it", "Итальянский"],
  ["ja", "Японский"],
  ["kk", "Казахский"],
  ["kn", "Каннада"],
  ["ko", "Корейский"],
  ["lv", "Латышский"],
  ["lt", "Литовский"],
  ["mk", "Македонский"],
  ["ms", "Малайский"],
  ["mr", "Маратхи"],
  ["mi", "Маори"],
  ["ne", "Непальский"],
  ["no", "Норвежский"],
  ["fa", "Персидский"],
  ["pl", "Польский"],
  ["pt", "Португальский"],
  ["ro", "Румынский"],
  ["ru", "Русский"],
  ["sr", "Сербский"],
  ["sk", "Словацкий"],
  ["sl", "Словенский"],
  ["es", "Испанский"],
  ["sw", "Суахили"],
  ["sv", "Шведский"],
  ["tl", "Тагальский"],
  ["ta", "Тамильский"],
  ["th", "Тайский"],
  ["tr", "Турецкий"],
  ["uk", "Украинский"],
  ["ur", "Урду"],
  ["vi", "Вьетнамский"],
  ["cy", "Валлийский"],
];

function LanguageControl({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300">
      <option value="">Автоопределение</option>
      {WHISPER_LANGUAGES.map(([code, name]) => (
        <option key={code} value={code}>{name} ({code})</option>
      ))}
    </select>
  );
}

function NumberControl({ value, onChange, unit, placeholder, min, max }: {
  value: string; onChange: (v: string) => void; unit?: string; placeholder?: string; min?: number; max?: number;
}) {
  const num = value === "" ? null : Number(value);
  const outOfRange = num !== null && ((min !== undefined && num < min) || (max !== undefined && num > max));

  return (
    <div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          min={min}
          max={max}
          className={`w-40 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${
            outOfRange ? "border-red-400 focus:ring-red-300" : "border-gray-200 focus:ring-blue-300"
          }`}
        />
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </div>
      {min !== undefined && max !== undefined && (
        <p className="text-xs text-gray-400 mt-1">Допустимо: {min} – {max}</p>
      )}
      {outOfRange && (
        <p className="text-xs text-red-500 mt-1">
          Значение должно быть от {min} до {max}
        </p>
      )}
    </div>
  );
}

function FormatsControl({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const active = value ? value.split(",").map(s => s.trim()).filter(Boolean) : ALL_FORMATS;

  function toggle(fmt: string) {
    const next = active.includes(fmt) ? active.filter(f => f !== fmt) : [...active, fmt];
    onChange(next.join(","));
  }

  return (
    <div className="flex flex-wrap gap-2">
      {ALL_FORMATS.map(fmt => (
        <label key={fmt} className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={active.includes(fmt)}
            onChange={() => toggle(fmt)}
            className="rounded text-blue-600 focus:ring-blue-300"
          />
          <span className="text-sm font-mono text-gray-700">.{fmt}</span>
        </label>
      ))}
    </div>
  );
}

export function SettingsPage() {
  const { token, user } = useAuth();
  const [settings, setSettings] = useState<Setting[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  const isSuperAdmin = user?.role === "super_admin";

  useEffect(() => {
    if (!isSuperAdmin) return;
    fetch(`${API_BASE}/v1/admin/settings`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data: Setting[]) => {
        setSettings(data);
        const map: Record<string, string> = {};
        data.forEach(s => { map[s.key] = s.value; });
        setEdits(map);
      })
      .catch(e => setError(String(e)));
  }, [token, isSuperAdmin]);

  const handleSave = async () => {
    setSaving(true); setError(null); setSuccess(false);
    const updates = settings.map(s => ({ key: s.key, value: edits[s.key] ?? s.value }));
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/settings`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${resp.status}`);
      }
      const saved: Setting[] = await resp.json();
      setSettings(saved);
      const map: Record<string, string> = {};
      saved.forEach(s => { map[s.key] = s.value; });
      setEdits(map);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  function renderControl(s: Setting) {
    const meta = SETTING_META[s.key];
    const val = edits[s.key] ?? s.value;
    const set = (v: string) => setEdits(prev => ({ ...prev, [s.key]: v }));

    if (!meta) {
      return (
        <input type="text" value={val} onChange={e => set(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-300" />
      );
    }
    switch (meta.control) {
      case "asr_model":   return <AsrModelControl value={val} onChange={set} />;
      case "language":    return <LanguageControl value={val} onChange={set} />;
      case "number":      return <NumberControl value={val} onChange={set} unit={meta.unit} placeholder={meta.placeholder} min={meta.min} max={meta.max} />;
      case "formats":     return <FormatsControl value={val} onChange={set} />;
      default:            return (
        <input type="text" value={val} onChange={e => set(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
      );
    }
  }

  if (!isSuperAdmin) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="bg-red-50 border border-red-200 text-red-700 rounded p-4">
          Доступ разрешён только супер-администраторам.
        </div>
      </div>
    );
  }

  // Сортируем по порядку из SETTING_META, неизвестные — в конец
  const ORDER = Object.keys(SETTING_META);
  const sorted = [...settings].sort((a, b) => {
    const ia = ORDER.indexOf(a.key), ib = ORDER.indexOf(b.key);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  });

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Настройки платформы</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{error}</div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 rounded p-3 mb-4 text-sm">
          Настройки сохранены
        </div>
      )}

      <div className="bg-white rounded-lg shadow divide-y divide-gray-100">
        {sorted.map(s => {
          const meta = SETTING_META[s.key];
          return (
            <div key={s.key} className="p-5">
              <div className="flex items-center mb-3">
                <span className="font-medium text-gray-800 text-sm">
                  {meta?.label ?? s.key}
                </span>
                {meta?.hint && <Tooltip text={meta.hint} />}
              </div>
              {renderControl(s)}
            </div>
          );
        })}

        {sorted.length === 0 && !error && (
          <div className="p-6 text-center text-gray-400 text-sm">Загрузка…</div>
        )}
      </div>

      {sorted.length > 0 && (
        <div className="mt-5 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
          >
            {saving ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      )}
    </div>
  );
}
