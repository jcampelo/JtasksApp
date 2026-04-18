"""
Painel admin de permissões (master-only).

Gate require_owner aplicado em nível de router. Toda lógica de mutação
fica em permissions_service.py — este arquivo só renderiza e dispara ações.
"""
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.deps import require_owner
from app.services import permissions_service
from app.services.permissions_service import KNOWN_FEATURES

router = APIRouter(
    prefix="/admin/permissions",
    dependencies=[Depends(require_owner)],
)
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def permissions_tab(request: Request, user=Depends(require_owner)):
    users = permissions_service.list_users_with_features(user)
    return templates.TemplateResponse(
        "partials/admin/permissions_tab.html",
        {
            "request": request,
            "users": users,
            "features": sorted(KNOWN_FEATURES),
        },
    )


@router.post("/grant", response_class=HTMLResponse)
async def grant(
    request: Request,
    user_id: str = Form(...),
    feature: str = Form(...),
    user=Depends(require_owner),
):
    permissions_service.grant_feature(user_id, feature, user)
    return _user_row_response(request, user_id, user, toast=f"Feature '{feature}' concedida.")


@router.post("/revoke", response_class=HTMLResponse)
async def revoke(
    request: Request,
    user_id: str = Form(...),
    feature: str = Form(...),
    user=Depends(require_owner),
):
    permissions_service.revoke_feature(user_id, feature, user)
    return _user_row_response(request, user_id, user, toast=f"Feature '{feature}' revogada.")


def _user_row_response(request: Request, user_id: str, master_user: dict, toast: str) -> HTMLResponse:
    """Re-renderiza apenas a linha do usuário afetado e dispara toast."""
    users = permissions_service.list_users_with_features(master_user)
    target = next((u for u in users if u["user_id"] == user_id), None)
    if target is None:
        return HTMLResponse("", status_code=200)
    response = templates.TemplateResponse(
        "partials/admin/permissions_user_row.html",
        {
            "request": request,
            "user_row": target,
            "features": sorted(KNOWN_FEATURES),
        },
    )
    response.headers["HX-Trigger"] = json.dumps({"showToast": toast})
    return response
