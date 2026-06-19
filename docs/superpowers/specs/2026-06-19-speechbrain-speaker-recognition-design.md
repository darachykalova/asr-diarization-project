# Дизайн: SpeechBrain ECAPA-TDNN + регистрация известных голосов

**Дата:** 2026-06-19
**Статус:** approved
**ТЗ:** §3.2, §3.3, U3, U4, FR-9, FR-12, FR-13

---

## 1. Цель

Заменить FFT-спектральный алгоритм извлечения голосовых эмбеддингов на нейросетевую модель SpeechBrain ECAPA-TDNN. Добавить endpoint для регистрации известных голосов с именем (U4). Результат: стабильная кросс-записная идентификация спикеров с EER ≤ 5% (цель ТЗ §4).

---

## 2. Архитектура

Изменения затрагивают только слой `services/` и `api/routes/`. Пайплайн обработки аудио (`pipeline_service.py`, `worker_job_service.py`, `audio_tasks.py`) не меняется.

```
audio file
    │
    ▼
VoiceEmbeddingService          ← ECAPA-TDNN (SpeechBrain), 192-dim
    │ extract_embedding(wav)
    ▼
SpeakerIdentificationService   ← Qdrant cosine, threshold из .env
    │ find_speaker / save_embedding
    ▼
Postgres: speakers (kind=registered|anonymous)
```

---

## 3. Компоненты

### 3.1 VoiceEmbeddingService

**Файл:** `services/voice_embedding_service.py`

- Модель: `speechbrain/spkrec-ecapa-voxceleb`
- Кеш модели: `/app/models/spkrec-ecapa-voxceleb` (Docker volume `models_cache`)
- Инициализация: модель загружается один раз при создании экземпляра, хранится как атрибут
- Устройство: CPU (GPU-поддержка через `run_opts={"device": "cuda"}` при наличии)

`extract_embedding(audio_path: str) -> list[float] | None`:
1. Загрузить WAV через torchaudio
2. Ресемплировать до 16000 Hz если нужно
3. Конвертировать в моно если multichannel
4. Прогнать через `classifier.encode_batch(signal)` → тензор `[1, 1, 192]`
5. Нормализовать L2, вернуть `list[float]` длиной 192

При ошибке — логировать и вернуть `None` (поведение как сейчас).

`VECTOR_SIZE = 192`

### 3.2 SpeakerIdentificationService

**Файл:** `services/speaker_identification_service.py`

- `VECTOR_SIZE = 192`
- `MATCH_THRESHOLD = float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.80"))`
- `_ensure_collection()`: если коллекция существует и её `vector_size != VECTOR_SIZE` — удалить и создать заново (миграция с 512-dim)

### 3.3 Модель данных — поле `kind`

**Файл:** `database/models.py`

Добавить колонку в таблицу `speakers`:
```python
kind: Mapped[str] = mapped_column(String, nullable=False, default="anonymous")
```

Значения: `"registered"` (зарегистрирован вручную) | `"anonymous"` (создан автоматически).

Миграция Alembic: `ADD COLUMN kind VARCHAR NOT NULL DEFAULT 'anonymous'`.

`crud.create_anonymous_speaker` → передаёт `kind="anonymous"`.
`crud.create_speaker` → передаёт `kind="registered"`.

### 3.4 Endpoint регистрации голоса

**Файл:** `api/routes/speakers.py`

`POST /v1/speakers` обновляется до `multipart/form-data`:

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `name` | string | да | Отображаемое имя |
| `phone` | string | нет | Телефон (как сейчас) |
| `audio` | file | нет | Аудио-сэмпл ≥ 10 с чистой речи |

Логика при наличии `audio`:
1. Сохранить во временный файл
2. `normalize_audio()` → 16kHz mono WAV
3. `VoiceEmbeddingService().extract_embedding(wav_path)`
4. Если эмбеддинг получен → `SpeakerIdentificationService().save_embedding(speaker_id, embedding)`
5. Удалить временные файлы

Если `audio` не передан — создать спикера без голосового вектора (поведение как сейчас).

Ошибки:
- Аудио < 10 с → `400 Bad Request: audio too short, minimum 10 seconds`
- Эмбеддинг не извлечён → `422 Unprocessable Entity: failed to extract voice embedding`

---

## 4. Docker

**`docker-compose.yml`:**
- Добавить volume `models_cache:/app/models` для сервисов `api` и `worker`
- Добавить `models_cache:` в секцию `volumes:`

**`.env`:**
```
SPEAKER_MATCH_THRESHOLD=0.80
```

**`requirements.txt`:**
```
speechbrain
```

---

## 5. Сброс данных

Существующие данные в Qdrant (512-dim) и Postgres (speakers) — тестовые, сбрасываются. `_ensure_collection` автоматически пересоздаёт коллекцию при несоответствии размера вектора.

---

## 6. Затронутые файлы

| Файл | Тип изменения |
|------|--------------|
| `requirements.txt` | + speechbrain |
| `services/voice_embedding_service.py` | полная замена |
| `services/speaker_identification_service.py` | VECTOR_SIZE, threshold, _ensure_collection |
| `database/models.py` | + kind колонка |
| `database/crud.py` | kind в create_* методах |
| `api/routes/speakers.py` | multipart POST |
| `.env` | + SPEAKER_MATCH_THRESHOLD |
| `docker-compose.yml` | + models_cache volume |
| `alembic/versions/*.py` | миграция kind |

Не меняются: `pipeline_service.py`, `worker_job_service.py`, `audio_tasks.py`, `diarization_service.py`, все остальные routes.
