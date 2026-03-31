from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.notify_config import load_all_configs
from app.services.email_service import build_email_html, send_email

_scheduler = BackgroundScheduler()


def _job_id(user_id: str) -> str:
    return f"email_daily_{user_id}"


def _run_email_job(cfg: dict):
    user_id = cfg.get("user_id", "")
    if not (cfg.get("smtp_user") and cfg.get("email_to") and cfg.get("smtp_password")):
        return
    try:
        html, subject = build_email_html(user_id=user_id)
        send_email(cfg, html, subject)
        print(f"[scheduler] Email enviado para {cfg['email_to']}: {subject}")
    except Exception as e:
        print(f"[scheduler] Erro ao enviar para {cfg.get('email_to')}: {e}")


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

        trigger = CronTrigger(hour=h, minute=m)
        _scheduler.add_job(
            _run_email_job, trigger,
            id=_job_id(user_id),
            args=[cfg],
            replace_existing=True,
        )


def start_scheduler():
    _scheduler.start()
    reschedule()
    print("[scheduler] APScheduler iniciado")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
