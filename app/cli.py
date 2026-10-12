import argparse
import sys

from .db import Base, engine, SessionLocal
from . import models  # noqa: F401
from .models import User
from .security.passwords import hash_password
from .services import users as users_service


def create_admin(username: str, email: str, password: str) -> int:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        u = users_service.register_user(db, username=username, email=email, password=password)
        u.role = "admin"
        db.commit()
        print(f"Создан администратор: id={u.id}, username={u.username}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    ca = sub.add_parser("create-admin", help="Создать администратора")
    ca.add_argument("--username", required=True)
    ca.add_argument("--email", required=True)
    ca.add_argument("--password", required=True)

    args = p.parse_args(argv)
    if args.cmd == "create-admin":
        return create_admin(args.username, args.email, args.password)
    return 1


if __name__ == "__main__":
    sys.exit(main())