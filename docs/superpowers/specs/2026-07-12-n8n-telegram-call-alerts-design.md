# Telegram-уведомления о звонках через n8n — дизайн

**Дата:** 2026-07-12
**Статус:** одобрен пользователем (все 4 секции)

## Цель

После завершения каждого звонка через `call-agent` (см. [[2026-07-09-anti-scam-agent-design]])
в Telegram-чат прилетает короткое уведомление с вердиктом и call_id. Доставка — через
локальный n8n (уже поднят в docker-compose, `n8n/`), а не напрямую из Python в Telegram
Bot API, чтобы дальнейшая логика уведомлений (маршрутизация, форматирование, доп. каналы)
жила в визуальном workflow, а не в коде call-agent.

## Ключевые решения

| Вопрос | Решение | Обоснование |
|---|---|---|
| Триггер | Любое завершение звонка (любой verdict: scam / undetermined / took_message) | Пользователь хочет знать про каждый звонок, не только про мошенников |
| Содержимое сообщения | Минимум: verdict + call_id | Осознанный выбор — детали (сценарий, confidence, длительность) при необходимости смотрят в админке |
| Где хранится URL n8n-webhook'а | Новая env-переменная `N8N_CALL_ALERT_WEBHOOK_URL` в `call_agent/config.py` | По образцу существующих (`OLLAMA_URL` и т.д.); настройка через БД — избыточно для одного статичного URL |
| Механизм доставки | Переиспользуем `services/webhook_service.send_webhook()` (HMAC-подпись, retries) | Тот же helper уже используется в `finalize_task` для webhook'ов обычных ASR-джобов — не плодим второй механизм |
| Точка вызова | `call_agent/main.py:_finalize()`, сразу после `crud.finalize_call(...)`, только на успешном пути | В except-фолбэке `_safe_finalize` данных меньше и ситуация уже нештатная — туда не лезем |
| Влияние сбоя на звонок | Best-effort: `try/except` + `logger.warning`, звонок финализируется независимо от результата отправки | Webhook — побочный эффект, не часть критического пути финализации звонка |
| Telegram-бот | Существующий бот/chat_id (`1109993976`), credential пересоздаётся в локальном n8n (тот же токен, новый инстанс) | Бот уже был настроен в облачном n8n на прошлой сессии |

## Архитектура и поток данных

```
call_agent/main.py:_finalize()
    │  (после успешного crud.finalize_call — есть call_id, verdict)
    ▼
services/webhook_service.send_webhook(N8N_CALL_ALERT_WEBHOOK_URL, {"call_id", "verdict"})
    │  HTTP POST по внутренней docker-сети asr-net, HMAC-подпись, до 3 попыток с backoff
    ▼
n8n: Webhook (Production URL, Authentication: None) → Telegram: Send Message
    │  текст строится expression'ом в самой Telegram-ноде по verdict
    ▼
Telegram chat 1109993976:
  "⚠️ Мошенник обнаружен (call_id: ...)"          — если verdict == "scam"
  "Звонок завершён: <verdict> (call_id: ...)"     — иначе
```

## Компоненты

### Python-сторона (call-agent)

- `call_agent/config.py`: новая опциональная переменная `N8N_CALL_ALERT_WEBHOOK_URL`
  (по умолчанию не задана — шаг пропускается, аналогично `webhook_url` в `finalize_task`).
- `call_agent/main.py:_finalize()`: после `crud.finalize_call(...)` — вызов
  `send_webhook(url=..., payload={"call_id": call_id, "verdict": result.verdict})`,
  обёрнутый в `try/except Exception` с `logger.warning` при неудаче.
- Второй вызов `send_webhook` не нужен — `services/webhook_service.py` не меняется.

### n8n-сторона (workflow)

- Один workflow: **Webhook** (POST, свой path-UUID, Authentication: None) →
  **Telegram: Send Message**.
- Chat ID захардкожен в ноде: `1109993976`.
- Текст сообщения — expression прямо в поле Text Telegram-ноды:
  ```
  {{ $json.body.verdict === 'scam' ? '⚠️ Мошенник обнаружен' : 'Звонок завершён: ' + $json.body.verdict }} (call_id: {{ $json.body.call_id }})
  ```
- Credential **Telegram account** создаётся заново в локальном n8n-инстансе (тот же
  токен бота от BotFather, что использовался в облачном n8n на прошлой сессии).
- Workflow должен быть **активирован** (тумблер Active), чтобы работал Production URL,
  а не Test URL (тестовый требует открытого редактора и нажатой кнопки «Слушайте
  тестовое событие» перед каждым вызовом).
- `N8N_CALL_ALERT_WEBHOOK_URL` указывает на Production URL этого webhook по внутреннему
  docker-имени сервиса: `http://n8n:5678/webhook/<uuid>` (call-agent и n8n — в одной
  сети `asr-net`, localhost не подходит между контейнерами).
- Workflow поставляется как JSON-файл для импорта через n8n UI (Import from
  File/Clipboard) — вручную собирать ноды не требуется.

## Обработка ошибок

Если n8n недоступен или webhook вернул 5xx — `send_webhook` делает до 3 попыток с
экспоненциальным backoff, затем логирует ошибку через `logger.error` и возвращает
`False`. Звонок в любом случае финализируется штатно: webhook — best-effort
побочный эффект, не часть критического пути `_finalize`.

## Тестирование

- Юнит-тест на `_finalize`: при заданном `N8N_CALL_ALERT_WEBHOOK_URL` в env —
  `send_webhook` вызывается с ожидаемым payload (мок `send_webhook`); при отсутствии
  переменной — вызова нет.
- Ручная проверка: прогнать звонок через браузерный симулятор call-agent → сообщение
  приходит в Telegram-чат.

## Вне рамок

- Маршрутизация уведомлений на разные chat_id по сценарию/важности — не нужно сейчас.
- HMAC-верификация подписи на стороне n8n (Function-нода) — подпись отправляется, но
  не проверяется; можно добавить позже без изменений в call-agent.
- Настройка URL через админ-панель — статичный env достаточен для одного адресата.
