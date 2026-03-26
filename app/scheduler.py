from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.notify_config import load_config
from app.services.email_service import build_email_html, send_email

_scheduler = BackgroundScheduler()
_current_job_id = "email_daily"


def _run_email_job():
    cfg = load_config()
    if not (cfg.get("enabled") and cfg.get("smtp_user") and cfg.get("email_to") and cfg.get("smtp_password")):
        return
    try:
        html, subject = build_email_html()
        send_email(cfg, html, subject)
        print(f"[scheduler] Email enviado: {subject}")
    except Exception as e:
        print(f"[scheduler] Erro ao enviar: {e}")


def _reschedule():
    cfg = load_config()
    if not cfg.get("enabled"):
        if _scheduler.get_job(_current_job_id):
            _scheduler.remove_job(_current_job_id)
        return

    time_str = cfg.get("schedule_time", "08:00")
    try:
        h, m = map(int, time_str.split(":"))
    except Exception:
        h, m = 8, 0

    trigger = CronTrigger(hour=h, minute=m)
    if _scheduler.get_job(_current_job_id):
        _scheduler.reschedule_job(_current_job_id, trigger=trigger)
    else:
        _scheduler.add_job(_run_email_job, trigger, id=_current_job_id)


def start_scheduler():
    _scheduler.start()
    _reschedule()
    print("[scheduler] APScheduler iniciado")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
