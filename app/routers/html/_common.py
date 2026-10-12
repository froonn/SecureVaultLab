from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ...models import Session as SessionModel
from ...security.csrf import make_csrf_token, validate_csrf_token

templates = Jinja2Templates(directory="app/templates")


def render(
    request: Request,
    name: str,
    *,
    sess: SessionModel,
    user=None,
    ctx: dict | None = None,
    status_code: int = 200,
):
    context = {
        "request": request,
        "user": user,
        "csrf_token": make_csrf_token(sess),
        "app_name": "Lab 2.1",
    }
    if ctx:
        context.update(ctx)
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def require_csrf(sess: SessionModel, form_token: str | None) -> None:
    if not validate_csrf_token(sess, form_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный CSRF-токен")


def redirect(url: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(url, status_code=status_code)


def html_redirect_if_anonymous(user) -> RedirectResponse | None:
    if user is None:
        return redirect("/auth/login")
    return None