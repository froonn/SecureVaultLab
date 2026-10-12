from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from .config import get_settings
from .db import get_db
from .models import Session as SessionModel, User

settings = get_settings()

DbDep = Annotated[OrmSession, Depends(get_db)]


def get_client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_session(request: Request) -> SessionModel | None:
    return getattr(request.state, "session", None)


def get_current_user(request: Request, db: DbDep) -> User | None:
    u = getattr(request.state, "user", None)
    if u is None:
        return None
    # перечитываем в текущей сессии, чтобы был managed-инстанс
    return db.get(User, u.id)


OptionalUser = Annotated[User | None, Depends(get_current_user)]


def require_user(user: OptionalUser) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_role(*roles: str):
    def _dep(user: Annotated[User, Depends(require_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _dep


RequiredUser = Annotated[User, Depends(require_user)]
AdminUser = Annotated[User, Depends(require_role("admin"))]