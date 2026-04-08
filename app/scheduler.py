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


def reschedule():
    # Remove all existing email jobs
    for job in _scheduler.get_jobs():
        if job.id.startswith("email_daily_"):
            _scheduler.remove_job(job.id)

    # Add a job per enabled user
    for cfg in load_all_configs():
        if not cfg.get("enabled"):
            continue
        user_id = cfg.get("user_id", "")
        if not user_id:
            continue

        time_str = cfg.get("schedule_time", "08:00")
        try:
            h, m = map(int, time_str.split(":"))
        except Exception:
            h, m = 8, 0

        trigger = CronTrigger(hour=h, minute=m, timezone="America/Sao_Paulo")
        _scheduler.add_job(
            _run_email_job, trigger,
            id=_job_id(user_id),
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

