import os
from typing import Optional

import httpx


def _base_url() -> str:
    return os.environ.get("JTASKS_INTERNAL_URL", "http://localhost:8000")


def _headers() -> dict:
    return {"X-Bot-Key": os.environ["BOT_API_KEY"]}


def _get(path: str, params: dict = None) -> dict:
    r = httpx.get(f"{_base_url()}{path}", headers=_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict = None) -> dict:
    r = httpx.post(f"{_base_url()}{path}", headers=_headers(), json=body or {}, timeout=10)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = httpx.patch(f"{_base_url()}{path}", headers=_headers(), json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    r = httpx.delete(f"{_base_url()}{path}", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


# ── Tarefas ──────────────────────────────────────────────────────────────────

def create_task(name: str, project: Optional[str], priority: str, deadline: Optional[str]) -> dict:
    return _post("/bot/tasks", {
        "name": name, "project": project, "priority": priority, "deadline": deadline
    })


def list_tasks(filter: Optional[str] = None) -> list:
    params = {"filter": filter} if filter else {}
    return _get("/bot/tasks", params).get("tasks", [])


def search_tasks(q: str) -> list:
    return _get("/bot/tasks/search", {"q": q}).get("tasks", [])


def get_task(task_id: str) -> dict:
    return _get(f"/bot/tasks/{task_id}").get("task", {})


def complete_task(task_id: str) -> dict:
    return _post(f"/bot/tasks/{task_id}/complete")


def discard_task(task_id: str) -> dict:
    return _post(f"/bot/tasks/{task_id}/discard")


def update_task(task_id: str, priority: Optional[str] = None, deadline: Optional[str] = None) -> dict:
    body = {}
    if priority:
        body["priority"] = priority
    if deadline:
        body["deadline"] = deadline
    return _patch(f"/bot/tasks/{task_id}", body)


def add_task_update(task_id: str, text: str) -> dict:
    return _post(f"/bot/tasks/{task_id}/updates", {"text": text})


# ── Notas ────────────────────────────────────────────────────────────────────

def create_note(content: str) -> dict:
    return _post("/bot/notes", {"content": content})


def list_notes() -> list:
    return _get("/bot/notes").get("notes", [])


def search_notes(q: str) -> list:
    return _get("/bot/notes/search", {"q": q}).get("notes", [])


def delete_note(note_id: str) -> dict:
    return _delete(f"/bot/notes/{note_id}")


# ── Ideias ───────────────────────────────────────────────────────────────────

def create_idea(title: str, description: Optional[str], project: Optional[str]) -> dict:
    return _post("/bot/ideas", {"title": title, "description": description, "project": project})


def list_ideas() -> list:
    return _get("/bot/ideas").get("ideas", [])


def search_ideas(q: str) -> list:
    return _get("/bot/ideas/search", {"q": q}).get("ideas", [])


def delete_idea(idea_id: str) -> dict:
    return _delete(f"/bot/ideas/{idea_id}")
