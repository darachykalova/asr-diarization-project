import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SESSION_EXPIRED_KEY, useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function LoginPage() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_EXPIRED_KEY)) {
      sessionStorage.removeItem(SESSION_EXPIRED_KEY);
      setSessionExpired(true);
    }
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/v1/admin/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const detail = (data as { detail?: string }).detail;
        // Бэкенд отвечает по-английски ("Invalid credentials") — показываем русский текст
        setError(
          !detail || detail === "Invalid credentials"
            ? "Неверный логин или пароль"
            : detail
        );
        return;
      }

      const { access_token } = (await resp.json()) as { access_token: string };

      const meResp = await fetch(`${API_BASE}/v1/admin/auth/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      const user = await meResp.json();

      setAuth(access_token, user);
      navigate("/audio", { replace: true });
    } catch {
      setError("Ошибка соединения с сервером");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-800">
          Вход в систему
        </h1>

        {sessionExpired && (
          <p role="status" className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded p-3 mb-4 text-sm">
            Сессия истекла — войдите снова.
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-username" className="block text-sm font-medium text-gray-700 mb-1">
              Логин
            </label>
            <input
              id="login-username"
              type="text"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              required
              autoComplete="username"
              className={`w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                error ? "border-red-300" : "border-gray-300"
              }`}
            />
          </div>

          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-gray-700 mb-1">
              Пароль
            </label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyUp={(e) => setCapsLockOn(e.getModifierState("CapsLock"))}
                required
                autoComplete="current-password"
                aria-describedby={capsLockOn ? "capslock-warning" : undefined}
                className={`w-full border rounded-md pl-3 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  error ? "border-red-300" : "border-gray-300"
                }`}
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                    <path d="M2 2l14 14M7.4 7.6a2.2 2.2 0 0 0 3 3M5.2 5.3C3.4 6.4 2 9 2 9s2.5 5 7 5c1.3 0 2.4-.4 3.4-1M9 4c4.5 0 7 5 7 5s-.6 1.2-1.7 2.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                    <path d="M2 9C2 9 4.5 4 9 4s7 5 7 5-2.5 5-7 5-7-5-7-5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
                    <circle cx="9" cy="9" r="2.2" stroke="currentColor" strokeWidth="1.4" />
                  </svg>
                )}
              </button>
            </div>
            {capsLockOn && (
              <p id="capslock-warning" role="status" className="mt-1 text-xs text-amber-700 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" aria-hidden="true" />
                Включён Caps Lock
              </p>
            )}
          </div>

          {error && (
            <p role="alert" aria-live="polite" className="text-red-600 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            aria-busy={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 active:scale-[0.97] transition-[background-color,opacity,transform] motion-reduce:active:scale-100"
          >
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>

        <p className="mt-6 text-xs text-gray-500 text-center">
          Не получается войти? Обратитесь к администратору платформы — он может сбросить пароль.
        </p>
      </div>
    </div>
  );
}
