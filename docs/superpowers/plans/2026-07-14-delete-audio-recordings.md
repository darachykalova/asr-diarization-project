# Удаление аудиозаписей из админки Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать модераторам и супер-админам удалять аудиозапись (Postgres + MinIO + Qdrant) прямо из веб-админки — из списка и из карточки записи.

**Architecture:** Новый эндпоинт `DELETE /v1/admin/audio/{job_id}` в admin-роутере (JWT-auth) переиспользует уже существующую функцию полного удаления `_delete_transcript_everywhere` из `api/routes/transcripts.py` и пишет событие в журнал аудита. Фронтенд добавляет кнопку «Удалить» + уже существующий `ConfirmDialog` на двух страницах (`AudioListPage`, `AudioDetailPage`).

**Tech Stack:** FastAPI (Python), React + TypeScript + Vite, pytest, Tailwind CSS.

## Global Constraints

- Auth для нового эндпоинта — `Depends(get_current_user)` (JWT), БЕЗ ограничения по роли: moderator и super_admin оба должны иметь доступ.
- Удаление разрешено независимо от статуса записи (`queued`/`processing`/`done`/`failed`) — гонки с активной celery-задачей намеренно не обрабатываются.
- Каждое успешное удаление обязано писать запись в audit log через `crud.create_access_log(db, user_id=..., job_id=..., action="delete")`.
- Не дублировать логику удаления из Postgres/MinIO/Qdrant — переиспользовать `_delete_transcript_everywhere` из `api/routes/transcripts.py`.
- Frontend fetch-вызовы пишутся инлайн в компоненте страницы — в проекте нет общего API-клиента, не создавать новую абстракцию ради одного вызова.
- В проекте нет фронтенд-тестов (`frontend/src/**/*.test.*` не существует) — для фронтенд-тасков вместо автотестов пишем шаги ручной проверки.
- После рабочих изменений — пересборка `frontend`-контейнера обязательна (`docker compose build frontend && docker compose up -d frontend`), т.к. образ печёт код через `COPY` (см. CLAUDE.md, «Pitfalls»).

---

### Task 1: Backend — эндпоинт DELETE `/v1/admin/audio/{job_id}`

**Files:**
- Modify: `api/routes/admin_audio.py` (добавить импорт + новый эндпоинт после `get_audio_item`, строка 120)
- Test: `tests/test_admin_audio_delete.py` (новый файл)

**Interfaces:**
- Consumes: `_delete_transcript_everywhere(job_id: str) -> dict` из `api/routes/transcripts.py` (уже существует, возвращает `{"deleted": bool, "job_id": str, "audio_key": str|None, "minio_deleted": bool, "qdrant_deleted": bool, "postgres_deleted": bool}` при успехе, или `{"deleted": False, "reason": "not_found"}`, если транскрипции нет).
- Consumes: `crud.create_access_log(db, user_id: int, job_id: str, action: str) -> TranscriptAccessLog` (уже существует в `database/crud.py:838`).
- Produces: `DELETE /v1/admin/audio/{job_id}` — 200 с телом `{"message": str, "job_id": str, "audio_key": str|None, "minio_deleted": bool, "qdrant_deleted": bool, "postgres_deleted": bool}`, либо 404 `{"detail": "Запись не найдена"}`, либо 401 без токена. Используется фронтендом в Task 2 и Task 3.

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_admin_audio_delete.py`:

```python
"""
Тесты DELETE /v1/admin/audio/{job_id}.

Гарантии:
- Удаление доступно модератору и super_admin
- 404, если запись не найдена; аудит при 404 не пишется
- При успехе пишется audit log с action="delete"
- Требуется авторизация
"""
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _make_user(role: str = "moderator") -> AdminUser:
    user = AdminUser()
    user.id = 3
    user.login = "testmod"
    user.role = role
    user.is_blocked = False
    user.created_at = datetime(2026, 7, 1)
    return user


def _deleted_result(job_id: str = "job-1") -> dict:
    return {
        "deleted": True,
        "job_id": job_id,
        "audio_key": f"jobs/{job_id}/audio.wav",
        "minio_deleted": True,
        "qdrant_deleted": True,
        "postgres_deleted": True,
    }


