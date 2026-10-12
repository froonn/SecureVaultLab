from sqlalchemy.orm import Session as OrmSession

from ..models import AuditLog


def log_action(
    db: OrmSession,
    *,
    actor_id: int | None,
    action: str,
    target: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    result: str = "ok",
    details: str | None = None,
) -> None:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target=(target or "")[:128] or None,
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
        result=result,
        details=details,
    )
    db.add(entry)
    db.commit()