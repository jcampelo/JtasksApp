import http.server
import json
import os
import threading
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
PORT = 8080

SUPABASE_URL = "https://mvlpqcziismuwvdgbyoi.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im12bHBxY3ppaXNtdXd2ZGdieW9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDM4OTIxOCwiZXhwIjoyMDg5OTY1MjE4fQ.QS_cBXQAItPhBaVx5Xa6i8ZiIISFHxCsD-m5Oka9CMM"


# ── CONFIG ──────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── SUPABASE DATA ────────────────────────────────────────────────────

def fetch_tasks_for_email():
    return _supabase_get("/rest/v1/tasks?status=eq.active&select=*,task_updates(*)")


# ── EMAIL ────────────────────────────────────────────────────────────

def _supabase_get(path):
    """Helper para GET no Supabase REST API."""
    import urllib.request
    url = SUPABASE_URL + path
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def build_email_html():
    """Busca dados do Supabase e monta o HTML completo do resumo de atividades."""
    today_iso = date.today().isoformat()
    today_dt  = date.today()

    # ── Buscar dados ──
    try:
        active = _supabase_get("/rest/v1/tasks?status=eq.active&select=*,task_updates(*)&order=deadline.asc.nullslast")
    except Exception as e:
        print(f"[email] Erro ao buscar ativas: {e}")
        active = []

    try:
        completed = _supabase_get(f"/rest/v1/tasks?status=eq.completed&completed_at=gte.{today_iso}T00:00:00&select=*")
    except Exception as e:
        print(f"[email] Erro ao buscar concluídas: {e}")
        completed = []

    try:
        discarded = _supabase_get(f"/rest/v1/tasks?status=eq.discarded&select=*&updated_at=gte.{today_iso}T00:00:00")
    except Exception as e:
        print(f"[email] Erro ao buscar descartadas: {e}")
        discarded = []

    # ── Formatação de data ──
    MESES = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    DIAS  = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira",
             "Sexta-feira","Sábado","Domingo"]
    dia_semana = DIAS[today_dt.weekday()]
    data_fmt   = f"{dia_semana}, {today_dt.day} de {MESES[today_dt.month-1]} de {today_dt.year}"

    # ── Classificação por deadline ──
    overdue  = []
    due_soon = []
    for task in active:
        dl = task.get("deadline")
        if not dl:
            continue
        diff = (date.fromisoformat(dl) - today_dt).days
        if diff < 0:
            overdue.append((task, abs(diff)))
        elif diff <= 3:
            due_soon.append((task, diff))
    overdue.sort(key=lambda x: x[1], reverse=True)
    due_soon.sort(key=lambda x: x[1])

    # ── Contagens ──
    criticas = [t for t in active if t.get("priority") == "critica"]
    urgentes = [t for t in active if t.get("priority") == "urgente"]
    normais  = [t for t in active if t.get("priority") == "normal"]

    total = len(active) + len(completed)
    taxa  = f"{round(len(completed)/total*100)}%" if total else "—"

    # ── Agrupamento por projeto ──
    proj_counts = {}
    for t in active:
        p = t.get("project") or "Sem projeto"
        proj_counts[p] = proj_counts.get(p, 0) + 1

    # ── Helpers HTML ──
    SECTION_TITLE = 'style="font-size:0.82rem;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;margin:0 0 12px;"'

    def pri_badge(p):
        colors = {"critica": ("#fff1f2","#e63946","Critica"),
                  "urgente": ("#fff7ed","#ea580c","Urgente"),
                  "normal":  ("#f1f5f9","#64748b","Normal")}
        bg, color, label = colors.get(p, ("#f1f5f9","#64748b", p))
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
        updates.sort(key=lambda u: u.get("created_at",""), reverse=True)
        last = updates[0]
        text = last.get("text","")
        if len(text) > 80:
            text = text[:77] + "..."
        dt = fmt_date(last.get("created_at"))
        return f'<div style="margin-top:4px;padding:6px 8px;background:#f8fafc;border-left:3px solid #3b82f6;border-radius:0 4px 4px 0;font-size:0.78rem;color:#475569;"><strong>Ultima nota ({dt}):</strong> {text}</div>'

    # ══════════════════════════════════════════════════════════════════
    # SEÇÃO 1: ALERTAS DE PRAZO
    # ══════════════════════════════════════════════════════════════════
    alert_html = ""
    if overdue or due_soon:
        rows = ""
        for task, days in overdue:
            name = task.get("name","—")
            project = task.get("project","")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {project}</span>' if project else ""
            rows += f'''<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">
                <div style="font-weight:600;color:#1a1a2e;">{name}{proj_html}</div>
                <div style="margin-top:2px;">{pri_badge(task.get("priority","normal"))}
                <span style="background:#fff1f2;color:#e63946;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;margin-left:4px;">{days}d em atraso</span></div>
            </td></tr>'''
        for task, days in due_soon:
            name = task.get("name","—")
            project = task.get("project","")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {project}</span>' if project else ""
            label = "Vence hoje" if days == 0 else f"{days}d restantes"
            rows += f'''<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">
                <div style="font-weight:600;color:#1a1a2e;">{name}{proj_html}</div>
                <div style="margin-top:2px;">{pri_badge(task.get("priority","normal"))}
                <span style="background:#fff7ed;color:#ea580c;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;margin-left:4px;">{label}</span></div>
            </td></tr>'''

        alert_html = f'''<tr><td style="padding:20px 28px 0;">
            <h2 {SECTION_TITLE}><span style="color:#e63946;">⚠ Alertas de Prazo</span></h2>
            <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </td></tr>'''

    # ══════════════════════════════════════════════════════════════════
    # SEÇÃO 2: LISTA DE ATIVIDADES ATIVAS (detalhada)
    # ══════════════════════════════════════════════════════════════════
    active_list_html = ""
    if active:
        rows = ""
        for t in active:
            name = t.get("name","—")
            project = t.get("project","")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {project}</span>' if project else ""
            dl_html = fmt_deadline(t.get("deadline"))
            update_html = get_last_update(t)
            rows += f'''<tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;">
                <div style="font-weight:600;color:#1a1a2e;margin-bottom:3px;">{name}{proj_html}</div>
                <div style="margin-bottom:2px;">{pri_badge(t.get("priority","normal"))}
                <span style="font-size:0.78rem;color:#64748b;margin-left:8px;">Deadline: {dl_html}</span></div>
                <div style="font-size:0.78rem;color:#94a3b8;">Criada em: {fmt_date(t.get("created_at"))}</div>
                {update_html}
            </td></tr>'''

        active_list_html = f'''<tr><td style="padding:20px 28px 0;">
            <h2 {SECTION_TITLE}>📋 Atividades Ativas ({len(active)})</h2>
            <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </td></tr>'''

    else:
        active_list_html = f'''<tr><td style="padding:20px 28px;text-align:center;color:#94a3b8;font-size:0.9rem;">
            Nenhuma atividade ativa no momento.
        </td></tr>'''

    # ══════════════════════════════════════════════════════════════════
    # SEÇÃO 3: CONCLUÍDAS HOJE
    # ══════════════════════════════════════════════════════════════════
    completed_html = ""
    if completed:
        rows = ""
        for t in completed:
            name = t.get("name","—")
            project = t.get("project","")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {project}</span>' if project else ""
            rows += f'''<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">
                <div style="font-weight:600;color:#1a1a2e;">{name}{proj_html}</div>
                <div style="margin-top:2px;">{pri_badge(t.get("priority","normal"))}
                <span style="font-size:0.78rem;color:#22c55e;margin-left:8px;font-weight:600;">Concluida em {fmt_date(t.get("completed_at"))}</span></div>
            </td></tr>'''

        completed_html = f'''<tr><td style="padding:20px 28px 0;">
            <h2 {SECTION_TITLE}><span style="color:#22c55e;">✅</span> Concluidas Hoje ({len(completed)})</h2>
            <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </td></tr>'''

    # ══════════════════════════════════════════════════════════════════
    # SEÇÃO 4: DESCARTADAS HOJE
    # ══════════════════════════════════════════════════════════════════
    discarded_html = ""
    if discarded:
        rows = ""
        for t in discarded:
            name = t.get("name","—")
            project = t.get("project","")
            proj_html = f' <span style="color:#64748b;font-size:0.78rem;">| {project}</span>' if project else ""
            rows += f'''<tr><td style="padding:8px 0;border-bottom:1px solid #f1f5f9;">
                <div style="color:#1a1a2e;text-decoration:line-through;">{name}{proj_html}</div>
                <div style="margin-top:2px;">{pri_badge(t.get("priority","normal"))}</div>
            </td></tr>'''

        discarded_html = f'''<tr><td style="padding:20px 28px 0;">
            <h2 {SECTION_TITLE}>🗑️ Descartadas Hoje ({len(discarded)})</h2>
            <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </td></tr>'''

    # ══════════════════════════════════════════════════════════════════
    # SEÇÃO 5: RESUMO POR PROJETO
    # ══════════════════════════════════════════════════════════════════
    proj_html = ""
    if proj_counts:
        rows = ""
        for proj_name, count in sorted(proj_counts.items(), key=lambda x: x[1], reverse=True):
            rows += f'''<tr><td style="padding:6px 0;border-bottom:1px solid #f8fafc;">
                <span style="color:#1a1a2e;font-weight:600;">📁 {proj_name}</span>
                <span style="float:right;font-weight:800;color:#3b82f6;">{count}</span>
            </td></tr>'''

        proj_html = f'''<tr><td style="padding:20px 28px 0;">
            <h2 {SECTION_TITLE}>📁 Por Projeto</h2>
            <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        </td></tr>'''

    # ══════════════════════════════════════════════════════════════════
    # SEÇÃO 6: POR PRIORIDADE
    # ══════════════════════════════════════════════════════════════════
    def pri_row(icon, label, count, color):
        return f'''<tr><td style="padding:6px 0;border-bottom:1px solid #f8fafc;">
            <span style="color:{color};font-weight:700;">{icon} {label}</span>
            <span style="float:right;font-weight:800;color:#1a1a2e;">{count}</span>
        </td></tr>'''

    pri_html = ""
    if active:
        pri_html = f'''<tr><td style="padding:20px 28px 0;">
            <h2 {SECTION_TITLE}>Por Prioridade</h2>
            <table width="100%" cellpadding="0" cellspacing="0">
              {pri_row("🔴","Critica", len(criticas),"#e63946")}
              {pri_row("🟡","Urgente", len(urgentes),"#ea580c")}
              {pri_row("⚪","Normal",  len(normais), "#64748b")}
            </table>
        </td></tr>'''

    # ══════════════════════════════════════════════════════════════════
    # MONTAGEM FINAL
    # ══════════════════════════════════════════════════════════════════
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;">
  <tr><td align="center" style="padding:24px 16px;">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.10);max-width:600px;">

      <!-- HEADER -->
      <tr>
        <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                   padding:24px 28px;border-bottom:3px solid #e63946;">
          <h1 style="color:#ffffff;margin:0;font-size:1.35rem;font-weight:800;letter-spacing:0.5px;">Jabil Notes</h1>
          <p style="color:rgba(255,255,255,0.65);margin:6px 0 0;font-size:0.83rem;">{data_fmt}</p>
        </td>
      </tr>

      <!-- RESUMO DO DIA -->
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
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Concluidas</div>
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

      <!-- FOOTER -->
      <tr>
        <td style="background:#1a1a2e;padding:14px 28px;text-align:center;">
          <p style="color:rgba(255,255,255,0.5);font-size:0.78rem;margin:0 0 6px;">
            <a href="http://129.121.48.36:8080" style="color:#3b82f6;text-decoration:none;font-weight:600;">Abrir Jabil Notes</a>
          </p>
          <p style="color:rgba(255,255,255,0.35);font-size:0.72rem;margin:0;">
            Relatorio gerado automaticamente em {today_iso}
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body></html>"""

    subject = f"Jabil Notes — Resumo {today_iso}"
    return html, subject


def send_email(cfg, html_body, subject):
    """Envia email via SMTP com STARTTLS (porta 587) ou SSL (porta 465)."""
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


# ── SCHEDULER ────────────────────────────────────────────────────────

_sched_stop = threading.Event()

def scheduler_loop():
    """Daemon thread: verifica a cada 30s se é hora de enviar o email diário."""
    last_sent_date = None
    while not _sched_stop.is_set():
        try:
            cfg = load_config()
            if cfg.get("enabled") and cfg.get("smtp_user") and cfg.get("email_to"):
                h, m = map(int, cfg.get("schedule_time", "08:00").split(":"))
                now   = datetime.now()
                today = now.date().isoformat()
                if now.hour == h and now.minute == m and last_sent_date != today:
                    html, subject = build_email_html()
                    send_email(cfg, html, subject)
                    last_sent_date = today
                    print(f"[scheduler] Email enviado: {subject}")
        except Exception as e:
            print(f"[scheduler] Erro: {e}")
        _sched_stop.wait(30)


# ── HTTP HANDLER ──────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path, content_type):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_file(os.path.join(os.path.dirname(__file__), "index.html"), "text/html; charset=utf-8")

        elif self.path == "/config":
            cfg = load_config()
            safe = {k: v for k, v in cfg.items() if k != "smtp_password"}
            safe["has_password"] = bool(cfg.get("smtp_password"))
            self._send_json(200, safe)

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/config":
            body = self._read_body()
            try:
                new_cfg = json.loads(body)
            except Exception:
                self._send_json(400, {"error": "invalid_json"}); return
            # Mantém senha existente se não foi enviada nova
            existing = load_config()
            if not new_cfg.get("smtp_password"):
                new_cfg["smtp_password"] = existing.get("smtp_password", "")
            try:
                save_config(new_cfg)
                self._send_json(200, {"ok": True})
            except Exception:
                self._send_json(500, {"error": "write_failed"})

        elif self.path == "/notify/send":
            cfg = load_config()
            if not cfg.get("email_to") or not cfg.get("smtp_user") or not cfg.get("smtp_host"):
                self._send_json(400, {"error": "Configuração incompleta. Preencha todos os campos SMTP."}); return
            if not cfg.get("smtp_password"):
                self._send_json(400, {"error": "Senha SMTP não configurada."}); return
            try:
                html, subject = build_email_html()
                send_email(cfg, html, subject)
                self._send_json(200, {"ok": True, "subject": subject})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    t = threading.Thread(target=scheduler_loop, name="email-scheduler", daemon=True)
    t.start()
    print(f"[scheduler] Iniciado — verificação a cada 30s")
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Jabil Notes rodando em http://0.0.0.0:{PORT}")
    server.serve_forever()