def test_delete_audio_returns_summary():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result("job-1")), \
         patch("api.routes.admin_audio.crud.create_access_log"):
        resp = client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-1"
    assert data["postgres_deleted"] is True
    assert data["minio_deleted"] is True
    assert data["qdrant_deleted"] is True


def test_delete_audio_accessible_by_moderator():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="moderator")
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result()), \
         patch("api.routes.admin_audio.crud.create_access_log"):
        resp = client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_delete_audio_accessible_by_super_admin():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="super_admin")
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result()), \
         patch("api.routes.admin_audio.crud.create_access_log"):
        resp = client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_delete_audio_requires_auth():
    resp = client.delete("/v1/admin/audio/job-1")
    assert resp.status_code == 401


def test_delete_audio_404_when_not_found():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch(
        "api.routes.admin_audio._delete_transcript_everywhere",
        return_value={"deleted": False, "reason": "not_found"},
    ), patch("api.routes.admin_audio.crud.create_access_log") as mock_log:
        resp = client.delete("/v1/admin/audio/no-such-job")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 404
    mock_log.assert_not_called()


def test_delete_audio_writes_audit_log():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result("job-1")), \
         patch("api.routes.admin_audio.crud.create_access_log") as mock_log:
        client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)

    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs.get("user_id") == 3
    assert kwargs.get("job_id") == "job-1"
    assert kwargs.get("action") == "delete"
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `python -m pytest tests/test_admin_audio_delete.py -v`
Expected: FAIL — `405 Method Not Allowed` вместо ожидаемых 200/404 (путь `/v1/admin/audio/{job_id}` существует для GET, но DELETE ещё не зарегистрирован), а `test_delete_audio_requires_auth` может тоже не совпасть по статусу.

- [ ] **Step 3: Добавить импорт и эндпоинт в `api/routes/admin_audio.py`**

В начале файла, рядом с остальными импортами (после строки `from api.auth_users import get_current_user`, строка 10), добавить:

```python
from api.routes.transcripts import _delete_transcript_everywhere
```

Сразу после функции `get_audio_item` (заканчивается строкой 120 `return item`), перед `@router.post("/upload", ...)`, вставить:

```python
@router.delete("/{job_id}")
def delete_audio(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = _delete_transcript_everywhere(job_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Запись не найдена")

    crud.create_access_log(
        db, user_id=current_user.id, job_id=result["job_id"], action="delete"
    )

    return {
        "message": f"Аудиозапись {result['job_id']} удалена",
        "job_id": result["job_id"],
        "audio_key": result["audio_key"],
        "minio_deleted": result["minio_deleted"],
        "qdrant_deleted": result["qdrant_deleted"],
        "postgres_deleted": result["postgres_deleted"],
    }
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `python -m pytest tests/test_admin_audio_delete.py -v`
Expected: PASS (6 passed)

Также прогнать существующие тесты аудио, чтобы убедиться, что новый импорт ничего не сломал:

Run: `python -m pytest tests/test_admin_audio.py tests/test_admin_transcript_audit.py -v`
Expected: PASS (все тесты как были)

- [ ] **Step 5: Commit**

```bash
git add api/routes/admin_audio.py tests/test_admin_audio_delete.py
git commit -m "feat(admin): add DELETE /v1/admin/audio/{job_id} endpoint"
```

---

### Task 2: Frontend — кнопка «Удалить» в списке аудиозаписей

**Files:**
- Modify: `frontend/src/pages/AudioListPage.tsx`

**Interfaces:**
- Consumes: `DELETE /v1/admin/audio/{job_id}` из Task 1 — 200 при успехе, JSON `{detail: string}` при ошибке (4xx/5xx).
- Consumes: `ConfirmDialog` из `frontend/src/components/ConfirmDialog.tsx` — props `open`, `title`, `message`, `confirmLabel`, `danger`, `onConfirm`, `onCancel` (уже существует, используется в `UsersPage.tsx`).

- [ ] **Step 1: Импортировать `ConfirmDialog`**

В `frontend/src/pages/AudioListPage.tsx`, после строки 4 (`import { LoadingSpinner } ...`), добавить:

```tsx
import { ConfirmDialog } from "../components/ConfirmDialog";
```

- [ ] **Step 2: Добавить состояние ожидающего подтверждения удаления**

В теле компонента `AudioListPage`, сразу после строки 86 (`const [initialLoading, setInitialLoading] = useState(true);`), добавить:

```tsx
  const [pendingDelete, setPendingDelete] = useState<AudioListItem | null>(null);
