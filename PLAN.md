# План реализации по ТЗ

Дата: 2026-06-22. Сверено с кодом вручную и проверено вживую (end-to-end на пересобранном образе).

## Критичные баги (найдены при живом тестировании) ✅ ИСПРАВЛЕНЫ 2026-06-22

1. **Диаризация была сломана** — `pyannote.audio` отсутствовал в `requirements.txt`, каждая
   задача падала в `partial`. Добавлен `pyannote.audio==4.0.5` (3.x несовместим с torchaudio 2.11),
   numpy поднят до 2.5.0. Проверено: диаризация выдаёт `SPEAKER_00`, статус `done`.
2. **`/healthz`, `/readyz`** были на `/v1/` — ТЗ требует корень. Health-роутер вынесен из `api_router`.
3. **`GET /v1/jobs/{несуществующий}`** возвращал 200 («queued») на любой id — Celery отдаёт PENDING
   на неизвестные таски. Теперь 404.
4. **FR-6: слова с таймкодами не сохранялись** — ASR их вычислял, но `repository.py` их выбрасывал.
   Теперь пишутся в БД и отдаются в API в формате ТЗ `{"w","start","end","conf"}`.
5. **FR-10: флаг `overlap` не сохранялся** — писался всегда `false`. Исправлено.
6. **Формат транскрипта**: добавлен массив `speakers` на верхний уровень (формат ТЗ:
   `local_label`, `speaker_id`, `display_name`, `match_score`).
7. **`POST /v1/transcriptions*`** отдавал 200 — ТЗ требует 202. Исправлено.

## Критичные баги (предыдущий аудит) ✅ ИСПРАВЛЕНЫ

1. `progress` column — `init_db` теперь делает idempotent ALTER TABLE для новых колонок
2. `dead_letter_task` — зарегистрирован как celery task, signal обновлён
3. `api_key_id` в audit log — `verify_api_key` теперь пишет в `request.state`
4. Full-text search — tsvector колонка + GIN индекс + `plainto_tsquery` вместо `ilike`
5. Rate limit per-key — `key_func` по Bearer токену вместо IP
6. Audio metadata — `language`, `duration_sec`, `sample_rate`, `channels` в ответе

## Уже готово

- Пайплайн: нормализация → VAD → ASR → диаризация → выравнивание → эмбеддинги
- `POST /v1/transcriptions/upload` — multipart, 2 GB лимит, idempotency-key
- `GET /v1/jobs/{job_id}` — статус задачи
- `GET /v1/transcripts/{id}` — JSON + экспорт SRT/VTT/TXT
- `GET /v1/transcripts/{id}/segments` — пагинация, фильтр по спикеру
- `GET /v1/transcripts` — список с пагинацией
- `DELETE /v1/transcripts/{id}` — каскадное удаление (Postgres + MinIO + Qdrant)
- `POST /v1/speakers` — регистрация с голосовым сэмплом
- `GET /v1/speakers` / `/{id}` — реестр
- `PATCH /v1/speakers/{id}` — переименование
- `DELETE /v1/speakers/{id}` — удаление с вектором
- `POST /v1/speakers/{id}/merge` — слияние дублей
- `GET /v1/speakers/{id}/recordings` — записи спикера
- `GET /v1/search?q=...` — semantic/keyword/hybrid через Qdrant
- `/healthz` + `/readyz`
- Webhook: HMAC-SHA256 + 3 ретрая с экспоненциальной задержкой
- Rate limiting: slowapi, 60/minute (конфиг через API_RATE_LIMIT)
- Prometheus `/metrics` + Grafana (профиль `--profile monitoring`)
- nginx reverse proxy на порту 80
- overlap-флаг в сегментах
- Порог идентификации 0.70
- Celery acks_late + reject_on_worker_lost

---

## Приоритет 1 — функциональные дыры MVP ✅ РЕАЛИЗОВАНО 2026-06-22

### 1.1 Статус задачи из Postgres, а не из Celery
- Файл: `api/routes/jobs.py`
- Сейчас: читает `AsyncResult` из Redis — пропадает после `result_expires=3600`
- Нужно: читать из `crud.get_job_by_id`, fallback на Celery если не нашли в БД
- Отдавать поля: `job_id`, `status`, `error_code`, `error_message`, `created_at`, `started_at`, `finished_at`

### 1.2 Прогресс задачи (FR-5)
- ТЗ: `GET /v1/jobs/{id}` должен отдавать прогресс
- Нужно:
  1. Добавить `progress: int` (0–100) в модель `Job` (`database/models.py`)
  2. Вызывать `update_job_status(..., progress=N)` в воркере по этапам:
     - queued → 0, нормализация → 10, VAD → 20, ASR → 50, диаризация → 70, выравнивание → 85, сохранение → 95, done → 100
  3. Отдавать `progress` в ответе `/jobs/{id}`

