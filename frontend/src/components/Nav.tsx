import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { type Role, useAuth } from "../auth/AuthContext";

interface NavItem {
  path: string;
  label: string;
  roles: Role[];
}

const PRIMARY_ITEMS: NavItem[] = [
  { path: "/upload",    label: "Загрузить",    roles: ["moderator", "super_admin"] },
  { path: "/audio",     label: "Аудиозаписи",  roles: ["moderator", "super_admin"] },
  { path: "/calls",     label: "Звонки",       roles: ["moderator", "super_admin"] },
  { path: "/analytics", label: "Аналитика",    roles: ["moderator", "super_admin"] },
];

const MANAGEMENT_ITEMS: NavItem[] = [
  { path: "/users",     label: "Пользователи",  roles: ["super_admin"] },
  { path: "/audit-log", label: "Журнал аудита", roles: ["super_admin"] },
  { path: "/settings",  label: "Настройки",     roles: ["super_admin"] },
  { path: "/simulator", label: "Симулятор",     roles: ["super_admin"] },
];

const ROLE_LABEL: Record<Role, string> = {
  moderator:   "Модератор",
  super_admin: "Супер-Админ",
};

export function Nav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!user) return null;

  const primary = PRIMARY_ITEMS.filter((item) => item.roles.includes(user.role));
  const management = MANAGEMENT_ITEMS.filter((item) => item.roles.includes(user.role));
  const managementActive = management.some((item) => location.pathname.startsWith(item.path));

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <nav className="bg-gray-800 text-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/audio" className="font-bold text-lg tracking-tight hover:text-gray-300 transition-colors">Аудио-Админка</Link>

        {primary.map((item) => {
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

        {management.length > 0 && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className={`text-sm transition-colors flex items-center gap-1 ${
                managementActive
                  ? "text-white underline underline-offset-4"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Управление <span className="text-xs">▾</span>
            </button>
            {menuOpen && (
              <div className="absolute left-0 top-full mt-2 bg-gray-800 border border-gray-700 rounded shadow-lg py-1 min-w-40 z-50">
                {management.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMenuOpen(false)}
                    className={`block px-4 py-2 text-sm transition-colors ${
                      location.pathname.startsWith(item.path)
                        ? "text-white bg-gray-700"
                        : "text-gray-300 hover:bg-gray-700 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
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
