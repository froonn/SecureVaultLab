import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import Session as OrmSession

from ..models import Session as SessionModel, User
from ..config import get_settings

settings = get_settings()
SESSION_TOKEN_BYTES = 32       # 256 бит
CSRF_SECRET_BYTES = 32

def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: OrmSession, user: User, *, ip: str | None, user_agent: str | None) -> tuple[str, SessionModel]:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    sid = _hash_token(token)
    now = datetime.now(timezone.utc)
    sess = SessionModel(
        id=sid,
        user_id=user.id,
        csrf_secret=secrets.token_urlsafe(CSRF_SECRET_BYTES),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return token, sess


def get_session(db: OrmSession, token: str | None) -> SessionModel | None:
    if not token:
        return None
    sid = _hash_token(token)
    sess = db.get(SessionModel, sid)
    if sess is None:
        return None
    if _ensure_utc(sess.expires_at) <= datetime.now(timezone.utc):
        db.delete(sess)
        db.commit()
        return None
    return sess


def revoke_session(db: OrmSession, token: str | None) -> None:
    if not token:
        return
    sid = _hash_token(token)
    db.execute(delete(SessionModel).where(SessionModel.id == sid))
    db.commit()


def revoke_all_user_sessions(db: OrmSession, user_id: int, *, keep_sid: str | None = None) -> None:
    stmt = delete(SessionModel).where(SessionModel.user_id == user_id)
    if keep_sid:
        stmt = stmt.where(SessionModel.id != keep_sid)
    db.execute(stmt)
    db.commit()


def rotate_session(db: OrmSession, old_token: str | None, user: User, *, ip: str | None, user_agent: str | None) -> tuple[str, SessionModel]:
    """Регенерация ID сессии при логине — защита от session fixation."""
    revoke_session(db, old_token)
    return create_session(db, user, ip=ip, user_agent=user_agent)


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

def create_anonymous_session(db: OrmSession, *, ip: str | None, user_agent: str | None) -> tuple[str, SessionModel]:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    sid = _hash_token(token)
    now = datetime.now(timezone.utc)
    sess = SessionModel(
        id=sid,
        user_id=None,
        csrf_secret=secrets.token_urlsafe(CSRF_SECRET_BYTES),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return token, sess


def bind_user_and_rotate(db: OrmSession, old_session: SessionModel, user: User, *, ip: str | None, user_agent: str | None) -> tuple[str, SessionModel]:
    """Логин: удаляем анонимную сессию, создаём аутентифицированную — защита от session fixation."""
    db.delete(old_session)
    db.commit()
    return create_session(db, user, ip=ip, user_agent=user_agent)