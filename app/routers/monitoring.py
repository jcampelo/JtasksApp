"""
Router de acompanhamento de usuários (owner only).

Gate de segurança aplicado em nível de router — todos os endpoints herdam.
NUNCA importar o cliente_de_servico aqui. Toda lógica de dados fica em monitoring_service.py.
"""
import json
from datetime import date

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.deps import require_feature
from app.services.supabase_client import get_user_client
from app.services import monitoring_service

router = APIRouter(
    prefix="/monitoring",
    dependencies=[Depends(require_feature("monitoring"))],
)
templates = Jinja2Templates(directory="app/templates")


def _get_client(user: dict):
    return get_user_client(user["access_token"], user["refresh_token"])


@router.get("", response_class=HTMLResponse)
async def monitoring_tab(request: Request, user=Depends(require_feature("monitoring"))):
    """Carrega a aba com cards colapsados (summaries de todos os pinados)."""
    client = _get_client(user)
    summaries = monitoring_service.get_all_summaries(user["user_id"], client)
    return templates.TemplateResponse(
        "partials/monitoring/monitoring_tab.html",
        {"request": request, "summaries": summaries},
    )


@router.get("/card/{watched_id}", response_class=HTMLResponse)
async def card_body(watched_id: str, request: Request, user=Depends(require_feature("monitoring"))):
    """Corpo expandido com tarefas agrupadas (lazy, ao expandir o card)."""
    client = _get_client(user)
    groups = monitoring_service.fetch_watched_user_data(
        user["user_id"], watched_id, "tasks_full", client
    )
    return templates.TemplateResponse(
        "partials/monitoring/user_card_body.html",
        {
            "request": request,
            "groups": groups,
            "watched_id": watched_id,
            "now_date": date.today().isoformat(),
        },
    )


@router.get("/refresh-all", response_class=HTMLResponse)
async def refresh_all(request: Request, user=Depends(require_feature("monitoring"))):
    """Refresh manual ou por polling — retorna apenas os cabeçalhos dos cards."""
    client = _get_client(user)
    summaries = monitoring_service.get_all_summaries(user["user_id"], client)
    return templates.TemplateResponse(
        "partials/monitoring/user_cards_list.html",
        {"request": request, "summaries": summaries},
    )


@router.get("/pin-picker", response_class=HTMLResponse)
async def pin_picker(request: Request, user=Depends(require_feature("monitoring"))):
    """Modal de pinar usuários."""
    client = _get_client(user)
    users = monitoring_service.get_all_users_for_picker(user["user_id"], client)
    return templates.TemplateResponse(
        "partials/monitoring/pin_picker.html",
        {"request": request, "users": users},
    )


@router.post("/pin", response_class=HTMLResponse)
async def pin(
    request: Request,
    watched_id: str = Form(...),
    user=Depends(require_feature("monitoring")),
):
    """Pina um usuário e retorna a lista atualizada de usuários no picker."""
    client = _get_client(user)
    monitoring_service.pin_user(user["user_id"], watched_id, client)
    users = monitoring_service.get_all_users_for_picker(user["user_id"], client)
    response = templates.TemplateResponse(
        "partials/monitoring/pin_picker_list.html",
        {"request": request, "users": users},
    )
    response.headers["HX-Trigger"] = json.dumps({"refreshMonitoringCards": True})
    return response


@router.delete("/pin/{watched_id}", response_class=HTMLResponse)
async def unpin(watched_id: str, request: Request, user=Depends(require_feature("monitoring"))):
    """Despina um usuário e retorna os cards atualizados."""
    client = _get_client(user)
    monitoring_service.unpin_user(user["user_id"], watched_id, client)
    summaries = monitoring_service.get_all_summaries(user["user_id"], client)
    response = templates.TemplateResponse(
        "partials/monitoring/user_cards_list.html",
        {"request": request, "summaries": summaries},
    )
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": "Usuário despinado."}
    )
    return response
