import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { type Role, useAuth } from "../auth/AuthContext";

interface NavItem {
  path: string;
  label: string;
  roles: Role[];
}

function NavDropdown({
  management, currentPath, onNavigate,
}: {
  management: NavItem[];
  currentPath: string;
  onNavigate: () => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      role="menu"
      className={`absolute left-0 top-full mt-2 bg-gray-800 border border-gray-700 rounded shadow-lg py-1 min-w-40 z-50 origin-top-left transition-[opacity,transform] duration-150 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:scale-100 ${
        visible ? "opacity-100 scale-100" : "opacity-0 scale-95"
      }`}
    >
      {management.map((item) => (
        <Link
          key={item.path}
          to={item.path}
          role="menuitem"
          onClick={onNavigate}
          className={`block px-4 py-2 text-sm transition-colors ${
            currentPath.startsWith(item.path)
              ? "text-white bg-gray-700"
              : "text-gray-300 hover:bg-gray-700 hover:text-white"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
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
  const [mobileOpen, setMobileOpen] = useState(false);
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

  // Закрыть открытые меню при переходе на другую страницу
  useEffect(() => {
    setMenuOpen(false);
    setMobileOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  if (!user) return null;

  const primary = PRIMARY_ITEMS.filter((item) => item.roles.includes(user.role));
  const management = MANAGEMENT_ITEMS.filter((item) => item.roles.includes(user.role));
  const managementActive = management.some((item) => location.pathname.startsWith(item.path));

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  function handleMenuKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") setMenuOpen(false);
  }

  return (
    <nav className="bg-gray-800 text-white px-4 sm:px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/audio" className="font-bold text-lg tracking-tight hover:text-gray-300 transition-colors">Аудио-Админка</Link>

          {/* Десктопная навигация */}
          <div className="hidden md:flex items-center gap-6">
            {primary.map((item) => {
              const active = location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`text-sm py-2 transition-colors ${
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
                  onKeyDown={handleMenuKeyDown}
                  aria-expanded={menuOpen}
                  aria-haspopup="menu"
                  className={`text-sm py-2 flex items-center gap-1 active:scale-[0.97] transition-[color,transform] motion-reduce:active:scale-100 ${
                    managementActive
                      ? "text-white underline underline-offset-4"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  Управление{" "}
                  <span className={`text-xs transition-transform duration-150 ease-out ${menuOpen ? "rotate-180" : ""}`}>▾</span>
                </button>
                {menuOpen && (
                  <NavDropdown
                    management={management}
                    currentPath={location.pathname}
                    onNavigate={() => setMenuOpen(false)}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        <div className="hidden md:flex items-center gap-4">
          <span className="text-sm text-gray-400">
            {user.login}{" "}
            <span className="text-gray-400">({ROLE_LABEL[user.role]})</span>
          </span>

          <button
            onClick={handleLogout}
            className="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded active:scale-[0.97] transition-[background-color,transform] motion-reduce:active:scale-100"
          >
            Выйти
          </button>
        </div>

        {/* Кнопка мобильного меню */}
        <button
          onClick={() => setMobileOpen((o) => !o)}
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? "Закрыть меню" : "Открыть меню"}
          className="md:hidden p-2 -mr-2 rounded hover:bg-gray-700 active:scale-[0.97] transition-[background-color,transform] motion-reduce:active:scale-100"
        >
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
            {mobileOpen ? (
              <path d="M5 5L17 17M17 5L5 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            ) : (
              <path d="M3 6h16M3 11h16M3 16h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </div>

      {/* Мобильное меню */}
      {mobileOpen && (
        <div className="md:hidden mt-3 pt-3 pb-1 border-t border-gray-700 flex flex-col gap-1">
          {primary.map((item) => {
            const active = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`px-2 py-2.5 rounded text-sm transition-colors ${
                  active ? "text-white bg-gray-700" : "text-gray-300 hover:bg-gray-700 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            );
          })}

          {management.length > 0 && (
            <div className="mt-1 pt-1 border-t border-gray-700 flex flex-col gap-1">
              {management.map((item) => {
                const active = location.pathname.startsWith(item.path);
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`px-2 py-2.5 rounded text-sm transition-colors ${
                      active ? "text-white bg-gray-700" : "text-gray-300 hover:bg-gray-700 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          )}

          <div className="mt-2 pt-3 border-t border-gray-700 flex items-center justify-between px-2 pb-2">
            <span className="text-sm text-gray-400">
              {user.login} <span className="text-gray-400">({ROLE_LABEL[user.role]})</span>
            </span>
            <button
              onClick={handleLogout}
              className="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded active:scale-[0.97] transition-[background-color,transform] motion-reduce:active:scale-100"
            >
              Выйти
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
