"""
Serviço de monitoramento de usuários (owner only).

REGRA DE OURO: get_service_client() é chamado APENAS aqui.
Toda query às tasks de outros usuários SEMPRE usa .eq("user_id", watched_user_id).
"""
from datetime import date, timezone, datetime
from typing import Literal

from fastapi import HTTPException

from app.services.supabase_client import get_service_client
from app.services.approval_service import list_all as list_all_approvals, OWNER_EMAIL


def get_watched_users(owner_id: str, user_client) -> list[dict]:
    """Retorna lista de watched_users do owner (via user_client com RLS)."""
    res = (
        user_client.table("watched_users")
        .select("watched_user_id, pinned_at")
        .eq("owner_id", owner_id)
        .order("pinned_at")
        .execute()
    )
    return res.data or []


def get_all_summaries(owner_id: str, user_client) -> list[dict]:
    """
    Busca todos os usuários pinados e seus resumos em queries batch (não N+1).
    Retorna lista de dicts com: watched_user_id, email, active, overdue, completed_today.
    """
    watched = get_watched_users(owner_id, user_client)
    if not watched:
        return []

    watched_ids = [w["watched_user_id"] for w in watched]
    today = date.today().isoformat()
    today_start = today + "T00:00:00"

    svc = get_service_client()

    # Email dos usuários monitorados (via user_approvals)
    emails_res = (
        svc.table("user_approvals")
        .select("user_id, email")
        .in_("user_id", watched_ids)
        .execute()
    )
    email_map = {e["user_id"]: e["email"] for e in (emails_res.data or [])}

    # Tarefas ativas de todos os monitorados — query batch
    active_res = (
        svc.table("tasks")
        .select("id, user_id, deadline")
        .in_("user_id", watched_ids)
        .eq("status", "active")
        .execute()
    )

    # Concluídas hoje de todos os monitorados — query batch
    completed_res = (
        svc.table("tasks")
        .select("id, user_id")
        .in_("user_id", watched_ids)
        .eq("status", "completed")
        .gte("completed_at", today_start)
        .execute()
    )

    # Agrupa em Python
    active_by_user: dict[str, list] = {}
    for t in (active_res.data or []):
        active_by_user.setdefault(t["user_id"], []).append(t)

    completed_by_user: dict[str, list] = {}
    for t in (completed_res.data or []):
        completed_by_user.setdefault(t["user_id"], []).append(t)

    result = []
    for wid in watched_ids:
        active = active_by_user.get(wid, [])
        completed = completed_by_user.get(wid, [])
        overdue = sum(
            1 for t in active
            if t.get("deadline") and t["deadline"] < today
        )
        result.append({
            "watched_user_id": wid,
            "email": email_map.get(wid, wid),
            "active": len(active),
            "overdue": overdue,
            "completed_today": len(completed),
        })

    return result


def _group_tasks(tasks: list[dict]) -> dict:
    """Agrupa tarefas ativas por prioridade/atraso, cada grupo ordenado por deadline ASC."""
    today = date.today().isoformat()
    atrasadas, critica, urgente, normal = [], [], [], []

    for t in tasks:
        deadline = t.get("deadline") or ""
        if deadline and deadline < today:
            atrasadas.append(t)
        elif t.get("priority") == "critica":
            critica.append(t)
        elif t.get("priority") == "urgente":
            urgente.append(t)
        else:
            normal.append(t)

    sort_key = lambda t: t.get("deadline") or "9999-12-31"
    for grp in [atrasadas, critica, urgente, normal]:
        grp.sort(key=sort_key)

    return {
        "atrasadas": atrasadas,
        "critica": critica,
        "urgente": urgente,
        "normal": normal,
    }


def fetch_watched_user_data(
    owner_id: str,
    watched_id: str,
    resource: Literal["tasks_full"],
    user_client,
) -> dict:
    """
    ÚNICO ponto de acesso a get_service_client() para tasks de outros usuários.
    1. Valida que watched_id está nos pinados do owner (via user_client com RLS).
    2. Busca tasks via service_client SEMPRE com .eq("user_id", watched_id).
    3. Retorna dados agrupados.
    """
    # Camada de validação: watched_id deve estar nos pinados do owner
    pin_check = (
        user_client.table("watched_users")
        .select("id")
        .eq("owner_id", owner_id)
        .eq("watched_user_id", watched_id)
        .limit(1)
        .execute()
    )
    if not pin_check.data:
        raise HTTPException(status_code=404, detail="Usuário não pinado.")

    svc = get_service_client()
    tasks_res = (
        svc.table("tasks")
        .select("id, name, project, priority, deadline, status")
        .eq("user_id", watched_id)  # SEMPRE filtrado por watched_id
        .eq("status", "active")
        .execute()
    )
    return _group_tasks(tasks_res.data or [])


def get_all_users_for_picker(owner_id: str, user_client) -> list[dict]:
    """
    Retorna todos os usuários aprovados (exceto o owner) com flag 'pinned'.
    Usado no modal de pinar.
    """
    all_approvals = list_all_approvals()  # usa get_service_client() internamente
    watched = get_watched_users(owner_id, user_client)
    pinned_ids = {w["watched_user_id"] for w in watched}

    result = []
    for a in all_approvals:
        if a["email"] == OWNER_EMAIL:
            continue
        if a.get("status") != "approved":
            continue
        result.append({
            "user_id": a["user_id"],
            "email": a["email"],
            "pinned": a["user_id"] in pinned_ids,
        })
    return result


def pin_user(owner_id: str, watched_id: str, user_client) -> None:
    """Pina um usuário (insert idempotente)."""
    user_client.table("watched_users").upsert(
        {"owner_id": owner_id, "watched_user_id": watched_id},
        on_conflict="owner_id,watched_user_id",
    ).execute()


def unpin_user(owner_id: str, watched_id: str, user_client) -> None:
    """Despina um usuário."""
    user_client.table("watched_users").delete().eq("owner_id", owner_id).eq(
        "watched_user_id", watched_id
    ).execute()
