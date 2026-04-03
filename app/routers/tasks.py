import json
import calendar as cal_mod
from datetime import date, datetime, timezone

from fastapi import APIRouter, Request, Depends, Form, Query
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
    return (
        client.table("projects")
        .select("*")
        .eq("user_id", user["user_id"])
        .order("name")
        .execute()
        .data or []
    )


def _get_tasks(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    return (
        client.table("tasks")
        .select("*, task_updates(*), task_checklist(*)")
        .eq("user_id", user["user_id"])
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
        .eq("user_id", user["user_id"])
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
    checklist = task.get("task_checklist") or []
    task["checklist_total"] = len(checklist)
    task["checklist_done"] = sum(1 for item in checklist if item.get("done"))
    task["days_badge"] = _days_badge(dl, today)
    task["created_fmt"] = _fmt_date(task.get("created_at"))
    task["completed_fmt"] = _fmt_datetime(task.get("completed_at"))
    if dl:
        try:
            diff = (date.fromisoformat(dl) - today).days
            task["urgency_class"] = "task-overdue" if diff < 0 else ("task-soon" if diff <= 3 else "")
        except Exception:
            task["urgency_class"] = ""
    else:
        task["urgency_class"] = ""
    return task


def _days_badge(deadline_str, today):
    if not deadline_str:
        return ""
    try:
        dl = date.fromisoformat(deadline_str)
        diff = (dl - today).days
        formatted = dl.strftime("%d/%m/%Y")
        if diff < 0:
            return f'<span class="days-badge overdue">🔥 {formatted} ({abs(diff)}d atraso)</span>'
        elif diff == 0:
            return f'<span class="days-badge today">⏰ {formatted} (hoje)</span>'
        elif diff <= 3:
            return f'<span class="days-badge soon">⚡ {formatted} ({diff}d)</span>'
        return f'<span class="days-badge ok">📅 {formatted} ({diff}d)</span>'
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


def _get_filtered_tasks(user, project="", priority="", sort="priority",
                        search="", overdue_only=False):
    """Busca tarefas ativas com filtros opcionais."""
    client = get_user_client(user["access_token"], user["refresh_token"])
    query = (
        client.table("tasks")
        .select("*, task_updates(*), task_checklist(*)")
        .eq("user_id", user["user_id"])
        .eq("status", "active")
    )
    if project:
        query = query.eq("project", project)
    if priority:
        query = query.eq("priority", priority)
    if search:
        query = query.ilike("name", f"%{search}%")

    # Ordenação no Supabase
    if sort == "deadline_asc":
        query = query.order("deadline", nullsfirst=False)
    elif sort == "created_desc":
        query = query.order("created_at", desc=True)
    elif sort == "created_asc":
        query = query.order("created_at")
    else:
        query = query.order("created_at")

    raw = query.execute().data or []
    tasks = [_enrich_task(t) for t in raw]

    # Ordenação por prioridade em Python (Supabase não suporta ORDER BY CASE)
    if sort == "priority":
        tasks.sort(key=lambda t: PRIORITY_ORDER.index(t.get("priority", "normal")))

    # Filtro pós-enrich: somente atrasadas
    if overdue_only:
        tasks = [t for t in tasks if t.get("urgency_class") == "task-overdue"]

    return tasks


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


@router.get("/tasks/filter", response_class=HTMLResponse)
async def filter_tasks(
    request: Request,
    project: str = "",
    priority: str = "",
    sort: str = "priority",
    search: str = "",
    overdue: str = "",
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    overdue_only = overdue == "true"
    tasks = _get_filtered_tasks(user, project, priority, sort, search, overdue_only)
    return templates.TemplateResponse(
        "partials/tasks/task_list_body.html",
        {"request": request, "tasks": tasks, "sort": sort},
    )


@router.post("/tasks", response_class=HTMLResponse)
async def add_task(
    request: Request,
    name: str = Form(...),
    project: str = Form(...),
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
        "project": project,
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


@router.post("/tasks/{task_id}/duplicate", response_class=HTMLResponse)
async def duplicate_task(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        original = client.table("tasks").select("*").eq("id", task_id).eq("user_id", user["user_id"]).single().execute().data
        client.table("tasks").insert({
            "name": original["name"],
            "project": original.get("project"),
            "priority": original.get("priority", "normal"),
            "deadline": original.get("deadline"),
            "user_id": user["user_id"],
            "status": "active",
            "date": date.today().isoformat(),
        }).execute()
    except Exception:
        return _task_list_response(request, user, toast="Erro ao duplicar tarefa.")
    return _task_list_response(request, user, toast="Tarefa duplicada!")


# ── Bulk Actions ──────────────────────────────────────────────────────────────

@router.post("/tasks/bulk/complete", response_class=HTMLResponse)
async def bulk_complete(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    form = await request.form()
    task_ids = form.getlist("task_ids")
    if not task_ids:
        return _task_list_response(request, user, toast="Nenhuma tarefa selecionada.")
    completed_dt = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0).isoformat()
    client = get_user_client(user["access_token"], user["refresh_token"])
    for tid in task_ids:
        client.table("tasks").update({
            "status": "completed",
            "completed_at": completed_dt,
        }).eq("id", tid).eq("user_id", user["user_id"]).execute()
    return _task_list_response(request, user, toast=f"{len(task_ids)} tarefa(s) concluida(s)!")


@router.post("/tasks/bulk/discard", response_class=HTMLResponse)
async def bulk_discard(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    form = await request.form()
    task_ids = form.getlist("task_ids")
    if not task_ids:
        return _task_list_response(request, user, toast="Nenhuma tarefa selecionada.")
    client = get_user_client(user["access_token"], user["refresh_token"])
    for tid in task_ids:
        client.table("tasks").update({"status": "discarded"}).eq("id", tid).eq("user_id", user["user_id"]).execute()
    return _task_list_response(request, user, toast=f"{len(task_ids)} tarefa(s) descartada(s).")


@router.post("/tasks/bulk/priority", response_class=HTMLResponse)
async def bulk_change_priority(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    form = await request.form()
    task_ids = form.getlist("task_ids")
    new_priority = form.get("priority", "normal")
    if not task_ids:
        return _task_list_response(request, user, toast="Nenhuma tarefa selecionada.")
    client = get_user_client(user["access_token"], user["refresh_token"])
    for tid in task_ids:
        client.table("tasks").update({"priority": new_priority}).eq("id", tid).eq("user_id", user["user_id"]).execute()
    return _task_list_response(request, user, toast=f"Prioridade atualizada para {len(task_ids)} tarefa(s)!")


@router.post("/tasks/bulk/move", response_class=HTMLResponse)
async def bulk_move_project(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    form = await request.form()
    task_ids = form.getlist("task_ids")
    new_project = form.get("project", "") or None
    if not task_ids:
        return _task_list_response(request, user, toast="Nenhuma tarefa selecionada.")
    client = get_user_client(user["access_token"], user["refresh_token"])
    for tid in task_ids:
        client.table("tasks").update({"project": new_project}).eq("id", tid).eq("user_id", user["user_id"]).execute()
    return _task_list_response(request, user, toast=f"{len(task_ids)} tarefa(s) movida(s)!")


@router.post("/tasks/{task_id}/discard", response_class=HTMLResponse)
async def discard_task(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("tasks").update({"status": "discarded"}).eq("id", task_id).eq("user_id", user["user_id"]).execute()
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
    result = client.table("tasks").select("*").eq("id", task_id).eq("user_id", user["user_id"]).single().execute()
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
        }).eq("id", task_id).eq("user_id", user["user_id"]).execute()
    except Exception:
        pass

    # Fecha modal e re-renderiza lista de ativas
    response = HTMLResponse(content="""
      <script>document.getElementById('modal-container').innerHTML='';</script>
    """)
    response.headers["HX-Trigger"] = '{"showToast":"Tarefa concluida!","refreshTasks":"1"}'
    return response


@router.get("/tasks/{task_id}/edit-form", response_class=HTMLResponse)
async def edit_form(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = client.table("tasks").select("*").eq("id", task_id).eq("user_id", user["user_id"]).single().execute()
    task = result.data
    projects = _get_projects(user)
    checklist = (
        client.table("task_checklist")
        .select("*")
        .eq("task_id", task_id)
        .eq("user_id", user["user_id"])
        .order("position")
        .order("created_at")
        .execute()
        .data or []
    )
    return templates.TemplateResponse(
        "partials/modals/edit_modal.html",
        {"request": request, "task": task, "projects": projects, "checklist": checklist, "error": None},
    )


@router.post("/tasks/{task_id}/edit", response_class=HTMLResponse)
async def edit_task(
    task_id: str,
    request: Request,
    name: str = Form(...),
    project: str = Form(...),
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
            "project": project,
            "priority": priority,
            "deadline": deadline or None,
        }).eq("id", task_id).eq("user_id", user["user_id"]).execute()
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


@router.post("/tasks/{task_id}/reopen", response_class=HTMLResponse)
async def reopen_task(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("tasks").update({
            "status": "pending",
            "completed_at": None,
        }).eq("id", task_id).eq("user_id", user["user_id"]).execute()
    except Exception:
        pass
    # Remove o item da lista sem recarregar a página
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast":"Tarefa reaberta!"}'
    return response


# ── Calendar ─────────────────────────────────────────────────────────────────

MONTH_NAMES = [
    "", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


@router.get("/tasks/calendar", response_class=HTMLResponse)
async def calendar_view(
    request: Request,
    month: int = Query(0),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    today = date.today()
    # Calculate target month/year from offset
    total_months = today.year * 12 + (today.month - 1) + month
    target_year = total_months // 12
    target_month = total_months % 12 + 1

    # Date range for the month
    first_day = date(target_year, target_month, 1)
    if target_month == 12:
        last_day = date(target_year + 1, 1, 1)
    else:
        last_day = date(target_year, target_month + 1, 1)

    # Fetch active tasks with deadlines in this month
    client = get_user_client(user["access_token"], user["refresh_token"])
    tasks_raw = (
        client.table("tasks")
        .select("id, name, project, priority, deadline, status")
        .eq("user_id", user["user_id"])
        .eq("status", "active")
        .not_.is_("deadline", "null")
        .gte("deadline", first_day.isoformat())
        .lt("deadline", last_day.isoformat())
        .order("priority")
        .execute()
        .data or []
    )

    # Build calendar grid
    cal = cal_mod.Calendar(firstweekday=0)  # Monday first
    weeks = cal.monthdatescalendar(target_year, target_month)

    # Group tasks by deadline date string
    tasks_by_date = {}
    for t in tasks_raw:
        dl = t.get("deadline")
        if dl:
            tasks_by_date.setdefault(dl, []).append(t)

    return templates.TemplateResponse(
        "partials/calendar/calendar_view.html",
        {
            "request": request,
            "weeks": weeks,
            "tasks_by_date": tasks_by_date,
            "target_year": target_year,
            "target_month": target_month,
            "month_name": MONTH_NAMES[target_month],
            "today": today,
            "current_offset": month,
        },
    )


# ── Updates ──────────────────────────────────────────────────────────────────

@router.get("/tasks/{task_id}/updates", response_class=HTMLResponse)
async def get_updates(task_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    task_res = client.table("tasks").select("*").eq("id", task_id).eq("user_id", user["user_id"]).single().execute()
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
        {"request": request, "task": task, "updates": updates, "task_id": task_id},
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
    client.table("task_updates").delete().eq("id", update_id).eq("user_id", user["user_id"]).execute()
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


# ── Checklist ─────────────────────────────────────────────────────────────────

def _checklist_response(request, client, task_id):
    items = (
        client.table("task_checklist")
        .select("*")
        .eq("task_id", task_id)
        .order("position")
        .order("created_at")
        .execute()
        .data or []
    )
    return templates.TemplateResponse(
        "partials/checklist/checklist_list.html",
        {"request": request, "task_id": task_id, "items": items},
    )


@router.post("/tasks/{task_id}/checklist", response_class=HTMLResponse)
async def add_checklist_item(
    task_id: str,
    request: Request,
    text: str = Form(...),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("task_checklist").insert({
        "task_id": task_id,
        "user_id": user["user_id"],
        "text": text.strip(),
    }).execute()
    response = _checklist_response(request, client, task_id)
    response.headers["HX-Trigger"] = '{"showToast":"Item adicionado!"}'
    return response


@router.post("/tasks/{task_id}/checklist/{item_id}/toggle", response_class=HTMLResponse)
async def toggle_checklist_item(
    task_id: str,
    item_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    item = client.table("task_checklist").select("done").eq("id", item_id).eq("user_id", user["user_id"]).single().execute().data
    client.table("task_checklist").update({"done": not item["done"]}).eq("id", item_id).eq("user_id", user["user_id"]).execute()
    return _checklist_response(request, client, task_id)


@router.delete("/tasks/{task_id}/checklist/{item_id}", response_class=HTMLResponse)
async def delete_checklist_item(
    task_id: str,
    item_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("task_checklist").delete().eq("id", item_id).eq("user_id", user["user_id"]).execute()
    return _checklist_response(request, client, task_id)
