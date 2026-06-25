# План: разбиение пайплайна на Celery-таски + chains

**Цель:** заменить монолитную `process_audio_task` цепочкой отдельных тасков,
соединённых через Celery `chain` / `chord`. Это даёт:

1. **Параллелизм** — ASR (Whisper) и диаризация (pyannote) независимы (обоим нужен
   только нормализованный WAV) → гоняем параллельно через `chord`.
2. **Изоляцию ресурсов** — тяжёлый inference в отдельной очереди, лёгкий I/O (DB,
   Qdrant, webhook) в другой. Воркеры специализируются → меньше памяти на воркер,
   inference можно вынести на GPU-машину.
3. **Гранулярные ретраи** — упал Qdrant-save → ретраим только его, а не Whisper заново.
4. **Наблюдаемость** — пер-степ тайминги, точный прогресс по этапам.

> **Важно про текущее железо:** на 6 CPU + concurrency=2 параллелизм ASR∥diar
> *сам по себе* выигрыша почти не даст (каждой половине достанется ~1.5 ядра).
> Реальный профит — «на перспективу»: GPU-воркер, вторая машина, раздельные пулы.
> Поэтому это рефакторинг архитектуры, а не сиюминутное ускорение.

---

## Принятые решения (развилки)

| Развилка | Выбор по умолчанию | Альтернатива |
|----------|--------------------|--------------|
| Хранилище промежуточных артефактов | **MinIO** (распределённо) | общий volume `./data` (только одна машина) |
| Стратегия миграции | **фича-флаг** `PIPELINE_MODE=chain\|monolith` | полная замена монолита |
| Топология очередей | **раздельные** `inference` / `io` + роутинг | одна очередь `default` |

---

## Целевая структура цепочки

```
normalize_task                         # ffmpeg → 16k mono WAV → MinIO
      │
      ▼
chord(
    group(
        asr_task,                      # Whisper → asr_segments + language + duration
        diarize_task,                  # pyannote → speaker_segments   (ПАРАЛЛЕЛЬНО)
    ),
    merge_align_task                   # callback: получает [asr_result, diar_result]
)                                      #   → assign speakers + alignment
      │
      ▼
embeddings_task                        # SpeechBrain voice embeddings per speaker
      │
      ▼
identify_speakers_task                 # match в Qdrant → speaker_id, occurrences
      │
      ▼
persist_task                          # Postgres transcript+segments, Qdrant text-векторы
      │
      ▼
finalize_task                          # статус job=done, webhook (HMAC)
```

`max_speakers == 1` (одиночный спикер) → `diarize_task` подменяется лёгким
`single_speaker_task` (присваивает SPEAKER_00, без pyannote), но структура chord
сохраняется ради единообразия.

---

## Контракт передачи данных между тасками

Celery сериализует результат таски (JSON) и кладёт в Redis backend. Правила:

- **Большие бинарники (audio, WAV-клипы) НЕ передаём инлайн** — только ключи MinIO.
- **JSON-данные (segments, language, duration) передаём инлайн** — они небольшие,
  Redis это держит.
- Каждая таска принимает и возвращает один `dict` — «контекст джобы».

Формат контекста (растёт по мере прохождения цепочки):

```python
# после normalize_task
{"job_id": "...", "normalized_key": "jobs/{job_id}/audio_16k_mono.wav",
 "params": {"language": ..., "min_speakers": ..., "max_speakers": ...,
            "model_size": "base", "initial_prompt": ..., "webhook_url": ...}}

# asr_task добавляет
{"asr_segments": [...], "language": "ru", "duration_sec": 205.5}

# diarize_task добавляет
{"speaker_segments": [...], "diarization_error": null}

# merge_align_task добавляет
{"aligned_segments": [...], "full_text": "..."}

# embeddings_task добавляет
{"speaker_embeddings": [...]}      # либо ключи клипов в MinIO

# identify_speakers_task добавляет
{"transcript_id": 123, "speaker_map": {"SPEAKER_00": 8, ...}}
```

**Тонкость chord:** callback `merge_align_task` получает СПИСОК результатов группы
`[asr_result, diar_result]`. Нужно смержить два dict-а в один контекст.

---

## Список тасков (новый модуль `tasks/pipeline_tasks.py`)

| Таска | Очередь | Грузит модели | Вход → Выход |
|-------|---------|---------------|--------------|
| `normalize_task` | `io` | — (ffmpeg) | input_key → normalized_key |
| `asr_task` | `inference` | Whisper | normalized_key → asr_segments |
| `diarize_task` | `inference` | pyannote | normalized_key → speaker_segments |
| `single_speaker_task` | `io` | — | → SPEAKER_00 segment |
| `merge_align_task` | `io` | — | [asr, diar] → aligned_segments |
| `embeddings_task` | `inference` | SpeechBrain | normalized_key+segments → embeddings |
| `identify_speakers_task` | `io` | — (Qdrant client) | embeddings → speaker_map, occurrences |
| `persist_task` | `io` | — | контекст → Postgres + Qdrant |
| `finalize_task` | `io` | — | → статус done + webhook |

Каждая таска:
- `bind=True`, свой `autoretry_for` + `max_retries` (гранулярный ретрай),
- идемпотентна (повторный запуск не дублирует данные — важно при ретраях),
- обновляет `jobs.progress` в Postgres (свой диапазон: normalize 0-15, asr 15-45,
  diar 15-45 параллельно, merge 45-60, embeddings 60-75, identify 75-90,
  persist 90-98, finalize 100).

---

## Обработка ошибок и partial-результаты

