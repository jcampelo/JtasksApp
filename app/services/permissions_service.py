"""
Serviço central de permissões (feature flags por usuário).

REGRA DE OURO: este é o ÚNICO arquivo autorizado a chamar get_service_client()
para escrever na tabela user_features. Routers nunca importam o service client.

Owner (OWNER_EMAIL hardcoded) é master:
- Sempre recebe todas as KNOWN_FEATURES implicitamente (sem precisar de linha no banco).
- Único autorizado a chamar grant_feature / revoke_feature / list_users_with_features.
"""
from fastapi import HTTPException, Request

from app.services.approval_service import OWNER_EMAIL, list_all as list_all_approvals
from app.services.supabase_client import get_service_client

# Conjunto canônico de features conhecidas. Adicionar aqui ao introduzir nova feature.
KNOWN_FEATURES: set[str] = {"monitoring"}


def is_owner(user: dict) -> bool:
    """True se o email do usuário corresponde ao OWNER_EMAIL."""
    if not user:
        return False
    return user.get("email") == OWNER_EMAIL


def get_user_features(user: dict, request: Request) -> set[str]:
    """
    Retorna set de features ativas do usuário.
    - Owner sempre recebe KNOWN_FEATURES (features implícitas).
    - Demais usuários: query em user_features filtrando por user_id.
    - Resultado cacheado em request.state.user_features para o ciclo do request.
    """
    cached = getattr(request.state, "user_features", None)
    if cached is not None:
        return cached

    if is_owner(user):
        features = set(KNOWN_FEATURES)
    else:
        features = _fetch_user_features(user["user_id"])

    request.state.user_features = features
    return features


def has_feature(user: dict, request: Request, feature: str) -> bool:
    """Atalho: feature in get_user_features(user, request)."""
    return feature in get_user_features(user, request)


def grant_feature(target_user_id: str, feature: str, master_user: dict) -> None:
    """
    Concede feature a um usuário (UPSERT idempotente).
    - 403 se master_user não for owner.
    - 400 se feature não estiver em KNOWN_FEATURES.
    """
    _require_owner(master_user)
    _require_known_feature(feature)

    svc = get_service_client()
    svc.table("user_features").upsert(
        {"user_id": target_user_id, "feature": feature},
        on_conflict="user_id,feature",
    ).execute()


def revoke_feature(target_user_id: str, feature: str, master_user: dict) -> None:
    """
    Revoga feature (DELETE idempotente).
    - 403 se master_user não for owner.
    """
    _require_owner(master_user)

    svc = get_service_client()
    (
        svc.table("user_features")
        .delete()
        .eq("user_id", target_user_id)
        .eq("feature", feature)
        .execute()
    )


def list_users_with_features(master_user: dict) -> list[dict]:
    """
    Lista todos os usuários aprovados (exceto o master) com suas features ativas.
    - 403 se master_user não for owner.
    Retorno: [{"user_id": str, "email": str, "features": set[str]}]
    """
    _require_owner(master_user)

    approvals = list_all_approvals()
    candidates = [
        a for a in approvals
        if a.get("status") == "approved" and a.get("email") != OWNER_EMAIL
    ]
    if not candidates:
        return []

    user_ids = [a["user_id"] for a in candidates]
    svc = get_service_client()
    res = (
        svc.table("user_features")
        .select("user_id, feature")
        .in_("user_id", user_ids)
        .execute()
    )
    features_by_user: dict[str, set[str]] = {}
    for row in (res.data or []):
        features_by_user.setdefault(row["user_id"], set()).add(row["feature"])

    return [
        {
            "user_id": a["user_id"],
            "email": a["email"],
            "features": features_by_user.get(a["user_id"], set()),
        }
        for a in candidates
    ]


# --- Internos ---------------------------------------------------------------

def _fetch_user_features(user_id: str) -> set[str]:
    """Lê features do usuário via service_key (RLS de SELECT também permite, mas
    centralizamos aqui para ter um único caminho de leitura)."""
    svc = get_service_client()
    res = (
        svc.table("user_features")
        .select("feature")
        .eq("user_id", user_id)
        .execute()
    )
    return {row["feature"] for row in (res.data or [])}


def _require_owner(master_user: dict) -> None:
    if not is_owner(master_user):
        raise HTTPException(status_code=403, detail="Acesso negado.")


def _require_known_feature(feature: str) -> None:
    if feature not in KNOWN_FEATURES:
        raise HTTPException(status_code=400, detail=f"Feature desconhecida: {feature}")
