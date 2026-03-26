from datetime import date

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_presets(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    return client.table("presets").select("*").order("name").execute().data or []


def _get_projects(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    return client.table("projects").select("*").order("name").execute().data or []


@router.get("/presets", response_class=HTMLResponse)
async def list_presets(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    presets = _get_presets(user)
    projects = _get_projects(user)
    return templates.TemplateResponse(
        "partials/modals/presets_modal.html",
        {"request": request, "presets": presets, "projects": projects},
    )


@router.post("/presets", response_class=HTMLResponse)
async def add_preset(
    request: Request,
    name: str = Form(...),
    project: str = Form(""),
    priority: str = Form("normal"),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("presets").insert({
        "name": name.strip(),
        "project": project or None,
        "priority": priority,
        "user_id": user["user_id"],
    }).execute()
    presets = _get_presets(user)
    response = templates.TemplateResponse(
        "partials/modals/presets_list.html",
        {"request": request, "presets": presets},
    )
    response.headers["HX-Trigger"] = '{"showToast":"Preset adicionado!"}'
    return response


@router.delete("/presets/{preset_id}", response_class=HTMLResponse)
async def delete_preset(preset_id: str, request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("presets").delete().eq("id", preset_id).execute()
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast":"Preset removido."}'
    return response


@router.post("/presets/apply", response_class=HTMLResponse)
async def apply_presets(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    client = get_user_client(user["access_token"], user["refresh_token"])
    presets = _get_presets(user)
    today_str = date.today().isoformat()

    existing = (
        client.table("tasks")
        .select("name")
        .eq("status", "active")
        .eq("date", today_str)
        .execute()
        .data or []
    )
    existing_names = {t["name"] for t in existing}

    created = 0
    for p in presets:
        if p["name"] not in existing_names:
            client.table("tasks").insert({
                "name": p["name"],
                "project": p.get("project"),
                "priority": p.get("priority", "normal"),
                "date": today_str,
                "user_id": user["user_id"],
                "status": "active",
            }).execute()
            created += 1

    # Re-renderiza lista de ativas
    from app.routers.tasks import _get_tasks, _enrich_task, _get_projects
    tasks = [_enrich_task(t) for t in _get_tasks(user)]
    projects = _get_projects(user)
    response = templates.TemplateResponse(
        "partials/tasks/task_list.html",
        {"request": request, "tasks": tasks, "projects": projects},
    )
    msg = f"{created} tarefa(s) criada(s) a partir dos presets!" if created else "Todos os presets já estão ativos hoje."
    response.headers["HX-Trigger"] = f'{{"showToast":"{msg}"}}'
    return response
