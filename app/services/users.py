import re
from sqlalchemy import select, or_
from sqlalchemy.orm import Session as OrmSession

from ..models import User
from ..security.passwords import hash_password, verify_password, needs_rehash

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LEN = 10


class UserError(Exception):
    pass


def _validate_username(username: str) -> None:
    if not USERNAME_RE.match(username or ""):
        raise UserError("Имя пользователя: 3–32 символа, только A–Z, a–z, 0–9, '_', '.', '-'")


def _validate_email(email: str) -> None:
    if not EMAIL_RE.match(email or "") or len(email) > 255:
        raise UserError("Некорректный email")


def _validate_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LEN:
        raise UserError(f"Пароль должен содержать минимум {MIN_PASSWORD_LEN} символов")
    if not any(c.isalpha() for c in password):
        raise UserError("Пароль должен содержать хотя бы одну букву")
    if not any(c.isdigit() for c in password):
        raise UserError("Пароль должен содержать хотя бы одну цифру")


def register_user(db: OrmSession, *, username: str, email: str, password: str) -> User:
    _validate_username(username)
    _validate_email(email)
    _validate_password(password)

    existing = db.execute(
        select(User).where(or_(User.username == username, User.email == email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise UserError("Пользователь с таким именем или email уже существует")

    user = User(
        username=username,
        email=email.lower(),
        password_hash=hash_password(password),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: OrmSession, *, login: str, password: str) -> User | None:
    user = db.execute(
        select(User).where(or_(User.username == login, User.email == login.lower()))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        # всё равно считаем хэш, чтобы выровнять время — минимальная защита от user enumeration
        hash_password(password)
        return None
    if not verify_password(password, user.password_hash):
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user


def get_by_id(db: OrmSession, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: OrmSession, *, q: str | None = None, limit: int = 200) -> list[User]:
    stmt = select(User).order_by(User.id.asc()).limit(limit)
    if q:
        like = f"%{q}%"
        stmt = select(User).where(
            or_(User.username.like(like), User.email.like(like))
        ).order_by(User.id.asc()).limit(limit)
    return list(db.execute(stmt).scalars())


def set_active(db: OrmSession, user_id: int, active: bool) -> User | None:
    user = db.get(User, user_id)
    if user is None:
        return None
    user.is_active = active
    db.commit()
    db.refresh(user)
    return user


def change_password(db: OrmSession, user: User, *, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise UserError("Неверный текущий пароль")
    _validate_password(new_password)
    user.password_hash = hash_password(new_password)
    db.commit()