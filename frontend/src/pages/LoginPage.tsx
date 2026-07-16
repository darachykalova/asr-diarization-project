import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function LoginPage() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuth();
  const navigate = useNavigate();

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
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className={`w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                error ? "border-red-300" : "border-gray-300"
              }`}
            />
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
