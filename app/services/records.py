from sqlalchemy import select, or_
from sqlalchemy.orm import Session as OrmSession

from ..models import PublicRecord, ConfidentialRecord, User
from ..security.crypto import encrypt_text, decrypt_text


class RecordError(Exception):
    pass


def _validate_title(title: str) -> None:
    if not title or len(title) < 1 or len(title) > 200:
        raise RecordError("Заголовок: 1–200 символов")


def _validate_content(content: str, max_len: int = 20_000) -> None:
    if content is None:
        raise RecordError("Содержимое не может быть пустым")
    if len(content) > max_len:
        raise RecordError(f"Содержимое: не более {max_len} символов")


# ---------- Public ----------

def create_public(db: OrmSession, owner: User, *, title: str, content: str) -> PublicRecord:
    _validate_title(title)
    _validate_content(content)
    r = PublicRecord(owner_id=owner.id, title=title, content=content)
    db.add(r); db.commit(); db.refresh(r)
    return r


def get_public(db: OrmSession, record_id: int) -> PublicRecord | None:
    return db.get(PublicRecord, record_id)


def list_public(db: OrmSession, *, q: str | None = None, owner_id: int | None = None, limit: int = 200) -> list[PublicRecord]:
    stmt = select(PublicRecord).order_by(PublicRecord.created_at.desc()).limit(limit)
    if owner_id is not None:
        stmt = stmt.where(PublicRecord.owner_id == owner_id)
    if q:
        like = f"%{q}%"
        stmt = select(PublicRecord).where(
            or_(PublicRecord.title.like(like), PublicRecord.content.like(like))
        ).order_by(PublicRecord.created_at.desc()).limit(limit)
        if owner_id is not None:
            stmt = stmt.where(PublicRecord.owner_id == owner_id)
    return list(db.execute(stmt).scalars())


def update_public(db: OrmSession, owner: User, record_id: int, *, title: str, content: str) -> PublicRecord:
    r = db.get(PublicRecord, record_id)
    if r is None:
        raise RecordError("Запись не найдена")
    if r.owner_id != owner.id:
        raise RecordError("Нет прав на изменение записи")
    _validate_title(title)
    _validate_content(content)
    r.title = title
    r.content = content
    db.commit(); db.refresh(r)
    return r


def delete_public(db: OrmSession, owner: User, record_id: int) -> None:
    r = db.get(PublicRecord, record_id)
    if r is None:
        raise RecordError("Запись не найдена")
    if r.owner_id != owner.id:
        raise RecordError("Нет прав на удаление записи")
    db.delete(r); db.commit()


# ---------- Confidential ----------

def create_confidential(db: OrmSession, owner: User, *, title: str, content: str) -> ConfidentialRecord:
    _validate_title(title)
    _validate_content(content)
    r = ConfidentialRecord(
        owner_id=owner.id,
        title=title,
        content_encrypted=encrypt_text(content),
    )
    db.add(r); db.commit(); db.refresh(r)
    return r


def get_confidential(db: OrmSession, owner: User, record_id: int) -> ConfidentialRecord:
    r = db.get(ConfidentialRecord, record_id)
    if r is None:
        raise RecordError("Запись не найдена")
    if r.owner_id != owner.id:
        raise RecordError("Нет прав на просмотр записи")
    return r


def list_confidential(db: OrmSession, owner: User, *, q: str | None = None, limit: int = 200) -> list[ConfidentialRecord]:
    stmt = select(ConfidentialRecord).where(ConfidentialRecord.owner_id == owner.id)
    if q:
        stmt = stmt.where(ConfidentialRecord.title.like(f"%{q}%"))
    stmt = stmt.order_by(ConfidentialRecord.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def decrypt_confidential(record: ConfidentialRecord) -> str:
    return decrypt_text(record.content_encrypted)


def update_confidential(db: OrmSession, owner: User, record_id: int, *, title: str, content: str) -> ConfidentialRecord:
    r = db.get(ConfidentialRecord, record_id)
    if r is None:
        raise RecordError("Запись не найдена")
    if r.owner_id != owner.id:
        raise RecordError("Нет прав на изменение записи")
    _validate_title(title)
    _validate_content(content)
    r.title = title
    r.content_encrypted = encrypt_text(content)
    db.commit(); db.refresh(r)
    return r


def delete_confidential(db: OrmSession, owner: User, record_id: int) -> None:
    r = db.get(ConfidentialRecord, record_id)
    if r is None:
        raise RecordError("Запись не найдена")
    if r.owner_id != owner.id:
        raise RecordError("Нет прав на удаление записи")
    db.delete(r); db.commit()