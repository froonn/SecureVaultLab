from fastapi import APIRouter, Form, Request

from ...deps import AdminUser, DbDep, get_client_ip
from ...services import users as users_service
from ...services.audit import log_action
from ._common import render, require_csrf, redirect

router = APIRouter(prefix="/admin", tags=["html-admin"])


@router.get("/users")
def users_list(request: Request, db: DbDep, admin: AdminUser, q: str | None = None):
    items = users_service.list_users(db, q=q)
    return render(request, "admin/users.html", sess=request.state.session, user=admin,
                  ctx={"items": items, "q": q or ""})


@router.post("/users/{user_id}/toggle")
def toggle_user(
    request: Request,
    db: DbDep,
    admin: AdminUser,
    user_id: int,
    csrf_token: str = Form(...),
):
    sess = request.state.session
    require_csrf(sess, csrf_token)
    target = users_service.get_by_id(db, user_id)
    if target is not None and target.id != admin.id:
        users_service.set_active(db, user_id, not target.is_active)
        log_action(db, actor_id=admin.id, action="admin.user_toggle", target=f"user:{user_id}",
                   ip=get_client_ip(request), details=f"is_active={not target.is_active}")
    return redirect("/admin/users")