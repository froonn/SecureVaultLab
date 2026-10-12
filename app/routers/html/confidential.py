from fastapi import APIRouter, Form, Request

from ...deps import DbDep, RequiredUser, get_client_ip
from ...services import records as rec
from ...services.audit import log_action
from ._common import render, require_csrf, redirect

router = APIRouter(prefix="/confidential", tags=["html-confidential"])


@router.get("")
def list_view(request: Request, db: DbDep, user: RequiredUser, q: str | None = None):
    items = rec.list_confidential(db, user, q=q)
    return render(request, "confidential/list.html", sess=request.state.session,
                  user=user, ctx={"items": items, "q": q or ""})


@router.get("/new")
def new_form(request: Request, user: RequiredUser):
    return render(request, "confidential/form.html", sess=request.state.session, user=user, ctx={"item": None})


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
        item = rec.create_confidential(db, user, title=title, content=content)
        log_action(db, actor_id=user.id, action="confidential.create", target=f"conf:{item.id}",
                   ip=get_client_ip(request))
        return redirect(f"/confidential/{item.id}")
    except rec.RecordError as e:
        return render(request, "confidential/form.html", sess=sess, user=user,
                      ctx={"item": None, "error": str(e), "title": title, "content": content})


@router.get("/{record_id}")
def view(request: Request, db: DbDep, user: RequiredUser, record_id: int):
    try:
        item = rec.get_confidential(db, user, record_id)
        content = rec.decrypt_confidential(item)
    except rec.RecordError:
        return redirect("/confidential")
    return render(request, "confidential/view.html", sess=request.state.session,
                  user=user, ctx={"item": item, "content": content})


@router.get("/{record_id}/edit")
def edit_form(request: Request, db: DbDep, user: RequiredUser, record_id: int):
    try:
        item = rec.get_confidential(db, user, record_id)
        content = rec.decrypt_confidential(item)
    except rec.RecordError:
        return redirect("/confidential")
    return render(request, "confidential/form.html", sess=request.state.session,
                  user=user, ctx={"item": item, "content": content})


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
        item = rec.update_confidential(db, user, record_id, title=title, content=content)
        log_action(db, actor_id=user.id, action="confidential.update", target=f"conf:{item.id}",
                   ip=get_client_ip(request))
        return redirect(f"/confidential/{item.id}")
    except rec.RecordError as e:
        return render(request, "confidential/form.html", sess=sess, user=user,
                      ctx={"item": None, "error": str(e), "title": title, "content": content})


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
        rec.delete_confidential(db, user, record_id)
        log_action(db, actor_id=user.id, action="confidential.delete", target=f"conf:{record_id}",
                   ip=get_client_ip(request))
    except rec.RecordError as e:
        log_action(db, actor_id=user.id, action="confidential.delete", target=f"conf:{record_id}",
                   result="fail", ip=get_client_ip(request), details=str(e))
    return redirect("/confidential")