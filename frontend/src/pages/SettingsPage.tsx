import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";

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

// Смысловые группы настроек; неизвестные ключи попадают в «Прочее»
const SETTING_GROUPS: { title: string; keys: string[] }[] = [
  { title: "Распознавание", keys: ["default_asr_model", "default_language", "max_speakers"] },
  { title: "Загрузка файлов", keys: ["max_upload_size_mb", "allowed_formats"] },
  { title: "Журнал аудита", keys: ["audit_log_retention_days"] },
];

function SuccessBanner({ show }: { show: boolean }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (!show) { setMounted(false); return; }
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, [show]);

  // Обёртка живёт в DOM постоянно, чтобы скринридер объявил появившийся текст
  return (
    <div role="status" aria-live="polite">
      {show && (
        <div
          className={`bg-green-50 border border-green-200 text-green-700 rounded p-3 mb-4 text-sm transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:translate-y-0 ${
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
          }`}
        >
          Настройки сохранены
        </div>
      )}
    </div>
  );
}

function Tooltip({ id, text }: { id: string; text: string }) {
  const [show, setShow] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!show) { setVisible(false); return; }
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, [show]);

  return (
    <span className="relative inline-block ml-1.5 align-middle">
      <button
        type="button"
        aria-label="Пояснение"
        aria-describedby={show ? id : undefined}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
        onKeyDown={(e) => { if (e.key === "Escape") setShow(false); }}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-200 text-gray-500 text-xs cursor-help hover:bg-blue-100 hover:text-blue-600 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500"
      >?</button>
      {show && (
        <span
          role="tooltip"
          id={id}
          className={`absolute left-6 top-0 z-50 w-72 bg-gray-800 text-white text-xs rounded-lg px-3 py-2 shadow-lg leading-relaxed origin-top-left transition-[opacity,transform] duration-150 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:scale-100 ${
            visible ? "opacity-100 scale-100" : "opacity-0 scale-95"
          }`}
        >
          {text}
        </span>
      )}
    </span>
  );
}

