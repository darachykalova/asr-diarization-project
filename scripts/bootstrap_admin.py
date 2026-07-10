"""Ручное создание супер-админа (используется когда auto-bootstrap через env недоступен)."""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.auth_users import hash_password
from database.crud import create_admin_user, get_admin_user_by_login
from database.session import SessionLocal

_MIN_PASSWORD_LEN = 8


def bootstrap(login: str, password: str, role: str) -> None:
    if len(password) < _MIN_PASSWORD_LEN:
        print(f"Ошибка: пароль должен быть не менее {_MIN_PASSWORD_LEN} символов.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = get_admin_user_by_login(db, login)
        if existing:
            print(f"Пользователь '{login}' уже существует (роль: {existing.role}).")
            print("Для смены роли используйте PATCH /v1/admin/users/{id}.")
            sys.exit(0)

        user = create_admin_user(db, login, hash_password(password), role)
        print()
        print("Пользователь создан:")
        print(f"  ID:    {user.id}")
        print(f"  Логин: {user.login}")
        print(f"  Роль:  {user.role}")
        print()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Создать admin-пользователя вручную"
    )
    parser.add_argument("--login", required=True, help="Логин пользователя")
    parser.add_argument(
        "--password",
        help="Пароль (если не задан — запрашивается интерактивно или из env ADMIN_BOOTSTRAP_PASSWORD)",
    )
    parser.add_argument(
        "--role",
        default="super_admin",
        choices=["super_admin", "moderator"],
        help="Роль (по умолчанию: super_admin)",
    )

    args = parser.parse_args()

    password = (
        args.password
        or os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
        or getpass.getpass("Пароль: ")
    )

    bootstrap(args.login, password, args.role)
