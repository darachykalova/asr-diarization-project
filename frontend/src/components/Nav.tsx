import { Link, useLocation, useNavigate } from "react-router-dom";
import { type Role, useAuth } from "../auth/AuthContext";

interface NavItem {
  path: string;
  label: string;
  roles: Role[];
}

const NAV_ITEMS: NavItem[] = [
  { path: "/upload",    label: "Загрузить",      roles: ["moderator", "super_admin"] },
  { path: "/audio",     label: "Аудиозаписи",   roles: ["moderator", "super_admin"] },
  { path: "/calls",     label: "Звонки",         roles: ["moderator", "super_admin"] },
  { path: "/analytics", label: "Аналитика",      roles: ["moderator", "super_admin"] },
  { path: "/users",     label: "Пользователи",   roles: ["super_admin"] },
  { path: "/audit-log", label: "Журнал аудита",  roles: ["super_admin"] },
  { path: "/settings",  label: "Настройки",      roles: ["super_admin"] },
  { path: "/simulator", label: "Симулятор",      roles: ["super_admin"] },
];

const ROLE_LABEL: Record<Role, string> = {
  moderator:   "Модератор",
  super_admin: "Супер-Админ",
};

export function Nav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (!user) return null;

  const visible = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <nav className="bg-gray-800 text-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/audio" className="font-bold text-lg tracking-tight hover:text-gray-300 transition-colors">Аудио-Админка</Link>

        {visible.map((item) => {
          const active = location.pathname.startsWith(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`text-sm transition-colors ${
                active
                  ? "text-white underline underline-offset-4"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-400">
          {user.login}{" "}
          <span className="text-gray-500">({ROLE_LABEL[user.role]})</span>
        </span>

        <button
          onClick={handleLogout}
          className="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded transition-colors"
        >
          Выйти
        </button>
      </div>
    </nav>
  );
}
