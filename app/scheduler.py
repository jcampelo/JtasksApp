"""
Agendador de Jobs (APScheduler) — Email diário de tarefas

Fluxo:
  1. start_scheduler() → inicia APScheduler
  2. reschedule() → lê configs de cada usuário (JSON local)
  3. Cria job por usuário: "email_daily_{user_id}" na hora configurada
  4. stop_scheduler() → para ao desligar a app

Configuração por usuário (configs/notify_{user_id}.json):
  {
    "enabled": true,
    "schedule_time": "08:00",  (ou "14:30", "20:00", etc)
    "email_to": "user@email.com",
    "user_id": "uuid",
    ...
  }

Timezone: America/Sao_Paulo (Brasil)

Ciclo de vida:
  FastAPI startup (lifespan) → start_scheduler()
                             → reschedule() lê configs
                             → jobs rodando no background
  FastAPI shutdown (lifespan) → stop_scheduler()
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.notify_config import load_all_configs
from app.services.email_service import build_email_html, send_email

# Scheduler global (roda em background thread)
_scheduler = BackgroundScheduler()


def _job_id(user_id: str) -> str:
    """Gera ID único do job por usuário (usado para add/remove/update)."""
    return f"email_daily_{user_id}"


def _run_email_job(cfg: dict):
    """
    Executa job de email para um usuário.

    Parâmetros:
      cfg: dict com configurações do usuário
        {
          "user_id": "uuid...",
          "email_to": "user@example.com",
          "enabled": true,
          "schedule_time": "08:00",
          ...
        }

    Fluxo:
      1. Valida se SMTP está configurado no servidor
      2. Valida se email_to está configurado para o usuário
      3. Monta HTML do email (relatório de tarefas)
      4. Envia via SMTP
      5. Log de sucesso ou erro
    """
    user_id  = cfg.get("user_id", "")
    email_to = cfg.get("email_to", "")

    # Validação: servidor SMTP deve estar configurado (.env)
    if not (settings.smtp_user and settings.smtp_password and email_to):
        print(f"[scheduler] Skipping {user_id}: SMTP do servidor ou email_to não configurado.")
        return

    try:
        # Monta HTML do email com relatório de tarefas
        html, subject = build_email_html(user_id=user_id)

        # Envia email via SMTP
        send_email(email_to, html, subject)
        print(f"[scheduler] Email enviado para {email_to}: {subject}")

    except Exception as e:
        # Se algo falhar (rede, SMTP, etc), registra erro (não interrompe scheduler)
        print(f"[scheduler] Erro ao enviar para {email_to}: {e}")


def reschedule():
    """
    Reconstrói todos os jobs de email.

    Fluxo:
      1. Remove TODOS os jobs antigos (email_daily_*)
      2. Lê configs de todos os usuários (JSON local em configs/)
      3. Para cada usuário habilitado (enabled=true):
         - Extrai horário (schedule_time: "HH:MM")
         - Cria CronTrigger para aquela hora (timezone: São Paulo)
         - Adiciona job ao scheduler
      4. replace_existing=True garante que updates refletem

    ⚠️ Chamado:
      - Ao iniciar app (start_scheduler)
      - Quando usuário salva config de notificação (/notify/config)

    Timezone:
      America/Sao_Paulo = UTC-3 (ou UTC-2 em horário de verão)
    """

    # Remove todos os jobs antigos de email
    for job in _scheduler.get_jobs():
        if job.id.startswith("email_daily_"):
            _scheduler.remove_job(job.id)

    # Carrega configs de TODOS os usuários (JSON local: configs/notify_{user_id}.json)
    for cfg in load_all_configs():
        # Pula usuários com notificações desabilitadas
        if not cfg.get("enabled"):
            continue

        user_id = cfg.get("user_id", "")
        if not user_id:
            continue

        # Extrai horário da config (ex: "08:00" → h=8, m=0)
        time_str = cfg.get("schedule_time", "08:00")
        try:
            h, m = map(int, time_str.split(":"))
        except Exception:
            h, m = 8, 0  # Default: 8:00 se parse falhar

        # Cria trigger CRON para rodar todos os dias naquele horário
        trigger = CronTrigger(hour=h, minute=m, timezone="America/Sao_Paulo")

        # Adiciona job ao scheduler
        _scheduler.add_job(
            _run_email_job,      # Função a executar
            trigger,             # Quando executar (CRON)
            id=_job_id(user_id), # ID único (para update/remove)
            args=[cfg],          # Argumentos da função (_run_email_job)
            replace_existing=True,  # Se job já existe, substitui
        )


def start_scheduler():
    """
    Inicia o APScheduler no startup da app.

    Chamado por: main.py (FastAPI lifespan)

    Fluxo:
      1. _scheduler.start() → inicia background thread
      2. reschedule() → lê configs e cria jobs
      3. Print de debug
    """
    _scheduler.start()
    reschedule()
    print("[scheduler] APScheduler iniciado")


def stop_scheduler():
    """
    Para o APScheduler no shutdown da app.

    Chamado por: main.py (FastAPI lifespan)

    wait=False: não espera jobs terminarem (graceful shutdown)
    """
    if _scheduler.running:
        _scheduler.shutdown(wait=False)

