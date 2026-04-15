"""Gate de aprovação para novos usuários.

A tabela user_approvals tem RLS restrito ao service_role, então usamos
get_service_client() — mas SEMPRE com filtro explícito por user_id.
"""
from datetime import datetime, timezone
from typing import Optional

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

from app.services.supabase_client import get_service_client

OWNER_EMAIL = "campelo.jefferson@gmail.com"


def get_status(user_id: str) -> Optional[str]:
    """Retorna 'pending'|'approved'|'rejected' ou None se não há registro."""
    client = get_service_client()
    res = (
        client.table("user_approvals")
        .select("status")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["status"]
    return None


def is_approved(user_id: str, email: str) -> bool:
    if email == OWNER_EMAIL:
        return True
    return get_status(user_id) == "approved"


def create_pending(user_id: str, email: str) -> None:
    """Insere solicitação pending (idempotente)."""
    client = get_service_client()
    status = "approved" if email == OWNER_EMAIL else "pending"
    payload = {"user_id": user_id, "email": email, "status": status}
    if status == "approved":
        payload["approved_at"] = _utcnow()
    client.table("user_approvals").upsert(payload, on_conflict="user_id").execute()


def list_pending() -> list[dict]:
    client = get_service_client()
    res = (
        client.table("user_approvals")
        .select("user_id, email, status, requested_at")
        .eq("status", "pending")
        .order("requested_at", desc=False)
        .execute()
    )
    return res.data or []


def list_all() -> list[dict]:
    client = get_service_client()
    res = (
        client.table("user_approvals")
        .select("user_id, email, status, requested_at, approved_at")
        .order("requested_at", desc=True)
        .execute()
    )
    return res.data or []


def set_status(user_id: str, status: str, approved_by: str) -> None:
    if status not in ("approved", "rejected", "pending"):
        raise ValueError("status inválido")
    client = get_service_client()
    payload = {"status": status}
    if status == "approved":
        payload["approved_at"] = _utcnow()
        payload["approved_by"] = approved_by
    client.table("user_approvals").update(payload).eq("user_id", user_id).execute()
