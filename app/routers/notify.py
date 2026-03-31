from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.services.notify_config import load_config, save_config
from app.services.email_service import build_email_html, send_email
from app.scheduler import reschedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/notify/config", response_class=HTMLResponse)
async def notify_config_page(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    cfg = load_config(user["user_id"])
    safe = {k: v for k, v in cfg.items() if k != "smtp_password"}
    safe["has_password"] = bool(cfg.get("smtp_password"))
    return templates.TemplateResponse(
        "partials/notify/notify_tab.html",
        {"request": request, "config": safe},
    )


@router.post("/notify/config", response_class=HTMLResponse)
async def save_notify_config(
    request: Request,
    email_to: str = Form(""),
    smtp_host: str = Form(""),
    smtp_port: str = Form("587"),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    schedule_time: str = Form("08:00"),
    enabled: str = Form(""),
    user=Depends(get_current_user),
):
    if isinstance(user, RedirectResponse):
        return user

    existing = load_config(user["user_id"])
    new_cfg = {
        "email_to": email_to,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password if smtp_password else existing.get("smtp_password", ""),
        "schedule_time": schedule_time,
        "enabled": enabled == "1",
        "user_id": user["user_id"],
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
    cfg = load_config(user["user_id"])
    if not cfg.get("email_to") or not cfg.get("smtp_user") or not cfg.get("smtp_host"):
        return HTMLResponse('<span style="color:#e63946;">⚠ Configure o SMTP antes de enviar.</span>')
    if not cfg.get("smtp_password"):
        return HTMLResponse('<span style="color:#e63946;">⚠ Senha SMTP não configurada.</span>')
    try:
        html, subject = build_email_html(user_id=user["user_id"])
        send_email(cfg, html, subject)
        return HTMLResponse(f'<span style="color:#22c55e;font-weight:600;">✅ Email enviado: {subject}</span>')
    except Exception as e:
        return HTMLResponse(f'<span style="color:#e63946;">Erro ao enviar: {e}</span>')