1. **Per-task retry** — каждая таска ретраит свои транзиентные сбои (как сейчас монолит).
2. **Chain-level error handler** — `link_error` на всю цепочку + `on_chord_error`
   для chord. При финальном провале → DLQ (`dead_letter_task`), статус `failed`.
3. **Partial-логика** — если `diarize_task` упала, но ASR прошёл: вместо падения
   цепочки `diarize_task` возвращает `{"speaker_segments": [], "diarization_error": "..."}`,
   а `finalize_task` ставит статус `partial`. Сохраняем текущее поведение
   `_PartialResultError`, но распределённо.
4. **`task_acks_late=True` + `task_reject_on_worker_lost=True`** — оставляем на всех
   тасках (crash safety при OOM).

---

## Изменения по файлам

### Новые файлы
- **`tasks/pipeline_tasks.py`** — все 9 тасков выше.
- **`services/artifact_store.py`** — helper: upload/download промежуточных артефактов
  в MinIO (ключи вида `jobs/{job_id}/normalized.wav`, `jobs/{job_id}/voice/{label}.wav`),
  опционально локальный кэш.

### Изменяемые файлы
- **`tasks/audio_tasks.py`** — `process_audio_task` остаётся как fallback
  (`PIPELINE_MODE=monolith`); добавить функцию `build_pipeline_chain(...)`, которая
  собирает `chain(normalize | chord(...) | embeddings | identify | persist | finalize)`.
- **`api/routes/transcriptions.py`** — на upload вместо `process_audio_task.delay(...)`
  вызывать диспетчер: если `PIPELINE_MODE=chain` → `build_pipeline_chain().apply_async()`.
- **`celery_app/app.py`** — `task_routes` (роутинг по очередям `inference`/`io`),
  объявить очереди, `task_track_started=True`.
- **`services/pipeline_service.py`** — разнять `_run_pipeline` на отдельные методы
  (normalize/asr/diarize/merge/embeddings), которые таски смогут переиспользовать.
  Логику оставить здесь, таски — тонкие обёртки.
- **`services/worker_job_service.py`** — вынести `_identify_speakers_safely`,
  `_save_*` в отдельные переиспользуемые функции для `identify_speakers_task` /
  `persist_task`.
- **`docker-compose.yml`** — два сервиса-воркера:
  - `worker-io`: `-Q io --concurrency=2` (лёгкий, мало памяти),
  - `worker-inference`: `-Q inference --concurrency=2` (грузит ML-модели);
  позже `worker-inference` переезжает на GPU-машину.
- **`schemas/`** — Pydantic-схема `JobContext` для контракта между тасками
  (валидация dict-а на входе/выходе каждой таски).
- **`.env` / `config`** — `PIPELINE_MODE`, имена очередей.
- **`README.md`** — обновить раздел Architecture (chord-диаграмма) и Performance.

---

## Этапы внедрения (инкрементально, с проверкой на каждом)

**Этап 0 — подготовка.** `artifact_store.py` (MinIO put/get для промежуточных
файлов). Рефакторинг `pipeline_service.py`: публичные методы `normalize()`, `asr()`,
`diarize()`, `merge_align()`, `embeddings()` — БЕЗ изменения поведения монолита.
Проверка: монолитный путь работает как раньше (регресс-тест на 15с аудио).

**Этап 1 — таски-обёртки + последовательный chain (без chord).** Собрать
`chain(normalize | asr | diarize | merge | embeddings | identify | persist | finalize)`
— пока строго последовательно, одна очередь. Цель: убедиться что передача контекста
и ретраи работают. Проверка: результат идентичен монолиту (тот же transcript, speakers).

**Этап 2 — chord (параллель ASR ∥ diarize).** Заменить `asr | diarize` на
`chord(group(asr, diarize), merge)`. Проверка: корректный мерж двух результатов,
тайминг по логам.

**Этап 3 — раздельные очереди + два воркера.** Роутинг `inference`/`io`,
`docker-compose` с `worker-io` и `worker-inference`. Проверка: таски уходят в
правильные очереди (Celery inspect), память воркеров.

**Этап 4 — фича-флаг + диспетчер в API.** `PIPELINE_MODE`. A/B: прогнать стресс-тест
обоими путями, сравнить тайминги. Проверка: переключение без перезапуска кода.

**Этап 5 — partial/DLQ/idempotency.** Перенести partial-логику, chain `link_error`,
проверить идемпотентность ретраев (нет дублей occurrences/speakers). Обновить README.

---

## Риски и тонкие места

1. **Идемпотентность.** Ретрай `identify_speakers_task` не должен плодить дубли
   спикеров/occurrences. Нужны upsert-ы или проверка «уже обработано» по job_id.
2. **chord на Redis backend.** chord требует result backend (есть — Redis db1).
   Убедиться, что `result_expires` достаточно большой (длинные джобы > TTL результата).
3. **Размер контекста в Redis.** `asr_segments` для длинного аудио могут быть
   большими. Если упрёмся — хранить segments в MinIO/Postgres, в контексте только ключ.
4. **Модели грузятся в inference-воркере дважды** (asr_task и diarize_task в одном
   пуле). На современном железе ок (COW prefork), но при разделении пулов память
   считать заново.
5. **Дебаг распределённых цепочек сложнее** монолита — нужен `task_track_started`,
   correlation по `job_id` во всех логах (структурный JSON-лог уже есть).
6. **Откат.** Фича-флаг обязателен на время обкатки — оставляем монолит как fallback.

---

## Что НЕ делаем в этой итерации
- GPU-воркер (только готовим почву: отдельная `inference`-очередь).
- Динамический автоскейлинг воркеров.
- Разбиение самого Whisper/pyannote на чанки аудио (отдельная большая тема).
