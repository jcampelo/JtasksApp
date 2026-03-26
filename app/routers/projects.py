from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_projects(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = client.table("projects").select("*").order("name").execute()
    return result.data or []


@router.get("/projects", response_class=HTMLResponse)
async def list_projects(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    projects = _get_projects(user)
    return templates.TemplateResponse(
        "partials/projects/project_list.html",
        {"request": request, "projects": projects, "error": None},
    )


@router.post("/projects", response_class=HTMLResponse)
async def add_project(
    request: Request,
    name: str = Form(...),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    name = name.strip()
    error = None
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("projects").insert({"name": name, "user_id": user["user_id"]}).execute()
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            error = f"Projeto '{name}' já existe."
        else:
            error = "Erro ao criar projeto."

    projects = _get_projects(user)
    response = templates.TemplateResponse(
        "partials/projects/project_list.html",
        {"request": request, "projects": projects, "error": error},
    )
    if not error:
        response.headers["HX-Trigger"] = '{"showToast":"Projeto adicionado!"}'
    return response


@router.delete("/projects/{project_id}", response_class=HTMLResponse)
async def delete_project(
    project_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("projects").delete().eq("id", project_id).execute()
    except Exception:
        pass
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast":"Projeto removido."}'
    return response