function AsrModelControl({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <select id={id} value={value} onChange={e => onChange(e.target.value)}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
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

// Частые для этой платформы языки — закреплены в начале списка
const PINNED_LANGUAGES = ["ru", "uk", "be", "en"];

function LanguageControl({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  const pinned = PINNED_LANGUAGES
    .map(code => WHISPER_LANGUAGES.find(([c]) => c === code))
    .filter((x): x is [string, string] => Boolean(x));
  const rest = WHISPER_LANGUAGES.filter(([c]) => !PINNED_LANGUAGES.includes(c));

  return (
    <select id={id} value={value} onChange={e => onChange(e.target.value)}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
      <option value="">Автоопределение</option>
      {pinned.map(([code, name]) => (
        <option key={code} value={code}>{name} ({code})</option>
      ))}
      <option value="" disabled>──────────</option>
      {rest.map(([code, name]) => (
        <option key={code} value={code}>{name} ({code})</option>
      ))}
    </select>
  );
}

function NumberControl({ id, value, onChange, unit, placeholder, min, max }: {
  id: string; value: string; onChange: (v: string) => void; unit?: string; placeholder?: string; min?: number; max?: number;
}) {
  const num = value === "" ? null : Number(value);
  const outOfRange = num !== null && ((min !== undefined && num < min) || (max !== undefined && num > max));

  return (
    <div>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="number"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          min={min}
          max={max}
          aria-invalid={outOfRange || undefined}
          aria-describedby={`${id}-range${outOfRange ? ` ${id}-err` : ""}`}
          className={`w-40 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${
            outOfRange ? "border-red-400 focus:ring-red-300" : "border-gray-300 focus:ring-blue-500"
          }`}
        />
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </div>
      {min !== undefined && max !== undefined && (
        <p id={`${id}-range`} className="text-xs text-gray-500 mt-1">Допустимо: {min} – {max}</p>
      )}
      {outOfRange && (
        <p id={`${id}-err`} className="text-xs text-red-500 mt-1">
          Значение должно быть от {min} до {max}
        </p>
      )}
    </div>
  );
}

function FormatsControl({ labelId, value, onChange }: { labelId: string; value: string; onChange: (v: string) => void }) {
  // Пустое значение = «не задано» = разрешены все (контракт API) — показываем это
  // честно, а не молча отмечаем все галочки обратно.
  const active = value ? value.split(",").map(s => s.trim()).filter(Boolean) : [];

  function toggle(fmt: string) {
    const next = active.includes(fmt) ? active.filter(f => f !== fmt) : [...active, fmt];
    onChange(next.join(","));
  }

  return (
    <div role="group" aria-labelledby={labelId}>
      <div className="flex flex-wrap gap-2">
        {ALL_FORMATS.map(fmt => (
          <label key={fmt} className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={active.includes(fmt)}
              onChange={() => toggle(fmt)}
              className="rounded text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-mono text-gray-700">.{fmt}</span>
          </label>
        ))}
      </div>
      {active.length === 0 && (
        <p className="text-xs text-gray-500 mt-2">
          Ни один формат не выбран — значение не задано, разрешены все форматы.
        </p>
      )}
    </div>
  );
}

export function SettingsPage() {
  const { token, user } = useAuth();
  const [settings, setSettings] = useState<Setting[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  const isSuperAdmin = user?.role === "super_admin";

  const dirtyCount = settings.filter(s => (edits[s.key] ?? s.value) !== s.value).length;
  const isDirty = dirtyCount > 0;

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
      .catch(e => setLoadError(String(e)));
  }, [token, isSuperAdmin]);

  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleSave = async () => {
    setSaving(true); setSaveError(null); setSuccess(false);
    const updates = settings.map(s => ({ key: s.key, value: edits[s.key] ?? s.value }));
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/settings`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${resp.status}`);
      }
      const saved: Setting[] = await resp.json();
      setSettings(saved);
      const map: Record<string, string> = {};
      saved.forEach(s => { map[s.key] = s.value; });
      setEdits(map);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setSaveError(
        msg === "Failed to fetch"
          ? "Нет соединения с сервером — настройки не сохранены."
          : `Не удалось сохранить: ${msg}`
      );
    } finally {
      setSaving(false);
    }
  };

  function renderControl(s: Setting) {
    const meta = SETTING_META[s.key];
    const val = edits[s.key] ?? s.value;
    const set = (v: string) => setEdits(prev => ({ ...prev, [s.key]: v }));
    const id = `set-${s.key}`;

    if (!meta) {
      return (
        <input id={id} type="text" value={val} onChange={e => set(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
      );
    }
    switch (meta.control) {
      case "asr_model":   return <AsrModelControl id={id} value={val} onChange={set} />;
      case "language":    return <LanguageControl id={id} value={val} onChange={set} />;
      case "number":      return <NumberControl id={id} value={val} onChange={set} unit={meta.unit} placeholder={meta.placeholder} min={meta.min} max={meta.max} />;
      case "formats":     return <FormatsControl labelId={`${id}-label`} value={val} onChange={set} />;
      default:            return (
        <input id={id} type="text" value={val} onChange={e => set(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      );
    }
  }

  function renderSettingRow(s: Setting) {
    const meta = SETTING_META[s.key];
    const id = `set-${s.key}`;
    const isGroupControl = meta?.control === "formats";
    return (
      <div key={s.key} className="p-5">
        <div className="flex items-center mb-3">
          {isGroupControl ? (
            <span id={`${id}-label`} className="font-medium text-gray-800 text-sm">
              {meta?.label ?? s.key}
            </span>
          ) : (
            <label htmlFor={id} className="font-medium text-gray-800 text-sm">
              {meta?.label ?? s.key}
            </label>
          )}
          {meta?.hint && <Tooltip id={`${id}-hint`} text={meta.hint} />}
        </div>
        {renderControl(s)}
      </div>
    );
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

  const known = new Set(SETTING_GROUPS.flatMap(g => g.keys));
  const groups = SETTING_GROUPS
    .map(g => ({
      title: g.title,
      items: g.keys
        .map(k => settings.find(s => s.key === k))
        .filter((s): s is Setting => Boolean(s)),
    }))
    .filter(g => g.items.length > 0);
  const other = settings.filter(s => !known.has(s.key));
  if (other.length > 0) groups.push({ title: "Прочее", items: other });

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Настройки платформы</h1>

      {loadError && (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">{loadError}</div>
      )}
      <SuccessBanner show={success} />

      {settings.length === 0 && !loadError ? (
        <LoadingSpinner label="Загрузка настроек…" />
      ) : (
        <>
          {groups.map(g => (
            <section key={g.title} className="mb-5">
              <h2 className="text-base font-semibold text-gray-800 mb-2">{g.title}</h2>
              <div className="bg-white rounded-lg shadow divide-y divide-gray-100">
                {g.items.map(renderSettingRow)}
              </div>
            </section>
          ))}

          {settings.length > 0 && (
            <div className="mt-5 flex items-center justify-end gap-4">
              {saveError && (
                <p role="alert" className="text-sm text-red-600">{saveError}</p>
              )}
              {isDirty && !saving && (
                <span className="text-sm text-gray-500">Изменено: {dirtyCount}</span>
              )}
              <button
                onClick={handleSave}
                disabled={saving || !isDirty}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-6 py-2.5 rounded-lg active:scale-[0.97] transition-[background-color,opacity,transform] motion-reduce:active:scale-100"
              >
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
