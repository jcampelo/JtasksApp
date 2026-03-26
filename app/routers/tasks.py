import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

PRIORITY_ORDER = ["critica", "urgente", "normal"]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_projects(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    return (client.table("projects").select("*").order("name").execute().data or [])


def _get_tasks(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    return (
        client.table("tasks")
        .select("*, task_updates(*)")
        .neq("status", "discarded")
        .eq("status", "active")
        .order("created_at")
        .execute()
        .data or []
    )


def _get_completed(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    return (
        client.table("tasks")
        .select("*, task_updates(*)")
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .execute()
        .data or []
    )


def _enrich_task(task):
    """Adiciona campos calculados para o template."""
    today = date.today()
    dl = task.get("deadline")
    task["update_count"] = len(task.get("task_updates") or [])
    task["days_badge"] = _days_badge(dl, today)
    task["created_fmt"] = _fmt_date(task.get("created_at"))
    task["completed_fmt"] = _fmt_datetime(task.get("completed_at"))
    return task


def _days_badge(deadline_str, today):
    if not deadline_str:
        return ""
    try:
        dl = date.fromisoformat(deadline_str)
        diff = (dl - today).days
        formatted = dl.strftime("%d/%m/%Y")
        if diff < 0:
            return f'<span class="days-badge overdue">{formatted} ({abs(diff)}d atraso)</span>'
        elif diff == 0:
            return f'<span class="days-badge today">{formatted} (hoje)</span>'
        elif diff <= 3:
            return f'<span class="days-badge today">{formatted} ({diff}d)</span>'
        return f'<span class="days-badge ok">{formatted} ({diff}d)</span>'
    except Exception:
        return ""


def _fmt_date(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return iso_str[:10] if len(iso_str) >= 10 else iso_str


def _fmt_datetime(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_str[:16] if len(iso_str) >= 16 else iso_str


def _task_list_response(request, user, toast=None, status_code=200):
    tasks = [_enrich_task(t) for t in _get_tasks(user)]
    projects = _get_projects(user)
    response = templates.TemplateResponse(
        "partials/tasks/task_list.html",
        {"request": request, "tasks": tasks, "projects": projects},
        status_code=status_code,
    )
    if toast:
        response.headers["HX-Trigger"] = json.dumps({"showToast": toast})
    return response


# ── Rotas ────────────────────────────────────────────────────────────────────

@router.get("/tasks", response_class=HTMLResponse)
async def list_tasks(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    return _task_list_response(request, user)


@router.post("/tasks", response_class=HTMLResponse)
async def add_task(
    request: Request,
    name: str = Form(...),
    project: str = Form(""),
    priority: str = Form("normal"),
    deadline: str = Form(""),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    name = name.strip()
    today_str = date.today().isoformat()

    payload = {
        "name": name,
        "project": project or None,
        "priority": priority,
        "date": today_str,
        "deadline": deadline or None,
        "user_id": user["user_id"],
        "status": "active",
    }
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("tasks").insert(payload).execute()
    except Exception:
        return _task_list_response(request, user, toast="Erro ao criar tarefa.")

    return _task_list_response(request, user, toast="Tarefa adicionada!")


@router.post("/tasks/{task_id}/discard", response_class=HTMLResponse)
async def discard_task(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("tasks").update({"status": "discarded"}).eq("id", task_id).execute()
    except Exception:
        pass
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast":"Tarefa descartada."}'
    return response


@router.get("/tasks/{task_id}/complete-form", response_class=HTMLResponse)
async def complete_form(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = client.table("tasks").select("*").eq("id", task_id).single().execute()
    task = result.data
    return templates.TemplateResponse(
        "partials/modals/complete_modal.html",
        {"request": request, "task": task, "today": date.today().isoformat(), "error": None},
    )


@router.post("/tasks/{task_id}/complete", response_class=HTMLResponse)
async def complete_task(
    task_id: str,
    request: Request,
    completed_date: str = Form(...),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    try:
        completed_dt = datetime.fromisoformat(completed_date).replace(
            hour=12, minute=0, second=0, tzinfo=timezone.utc
        ).isoformat()
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("tasks").update({
            "status": "completed",
            "completed_at": completed_dt,
        }).eq("id", task_id).execute()
    except Exception:
        pass

    # Fecha modal e re-renderiza lista de ativas
    response = HTMLResponse(content="""
      <script>document.getElementById('modal-container').innerHTML='';</script>
    """)
    response.headers["HX-Trigger"] = '{"showToast":"Tarefa concluída! ✅","refreshTasks":"1"}'
    return response


@router.get("/tasks/{task_id}/edit-form", response_class=HTMLResponse)
async def edit_form(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = client.table("tasks").select("*").eq("id", task_id).single().execute()
    task = result.data
    projects = _get_projects(user)
    return templates.TemplateResponse(
        "partials/modals/edit_modal.html",
        {"request": request, "task": task, "projects": projects, "error": None},
    )


@router.post("/tasks/{task_id}/edit", response_class=HTMLResponse)
async def edit_task(
    task_id: str,
    request: Request,
    name: str = Form(...),
    project: str = Form(""),
    priority: str = Form("normal"),
    deadline: str = Form(""),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("tasks").update({
            "name": name.strip(),
            "project": project or None,
            "priority": priority,
            "deadline": deadline or None,
        }).eq("id", task_id).execute()
    except Exception:
        pass

    response = HTMLResponse(content="""
      <script>document.getElementById('modal-container').innerHTML='';</script>
    """)
    response.headers["HX-Trigger"] = '{"showToast":"Tarefa atualizada!","refreshTasks":"1"}'
    return response


@router.get("/tasks/completed", response_class=HTMLResponse)
async def list_completed(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    tasks = [_enrich_task(t) for t in _get_completed(user)]
    return templates.TemplateResponse(
        "partials/tasks/task_list_completed.html",
        {"request": request, "tasks": tasks},
    )


# ── Updates ──────────────────────────────────────────────────────────────────

@router.get("/tasks/{task_id}/updates", response_class=HTMLResponse)
async def get_updates(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    task_res = client.table("tasks").select("*").eq("id", task_id).single().execute()
    updates_res = (
        client.table("task_updates")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .execute()
    )
    task = task_res.data
    updates = updates_res.data or []
    for u in updates:
        u["created_fmt"] = _fmt_datetime(u.get("created_at"))
    return templates.TemplateResponse(
        "partials/modals/updates_modal.html",
        {"request": request, "task": task, "updates": updates},
    )


@router.post("/tasks/{task_id}/updates", response_class=HTMLResponse)
async def add_update(
    task_id: str,
    request: Request,
    text: str = Form(...),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("task_updates").insert({
        "task_id": task_id,
        "user_id": user["user_id"],
        "text": text.strip(),
    }).execute()
    updates_res = (
        client.table("task_updates")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .execute()
    )
    updates = updates_res.data or []
    for u in updates:
        u["created_fmt"] = _fmt_datetime(u.get("created_at"))
    response = templates.TemplateResponse(
        "partials/modals/updates_list.html",
        {"request": request, "task_id": task_id, "updates": updates},
    )
    response.headers["HX-Trigger"] = '{"showToast":"Nota adicionada!"}'
    return response


@router.delete("/tasks/{task_id}/updates/{update_id}", response_class=HTMLResponse)
async def delete_update(
    task_id: str,
    update_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("task_updates").delete().eq("id", update_id).execute()
    updates_res = (
        client.table("task_updates")
        .select("*")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .execute()
    )
    updates = updates_res.data or []
    for u in updates:
        u["created_fmt"] = _fmt_datetime(u.get("created_at"))
    return templates.TemplateResponse(
        "partials/modals/updates_list.html",
        {"request": request, "task_id": task_id, "updates": updates},
    )
