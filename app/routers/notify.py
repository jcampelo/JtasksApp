from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.deps import get_current_user
from app.services.notify_config import load_config, save_config
from app.services.email_service import build_email_html, send_email
from app.scheduler import reschedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _smtp_configured() -> bool:
    """Verifica se as variáveis SMTP do servidor estão preenchidas no .env."""
    return bool(settings.smtp_user and settings.smtp_password and settings.smtp_host)


@router.get("/notify/config", response_class=HTMLResponse)
async def notify_config_page(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    cfg = load_config(user["user_id"])
    return templates.TemplateResponse(
        "partials/notify/notify_tab.html",
        {
            "request": request,
            "config": cfg,
            "smtp_configured": _smtp_configured(),
            "smtp_from": settings.smtp_user,
            "smtp_from_name": settings.smtp_from_name,
        },
    )


@router.post("/notify/config", response_class=HTMLResponse)
async def save_notify_config(
    request: Request,
    email_to: str = Form(""),
    schedule_time: str = Form("08:00"),
    enabled: str = Form(""),
    telegram_enabled: str = Form(""),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    new_cfg = {
        "user_id": user["user_id"],
        "email_to": email_to,
        "schedule_time": schedule_time,
        "enabled": enabled == "1",
        "telegram_enabled": telegram_enabled == "1",
    }
    try:
        save_config(new_cfg, user["user_id"])
        reschedule()
        return HTMLResponse('<span style="color:#22c55e;font-weight:600;">✅ Configuração salva!</span>')
    except Exception as e:
        return HTMLResponse(f'<span style="color:#e63946;">Erro: {e}</span>')


@router.post("/notify/send", response_class=HTMLResponse)
async def send_now(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user

    if not _smtp_configured():
        return HTMLResponse(
            '<span style="color:#e63946;">⚠ SMTP não configurado no servidor. '
            'Contate o administrador.</span>'
        )

    cfg = load_config(user["user_id"])
    email_to = cfg.get("email_to", "")
    if not email_to:
        return HTMLResponse(
            '<span style="color:#e63946;">⚠ Configure seu email de destino antes de enviar.</span>'
        )

    try:
        html, subject = build_email_html(user_id=user["user_id"])
        send_email(email_to, html, subject)
        return HTMLResponse(f'<span style="color:#22c55e;font-weight:600;">✅ Email enviado: {subject}</span>')
    except Exception as e:
        return HTMLResponse(f'<span style="color:#e63946;">Erro ao enviar: {e}</span>')
