from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.supabase_client import get_service_client

router = APIRouter(prefix="/bot", tags=["bot"])


# ── Autenticação ─────────────────────────────────────────────────────────────

def verify_bot_key(x_bot_key: str = Header(...)):
    if x_bot_key != settings.bot_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


def _client():
    return get_service_client()


def _uid() -> str:
    return settings.bot_owner_user_id


# ── Modelos de Tarefas ────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    name: str
    project: Optional[str] = None
    priority: str = "normal"
    deadline: Optional[str] = None


class TaskUpdate(BaseModel):
    priority: Optional[str] = None
    deadline: Optional[str] = None


class UpdateCreate(BaseModel):
    text: str


# ── Endpoints de Tarefas ─────────────────────────────────────────────────────

@router.post("/tasks")
def create_task(body: TaskCreate, _: None = Depends(verify_bot_key)):
    client = _client()
    result = client.table("tasks").insert({
        "name": body.name,
        "project": body.project,
        "priority": body.priority,
        "deadline": body.deadline,
        "status": "active",
        "user_id": _uid(),
    }).execute()
    return {"ok": True, "task_id": result.data[0]["id"]}


# IMPORTANTE: /tasks/search deve ser declarado ANTES de /tasks/{task_id}
@router.get("/tasks/search")
def search_tasks(q: str = Query(...), _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("tasks")
        .select("id, name, priority, deadline, status")
        .eq("user_id", _uid())
        .eq("status", "active")
        .ilike("name", f"%{q}%")
        .execute()
    )
    return {"tasks": result.data or []}


@router.get("/tasks")
def list_tasks(filter: Optional[str] = Query(None), _: None = Depends(verify_bot_key)):
    client = _client()
    today = date.today().isoformat()
    query = (
        client.table("tasks")
        .select("id, name, priority, deadline, status")
        .eq("user_id", _uid())
        .eq("status", "active")
    )
    if filter == "today":
        query = query.eq("deadline", today)
    elif filter == "overdue":
        query = query.lt("deadline", today).not_.is_("deadline", "null")
    result = query.order("created_at", desc=True).execute()
    return {"tasks": result.data or []}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("tasks")
        .select("id, name, priority, deadline, status, project, task_updates(*)")
        .eq("id", task_id)
        .eq("user_id", _uid())
        .single()
        .execute()
    )
    return {"task": result.data}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate, _: None = Depends(verify_bot_key)):
    updates = {}
    if body.priority is not None:
        updates["priority"] = body.priority
    if body.deadline is not None:
        updates["deadline"] = body.deadline
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    _client().table("tasks").update(updates).eq("id", task_id).eq("user_id", _uid()).execute()
    return {"ok": True}


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, _: None = Depends(verify_bot_key)):
    completed_dt = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0).isoformat()
    _client().table("tasks").update({
        "status": "completed",
        "completed_at": completed_dt,
    }).eq("id", task_id).eq("user_id", _uid()).execute()
    return {"ok": True}


@router.post("/tasks/{task_id}/discard")
def discard_task(task_id: str, _: None = Depends(verify_bot_key)):
    _client().table("tasks").update({"status": "discarded"}).eq("id", task_id).eq("user_id", _uid()).execute()
    return {"ok": True}


@router.post("/tasks/{task_id}/updates")
def add_task_update(task_id: str, body: UpdateCreate, _: None = Depends(verify_bot_key)):
    _client().table("task_updates").insert({
        "task_id": task_id,
        "user_id": _uid(),
        "text": body.text,
    }).execute()
    return {"ok": True}


# ── Modelos de Notas e Ideias ────────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str


class IdeaCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project: Optional[str] = None


# ── Endpoints de Notas ───────────────────────────────────────────────────────

@router.post("/notes")
def create_note(body: NoteCreate, _: None = Depends(verify_bot_key)):
    client = _client()
    result = client.table("notes").insert({
        "content": body.content,
        "color": "yellow",
        "user_id": _uid(),
    }).execute()
    return {"ok": True, "note_id": result.data[0]["id"]}


# IMPORTANTE: /notes/search deve ser declarado ANTES de /notes/{note_id}
@router.get("/notes/search")
def search_notes(q: str = Query(...), _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("notes")
        .select("id, content, created_at")
        .eq("user_id", _uid())
        .ilike("content", f"%{q}%")
        .execute()
    )
    return {"notes": result.data or []}


@router.get("/notes")
def list_notes(_: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("notes")
        .select("id, content, created_at")
        .eq("user_id", _uid())
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return {"notes": result.data or []}


@router.delete("/notes/{note_id}")
def delete_note(note_id: str, _: None = Depends(verify_bot_key)):
    _client().table("notes").delete().eq("id", note_id).eq("user_id", _uid()).execute()
    return {"ok": True}


# ── Endpoints de Ideias ──────────────────────────────────────────────────────

@router.post("/ideas")
def create_idea(body: IdeaCreate, _: None = Depends(verify_bot_key)):
    client = _client()
    result = client.table("ideas").insert({
        "title": body.title,
        "description": body.description,
        "project": body.project,
        "potential": "media",
        "user_id": _uid(),
    }).execute()
    return {"ok": True, "idea_id": result.data[0]["id"]}


# IMPORTANTE: /ideas/search deve ser declarado ANTES de /ideas/{idea_id}
@router.get("/ideas/search")
def search_ideas(q: str = Query(...), _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("ideas")
        .select("id, title, description, project")
        .eq("user_id", _uid())
        .ilike("title", f"%{q}%")
        .execute()
    )
    return {"ideas": result.data or []}


@router.get("/ideas")
def list_ideas(_: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("ideas")
        .select("id, title, description, project, created_at")
        .eq("user_id", _uid())
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return {"ideas": result.data or []}


@router.delete("/ideas/{idea_id}")
def delete_idea(idea_id: str, _: None = Depends(verify_bot_key)):
    _client().table("ideas").delete().eq("id", idea_id).eq("user_id", _uid()).execute()
    return {"ok": True}