```

- [ ] **Step 3: Добавить обработчик удаления**

Сразу после функции `fetchListWith` (после закрывающей `}` на строке 137, перед `useEffect(() => { fetchList(); }, []);` на строке 139), добавить:

```tsx
  async function handleDelete(jobId: string) {
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/audio/${jobId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      setData((d) =>
        d
          ? { ...d, items: d.items.filter((i) => i.job_id !== jobId), total: d.total - 1 }
          : d
      );
    } catch (e) {
      setError(String(e));
    }
  }
```

- [ ] **Step 4: Добавить колонку «Действия» в таблицу**

В заголовке таблицы, после `<SortHeader col="speakers" ... />` (строка 274), добавить:

```tsx
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Действия</th>
```

Изменить `colSpan={5}` на `colSpan={6}` в пустом состоянии (строка 280), т.к. добавилась колонка.

В строке таблицы, после `<td className="px-4 py-3 text-gray-600">{item.speaker_count}</td>` (строка 313), добавить:

```tsx
                          <td className="px-4 py-3">
                            <button
                              onClick={() => setPendingDelete(item)}
                              className="text-red-600 hover:underline text-sm"
                            >
                              Удалить
                            </button>
                          </td>
```

- [ ] **Step 5: Отрендерить `ConfirmDialog`**

Перед закрывающим `</div>` компонента (строка 338, прямо перед `);` на строке 339), добавить:

```tsx
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Удалить аудиозапись?"
        message={
          pendingDelete
            ? `«${pendingDelete.title}» будет удалена без возможности восстановления.`
            : ""
        }
        confirmLabel="Удалить"
        danger
        onConfirm={() => {
          if (pendingDelete) handleDelete(pendingDelete.job_id);
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
```

- [ ] **Step 6: Проверить типы**

Run: `cd frontend && npx tsc --noEmit`
Expected: без ошибок (пустой вывод)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/AudioListPage.tsx
git commit -m "feat(admin): add delete button to audio list rows"
```

---

### Task 3: Frontend — кнопка «Удалить» в карточке записи

**Files:**
- Modify: `frontend/src/pages/AudioDetailPage.tsx`

**Interfaces:**
- Consumes: `DELETE /v1/admin/audio/{job_id}` из Task 1 (тот же контракт, что в Task 2).
- Consumes: `ConfirmDialog` (тот же компонент, что в Task 2).
- Consumes: `useNavigate` из `react-router-dom` (уже в зависимостях проекта — `useParams`/`Link` из того же пакета уже импортированы в этом файле).

- [ ] **Step 1: Добавить импорты**

Заменить строку 1-2:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
```

на:

```tsx
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
```

- [ ] **Step 2: Добавить хук навигации и состояние диалога**

В теле компонента `AudioDetailPage`, после строки 66 (`const { token } = useAuth();`), добавить:

```tsx
  const navigate = useNavigate();
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
```

- [ ] **Step 3: Добавить обработчик удаления**

Сразу после функции `handleReveal` (после закрывающей `}` на строке 109, перед `const speakerColorMap` на строке 111), добавить:

```tsx
  async function handleDelete() {
    if (!jobId) return;
    setItemError(null);
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/audio/${jobId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      navigate("/audio");
    } catch (e) {
      setItemError(String(e));
    }
  }
```

- [ ] **Step 4: Добавить кнопку рядом со статус-бейджем**

Заменить блок строк 136-149:

```tsx
                <div>
                  <h1 className="text-xl font-bold text-gray-800">{item.title}</h1>
                  <p className="text-xs text-gray-400 mt-0.5">{item.job_id}</p>
                </div>
                <span className={`mt-1 inline-block px-2.5 py-1 rounded-full text-xs font-medium ${
                  item.status === "done"       ? "bg-green-100 text-green-700" :
                  item.status === "failed"     ? "bg-red-100 text-red-700" :
                  item.status === "processing" ? "bg-blue-100 text-blue-700" :
                                                 "bg-gray-100 text-gray-600"
                }`}>
                  {STATUS_LABEL[item.status] ?? item.status}
                </span>
```

на:

```tsx
                <div>
                  <h1 className="text-xl font-bold text-gray-800">{item.title}</h1>
                  <p className="text-xs text-gray-400 mt-0.5">{item.job_id}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`mt-1 inline-block px-2.5 py-1 rounded-full text-xs font-medium ${
                    item.status === "done"       ? "bg-green-100 text-green-700" :
                    item.status === "failed"     ? "bg-red-100 text-red-700" :
                    item.status === "processing" ? "bg-blue-100 text-blue-700" :
                                                   "bg-gray-100 text-gray-600"
                  }`}>
                    {STATUS_LABEL[item.status] ?? item.status}
                  </span>
                  <button
                    onClick={() => setConfirmDeleteOpen(true)}
                    className="px-3 py-1.5 rounded text-sm text-red-600 border border-red-200 hover:bg-red-50 transition-colors"
                  >
                    Удалить
                  </button>
                </div>
