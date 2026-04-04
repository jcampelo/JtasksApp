from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_ideas(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = (
        client.table("ideas")
        .select("*")
        .eq("user_id", user["user_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def _get_projects(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = client.table("projects").select("*").eq("user_id", user["user_id"]).order("name").execute()
    return result.data or []


@router.get("/ideas", response_class=HTMLResponse)
async def list_ideas(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    ideas = _get_ideas(user)
    projects = _get_projects(user)
    return templates.TemplateResponse(
        "partials/ideas/idea_list.html",
        {"request": request, "ideas": ideas, "projects": projects, "error": None},
    )


@router.post("/ideas", response_class=HTMLResponse)
async def add_idea(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    stakeholders: Optional[str] = Form(None),
    potential: str = Form("media"),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    title = title.strip()
    error = None
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("ideas").insert({
            "title": title,
            "description": (description or "").strip() or None,
            "project": (project or "").strip() or None,
            "stakeholders": (stakeholders or "").strip() or None,
            "potential": potential,
            "user_id": user["user_id"],
        }).execute()
    except Exception:
        error = "Erro ao registrar ideia."

    ideas = _get_ideas(user)
    projects = _get_projects(user)
    response = templates.TemplateResponse(
        "partials/ideas/idea_list.html",
        {"request": request, "ideas": ideas, "projects": projects, "error": error},
    )
    if not error:
        response.headers["HX-Trigger"] = '{"showToast":"Ideia registrada!"}'
    return response


@router.patch("/ideas/{idea_id}/status", response_class=HTMLResponse)
async def update_idea_status(
    idea_id: str,
    request: Request,
    status: str = Form(...),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("ideas").update({"status": status}).eq("id", idea_id).eq("user_id", user["user_id"]).execute()
    except Exception:
        pass

    ideas = _get_ideas(user)
    projects = _get_projects(user)
    response = templates.TemplateResponse(
        "partials/ideas/idea_list.html",
        {"request": request, "ideas": ideas, "projects": projects, "error": None},
    )
    response.headers["HX-Trigger"] = '{"showToast":"Status atualizado!"}'
    return response


@router.delete("/ideas/{idea_id}", response_class=HTMLResponse)
async def delete_idea(
    idea_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("ideas").delete().eq("id", idea_id).eq("user_id", user["user_id"]).execute()
    except Exception:
        pass
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast":"Ideia removida.","refreshIdeas":true}'
    return response
