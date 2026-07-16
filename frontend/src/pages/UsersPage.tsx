import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface AdminUser {
  id: number;
  login: string;
  role: string;
  is_blocked: boolean;
  created_at: string;
}

const ROLE_LABEL: Record<string, string> = {
  moderator: "Модератор",
  super_admin: "Супер-Админ",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function UsersPage() {
  const { token, user: me } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [patchingIds, setPatchingIds] = useState<Set<number>>(new Set());

  // Форма создания
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"moderator" | "super_admin">("moderator");
  const [creating, setCreating] = useState(false);
  const loginInputRef = useRef<HTMLInputElement>(null);

  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    message: string;
    confirmLabel: string;
    danger: boolean;
    onConfirm: () => void;
  } | null>(null);

  function errMessage(e: unknown): string {
    return e instanceof Error ? e.message : String(e);
  }

  async function load() {
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setUsers(await resp.json());
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setInitialLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null); setNotice(null);
    const createdLogin = login;
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/users`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ login, password, role }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      setLogin(""); setPassword(""); setRole("moderator");
      setNotice(`Пользователь «${createdLogin}» создан`);
      setTimeout(() => setNotice(null), 4000);
      loginInputRef.current?.focus();
      await load();
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setCreating(false);
    }
  }

  async function patchUser(id: number, patch: Partial<{ role: string; is_blocked: boolean }>) {
    setError(null);
    setPatchingIds(prev => new Set(prev).add(id));
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/users/${id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      await load();
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setPatchingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  function askBlockConfirm(u: AdminUser) {
    setConfirmAction({
      title: u.is_blocked ? "Разблокировать пользователя?" : "Заблокировать пользователя?",
      message: u.is_blocked
        ? `${u.login} снова сможет войти в систему.`
        : `${u.login} больше не сможет войти в систему.`,
      confirmLabel: u.is_blocked ? "Разблокировать" : "Заблокировать",
      danger: !u.is_blocked,
      onConfirm: () => {
        patchUser(u.id, { is_blocked: !u.is_blocked });
        setConfirmAction(null);
      },
    });
  }

  function askRoleConfirm(u: AdminUser, newRole: string) {
    const demotingSuperAdmin = u.role === "super_admin" && newRole !== "super_admin";
    setConfirmAction({
      title: "Сменить роль пользователя?",
      message: `${u.login}: роль изменится на «${ROLE_LABEL[newRole] ?? newRole}».`,
      confirmLabel: "Сменить роль",
      danger: demotingSuperAdmin,
      onConfirm: () => {
        patchUser(u.id, { role: newRole });
        setConfirmAction(null);
      },
    });
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Пользователи</h1>

      {error && (
        <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded p-3 mb-4 text-sm">
          {error}
        </div>
      )}
      <div role="status" aria-live="polite">
        {notice && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded p-3 mb-4 text-sm">
            {notice}
          </div>
        )}
      </div>

      {initialLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          {/* Форма создания */}
          <form onSubmit={handleCreate} autoComplete="off" className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-40">
              <label htmlFor="new-user-login" className="block text-xs font-medium text-gray-600 mb-1">Логин</label>
              <input
                id="new-user-login" name="new-user-login" ref={loginInputRef}
                value={login} onChange={e => setLogin(e.target.value)} required
                autoComplete="off"
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1 min-w-40">
              <label htmlFor="new-user-password" className="block text-xs font-medium text-gray-600 mb-1">Пароль</label>
              <input
                id="new-user-password" name="new-user-password"
                type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8}
                autoComplete="new-password"
                aria-describedby="new-user-password-hint"
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p id="new-user-password-hint" className="text-xs text-gray-500 mt-1">Минимум 8 символов</p>
            </div>
            <div className="min-w-36">
              <label htmlFor="new-user-role" className="block text-xs font-medium text-gray-600 mb-1">Роль</label>
              <select
                id="new-user-role"
                value={role} onChange={e => setRole(e.target.value as "moderator" | "super_admin")}
                className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="moderator">Модератор</option>
                <option value="super_admin">Супер-Админ</option>
              </select>
            </div>
            <button
              type="submit" disabled={creating}
              className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50 active:scale-[0.97] transition-[background-color,opacity,transform] motion-reduce:active:scale-100"
            >
              {creating ? "Создаётся…" : "Создать"}
            </button>
          </form>

          {/* Таблица */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Логин</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Роль</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Статус</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Создан</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-gray-400">
                      Пользователей пока нет — создайте первого через форму выше.
                    </td>
                  </tr>
                ) : users.map(u => {
                  const isSelf = u.login === me?.login;
                  const busy = patchingIds.has(u.id);
                  return (
                    <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium">
                        {u.login}
                        {isSelf && <span className="ml-1.5 text-xs text-gray-500">(вы)</span>}
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={u.role}
                          onChange={e => askRoleConfirm(u, e.target.value)}
                          disabled={isSelf || busy}
                          aria-label={`Роль пользователя ${u.login}`}
                          title={isSelf ? "Свою роль изменить нельзя" : undefined}
                          className="border border-gray-300 rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                        >
                          <option value="moderator">Модератор</option>
                          <option value="super_admin">Супер-Админ</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          u.is_blocked ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                        }`}>
                          {u.is_blocked ? "Заблокирован" : "Активен"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{fmtDate(u.created_at)}</td>
                      <td className="px-4 py-3">
                        {isSelf ? (
                          <span className="text-xs text-gray-400" title="Себя заблокировать нельзя">—</span>
                        ) : (
                          <button
                            onClick={() => askBlockConfirm(u)}
                            disabled={busy}
                            aria-label={`${u.is_blocked ? "Разблокировать" : "Заблокировать"} пользователя ${u.login}`}
                            className={`text-xs px-2 py-1 rounded transition-colors disabled:opacity-50 ${
                              u.is_blocked
                                ? "bg-green-50 text-green-700 hover:bg-green-100"
                                : "bg-red-50 text-red-700 hover:bg-red-100"
                            }`}
                          >
                            {busy ? "…" : u.is_blocked ? "Разблокировать" : "Заблокировать"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction?.title ?? ""}
        message={confirmAction?.message ?? ""}
        confirmLabel={confirmAction?.confirmLabel}
        danger={confirmAction?.danger}
        onConfirm={() => confirmAction?.onConfirm()}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}
