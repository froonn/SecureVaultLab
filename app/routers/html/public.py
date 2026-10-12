from fastapi import APIRouter, Form, Request

from ...deps import DbDep, OptionalUser, RequiredUser, get_client_ip
from ...services import records as rec
from ...services.audit import log_action
from ._common import render, require_csrf, redirect, html_redirect_if_anonymous

router = APIRouter(prefix="/public", tags=["html-public"])


@router.get("")
def list_view(request: Request, db: DbDep, user: OptionalUser, q: str | None = None):
    sess = request.state.session
    items = rec.list_public(db, q=q)
    return render(request, "public/list.html", sess=sess, user=user, ctx={"items": items, "q": q or ""})


@router.get("/new")
def new_form(request: Request, user: OptionalUser):
    r = html_redirect_if_anonymous(user)
    if r:
        return r
    return render(request, "public/form.html", sess=request.state.session, user=user, ctx={"item": None})


@router.post("/new")
def create_submit(
    request: Request,
    db: DbDep,
    user: RequiredUser,
    title: str = Form(...),
    content: str = Form(...),
    csrf_token: str = Form(...),
):
    sess = request.state.session
    require_csrf(sess, csrf_token)
    try:
        item = rec.create_public(db, user, title=title, content=content)
        log_action(db, actor_id=user.id, action="public.create", target=f"public:{item.id}",
                   ip=get_client_ip(request))
        return redirect(f"/public/{item.id}")
    except rec.RecordError as e:
        return render(request, "public/form.html", sess=sess, user=user,
                      ctx={"item": None, "error": str(e), "title": title, "content": content})


@router.get("/{record_id}")
def view(request: Request, db: DbDep, user: OptionalUser, record_id: int):
    item = rec.get_public(db, record_id)
    if item is None:
        return render(request, "public/view.html", sess=request.state.session, user=user,
                      ctx={"item": None}, status_code=404)
    return render(request, "public/view.html", sess=request.state.session, user=user, ctx={"item": item})


@router.get("/{record_id}/edit")
def edit_form(request: Request, db: DbDep, user: OptionalUser, record_id: int):
    r = html_redirect_if_anonymous(user)
    if r:
        return r
    item = rec.get_public(db, record_id)
    if item is None or item.owner_id != user.id:
        return redirect("/public")
    return render(request, "public/form.html", sess=request.state.session, user=user, ctx={"item": item})


@router.post("/{record_id}/edit")
def edit_submit(
    request: Request,
    db: DbDep,
    user: RequiredUser,
    record_id: int,
    title: str = Form(...),
    content: str = Form(...),
    csrf_token: str = Form(...),
):
    sess = request.state.session
    require_csrf(sess, csrf_token)
    try:
        item = rec.update_public(db, user, record_id, title=title, content=content)
        log_action(db, actor_id=user.id, action="public.update", target=f"public:{item.id}",
                   ip=get_client_ip(request))
        return redirect(f"/public/{item.id}")
    except rec.RecordError as e:
        item = rec.get_public(db, record_id)
        return render(request, "public/form.html", sess=sess, user=user,
                      ctx={"item": item, "error": str(e), "title": title, "content": content})


@router.post("/{record_id}/delete")
def delete_submit(
    request: Request,
    db: DbDep,
    user: RequiredUser,
    record_id: int,
    csrf_token: str = Form(...),
):
    sess = request.state.session
    require_csrf(sess, csrf_token)
    try:
        rec.delete_public(db, user, record_id)
        log_action(db, actor_id=user.id, action="public.delete", target=f"public:{record_id}",
                   ip=get_client_ip(request))
    except rec.RecordError as e:
        log_action(db, actor_id=user.id, action="public.delete", target=f"public:{record_id}",
                   result="fail", ip=get_client_ip(request), details=str(e))
    return redirect("/public")