```

- [ ] **Step 5: Отрендерить `ConfirmDialog`**

Перед закрывающим `</div>` компонента (строка 243, прямо перед `);` на строке 244), добавить:

```tsx
      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Удалить аудиозапись?"
        message="Запись, транскрипция и файл будут удалены без возможности восстановления."
        confirmLabel="Удалить"
        danger
        onConfirm={() => {
          setConfirmDeleteOpen(false);
          handleDelete();
        }}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
```

- [ ] **Step 6: Проверить типы**

Run: `cd frontend && npx tsc --noEmit`
Expected: без ошибок (пустой вывод)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/AudioDetailPage.tsx
git commit -m "feat(admin): add delete button to audio detail page"
```

---

### Task 4: Пересборка и ручная проверка

**Files:** нет изменений кода — только сборка и проверка.

- [ ] **Step 1: Пересобрать и поднять `api` (бэкенд-эндпоинт)**

Run: `docker compose build api && docker compose up -d api`

- [ ] **Step 2: Пересобрать и поднять `frontend`**

Run: `docker compose build frontend && docker compose up -d frontend`

- [ ] **Step 3: Прогнать полный тестовый набор бэкенда**

Run: `python -m pytest tests/`
Expected: все тесты зелёные, включая новые из Task 1.

- [ ] **Step 4: Ручная проверка в браузере**

Открыть `http://localhost:${FRONTEND_PORT:-5173}` (или порт из `docker compose ps frontend`), залогиниться под moderator или super_admin:

1. На странице «Аудиозаписи» — нажать «Удалить» в любой строке → появляется диалог подтверждения с названием файла → «Отмена» ничего не удаляет → «Удалить» убирает строку из таблицы, счётчик «Найдено: N записей» уменьшается.
2. Открыть карточку другой записи (`/audio/{job_id}`) → нажать «Удалить» рядом со статус-бейджем → диалог подтверждения → после подтверждения — переход на `/audio`, удалённой записи в списке больше нет.
3. Проверить, что запись действительно удалена из MinIO/Qdrant/Postgres — повторный `GET /v1/admin/audio/{job_id}` (например, через `curl` с админ-токеном) возвращает 404.
4. Открыть «Журнал аудита» (`/audit-log`) → убедиться, что появилось новое событие с `action: delete` для удалённого `job_id`.
5. Проверить, что удаление доступно и под ролью `moderator`, и под `super_admin` (если есть тестовые учётки обеих ролей).

- [ ] **Step 5: Ничего коммитить не нужно** — этот таск только проверочный. Если найдены баги — завести отдельный fix-таск, не расширять этот план задним числом.

---

## Self-Review Notes

- **Spec coverage:** место кнопок (список + карточка) — Task 2 и 3; права доступа (moderator + super_admin, без ограничения роли) — Task 1 Step 3 (`get_current_user` без `require_role`) и тесты `test_delete_audio_accessible_by_*`; статус записи не блокирует удаление — Task 1 не содержит проверки `status`; переход на `/audio` после удаления из карточки — Task 3 Step 3; аудит-лог — Task 1 Step 3 + тест `test_delete_audio_writes_audit_log`; переиспользование `_delete_transcript_everywhere` вместо дублирования — Task 1 Step 3. Все пункты спеки покрыты.
- **Type consistency:** `AudioListItem` (Task 2) и `_delete_transcript_everywhere` result dict (Task 1) используются с одинаковыми именами полей (`job_id`, `title`) во всех тасках.
