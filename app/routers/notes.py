from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import date

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_notes(user):
    client = get_user_client(user["access_token"], user["refresh_token"])
    result = (
        client.table("notes")
        .select("*")
        .eq("user_id", user["user_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@router.get("/notes", response_class=HTMLResponse)
async def list_notes(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    notes = _get_notes(user)
    return templates.TemplateResponse(
        "partials/notes/notes_list.html",
        {"request": request, "notes": notes, "error": None},
    )


@router.post("/notes", response_class=HTMLResponse)
async def add_note(
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    error = None
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("notes").insert({
            "title": "Nova nota",
            "content": "",
            "color": "yellow",
            "user_id": user["user_id"],
        }).execute()
    except Exception as e:
        error = f"Erro ao criar nota: {str(e)}"

    notes = _get_notes(user)
    response = templates.TemplateResponse(
        "partials/notes/notes_list.html",
        {"request": request, "notes": notes, "error": error},
    )
    if not error:
        response.headers["HX-Trigger"] = '{"showToast":"Nota adicionada!"}'
    return response


@router.patch("/notes/{note_id}", response_class=HTMLResponse)
async def update_note(
    note_id: str,
    request: Request,
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    update_data = {}
    # Título: ignora se vier vazio (tolerância para auto-save durante digitação)
    if title is not None and title.strip():
        update_data["title"] = title.strip()
    if content is not None:
        update_data["content"] = content
    if color is not None:
        update_data["color"] = color

    if update_data:
        try:
            client = get_user_client(user["access_token"], user["refresh_token"])
            client.table("notes").update(update_data).eq("id", note_id).eq("user_id", user["user_id"]).execute()
        except Exception:
            pass

    # Só re-renderiza a lista ao mudar cor (para atualizar o color-picker ativo)
    if color is not None:
        notes = _get_notes(user)
        response = templates.TemplateResponse(
            "partials/notes/notes_list.html",
            {"request": request, "notes": notes, "error": None},
        )
        response.headers["HX-Trigger"] = '{"showToast":"Cor alterada!"}'
        return response

    # Título/conteúdo: resposta mínima sem re-render (preserva estado minimizado)
    return HTMLResponse(content="", status_code=204)


@router.delete("/notes/{note_id}", response_class=HTMLResponse)
async def delete_note(
    note_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        client.table("notes").delete().eq("id", note_id).eq("user_id", user["user_id"]).execute()
    except Exception:
        pass

    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast":"Nota excluída.","refreshNotes":true}'
    return response


@router.post("/notes/{note_id}/convert", response_class=HTMLResponse)
async def convert_note_to_task(
    note_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    error = None
    try:
        client = get_user_client(user["access_token"], user["refresh_token"])

        # 1. Obter a nota (title + content)
        note_res = (
            client.table("notes")
            .select("title, content")
            .eq("id", note_id)
            .eq("user_id", user["user_id"])
            .execute()
        )
        if note_res.data:
            note = note_res.data[0]
            # Usa title como nome da tarefa; fallback para content se title vazio
            task_name = (note.get("title") or "").strip() or (note.get("content") or "")[:40]

            # 2. Inserir em tasks
            client.table("tasks").insert({
                "user_id": user["user_id"],
                "name": task_name,
                "date": date.today().isoformat(),
                "priority": "normal",
                "status": "active",
            }).execute()

            # 3. Deletar a nota
            client.table("notes").delete().eq("id", note_id).eq("user_id", user["user_id"]).execute()
    except Exception:
        error = "Erro ao converter nota."

    notes = _get_notes(user)
    response = templates.TemplateResponse(
        "partials/notes/notes_list.html",
        {"request": request, "notes": notes, "error": error},
    )
    if not error:
        response.headers["HX-Trigger"] = '{"showToast":"Convertido para atividade!","refreshTasks":true}'
    return response
