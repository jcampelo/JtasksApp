import uuid
from datetime import datetime, timezone
from typing import Optional

from app.services.supabase_client import get_service_client

_TABLE = "app_sessions"


def create_session(user_id: str, email: str, access_token: str, refresh_token: str, expires_at: int) -> str:
    """Cria uma sessão server-side e retorna o session_id (UUID)."""
    session_id = str(uuid.uuid4())
    client = get_service_client()
    client.table(_TABLE).insert({
        "id": session_id,
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }).execute()
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """Busca sessão ativa pelo session_id. Retorna None se não existir ou revogada."""
    client = get_service_client()
    result = (
        client.table(_TABLE)
        .select("id, user_id, email, access_token, refresh_token, expires_at")
        .eq("id", session_id)
        .is_("revoked_at", "null")
        .single()
        .execute()
    )
    if not result.data:
        return None
    _touch(session_id, client)
    return result.data


def update_tokens(session_id: str, access_token: str, refresh_token: str, expires_at: int) -> None:
    """Atualiza tokens após refresh do Supabase."""
    client = get_service_client()
    client.table(_TABLE).update({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()


def delete_session(session_id: str) -> None:
    """Revoga a sessão no logout."""
    client = get_service_client()
    client.table(_TABLE).update({
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()


def _touch(session_id: str, client) -> None:
    client.table(_TABLE).update({
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()
