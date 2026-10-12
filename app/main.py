from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import PlainTextResponse

from .config import get_settings
from .db import Base, engine, SessionLocal
from . import models  # noqa: F401
from .models import Session as SessionModel, User
from .security.sessions import create_anonymous_session, get_session
from .routers.html import auth as html_auth
from .routers.html import public as html_public
from .routers.html import confidential as html_confidential
from .routers.html import admin as html_admin
from .routers.html._common import render
from .deps import get_client_ip

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Lab 2.1",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.is_dev else None,
    lifespan=lifespan,
)

# Доверяем Host-заголовку только ожидаемым именам
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "app", "testserver", "*.ngrok-free.app", "*"])


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    if request.url.path.startswith("/static"):
        return await call_next(request)

    new_token = None
    with SessionLocal() as db:
        token = request.cookies.get(settings.cookie_name)
        sess = get_session(db, token)
        if sess is None:
            token, sess = create_anonymous_session(
                db,
                ip=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
            new_token = token

        request.state.session = sess
        request.state.user = None
        if sess.user_id:
            u = db.get(User, sess.user_id)
            if u is not None and u.is_active:
                request.state.user = u

    response = await call_next(request)

    if new_token:
        response.set_cookie(
            key=settings.cookie_name,
            value=new_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            max_age=settings.session_ttl_minutes * 60,
            path="/",
        )

    # security headers (дублируем на случай прямого доступа к uvicorn)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


app.include_router(html_auth.router)
app.include_router(html_public.router)
app.include_router(html_confidential.router)
app.include_router(html_admin.router)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return '{"status":"ok"}'


@app.get("/")
def home(request: Request):
    return render(request, "home.html", sess=request.state.session, user=request.state.user)