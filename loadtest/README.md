# Нагрузочное тестирование — инструкция

## Файлы

| Файл | Назначение |
|------|-----------|
| `postman_collection.json` | Коллекция сценариев (все эндпоинты ТЗ) |
| `postman_environment.json` | Переменные окружения (base_url, api_key, done_job_id) |
| `audio_short_15s.mp3` | Короткий клип для теста `POST /v1/transcriptions/upload` |

## Шаг 1. Импорт в Postman

1. Postman → **Import** → выбери оба файла (`postman_collection.json` и `postman_environment.json`).
2. В правом верхнем углу выбери окружение **"ASR Diarization — Local"**.

## Шаг 2. Отключить проверку SSL-сертификата

Settings (шестерёнка) → **General** → **SSL certificate verification** → **OFF**

Без этого все запросы на `https://localhost` (самоподписанный сертификат) дадут ошибку.

## Шаг 3. Обновить `done_job_id` в окружении

Нужен ID любой завершённой задачи из твоей БД. Возьми из ответа на `GET /v1/transcripts`.
В Environments → "ASR Diarization — Local" → значение `done_job_id`.

## Шаг 4. Прикрепить аудиофайл для POST-теста

В коллекции найди запрос **"POST /v1/transcriptions/upload → 202"**:
- Body → form-data → строка `file` → нажми иконку файла → выбери `audio_short_15s.mp3` из этой папки.

## Шаг 5. Запуск нагрузочного теста (Postman Performance)

1. Открой коллекцию → кнопка **Run** (треугольник).
2. Перейди на вкладку **Performance**.
3. Настройки:
   - **Virtual users**: 5 (для начала; потом попробуй 10, 20)
   - **Test duration**: 60 сек
   - **Profile**: Fixed
4. Нажми **Run**.
5. Смотри на графики: **Requests/sec**, **Response time (p95)**, **% Error**.

## Целевые метрики

| Метрика | Цель |
|---------|------|
| Requests/min | ≥ 50 (ожидается 200–500+) |
| % ошибок | 0% |
| p95 latency (GET) | < 500 мс |
| Воркер (RAM) | < 5 ГБ суммарно |

## Шаг 6. Throughput-тест (параллельная обработка)

Отправь несколько задач одновременно и посмотри как очередь разгребается двумя воркерами:

```bash
# Отправить 2 задачи одновременно
curl -sk -X POST https://localhost/v1/transcriptions/upload \
  -H "Authorization: Bearer test-admin-key-123456789" \
  -F "file=@loadtest/audio_short_15s.mp3" &
curl -sk -X POST https://localhost/v1/transcriptions/upload \
  -H "Authorization: Bearer test-admin-key-123456789" \
  -F "file=@loadtest/audio_short_15s.mp3"
# Проверить статусы:
docker logs asr_diarization_project-worker-1 --tail 20
```

Два задания должны обрабатываться ПАРАЛЛЕЛЬНО в ForkPoolWorker-1 и ForkPoolWorker-2.

## Мониторинг во время теста

```bash
# RAM и CPU контейнеров в реальном времени:
docker stats

# Логи воркера (видно какой PID обрабатывает какую задачу):
docker logs -f asr_diarization_project-worker-1

# Метрики Prometheus:
https://localhost/metrics

# Grafana + Prometheus (если включён профиль мониторинга):
docker compose --profile monitoring up -d
# Grafana: http://localhost:3000 (admin/admin)
```