### 1.3 Частичный результат `partial` (FR-11)
- ТЗ: при падении диаризации сохранить ASR-результат со статусом `partial`
- Файл: `services/pipeline_service.py` + `services/worker_job_service.py`
- Нужно: обернуть диаризацию/идентификацию в try; при падении — сохранить транскрипт без спикеров, выставить `status="partial"` + `error_message`

### 1.4 Autoretry 2× + DLQ (NFR Надёжность)
- Файл: `tasks/audio_tasks.py`
- Нужно: добавить на `process_audio_task`:
  ```python
  autoretry_for=(Exception,), max_retries=2, retry_backoff=True, retry_backoff_max=60
  ```
- DLQ: при исчерпании ретраев — писать в отдельную очередь `dead_letter` или таблицу

### 1.5 Лимит длительности ≤ 4 ч → 413 (FR-3)
- Файл: `api/routes/transcriptions.py` или `services/audio_service.py`
- Нужно: после сохранения во временный файл — `ffprobe` или `wave`/`pydub` для проверки длины; при > 4 ч → 413

### 1.6 Валидация форматов аудио (FR-2)
- Файл: `api/routes/transcriptions.py`
- Поддерживаемые: WAV, MP3, FLAC, OGG/Opus, M4A/AAC, WebM
- Нужно: проверять `file.content_type` и расширение, при неподдерживаемом → 415

---

## Приоритет 2 — приём и реестр ✅ РЕАЛИЗОВАНО 2026-06-22

### 2.1 Загрузка по URL (FR-1)
- ТЗ: «multipart ИЛИ URL (presigned MinIO / HTTP)»
- Нужно: добавить `POST /v1/transcriptions/url` с телом `{"audio_url": "...", ...}`
- Воркер скачивает по HTTP → MinIO → пайплайн

### 2.2 Occurrences в `GET /v1/speakers/{id}` (U3/U4)
- Сейчас: отдаёт только поля спикера
- Нужно: включить список `occurrences` (`transcript_id`, `job_id`, `local_label`, `match_score`)
- Это ключевое для сквозной идентификации

---

## Приоритет 3 — продовая обвязка (Этап 3 ТЗ) ✅ РЕАЛИЗОВАНО 2026-06-22

### 3.1 JSON-логи с job_id (NFR Наблюдаемость)
- Сейчас: `logging.basicConfig` плоским текстом
- Нужно: JSON-форматтер (pythonjsonlogger), добавить `job_id` в контекст

### 3.2 TLS на nginx (NFR Безопасность)
- Сейчас: только `:80`
- Нужно: `:443` + self-signed серт для dev, редирект 80→443

### 3.3 MinIO lifecycle / TTL (NFR Хранение)
- Нужно: настроить lifecycle-политику на бакет при старте (TTL из env, напр. `AUDIO_TTL_DAYS=30`)

### 3.4 Бэкапы по cron (NFR Хранение)
- pg_dump + Qdrant snapshot + MinIO mirror
- Отдельный контейнер под профилем `--profile backup`

### 3.5 Многохостовый compose для воркеров (Масштабирование)
- Отдельный `compose.worker.yml` — только воркер, указывает на внешние Redis/Postgres/MinIO/Qdrant

### 3.6 Аудит-лог доступа (NFR Безопасность)
- Middleware, пишущий в лог: api_key_id, endpoint, ip, timestamp, status_code

---

## Осталось из обязательных требований ТЗ

- **FR-8 / U2: stereo-телефония** («канал = спикер» без диаризационной модели) — НЕ реализовано.
  Единственное незакрытое обязательное FR. Нужно только если в трафике есть стерео-звонки
  (открытый вопрос №2 в ТЗ). Следующий логичный шаг при необходимости.

## Вне скоупа (объективно требует ресурсов заказчика или запрещено ТЗ)

- GPU-образ (CUDA) — требует железа; CPU-образ работает
- Замеры WER/DER/EER (Этап 0) — требует размеченного тест-сета заказчика (≥5 ч аудио)
- LLM / суммаризация — запрещено ТЗ
- Frontend/UI — только API
- Реал-тайм стриминг — отдельное ТЗ

## Эксплуатация (важно помнить)

- Код вшит в образ `asr-app` через `COPY` — тома с кодом НЕТ. Правки `.py` или `requirements.txt`
  требуют `docker compose build` + `docker compose up -d` (просто `restart` берёт старую копию).
- Сборка слоистая: смена requirements/моделей — долго; смена только кода — секунды (кэш).
- Первый admin API-ключ создаётся напрямую в БД (эндпоинт `/v1/api-keys` требует scope `admin`).
