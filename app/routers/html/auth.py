from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from ...db import get_db
from ...deps import DbDep, OptionalUser, get_client_ip
from ...security.sessions import bind_user_and_rotate, revoke_session
from ...services import users as users_service
from ...services.audit import log_action
from ._common import render, require_csrf, redirect

router = APIRouter(prefix="/auth", tags=["html-auth"])


@router.get("/register")
def register_form(request: Request, db: DbDep, user: OptionalUser):
    if user is not None:
        return redirect("/")
    sess = request.state.session
    return render(request, "auth/register.html", sess=sess, user=user)


@router.post("/register")
def register_submit(
    request: Request,
    db: DbDep,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    sess = request.state.session
    require_csrf(sess, csrf_token)

    try:
        u = users_service.register_user(db, username=username, email=email, password=password)
        log_action(db, actor_id=u.id, action="auth.register", target=f"user:{u.id}",
                   ip=get_client_ip(request), user_agent=request.headers.get("user-agent"))
        return redirect("/auth/login")
    except users_service.UserError as e:
        log_action(db, actor_id=None, action="auth.register", result="fail",
                   ip=get_client_ip(request), details=str(e))
        return render(request, "auth/register.html",
                      sess=sess, user=None, ctx={"error": str(e), "username": username, "email": email})


@router.get("/login")
def login_form(request: Request, user: OptionalUser):
    if user is not None:
        return redirect("/")
    sess = request.state.session
    return render(request, "auth/login.html", sess=sess, user=user)


@router.post("/login")
def login_submit(
    request: Request,
    db: DbDep,
    login: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    sess = request.state.session
    require_csrf(sess, csrf_token)

    u = users_service.authenticate(db, login=login, password=password)
    if u is None:
        log_action(db, actor_id=None, action="auth.login", result="fail",
                   ip=get_client_ip(request), details=f"login={login[:64]}")
        return render(request, "auth/login.html",
                      sess=sess, user=None, ctx={"error": "Неверное имя пользователя или пароль", "login": login})

    new_token, new_sess = bind_user_and_rotate(
        db, sess, u,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    log_action(db, actor_id=u.id, action="auth.login", target=f"user:{u.id}",
               ip=get_client_ip(request), user_agent=request.headers.get("user-agent"))

    resp = redirect("/")
    from ...config import get_settings
    settings = get_settings()
    resp.set_cookie(
        key=settings.cookie_name,
        value=new_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )
    return resp


@router.post("/logout")
def logout(request: Request, db: DbDep, csrf_token: str = Form(...)):
    sess = request.state.session
    require_csrf(sess, csrf_token)
    user = getattr(request.state, "user", None)
    if user is not None:
        log_action(db, actor_id=user.id, action="auth.logout", target=f"user:{user.id}",
                   ip=get_client_ip(request))
    from ...config import get_settings
    settings = get_settings()
    revoke_session(db, request.cookies.get(settings.cookie_name))
    resp = redirect("/auth/login")
    resp.delete_cookie(settings.cookie_name, path="/")
    return resp