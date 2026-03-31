import smtplib
import ssl
import urllib.request
import json
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def _supabase_get(path: str):
    url = settings.supabase_url + path
    req = urllib.request.Request(url, headers={
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def build_email_html(user_id: str = "") -> tuple[str, str]:
    today_iso = date.today().isoformat()
    today_dt  = date.today()

    MESES = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    DIAS  = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira",
             "Sexta-feira","Sábado","Domingo"]
    dia_semana = DIAS[today_dt.weekday()]
    data_fmt   = f"{dia_semana}, {today_dt.day} de {MESES[today_dt.month-1]} de {today_dt.year}"

    uid_filter = f"&user_id=eq.{user_id}" if user_id else ""

    try:
        active = _supabase_get(
            f"/rest/v1/tasks?status=eq.active{uid_filter}&select=*,task_updates(*)&order=deadline.asc.nullslast"
        )
    except Exception as e:
        print(f"[email] Erro ao buscar ativas: {e}")
        active = []

    try:
        completed = _supabase_get(
            f"/rest/v1/tasks?status=eq.completed&completed_at=gte.{today_iso}T00:00:00{uid_filter}&select=*"
        )
    except Exception as e:
        print(f"[email] Erro ao buscar concluídas: {e}")
        completed = []

    try:
        discarded = _supabase_get(
            f"/rest/v1/tasks?status=eq.discarded{uid_filter}&select=*&updated_at=gte.{today_iso}T00:00:00"
        )
    except Exception as e:
        print(f"[email] Erro ao buscar descartadas: {e}")
        discarded = []

    total = len(active) + len(completed)
    taxa  = f"{round(len(completed)/total*100)}%" if total else "—"

    SECTION_TITLE = 'style="font-size:0.82rem;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;margin:0 0 12px;"'

    def pri_badge(p):
        colors = {
            "critica": ("#fff1f2", "#e63946", "Crítica"),
            "urgente": ("#fff7ed", "#ea580c", "Urgente"),
            "normal":  ("#f1f5f9", "#64748b", "Normal"),
        }
        bg, color, label = colors.get(p, ("#f1f5f9", "#64748b", p))
        return f'<span style="background:{bg};color:{color};padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;">{label}</span>'

    def fmt_date(iso_str):
        if not iso_str:
            return "—"
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return iso_str[:10] if len(iso_str) >= 10 else iso_str

    def fmt_deadline(dl):
        if not dl:
            return '<span style="color:#94a3b8;">—</span>'
        diff = (date.fromisoformat(dl) - today_dt).days
        d = date.fromisoformat(dl)
        formatted = d.strftime("%d/%m/%Y")
        if diff < 0:
            return f'<span style="color:#e63946;font-weight:700;">{formatted} ({abs(diff)}d atraso)</span>'
        elif diff == 0:
            return f'<span style="color:#ea580c;font-weight:700;">{formatted} (hoje)</span>'
        elif diff <= 3:
            return f'<span style="color:#ea580c;">{formatted} ({diff}d)</span>'
        return f'<span style="color:#1a1a2e;">{formatted} ({diff}d)</span>'

    def get_last_update(task):
        updates = task.get("task_updates") or []
        if not updates:
            return ""
        updates.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        last = updates[0]
        text = last.get("text", "")
        if len(text) > 80:
            text = text[:77] + "..."
        dt = fmt_date(last.get("created_at"))
        return (
            f'<div style="margin-top:4px;padding:6px 8px;background:#f8fafc;'
            f'border-left:3px solid #3b82f6;border-radius:0 4px 4px 0;'
            f'font-size:0.78rem;color:#475569;">'
            f'<strong>Última nota ({dt}):</strong> {text}</div>'
        )

    # Seção de alertas de prazo
    overdue  = [(t, abs((date.fromisoformat(t["deadline"]) - today_dt).days))
                for t in active if t.get("deadline") and (date.fromisoformat(t["deadline"]) - today_dt).days < 0]
    due_soon = [(t, (date.fromisoformat(t["deadline"]) - today_dt).days)
                for t in active if t.get("deadline") and 0 <= (date.fromisoformat(t["deadline"]) - today_dt).days <= 3]
    overdue.sort(key=lambda x: x[1], reverse=True)
    due_soon.sort(key=lambda x: x[1])

    alert_html = ""
    if overdue or due_soon:
        rows = ""
        for task, days in overdue:
            name = task.get("name", "—")
            proj = task.get("project", "")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {proj}</span>' if proj else ""
            rows += (
                f'<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">'
                f'<div style="font-weight:600;color:#1a1a2e;">{name}{proj_html}</div>'
                f'<div style="margin-top:2px;">{pri_badge(task.get("priority","normal"))}'
                f'<span style="background:#fff1f2;color:#e63946;padding:2px 8px;border-radius:4px;'
                f'font-size:0.75rem;font-weight:700;margin-left:4px;">{days}d em atraso</span></div>'
                f'</td></tr>'
            )
        for task, days in due_soon:
            name = task.get("name", "—")
            proj = task.get("project", "")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {proj}</span>' if proj else ""
            label = "hoje" if days == 0 else f"{days}d restante"
            rows += (
                f'<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">'
                f'<div style="font-weight:600;color:#1a1a2e;">{name}{proj_html}</div>'
                f'<div style="margin-top:2px;">{pri_badge(task.get("priority","normal"))}'
                f'<span style="background:#fff7ed;color:#ea580c;padding:2px 8px;border-radius:4px;'
                f'font-size:0.75rem;font-weight:700;margin-left:4px;">{label}</span></div>'
                f'</td></tr>'
            )
        alert_html = (
            f'<tr><td style="padding:20px 28px 0;">'
            f'<h2 {SECTION_TITLE}>⚠ Alertas de Prazo</h2>'
            f'<table width="100%">{rows}</table></td></tr>'
        )

    # Seção atividades ativas
    active_rows = ""
    for task in active:
        name = task.get("name", "—")
        proj = task.get("project", "")
        proj_html = f' <span style="color:#64748b;"> | {proj}</span>' if proj else ""
        active_rows += (
            f'<tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;">'
            f'<div style="font-weight:600;color:#1a1a2e;">{name}{proj_html}</div>'
            f'<div style="margin-top:4px;">{pri_badge(task.get("priority","normal"))} {fmt_deadline(task.get("deadline"))}</div>'
            f'{get_last_update(task)}'
            f'<div style="margin-top:4px;font-size:0.75rem;color:#94a3b8;">Criada: {fmt_date(task.get("created_at"))}</div>'
            f'</td></tr>'
        )
    active_list_html = ""
    if active:
        active_list_html = (
            f'<tr><td style="padding:20px 28px 0;">'
            f'<h2 {SECTION_TITLE}>📋 Atividades Ativas ({len(active)})</h2>'
            f'<table width="100%">{active_rows}</table></td></tr>'
        )

    # Concluídas hoje
    completed_html = ""
    if completed:
        rows = ""
        for task in completed:
            name = task.get("name", "—")
            proj = task.get("project", "")
            proj_html = f' | {proj}' if proj else ""
            rows += (
                f'<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">'
                f'<div style="font-weight:600;color:#1a1a2e;">{name}'
                f'<span style="color:#64748b;font-size:0.78rem;">{proj_html}</span></div>'
                f'<div style="margin-top:2px;">{pri_badge(task.get("priority","normal"))}'
                f'<span style="font-size:0.78rem;color:#64748b;margin-left:6px;">'
                f'Concluída: {fmt_date(task.get("completed_at"))}</span></div>'
                f'</td></tr>'
            )
        completed_html = (
            f'<tr><td style="padding:20px 28px 0;">'
            f'<h2 {SECTION_TITLE}>✅ Concluídas Hoje ({len(completed)})</h2>'
            f'<table width="100%">{rows}</table></td></tr>'
        )

    # Descartadas hoje
    discarded_html = ""
    if discarded:
        rows = ""
        for task in discarded:
            name = task.get("name", "—")
            rows += (
                f'<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">'
                f'<div style="font-weight:600;color:#94a3b8;text-decoration:line-through;">{name}</div>'
                f'</td></tr>'
            )
        discarded_html = (
            f'<tr><td style="padding:20px 28px 0;">'
            f'<h2 {SECTION_TITLE}>🗑️ Descartadas Hoje ({len(discarded)})</h2>'
            f'<table width="100%">{rows}</table></td></tr>'
        )

    # Por projeto
    proj_counts: dict = {}
    for t in active:
        p = t.get("project") or "Sem projeto"
        proj_counts[p] = proj_counts.get(p, 0) + 1
    proj_html = ""
    if proj_counts:
        rows = "".join(
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #f1f5f9;">'
            f'<span style="font-weight:600;color:#1a1a2e;">{p}</span>'
            f'<span style="color:#64748b;margin-left:8px;">{c} tarefa(s)</span></td></tr>'
            for p, c in sorted(proj_counts.items(), key=lambda x: -x[1])
        )
        proj_html = (
            f'<tr><td style="padding:20px 28px 0;">'
            f'<h2 {SECTION_TITLE}>📁 Por Projeto</h2>'
            f'<table width="100%">{rows}</table></td></tr>'
        )

    # Por prioridade
    criticas = [t for t in active if t.get("priority") == "critica"]
    urgentes = [t for t in active if t.get("priority") == "urgente"]
    normais  = [t for t in active if t.get("priority") == "normal"]
    pri_html = ""
    if active:
        pri_html = (
            f'<tr><td style="padding:20px 28px 0;">'
            f'<h2 {SECTION_TITLE}>Por Prioridade</h2>'
            f'<div style="display:flex;gap:16px;">'
            f'<div>{pri_badge("critica")} {len(criticas)}</div>'
            f'<div>{pri_badge("urgente")} {len(urgentes)}</div>'
            f'<div>{pri_badge("normal")} {len(normais)}</div>'
            f'</div></td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;">
  <tr><td align="center" style="padding:24px 16px;">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.10);max-width:600px;">
      <tr>
        <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                   padding:24px 28px;border-bottom:3px solid #e63946;">
          <h1 style="color:#ffffff;margin:0;font-size:1.35rem;font-weight:800;letter-spacing:0.5px;">Jtasks</h1>
          <p style="color:rgba(255,255,255,0.65);margin:6px 0 0;font-size:0.83rem;">{data_fmt}</p>
        </td>
      </tr>
      <tr>
        <td style="padding:20px 28px 0;">
          <h2 {SECTION_TITLE}>Resumo do Dia</h2>
        </td>
      </tr>
      <tr>
        <td style="padding:0 28px 20px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f8fafc;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="text-align:center;padding:16px 8px;">
                <div style="font-size:1.8rem;font-weight:800;color:#e63946;line-height:1;">{len(active)}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Ativas</div>
              </td>
              <td style="text-align:center;padding:16px 8px;border-left:1px solid #e2e8f0;">
                <div style="font-size:1.8rem;font-weight:800;color:#22c55e;line-height:1;">{len(completed)}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Concluídas</div>
              </td>
              <td style="text-align:center;padding:16px 8px;border-left:1px solid #e2e8f0;">
                <div style="font-size:1.8rem;font-weight:800;color:#64748b;line-height:1;">{len(discarded)}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Descartadas</div>
              </td>
              <td style="text-align:center;padding:16px 8px;border-left:1px solid #e2e8f0;">
                <div style="font-size:1.8rem;font-weight:800;color:#3b82f6;line-height:1;">{taxa}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Taxa do dia</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      {alert_html}
      {active_list_html}
      {completed_html}
      {discarded_html}
      {proj_html}
      {pri_html}
      <tr>
        <td style="background:#1a1a2e;padding:14px 28px;text-align:center;">
          <p style="color:rgba(255,255,255,0.35);font-size:0.72rem;margin:0;">
            Relatório gerado automaticamente em {today_iso}
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    subject = f"Jtasks — Resumo {today_iso}"
    return html, subject


def send_email(cfg: dict, html_body: str, subject: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["smtp_user"]
    msg["To"]      = cfg["email_to"]
    msg.attach(MIMEText("Abra este email em um cliente que suporte HTML.", "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    port = int(cfg.get("smtp_port", 587))
    host = cfg["smtp_host"]
    ctx  = ssl.create_default_context()

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) as smtp:
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.sendmail(cfg["smtp_user"], cfg["email_to"], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.sendmail(cfg["smtp_user"], cfg["email_to"], msg.as_string())
