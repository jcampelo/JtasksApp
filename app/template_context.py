"""Helper de contexto Jinja2 compartilhado pelos renders de páginas com sidebar."""
from fastapi import Request

from app.services.permissions_service import get_user_features, is_owner


def build_user_context(request: Request, user: dict) -> dict:
    """
    Contexto comum injetado em renders que dependem de gates por feature.
    Retorna user, is_owner e user_features (set, sempre — nunca None).
    """
    return {
        "user": user,
        "is_owner": is_owner(user),
        "user_features": get_user_features(user, request),
    }
