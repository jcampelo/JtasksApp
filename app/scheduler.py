import json

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.notify_config import load_all_configs
from app.services.email_service import build_email_html, send_email
from app.services.supabase_client import get_service_client
from datetime import date

_scheduler = BackgroundScheduler()


def _job_id(user_id: str) -> str:
    return f"email_daily_{user_id}"


def _run_email_job(cfg: dict):
    user_id  = cfg.get("user_id", "")
    email_to = cfg.get("email_to", "")

    # Verifica se o SMTP do servidor e o destino estão configurados
    if not (settings.smtp_user and settings.smtp_password and email_to):
        print(f"[scheduler] Skipping {user_id}: SMTP do servidor ou email_to não configurado.")
        return
    try:
        html, subject = build_email_html(user_id=user_id)
        send_email(email_to, html, subject)
        print(f"[scheduler] Email enviado para {email_to}: {subject}")
    except Exception as e:
        print(f"[scheduler] Erro ao enviar para {email_to}: {e}")


def _run_overdueDate_job():
    """Converte tarefas vencidas (deadline < hoje) para críticas automaticamente"""
    try:
        client = get_service_client()
        today = date.today().isoformat()
        
        # update() no supabase não suporta facilmente 'where != X' com o postgrest python de forma simples em uma só query p/ updates massivos?
        # Supabase python client suporta chained filters
        response = client.table("tasks") \
            .update({"priority": "critica"}) \
            .lt("deadline", today) \
            .eq("status", "active") \
            .neq("priority", "critica") \
            .execute()
        
        count = len(response.data) if response.data else 0
        if count > 0:
            print(f"[scheduler] {count} tarefas vencidas atualizadas para prioridade crítica.")
    except Exception as e:
        print(f"[scheduler] Erro ao atualizar tarefas vencidas: {e}")


def _run_telegram_job(cfg: dict):
    """Envia o resumo diário de tarefas, notas e ideias via Telegram."""
    from bot.formatters import format_daily_summary

    chat_id = settings.telegram_chat_id
    token = settings.telegram_bot_token

    if not (chat_id and token):
        print("[scheduler] Telegram: TELEGRAM_CHAT_ID ou TELEGRAM_BOT_TOKEN não configurados.")
        return

    base = settings.jtasks_internal_url
    headers = {"X-Bot-Key": settings.bot_api_key}

    try:
        tasks = httpx.get(f"{base}/bot/tasks", headers=headers, params={"filter": "active"}, timeout=10).json().get("tasks", [])
        notes = httpx.get(f"{base}/bot/notes", headers=headers, timeout=10).json().get("notes", [])
        ideas = httpx.get(f"{base}/bot/ideas", headers=headers, timeout=10).json().get("ideas", [])
    except Exception as e:
        print(f"[scheduler] Telegram: erro ao buscar dados — {e}")
        return

    text = format_daily_summary(tasks, notes, ideas)

    # Botões inline para concluir cada tarefa ativa
    keyboard = []
    for t in tasks:
        keyboard.append([{
            "text": f"✅ {t['name'][:40]}",
            "callback_data": f"task:{t['id']}:complete",
        }])

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[scheduler] Telegram: resumo diário enviado para chat_id={chat_id}")
    except Exception as e:
        print(f"[scheduler] Telegram: erro ao enviar mensagem — {e}")


def reschedule():
    # Remove all existing email and telegram jobs
    for job in _scheduler.get_jobs():
        if job.id.startswith("email_daily_") or job.id.startswith("telegram_daily_"):
            _scheduler.remove_job(job.id)

    # Add a job per enabled user
    for cfg in load_all_configs():
        user_id = cfg.get("user_id", "")
        if not user_id:
            continue

        time_str = cfg.get("schedule_time", "08:00")
        try:
            h, m = map(int, time_str.split(":"))
        except Exception:
            h, m = 8, 0

        trigger = CronTrigger(hour=h, minute=m, timezone="America/Sao_Paulo")

        if cfg.get("enabled"):
            _scheduler.add_job(
                _run_email_job, trigger,
                id=_job_id(user_id),
                args=[cfg],
                replace_existing=True,
            )

        if cfg.get("telegram_enabled"):
            _scheduler.add_job(
                _run_telegram_job, trigger,
                id=f"telegram_daily_{user_id}",
                args=[cfg],
                replace_existing=True,
            )


def start_scheduler():
    # Job diário para verificação de tarefas expiradas à meia-noite
    _scheduler.add_job(
        _run_overdueDate_job,
        CronTrigger(hour=0, minute=5, timezone="America/Sao_Paulo"),
        id="overdue_tasks_daily",
        replace_existing=True,
    )
    
    _scheduler.start()
    
    # Rodar imediatamente no startup
    _run_overdueDate_job()
    
    reschedule()
    print("[scheduler] APScheduler iniciado")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)

